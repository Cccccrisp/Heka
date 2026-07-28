"""Portable HPEP JSONL export; the database remains the local source of truth."""
from __future__ import annotations
import json
from pathlib import Path
from .db import HekaStore

def export_hpep(store: HekaStore, target: Path) -> int:
    rows = store.connection.execute("""SELECT e.id,e.created_at,e.source,e.raw_text,t.payload
        FROM entries e JOIN traces t ON t.entry_id=e.id ORDER BY e.id""").fetchall()
    target.parent.mkdir(parents=True, exist_ok=True)
    written=0
    with target.open("w",encoding="utf-8") as out:
        for row in rows:
            source={"id":f"source_{row['id']}","schema_version":"hpep/0.1","type":"source","created_at":row['created_at'],"source":row['source'],"content":row['raw_text']}
            evidence={"id":f"evidence_{row['id']}","schema_version":"hpep/0.1","type":"evidence","source_ids":[source['id']],"trace":json.loads(row['payload'])}
            out.write(json.dumps(source,ensure_ascii=False)+"\n");out.write(json.dumps(evidence,ensure_ascii=False)+"\n");written+=2
        for row in store.connection.execute("SELECT id,created_at,payload,status FROM proposals ORDER BY id"):
            claim={"id":f"claim_{row['id']}","schema_version":"hpep/0.1","type":"claim","created_at":row['created_at'],"status":row['status'],"proposal":json.loads(row['payload'])}
            out.write(json.dumps(claim,ensure_ascii=False)+"\n");written+=1
        for row in store.connection.execute("SELECT * FROM action_cases ORDER BY id"):
            plan=json.loads(row['plan']); evidence=json.loads(row['evidence']); base={"schema_version":"hpep/0.1","created_at":row['created_at'],"status":row['status']}
            objects=[{**base,"id":f"problem_{row['id']}","type":"problem","statement":row['problem'],"evidence":evidence},{**base,"id":f"experiment_{row['id']}","type":"experiment","problem_id":f"problem_{row['id']}","plan":plan,"selected_option":row['selected_option']}]
            if row['result_note']: objects.append({**base,"id":f"review_{row['id']}","type":"review","experiment_id":f"experiment_{row['id']}","result":row['result_note'],"reviewed_at":row['reviewed_at']})
            for obj in objects: out.write(json.dumps(obj,ensure_ascii=False)+"\n");written+=1
    return written
