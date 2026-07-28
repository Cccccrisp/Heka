"""Local semantic organizer: classify records before they enter Heka's database."""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .schema import validate_analysis


SYSTEM_PROMPT = '''You are Heka's LOCAL semantic organizer. Return JSON only.

You process one private user record before it is saved to a local SQLite database. Extract a verifiable Trace, classify it with 1–5 short snake_case tags, and propose one possible model update. Write all human-readable fields in concise Chinese; only tags and dimension names use snake_case English. You are not allowed to diagnose personality, treat one event as a stable trait, execute database operations, or accept an update yourself.

Return this JSON object exactly:
{
  "trace": {
    "event_type": "decision|emotion|action|reflection|interaction|other",
    "tags": ["short_topic"],
    "time_reference": "today|recently|historical|unknown",
    "observable_facts": [{"statement": "fact directly supported by the record", "category": "choice|action|emotion|context|outcome|expression", "source_quote": "short excerpt from the record", "confidence": 0.0}],
    "candidate_interpretations": [{"statement": "possible explanation, clearly not fact", "based_on_facts": [0], "missing_information": "what would distinguish this explanation", "confidence": 0.0}],
    "decision": {"question": "what was being decided", "stage": "considering|made|revisited", "selected_option": "chosen option or empty", "options": ["option A", "option B"], "reason_fact_indices": [0], "reversibility": "high|medium|low|unknown"},
    "actions": [{"statement": "an action actually taken or explicitly planned", "status": "done|planned|stopped|unknown", "source_quote": "short excerpt"}],
    "emotions": [{"label": "emotion in Chinese", "intensity": "low|medium|high|unknown", "source_quote": "short excerpt"}],
    "confidence": 0.0
  },
  "proposal": {
    "kind": "dimension_update|hypothesis|no_change",
    "dimension": "only for dimension_update, snake_case",
    "scope": "the situation this proposal applies to, in concise Chinese",
    "suggested_value": 0.0,
    "statement": "only for hypothesis",
    "reason": "why this is only a proposal",
    "evidence": ["specific evidence from this record"],
    "confidence": 0.0,
    "needs_user_confirmation": true,
    "next_validation": "future evidence that could strengthen or weaken it"
  }
}

Fact and interpretation indexes start at 0. For one record, prefer hypothesis or no_change; its proposal confidence must be at most 0.4. Output valid JSON only.'''


def analyse_record(raw_text: str, current_model: dict) -> tuple[dict, str]:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen3:4b")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Current confirmed model:\n" + json.dumps(current_model, ensure_ascii=False) + "\n\nPrivate record:\n" + raw_text},
    ]
    max_retries = max(0, int(os.getenv("HEKA_LOCAL_REPAIR_RETRIES", "1")))
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        body = {
        "model": model,
        "messages": messages,
        "format": "json",
        # Qwen3's extended thinking is useful for a final answer, but makes a
        # single-record filing pass unnecessarily slow. The cloud model is the
        # deliberation layer; the local model is a fast, conservative organizer.
        "think": False,
        "stream": False,
        "options": {"temperature": 0.2},
        "keep_alive": "10m",
    }
        request = Request(base_url + "/api/chat", data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=180) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise RuntimeError(f"Local organizer returned HTTP {error.code}: {error.read().decode('utf-8', 'replace')}") from error
        except URLError as error:
            raise RuntimeError(f"Could not reach local Ollama: {error.reason}") from error
        content = data.get("message", {}).get("content")
        if not content:
            last_error = ValueError("The local organizer returned empty content")
        else:
            try:
                return validate_analysis(json.loads(content)), f"ollama:{model}"
            except (json.JSONDecodeError, ValueError) as error:
                last_error = error
        if attempt < max_retries:
            messages.extend([
                {"role": "assistant", "content": content or ""},
                {"role": "user", "content": "你的上一次输出未通过结构校验：" + str(last_error) + "。只修复并返回符合既定 JSON 结构的内容；不要添加解释或 Markdown。"},
            ])
    raise RuntimeError(f"Local organizer output could not pass Heka's trace contract after {max_retries + 1} attempt(s): {last_error}")
