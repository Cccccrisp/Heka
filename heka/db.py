"""Small local SQLite store; no personal text is uploaded except for a chosen analysis call."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema import empty_model, utc_now


class HekaStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def initialise(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                source TEXT NOT NULL,
                raw_text TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS source_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL UNIQUE REFERENCES entries(id),
                source_path TEXT NOT NULL,
                title TEXT NOT NULL,
                document_date TEXT,
                record_kind TEXT NOT NULL DEFAULT 'reflection' CHECK(record_kind IN ('evidence', 'reflection', 'research', 'exclude')),
                content_hash TEXT NOT NULL UNIQUE,
                imported_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL REFERENCES entries(id),
                created_at TEXT NOT NULL,
                payload TEXT NOT NULL,
                analyzer TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS trace_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id INTEGER NOT NULL UNIQUE REFERENCES traces(id),
                event_type TEXT NOT NULL,
                time_reference TEXT NOT NULL DEFAULT 'unknown'
            );
            CREATE TABLE IF NOT EXISTS trace_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id INTEGER NOT NULL REFERENCES traces(id),
                ordinal INTEGER NOT NULL,
                statement TEXT NOT NULL,
                category TEXT NOT NULL,
                source_quote TEXT NOT NULL,
                confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
                UNIQUE(trace_id, ordinal)
            );
            CREATE TABLE IF NOT EXISTS trace_tags (
                trace_id INTEGER NOT NULL REFERENCES traces(id),
                tag TEXT NOT NULL,
                PRIMARY KEY(trace_id, tag)
            );
            CREATE TABLE IF NOT EXISTS trace_interpretations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id INTEGER NOT NULL REFERENCES traces(id),
                ordinal INTEGER NOT NULL,
                statement TEXT NOT NULL,
                fact_indices TEXT NOT NULL,
                missing_information TEXT NOT NULL,
                confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
                UNIQUE(trace_id, ordinal)
            );
            CREATE TABLE IF NOT EXISTS trace_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id INTEGER NOT NULL UNIQUE REFERENCES traces(id),
                question TEXT NOT NULL,
                stage TEXT NOT NULL CHECK(stage IN ('considering', 'made', 'revisited')),
                selected_option TEXT NOT NULL,
                reason_fact_indices TEXT NOT NULL,
                reversibility TEXT NOT NULL CHECK(reversibility IN ('high', 'medium', 'low', 'unknown'))
            );
            CREATE TABLE IF NOT EXISTS trace_decision_options (
                decision_id INTEGER NOT NULL REFERENCES trace_decisions(id),
                ordinal INTEGER NOT NULL,
                label TEXT NOT NULL,
                PRIMARY KEY(decision_id, ordinal)
            );
            CREATE TABLE IF NOT EXISTS trace_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id INTEGER NOT NULL REFERENCES traces(id),
                ordinal INTEGER NOT NULL,
                statement TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('done', 'planned', 'stopped', 'unknown')),
                source_quote TEXT NOT NULL,
                UNIQUE(trace_id, ordinal)
            );
            CREATE TABLE IF NOT EXISTS trace_emotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id INTEGER NOT NULL REFERENCES traces(id),
                ordinal INTEGER NOT NULL,
                label TEXT NOT NULL,
                intensity TEXT NOT NULL CHECK(intensity IN ('low', 'medium', 'high', 'unknown')),
                source_quote TEXT NOT NULL,
                UNIQUE(trace_id, ordinal)
            );
            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id INTEGER NOT NULL REFERENCES traces(id),
                created_at TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('proposed', 'accepted', 'rejected')),
                reviewed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS model_snapshots (
                version INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL,
                payload TEXT NOT NULL,
                proposal_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS evolution_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                signature TEXT NOT NULL UNIQUE,
                dimension TEXT NOT NULL,
                scope TEXT NOT NULL,
                previous_value REAL NOT NULL,
                current_value REAL NOT NULL,
                delta REAL NOT NULL,
                evidence TEXT NOT NULL,
                counter_evidence TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('proposed', 'confirmed', 'rejected')),
                reviewed_at TEXT,
                user_note TEXT
            );
            CREATE TABLE IF NOT EXISTS initial_self_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                answers TEXT NOT NULL,
                summary TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS action_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                problem TEXT NOT NULL,
                evidence TEXT NOT NULL,
                plan TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('proposed', 'selected', 'reviewed')),
                selected_option INTEGER,
                result_note TEXT,
                reviewed_at TEXT
            );
            """
        )
        source_columns = {row[1] for row in self.connection.execute("PRAGMA table_info(source_documents)")}
        if "record_kind" not in source_columns:
            self.connection.execute("ALTER TABLE source_documents ADD COLUMN record_kind TEXT NOT NULL DEFAULT 'reflection'")
        self.connection.execute(
            """UPDATE source_documents SET record_kind='research'
               WHERE title LIKE 'Day 3%' OR title LIKE 'Day 4%' OR title LIKE 'Day 5%' OR title LIKE '2026-07-24%'"""
        )
        exists = self.connection.execute("SELECT 1 FROM model_snapshots LIMIT 1").fetchone()
        if not exists:
            model = empty_model()
            self.connection.execute(
                "INSERT INTO model_snapshots(version, created_at, payload, proposal_id) VALUES (?, ?, ?, NULL)",
                (model["version"], model["updated_at"], json.dumps(model, ensure_ascii=False)),
            )
        self.connection.commit()

    def add_analysis(
        self,
        raw_text: str,
        source: str,
        analysis: dict[str, Any],
        analyzer: str,
        source_document: dict[str, str | None] | None = None,
    ) -> int:
        now = utc_now()
        cursor = self.connection.execute(
            "INSERT INTO entries(created_at, source, raw_text) VALUES (?, ?, ?)", (now, source, raw_text)
        )
        entry_id = cursor.lastrowid
        if source_document is not None:
            self.connection.execute(
                """INSERT INTO source_documents(entry_id, source_path, title, document_date, record_kind, content_hash, imported_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry_id,
                    source_document["source_path"],
                    source_document["title"],
                    source_document.get("document_date"),
                    source_document.get("record_kind", "reflection"),
                    source_document["content_hash"],
                    now,
                ),
            )
        trace_id = self.connection.execute(
            "INSERT INTO traces(entry_id, created_at, payload, analyzer) VALUES (?, ?, ?, ?)",
            (entry_id, now, json.dumps(analysis["trace"], ensure_ascii=False), analyzer),
        ).lastrowid
        trace = analysis["trace"]
        self.connection.execute(
            "INSERT INTO trace_events(trace_id, event_type, time_reference) VALUES (?, ?, ?)",
            (trace_id, trace["event_type"], trace.get("time_reference", "unknown")),
        )
        self.connection.executemany(
            """INSERT INTO trace_facts(trace_id, ordinal, statement, category, source_quote, confidence)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [(trace_id, index, fact["statement"], fact["category"], fact["source_quote"], fact["confidence"])
             for index, fact in enumerate(trace["observable_facts"])],
        )
        self.connection.executemany(
            "INSERT INTO trace_tags(trace_id, tag) VALUES (?, ?)",
            [(trace_id, tag) for tag in trace.get("tags", [])],
        )
        self.connection.executemany(
            """INSERT INTO trace_interpretations(trace_id, ordinal, statement, fact_indices, missing_information, confidence)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [(trace_id, index, item["statement"], json.dumps(item["based_on_facts"]), item["missing_information"], item["confidence"])
             for index, item in enumerate(trace["candidate_interpretations"])],
        )
        if trace.get("decision") is not None:
            decision = trace["decision"]
            decision_id = self.connection.execute(
                """INSERT INTO trace_decisions(trace_id, question, stage, selected_option, reason_fact_indices, reversibility)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (trace_id, decision["question"], decision["stage"], decision["selected_option"], json.dumps(decision["reason_fact_indices"]), decision["reversibility"]),
            ).lastrowid
            self.connection.executemany(
                "INSERT INTO trace_decision_options(decision_id, ordinal, label) VALUES (?, ?, ?)",
                [(decision_id, index, option) for index, option in enumerate(decision["options"])],
            )
        self.connection.executemany(
            "INSERT INTO trace_actions(trace_id, ordinal, statement, status, source_quote) VALUES (?, ?, ?, ?, ?)",
            [(trace_id, index, item["statement"], item["status"], item["source_quote"])
             for index, item in enumerate(trace.get("actions", []))],
        )
        self.connection.executemany(
            "INSERT INTO trace_emotions(trace_id, ordinal, label, intensity, source_quote) VALUES (?, ?, ?, ?, ?)",
            [(trace_id, index, item["label"], item["intensity"], item["source_quote"])
             for index, item in enumerate(trace.get("emotions", []))],
        )
        proposal_id = self.connection.execute(
            "INSERT INTO proposals(trace_id, created_at, payload, status) VALUES (?, ?, ?, 'proposed')",
            (trace_id, now, json.dumps(analysis["proposal"], ensure_ascii=False)),
        ).lastrowid
        self.connection.commit()
        return int(proposal_id)

    def source_document_exists(self, content_hash: str) -> bool:
        """True when this exact Obsidian revision has already entered Heka."""
        return self.connection.execute(
            "SELECT 1 FROM source_documents WHERE content_hash=? LIMIT 1", (content_hash,)
        ).fetchone() is not None

    def source_document_count(self) -> int:
        return int(self.connection.execute("SELECT count(*) FROM source_documents").fetchone()[0])

    def refresh_source_document_metadata(
        self, content_hash: str, source_path: str, title: str, document_date: str | None, record_kind: str
    ) -> None:
        """Keep provenance labels current without creating another Trace revision."""
        self.connection.execute(
            """UPDATE source_documents
               SET source_path=?, title=?, document_date=?, record_kind=?
               WHERE content_hash=?""",
            (source_path, title, document_date, record_kind, content_hash),
        )
        self.connection.commit()

    def pending_proposals(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """SELECT p.id, p.created_at, p.payload, e.raw_text, t.payload AS trace_payload,
                      sd.title AS source_title, sd.source_path AS source_path, sd.record_kind AS record_kind
               FROM proposals p JOIN traces t ON t.id=p.trace_id JOIN entries e ON e.id=t.entry_id
               LEFT JOIN source_documents sd ON sd.entry_id=e.id
               WHERE p.status='proposed' AND (sd.record_kind IS NULL OR sd.record_kind IN ('evidence', 'reflection')) ORDER BY p.id DESC"""
        ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"]), "trace": json.loads(row["trace_payload"])} for row in rows]

    def save_initial_self_report(self, answers: dict[str, str], summary: str) -> None:
        self.connection.execute(
            "INSERT INTO initial_self_reports(created_at, answers, summary) VALUES (?, ?, ?)",
            (utc_now(), json.dumps(answers, ensure_ascii=False), summary),
        )
        self.connection.commit()

    def latest_initial_self_report(self) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM initial_self_reports ORDER BY id DESC LIMIT 1").fetchone()
        return None if row is None else {**dict(row), "answers": json.loads(row["answers"])}

    def add_action_case(self, problem: str, evidence: list[dict[str, Any]], plan: dict[str, Any]) -> int:
        cursor = self.connection.execute(
            "INSERT INTO action_cases(created_at, problem, evidence, plan, status) VALUES (?, ?, ?, ?, 'proposed')",
            (utc_now(), problem, json.dumps(evidence, ensure_ascii=False), json.dumps(plan, ensure_ascii=False)),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def action_cases(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM action_cases ORDER BY id DESC").fetchall()
        return [{**dict(row), "evidence": json.loads(row["evidence"]), "plan": json.loads(row["plan"])} for row in rows]

    def select_action_option(self, case_id: int, option_index: int) -> dict[str, Any] | None:
        self.connection.execute("UPDATE action_cases SET status='selected', selected_option=? WHERE id=? AND status='proposed'", (option_index, case_id))
        self.connection.commit()
        return next((case for case in self.action_cases() if case["id"] == case_id), None)

    def review_action_case(self, case_id: int, result_note: str) -> dict[str, Any] | None:
        self.connection.execute("UPDATE action_cases SET status='reviewed', result_note=?, reviewed_at=? WHERE id=? AND status='selected'", (result_note, utc_now(), case_id))
        self.connection.commit()
        return next((case for case in self.action_cases() if case["id"] == case_id), None)

    def proposal(self, proposal_id: int) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
        return None if row is None else {**dict(row), "payload": json.loads(row["payload"])}

    def set_proposal_status(self, proposal_id: int, status: str) -> None:
        self.connection.execute("UPDATE proposals SET status=?, reviewed_at=? WHERE id=?", (status, utc_now(), proposal_id))
        self.connection.commit()

    def current_model(self) -> dict[str, Any]:
        row = self.connection.execute("SELECT payload FROM model_snapshots ORDER BY version DESC LIMIT 1").fetchone()
        if row is None:
            raise RuntimeError("store has not been initialised")
        return json.loads(row["payload"])

    def recent_evidence(self, limit: int = 12) -> list[dict[str, Any]]:
        """A bounded, auditable packet for cloud synthesis; never expose the whole database."""
        rows = self.connection.execute(
            """SELECT e.created_at, e.raw_text, t.payload AS trace_payload, p.payload AS proposal_payload, p.status
               FROM entries e JOIN traces t ON t.entry_id=e.id JOIN proposals p ON p.trace_id=t.id
               ORDER BY e.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            {
                "created_at": row["created_at"], "record": row["raw_text"], "trace": json.loads(row["trace_payload"]),
                "proposal": json.loads(row["proposal_payload"]), "proposal_status": row["status"],
            }
            for row in rows
        ]

    def add_model_snapshot(self, model: dict[str, Any], proposal_id: int) -> None:
        self.connection.execute(
            "INSERT INTO model_snapshots(version, created_at, payload, proposal_id) VALUES (?, ?, ?, ?)",
            (model["version"], model["updated_at"], json.dumps(model, ensure_ascii=False), proposal_id),
        )
        self.connection.commit()

    def evolution_events(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM evolution_events ORDER BY id DESC").fetchall()
        return [{**dict(row), "evidence": json.loads(row["evidence"]), "counter_evidence": json.loads(row["counter_evidence"])} for row in rows]

    def generate_evolution_candidates(self, days: int = 90) -> list[dict[str, Any]]:
        """Surface deterministic review cards from accepted dimension updates.

        The method never changes the personal model. It refuses to call a short
        burst of entries an evolution, and leaves the final decision to the user.
        """
        if not 14 <= days <= 365:
            raise ValueError("演化回看窗口需要在 14 到 365 天之间。")
        rows = self.connection.execute(
            "SELECT id, created_at, payload FROM proposals WHERE status='accepted' ORDER BY created_at"
        ).fetchall()
        grouped: dict[str, list[dict[str, Any]]] = {}
        now = datetime.now(timezone.utc)
        for row in rows:
            payload = json.loads(row["payload"])
            if payload.get("kind") != "dimension_update":
                continue
            created_at = datetime.fromisoformat(row["created_at"])
            if (now - created_at).days > days:
                continue
            grouped.setdefault(payload["dimension"], []).append({
                "proposal_id": row["id"], "created_at": row["created_at"],
                "value": payload["suggested_value"], "scope": payload.get("scope", "当前记录的场景"),
                "evidence": payload.get("evidence", []),
            })

        rejected_rows = self.connection.execute(
            "SELECT id, created_at, payload FROM proposals WHERE status='rejected'"
        ).fetchall()
        for dimension, evidence in grouped.items():
            if len(evidence) < 3:
                continue
            first_at = datetime.fromisoformat(evidence[0]["created_at"])
            last_at = datetime.fromisoformat(evidence[-1]["created_at"])
            if (last_at - first_at).days < 14:
                continue
            previous_value, current_value = evidence[0]["value"], evidence[-1]["value"]
            delta = round(current_value - previous_value, 3)
            if abs(delta) < 0.12:
                continue
            counters = []
            for row in rejected_rows:
                payload = json.loads(row["payload"])
                if payload.get("dimension") == dimension:
                    counters.append({"proposal_id": row["id"], "created_at": row["created_at"], "reason": payload.get("reason", "")})
            signature = dimension + ":" + ",".join(str(item["proposal_id"]) for item in evidence)
            self.connection.execute(
                """INSERT OR IGNORE INTO evolution_events(
                   created_at, signature, dimension, scope, previous_value, current_value, delta, evidence, counter_evidence, status
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed')""",
                (utc_now(), signature, dimension, evidence[-1]["scope"], previous_value, current_value, delta,
                 json.dumps(evidence, ensure_ascii=False), json.dumps(counters, ensure_ascii=False)),
            )
        self.connection.commit()
        return self.evolution_events()

    def review_evolution_event(self, event_id: int, decision: str, user_note: str = "") -> dict[str, Any] | None:
        if decision not in {"confirm", "reject"}:
            raise ValueError("decision 必须是 confirm 或 reject")
        status = "confirmed" if decision == "confirm" else "rejected"
        self.connection.execute(
            "UPDATE evolution_events SET status=?, reviewed_at=?, user_note=? WHERE id=? AND status='proposed'",
            (status, utc_now(), user_note.strip(), event_id),
        )
        self.connection.commit()
        row = self.connection.execute("SELECT * FROM evolution_events WHERE id=?", (event_id,)).fetchone()
        return None if row is None else {**dict(row), "evidence": json.loads(row["evidence"]), "counter_evidence": json.loads(row["counter_evidence"])}
