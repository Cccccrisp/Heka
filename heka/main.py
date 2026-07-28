from __future__ import annotations

import argparse
import json
from pathlib import Path

from .db import HekaStore
from .deepseek import load_dotenv, mock_analysis
from .local import analyse_record
from .obsidian import import_daily_records
from .schema import apply_confirmed_proposal


def pretty(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Heka V0.1 — a user-confirmed personal-model loop")
    parser.add_argument("--db", default="heka.db", help="SQLite database path (default: heka.db)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="create the local database and empty model")
    capture = sub.add_parser("capture", help="analyse one record and save a pending proposal")
    capture.add_argument("text")
    capture.add_argument("--source", default="cli")
    capture.add_argument("--mock", action="store_true", help="run the offline test path; no text leaves this computer")
    sub.add_parser("pending", help="show proposals waiting for your decision")
    review = sub.add_parser("review", help="accept or reject a proposal")
    review.add_argument("proposal_id", type=int)
    review.add_argument("decision", choices=("accept", "reject"))
    sub.add_parser("model", help="show the current confirmed model")
    obsidian_import = sub.add_parser("obsidian-import", help="import new or changed Obsidian daily records")
    obsidian_import.add_argument("folder", help="the chosen Obsidian daily-record folder")
    obsidian_import.add_argument("--dry-run", action="store_true", help="list records without reading them into Heka")
    obsidian_import.add_argument("--mock", action="store_true", help="test the import path without calling the local model")

    args = parser.parse_args()
    load_dotenv()
    store = HekaStore(Path(args.db))
    try:
        store.initialise()
        if args.command == "init":
            print(f"Ready: {Path(args.db).resolve()}")
        elif args.command == "capture":
            if args.mock:
                analysis, analyzer = mock_analysis(args.text), "offline-mock"
            else:
                analysis, analyzer = analyse_record(args.text, store.current_model())
            proposal_id = store.add_analysis(args.text, args.source, analysis, analyzer)
            print(f"Saved Trace and pending proposal #{proposal_id}. Nothing changed in the personal model.")
            pretty(analysis)
        elif args.command == "pending":
            pending = store.pending_proposals()
            if not pending:
                print("No pending proposals.")
            else:
                for item in pending:
                    print(f"\n#{item['id']} — record: {item['raw_text']}")
                    pretty(item["payload"])
        elif args.command == "review":
            proposal = store.proposal(args.proposal_id)
            if not proposal or proposal["status"] != "proposed":
                raise SystemExit("No pending proposal with that ID.")
            if args.decision == "reject":
                store.set_proposal_status(args.proposal_id, "rejected")
                print(f"Rejected proposal #{args.proposal_id}; model unchanged.")
            else:
                model = apply_confirmed_proposal(store.current_model(), proposal["payload"])
                store.add_model_snapshot(model, args.proposal_id)
                store.set_proposal_status(args.proposal_id, "accepted")
                print(f"Accepted proposal #{args.proposal_id}; saved model version {model['version']}.")
                pretty(model)
        elif args.command == "model":
            pretty(store.current_model())
        elif args.command == "obsidian-import":
            result = import_daily_records(
                store,
                Path(args.folder).expanduser(),
                offline_mock=args.mock,
                dry_run=args.dry_run,
            )
            print(f"Found {result['found']} Obsidian records; imported {len(result['imported'])}; skipped {len(result['skipped'])} unchanged records.")
            pretty(result)
    finally:
        store.close()


if __name__ == "__main__":
    main()
