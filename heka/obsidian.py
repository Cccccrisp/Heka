"""A narrow, local-first Obsidian importer for Heka daily records.

This module deliberately accepts a chosen folder rather than scanning a whole
vault. Markdown remains the source document; Heka only stores a traceable copy
and the derived, still-pending Trace proposal.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .db import HekaStore
from .deepseek import mock_analysis
from .local import analyse_record


@dataclass(frozen=True)
class ObsidianDocument:
    path: Path
    relative_path: str
    title: str
    document_date: str | None
    raw_text: str
    content_hash: str
    record_kind: str


def _frontmatter_value(markdown: str, key: str) -> str | None:
    if not markdown.startswith("---\n"):
        return None
    closing = markdown.find("\n---", 4)
    if closing < 0:
        return None
    match = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", markdown[4:closing], re.MULTILINE)
    return match.group(1).strip().strip('"') if match else None


def _heading(markdown: str) -> str | None:
    match = re.search(r"^#\s+(.+?)\s*$", markdown, re.MULTILINE)
    return match.group(1).strip() if match else None


def _date_from_filename(name: str) -> str | None:
    match = re.match(r"(\d{4}-\d{2}-\d{2})", name)
    return match.group(1) if match else None


def _record_kind(markdown: str) -> str:
    explicit = _frontmatter_value(markdown, "heka")
    if explicit in {"evidence", "reflection", "research", "exclude"}:
        return explicit
    return "evidence" if _frontmatter_value(markdown, "type") == "trace" else "reflection"


def discover_daily_records(folder: Path) -> list[ObsidianDocument]:
    """Read direct Markdown children in chronological order; never scan a whole vault."""
    if not folder.is_dir():
        raise ValueError(f"找不到 Obsidian 每日记录目录：{folder}")
    documents = []
    for path in sorted(folder.glob("*.md")):
        raw_text = path.read_text(encoding="utf-8").strip()
        if not raw_text:
            continue
        content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        documents.append(
            ObsidianDocument(
                path=path,
                relative_path=path.name,
                title=_frontmatter_value(raw_text, "title") or _heading(raw_text) or path.stem,
                document_date=(
                    _frontmatter_value(raw_text, "date")
                    or _frontmatter_value(raw_text, "created")
                    or _date_from_filename(path.name)
                ),
                raw_text=raw_text,
                content_hash=content_hash,
                record_kind=_record_kind(raw_text),
            )
        )
    return documents


def import_daily_records(
    store: HekaStore,
    folder: Path,
    *,
    offline_mock: bool = False,
    dry_run: bool = False,
) -> dict[str, object]:
    documents = discover_daily_records(folder)
    imported: list[dict[str, object]] = []
    skipped: list[str] = []
    for document in documents:
        if store.source_document_exists(document.content_hash):
            if not dry_run:
                store.refresh_source_document_metadata(
                    document.content_hash,
                    str(document.path),
                    document.title,
                    document.document_date,
                    document.record_kind,
                )
            skipped.append(document.relative_path)
            continue
        if dry_run:
            imported.append({"path": document.relative_path, "title": document.title, "status": "ready"})
            continue
        if offline_mock:
            analysis, analyzer = mock_analysis(document.raw_text), "offline-mock"
        else:
            analysis, analyzer = analyse_record(document.raw_text, store.current_model())
        proposal_id = store.add_analysis(
            document.raw_text,
            f"obsidian:每日/{document.relative_path}",
            analysis,
            analyzer,
            source_document={
                "source_path": str(document.path),
                "title": document.title,
                "document_date": document.document_date,
                "content_hash": document.content_hash,
                "record_kind": document.record_kind,
            },
        )
        imported.append({"path": document.relative_path, "title": document.title, "proposal_id": proposal_id})
    return {"found": len(documents), "imported": imported, "skipped": skipped}
