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
            CREATE TABLE IF NOT EXISTS model_claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_key TEXT NOT NULL UNIQUE,
                statement TEXT NOT NULL,
                scope TEXT NOT NULL,
                source_dimension TEXT,
                status TEXT NOT NULL CHECK(status IN ('hypothesis', 'confirmed', 'rejected')),
                confirmation TEXT NOT NULL CHECK(confirmation IN ('pending', 'confirmed', 'corrected')),
                evidence_count INTEGER NOT NULL DEFAULT 0,
                counter_evidence_count INTEGER NOT NULL DEFAULT 0,
                source_diversity INTEGER NOT NULL DEFAULT 0,
                recency_score REAL NOT NULL DEFAULT 0,
                confidence REAL NOT NULL DEFAULT 0,
                resonance INTEGER CHECK(resonance BETWEEN 1 AND 5),
                next_validation TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS model_claim_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id INTEGER NOT NULL REFERENCES model_claims(id),
                trace_id INTEGER REFERENCES traces(id),
                stance TEXT NOT NULL CHECK(stance IN ('support', 'counter')),
                evidence_type TEXT NOT NULL CHECK(evidence_type IN ('self_report', 'decision', 'action', 'outcome', 'user_feedback')),
                quote TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS fact_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_fact_id INTEGER NOT NULL UNIQUE REFERENCES trace_facts(id),
                status TEXT NOT NULL CHECK(status IN ('confirmed', 'corrected')),
                note TEXT NOT NULL DEFAULT '',
                reviewed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS prediction_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                claim_id INTEGER REFERENCES model_claims(id),
                statement TEXT NOT NULL,
                scope TEXT NOT NULL,
                probability REAL NOT NULL CHECK(probability >= 0 AND probability <= 1),
                due_date TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending', 'verified', 'dismissed')),
                outcome INTEGER CHECK(outcome IN (0, 1)),
                outcome_note TEXT,
                reviewed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, title TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS conversation_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id INTEGER NOT NULL REFERENCES conversations(id), created_at TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('user','assistant')), content TEXT NOT NULL, tool_context TEXT NOT NULL DEFAULT '[]');
            CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, title TEXT NOT NULL, purpose TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'archived')));
            """
        )
        source_columns = {row[1] for row in self.connection.execute("PRAGMA table_info(source_documents)")}
        if "record_kind" not in source_columns:
            self.connection.execute("ALTER TABLE source_documents ADD COLUMN record_kind TEXT NOT NULL DEFAULT 'reflection'")
        entry_columns = {row[1] for row in self.connection.execute("PRAGMA table_info(entries)")}
        if "project_id" not in entry_columns:
            self.connection.execute("ALTER TABLE entries ADD COLUMN project_id INTEGER REFERENCES projects(id)")
        conversation_columns = {row[1] for row in self.connection.execute("PRAGMA table_info(conversations)")}
        if "project_id" not in conversation_columns:
            self.connection.execute("ALTER TABLE conversations ADD COLUMN project_id INTEGER REFERENCES projects(id)")
        action_columns = {row[1] for row in self.connection.execute("PRAGMA table_info(action_cases)")}
        if "helpfulness" not in action_columns:
            self.connection.execute("ALTER TABLE action_cases ADD COLUMN helpfulness INTEGER CHECK(helpfulness BETWEEN 1 AND 5)")
        if "expected_signal" not in action_columns:
            self.connection.execute("ALTER TABLE action_cases ADD COLUMN expected_signal TEXT NOT NULL DEFAULT ''")
        if "follow_up_date" not in action_columns:
            self.connection.execute("ALTER TABLE action_cases ADD COLUMN follow_up_date TEXT")
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
        project_id: int | None = None,
    ) -> int:
        now = utc_now()
        cursor = self.connection.execute(
            "INSERT INTO entries(created_at, source, raw_text, project_id) VALUES (?, ?, ?, ?)", (now, source, raw_text, project_id)
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
        if project_id:
            self.connection.execute("UPDATE projects SET updated_at=? WHERE id=?", (now, project_id))
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

    def rate_action_case(self, case_id: int, helpfulness: int) -> dict[str, Any] | None:
        if helpfulness not in {1, 2, 3, 4, 5}:
            raise ValueError("行动帮助度需要在 1 到 5 之间。")
        self.connection.execute(
            "UPDATE action_cases SET helpfulness=? WHERE id=? AND status='reviewed'", (helpfulness, case_id)
        )
        self.connection.commit()
        return next((case for case in self.action_cases() if case["id"] == case_id), None)

    @staticmethod
    def _claim_confidence(evidence_count: int, counter_count: int, source_diversity: int, recency_score: float, confirmation: str) -> float:
        """A transparent confidence heuristic, not a personality measurement."""
        support = min(1.0, evidence_count / 6)
        diversity = min(1.0, source_diversity / 3)
        confirmation_weight = {"pending": 0.4, "confirmed": 0.85, "corrected": 1.0}[confirmation]
        contradiction = min(0.6, counter_count / (evidence_count + counter_count + 1))
        return round((0.35 * support + 0.20 * diversity + 0.20 * recency_score + 0.25 * confirmation_weight) * (1 - 0.5 * contradiction), 3)

    def record_claim(
        self, claim_key: str, statement: str, scope: str, evidence: list[str], *, source_dimension: str | None = None,
        trace_id: int | None = None, status: str = "confirmed", confirmation: str = "confirmed", next_validation: str = ""
    ) -> None:
        """Upsert one reviewable claim. It only records user-confirmed model writes."""
        now = utc_now()
        existing = self.connection.execute("SELECT id FROM model_claims WHERE claim_key=?", (claim_key,)).fetchone()
        if existing:
            claim_id = int(existing["id"])
            self.connection.execute(
                "UPDATE model_claims SET statement=?, scope=?, status=?, confirmation=?, next_validation=?, updated_at=? WHERE id=?",
                (statement, scope, status, confirmation, next_validation, now, claim_id),
            )
        else:
            claim_id = int(self.connection.execute(
                """INSERT INTO model_claims(claim_key, statement, scope, source_dimension, status, confirmation, next_validation, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (claim_key, statement, scope, source_dimension, status, confirmation, next_validation, now, now),
            ).lastrowid)
        already = self.connection.execute("SELECT count(*) FROM model_claim_evidence WHERE claim_id=? AND stance='support'", (claim_id,)).fetchone()[0]
        if not already:
            self.connection.executemany(
                "INSERT INTO model_claim_evidence(claim_id, trace_id, stance, evidence_type, quote, created_at) VALUES (?, ?, 'support', 'user_feedback', ?, ?)",
                [(claim_id, trace_id, item[:500], now) for item in evidence[:12]],
            )
        self._refresh_claim(claim_id)
        self.connection.commit()

    def _refresh_claim(self, claim_id: int) -> None:
        row = self.connection.execute("SELECT confirmation, created_at FROM model_claims WHERE id=?", (claim_id,)).fetchone()
        if row is None:
            return
        counts = self.connection.execute(
            """SELECT stance, count(*) AS n, count(DISTINCT trace_id) AS traces
               FROM model_claim_evidence WHERE claim_id=? GROUP BY stance""", (claim_id,)
        ).fetchall()
        grouped = {item["stance"]: item for item in counts}
        evidence_count = int(grouped.get("support", {"n": 0})["n"])
        counter_count = int(grouped.get("counter", {"n": 0})["n"])
        source_diversity = max(1 if evidence_count else 0, int(grouped.get("support", {"traces": 0})["traces"]))
        created = datetime.fromisoformat(row["created_at"])
        age_days = max(0, (datetime.now(timezone.utc) - created).days)
        recency_score = round(2.718281828 ** (-age_days / 90), 3)
        confidence = self._claim_confidence(evidence_count, counter_count, source_diversity, recency_score, row["confirmation"])
        self.connection.execute(
            "UPDATE model_claims SET evidence_count=?, counter_evidence_count=?, source_diversity=?, recency_score=?, confidence=?, updated_at=? WHERE id=?",
            (evidence_count, counter_count, source_diversity, recency_score, confidence, utc_now(), claim_id),
        )

    def sync_claims_from_model(self, model: dict[str, Any]) -> None:
        """Backfill claims for initial-seed dimensions without reinterpreting old Trace."""
        for name, item in model.get("confirmed_dimensions", {}).items():
            self.record_claim(
                f"dimension:{name}", f"当前对「{name.replace('_', ' · ')}」的工作判断", item.get("scope", "已确认模型范围"),
                list(item.get("evidence", [])), source_dimension=name,
            )
        for index, item in enumerate(model.get("hypotheses", [])):
            self.record_claim(
                f"hypothesis:{index}:{item.get('statement', '')[:60]}", item.get("statement", "待验证的理解"), item.get("scope", "当前记录范围"),
                list(item.get("evidence", [])), status="hypothesis", confirmation="pending", next_validation=item.get("next_validation", ""),
            )

    def model_claims(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM model_claims WHERE status != 'rejected' ORDER BY confidence DESC, id DESC").fetchall()
        return [dict(row) for row in rows]

    def rate_claim_resonance(self, claim_id: int, resonance: int) -> dict[str, Any] | None:
        if resonance not in {1, 2, 3, 4, 5}:
            raise ValueError("相似度需要在 1 到 5 之间。")
        self.connection.execute("UPDATE model_claims SET resonance=?, updated_at=? WHERE id=?", (resonance, utc_now(), claim_id))
        self.connection.commit()
        row = self.connection.execute("SELECT * FROM model_claims WHERE id=?", (claim_id,)).fetchone()
        return None if row is None else dict(row)

    def create_prediction(self, statement: str, scope: str, probability: float, due_date: str, claim_id: int | None = None) -> dict[str, Any]:
        try:
            datetime.strptime(due_date, "%Y-%m-%d")
        except ValueError as error:
            raise ValueError("验证日期格式应为 YYYY-MM-DD。") from error
        if not 0.05 <= probability <= 0.95:
            raise ValueError("预测把握请设置在 5% 到 95% 之间。")
        cursor = self.connection.execute(
            """INSERT INTO prediction_cases(created_at, claim_id, statement, scope, probability, due_date, status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
            (utc_now(), claim_id, statement.strip()[:500], scope.strip()[:300], probability, due_date),
        )
        self.connection.commit()
        return self.prediction(int(cursor.lastrowid)) or {}

    def prediction(self, prediction_id: int) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM prediction_cases WHERE id=?", (prediction_id,)).fetchone()
        return None if row is None else dict(row)

    def predictions(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM prediction_cases ORDER BY due_date, id DESC").fetchall()
        return [dict(row) for row in rows]

    def review_prediction(self, prediction_id: int, outcome: bool, note: str) -> dict[str, Any] | None:
        self.connection.execute(
            """UPDATE prediction_cases SET status='verified', outcome=?, outcome_note=?, reviewed_at=?
               WHERE id=? AND status='pending'""", (int(outcome), note.strip()[:1000], utc_now(), prediction_id)
        )
        self.connection.commit()
        return self.prediction(prediction_id)

    def review_fact(self, fact_id: int, status: str, note: str = "") -> None:
        if status not in {"confirmed", "corrected"}:
            raise ValueError("事实审阅只能为 confirmed 或 corrected。")
        self.connection.execute(
            """INSERT INTO fact_reviews(trace_fact_id, status, note, reviewed_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(trace_fact_id) DO UPDATE SET status=excluded.status, note=excluded.note, reviewed_at=excluded.reviewed_at""",
            (fact_id, status, note.strip()[:1000], utc_now()),
        )
        self.connection.commit()

    def model_validity(self) -> dict[str, Any]:
        claims = self.model_claims()
        fact = self.connection.execute("SELECT count(*) AS n, sum(status='confirmed') AS correct FROM fact_reviews").fetchone()
        reviewed_predictions = self.connection.execute("SELECT count(*) AS n, sum(outcome=1) AS correct FROM prediction_cases WHERE status='verified'").fetchone()
        reviewed_actions = self.connection.execute("SELECT count(*) AS n, avg(helpfulness) AS average FROM action_cases WHERE status='reviewed' AND helpfulness IS NOT NULL").fetchone()
        ratings = [item["resonance"] for item in claims if item["resonance"] is not None]
        return {
            "label": f"Hypothesis Model v{self.current_model().get('version', 0)}",
            "disclaimer": "这是基于有限记录、可被反证的工作假设；它不是完整人格，也不自动替你下结论。",
            "claims": claims,
            "metrics": {
                "fact": {"reviewed": int(fact["n"] or 0), "correct": int(fact["correct"] or 0)},
                "pattern": {"rated": len(ratings), "average": round(sum(ratings) / len(ratings), 1) if ratings else None},
                "prediction": {"reviewed": int(reviewed_predictions["n"] or 0), "correct": int(reviewed_predictions["correct"] or 0)},
                "intervention": {"reviewed": int(reviewed_actions["n"] or 0), "average": round(float(reviewed_actions["average"]), 1) if reviewed_actions["average"] is not None else None},
            },
            "predictions": self.predictions(),
            "actions": self.action_cases(),
        }

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

    def search_evidence(self, query: str, limit: int = 4) -> list[dict[str, Any]]:
        tokens = [token for token in query.replace("，", " ").replace("。", " ").split() if len(token) > 1][:6]
        rows = self.connection.execute("""SELECT e.created_at, e.raw_text, t.payload AS trace_payload, p.status
            FROM entries e JOIN traces t ON t.entry_id=e.id JOIN proposals p ON p.trace_id=t.id ORDER BY e.id DESC LIMIT 30""").fetchall()
        ranked = sorted(rows, key=lambda row: sum(token in row["raw_text"] for token in tokens), reverse=True)
        return [{"created_at": row["created_at"], "record": row["raw_text"], "trace": json.loads(row["trace_payload"]), "proposal_status": row["status"]} for row in ranked[:max(1, min(limit, 6))]]

    def projects(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("""SELECT p.*, count(DISTINCT c.id) AS conversation_count, count(DISTINCT e.id) AS trace_count
            FROM projects p LEFT JOIN conversations c ON c.project_id=p.id LEFT JOIN entries e ON e.project_id=p.id
            WHERE p.status='active' GROUP BY p.id ORDER BY p.updated_at DESC, p.id DESC""").fetchall()
        return [dict(row) for row in rows]

    def create_project(self, title: str, purpose: str = "") -> dict[str, Any]:
        title = title.strip()[:48]
        if not title: raise ValueError("给这个长期方向起一个简短名称。")
        now = utc_now()
        cursor = self.connection.execute("INSERT INTO projects(created_at, updated_at, title, purpose) VALUES (?, ?, ?, ?)", (now, now, title, purpose.strip()[:180]))
        self.connection.commit()
        return {"id": int(cursor.lastrowid), "title": title, "purpose": purpose.strip()[:180], "conversation_count": 0, "trace_count": 0}

    def conversations(self, project_id: int | None = None) -> list[dict[str, Any]]:
        if project_id:
            rows = self.connection.execute("SELECT id, title, updated_at, project_id FROM conversations WHERE project_id=? ORDER BY updated_at DESC LIMIT 24", (project_id,)).fetchall()
        else:
            rows = self.connection.execute("SELECT id, title, updated_at, project_id FROM conversations WHERE project_id IS NULL ORDER BY updated_at DESC LIMIT 24").fetchall()
        return [dict(row) for row in rows]

    def conversation(self, conversation_id: int) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT id, title, updated_at, project_id FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        return None if row is None else dict(row)

    def create_conversation(self, title: str = "和 Heka 的对话", project_id: int | None = None) -> int:
        now = utc_now(); cursor = self.connection.execute("INSERT INTO conversations(created_at, updated_at, title, project_id) VALUES (?, ?, ?, ?)", (now, now, title, project_id)); self.connection.commit(); return int(cursor.lastrowid)

    def add_conversation_message(self, conversation_id: int, role: str, content: str, tool_context: list[str] | None = None) -> None:
        now = utc_now(); self.connection.execute("INSERT INTO conversation_messages(conversation_id, created_at, role, content, tool_context) VALUES (?, ?, ?, ?, ?)", (conversation_id, now, role, content, json.dumps(tool_context or [], ensure_ascii=False))); self.connection.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conversation_id)); self.connection.execute("UPDATE projects SET updated_at=? WHERE id=(SELECT project_id FROM conversations WHERE id=?)", (now, conversation_id)); self.connection.commit()

    def conversation_messages(self, conversation_id: int, limit: int = 14) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT role, content, tool_context FROM conversation_messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?", (conversation_id, limit)).fetchall()
        return [{"role": row["role"], "content": row["content"], "tool_context": json.loads(row["tool_context"])} for row in reversed(rows)]

    def trace_calendar(self, days: int = 42) -> list[dict[str, Any]]:
        """Daily local Trace counts for the calendar; never returns raw text."""
        rows = self.connection.execute(
            """SELECT substr(e.created_at, 1, 10) AS day, count(*) AS count
               FROM entries e JOIN traces t ON t.entry_id=e.id
               WHERE date(e.created_at) >= date('now', ?)
               GROUP BY substr(e.created_at, 1, 10) ORDER BY day""",
            (f"-{max(1, min(days, 366))} days",),
        ).fetchall()
        return [dict(row) for row in rows]

    def traces_for_day(self, day: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """SELECT e.id, e.created_at, e.raw_text, t.payload AS trace_payload, p.status AS proposal_status
               FROM entries e JOIN traces t ON t.entry_id=e.id JOIN proposals p ON p.trace_id=t.id
               WHERE substr(e.created_at, 1, 10)=? ORDER BY e.id DESC""",
            (day,),
        ).fetchall()
        return [{**dict(row), "trace": json.loads(row["trace_payload"])} for row in rows]

    def delete_trace_entry(self, entry_id: int) -> dict[str, Any] | None:
        """Remove one local Trace and its derived analysis, never model history."""
        row = self.connection.execute(
            """SELECT t.id AS trace_id, p.status AS proposal_status
               FROM entries e JOIN traces t ON t.entry_id=e.id
               LEFT JOIN proposals p ON p.trace_id=t.id WHERE e.id=?""",
            (entry_id,),
        ).fetchone()
        if row is None:
            return None
        trace_id = int(row["trace_id"])
        self.connection.execute("DELETE FROM proposals WHERE trace_id=?", (trace_id,))
        self.connection.execute(
            "DELETE FROM trace_decision_options WHERE decision_id IN (SELECT id FROM trace_decisions WHERE trace_id=?)",
            (trace_id,),
        )
        for table in ("trace_decisions", "trace_actions", "trace_emotions", "trace_interpretations", "trace_tags", "trace_facts", "trace_events"):
            self.connection.execute(f"DELETE FROM {table} WHERE trace_id=?", (trace_id,))
        self.connection.execute("DELETE FROM source_documents WHERE entry_id=?", (entry_id,))
        self.connection.execute("DELETE FROM traces WHERE id=?", (trace_id,))
        self.connection.execute("DELETE FROM entries WHERE id=?", (entry_id,))
        self.connection.commit()
        return {"proposal_status": row["proposal_status"]}

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
