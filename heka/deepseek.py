"""A minimal OpenAI-compatible cloud judge built with the Python standard library."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .schema import validate_analysis


SYSTEM_PROMPT = '''You are Heka's evidence-bounded observation module. Return JSON only.

Your task is to turn exactly one user record into an observation Trace and one model-update proposal. Do not diagnose, make personality claims, or treat a single event as a stable trait. Observable facts must be directly supported by the input; interpretations must be framed as candidates.

Return exactly this JSON object:
{
  "trace": {
    "event_type": "decision|emotion|action|reflection|interaction|other",
    "observable_facts": ["fact from the record"],
    "candidate_interpretations": ["possible explanation, not fact"],
    "confidence": 0.0
  },
  "proposal": {
    "kind": "dimension_update|hypothesis|no_change",
    "dimension": "only for dimension_update, snake_case",
    "suggested_value": 0.0,
    "statement": "only for hypothesis",
    "reason": "why this is only a proposal",
    "evidence": ["specific evidence from this record"],
    "confidence": 0.0,
    "needs_user_confirmation": true,
    "next_validation": "what future evidence would strengthen or weaken it"
  }
}

For a single record, prefer hypothesis or no_change over dimension_update. The term JSON must appear in your response.''' 


def load_dotenv(path: str | Path = ".env") -> None:
    dotenv = Path(path)
    if not dotenv.exists():
        return
    for line in dotenv.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def cloud_key() -> str:
    """Prefer the provider-neutral name, while preserving older DeepSeek setups."""
    key = os.getenv("HEKA_CLOUD_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    if not key or key == "your_key_here":
        raise RuntimeError(
            "Missing HEKA_CLOUD_API_KEY. Copy .env.example to .env and paste your own provider key."
        )
    return key


def cloud_endpoint() -> str:
    """OpenAI-compatible chat-completions endpoint; DeepSeek is the default."""
    base_url = os.getenv("HEKA_CLOUD_BASE_URL", "https://api.deepseek.com").rstrip("/")
    return base_url + "/chat/completions"


def analyse_record(raw_text: str, current_model: dict, model: str | None = None) -> tuple[dict, str]:
    key = cloud_key()
    selected_model = model or os.getenv("HEKA_MODEL", "deepseek-chat")
    body = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Current confirmed model (may be empty):\n" + json.dumps(current_model, ensure_ascii=False) + "\n\nUser record:\n" + raw_text},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": 1200,
    }
    request = Request(
        cloud_endpoint(),
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"Cloud model returned HTTP {error.code}: {error.read().decode('utf-8', 'replace')}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach cloud model: {error.reason}") from error
    content = data.get("choices", [{}])[0].get("message", {}).get("content")
    if not content:
        raise RuntimeError("DeepSeek returned empty content; run the command again.")
    return validate_analysis(json.loads(content)), selected_model


def answer_question(question: str, current_model: dict, evidence: list[dict]) -> str:
    """Cloud judge: makes an explicit, evidence-bounded final synthesis on request."""
    key = cloud_key()
    model = os.getenv("HEKA_MODEL", "deepseek-chat")
    system = '''You are Heka's cloud judgment layer. Answer the user's question from the supplied evidence packet and confirmed personal model only. Distinguish Confirmed, Inference, and Hypothesis. Do not claim a stable trait from one record. Cite the dates or record details you relied on. State what would falsify an important hypothesis. Answer in concise Chinese.''' 
    user = "Question:\n" + question + "\n\nConfirmed model:\n" + json.dumps(current_model, ensure_ascii=False) + "\n\nBounded evidence packet:\n" + json.dumps(evidence, ensure_ascii=False)
    body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": 0.3, "max_tokens": 1600}
    request = Request(cloud_endpoint(), data=json.dumps(body).encode("utf-8"), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"Cloud model returned HTTP {error.code}: {error.read().decode('utf-8', 'replace')}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach cloud model: {error.reason}") from error
    content = data.get("choices", [{}])[0].get("message", {}).get("content")
    if not content:
        raise RuntimeError("DeepSeek returned empty content; try again.")
    return content


def deepen_trace(transcript: str) -> dict:
    """Create an explicit cloud-only event reading; it never writes a model update."""
    key = cloud_key()
    system = '''You are Heka's optional cloud interpretation layer. You receive one Trace conversation only because the user explicitly requested deeper analysis.

Return JSON only. Make a useful event-level reading, not a personality diagnosis. Separate what the user actually said from your provisional interpretation. Do not make a model update, do not claim stable traits, and do not assume the user's next action. The recommended question must be empty if the transcript already supports a bounded conclusion.

Return:
{"observed":["atomic supported fact"],"interpretation":"provisional reading of this event","alternative":"a plausible competing reading","confidence":0.0,"what_would_change_it":"future or missing evidence that would revise this","recommended_question":"one question that would materially change the reading, or empty","boundary":"what this one Trace cannot establish"}'''
    body = {
        "model": os.getenv("HEKA_MODEL", "deepseek-chat"),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": "Trace conversation:\n" + transcript}],
        "response_format": {"type": "json_object"},
        "temperature": 0.25,
        "max_tokens": 1000,
    }
    request = Request(cloud_endpoint(), data=json.dumps(body).encode("utf-8"), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"Cloud model returned HTTP {error.code}: {error.read().decode('utf-8', 'replace')}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach cloud model: {error.reason}") from error
    content = data.get("choices", [{}])[0].get("message", {}).get("content")
    try:
        result = json.loads(content or "{}")
    except json.JSONDecodeError as error:
        raise RuntimeError("云端模型没有返回可用的深入判断，请重试。") from error
    required_text = ("interpretation", "alternative", "what_would_change_it", "recommended_question", "boundary")
    if not isinstance(result.get("observed"), list) or not all(isinstance(result.get(field), str) for field in required_text):
        raise RuntimeError("云端深入判断格式不完整，请重试。")
    confidence = result.get("confidence", 0.0)
    return {
        "observed": [str(item) for item in result["observed"][:4]],
        "interpretation": result["interpretation"].strip(),
        "alternative": result["alternative"].strip(),
        "confidence": min(0.7, max(0.0, float(confidence) if isinstance(confidence, (int, float)) else 0.0)),
        "what_would_change_it": result["what_would_change_it"].strip(),
        "recommended_question": result["recommended_question"].strip(),
        "boundary": result["boundary"].strip(),
    }


def propose_action_experiments(problem: str, evidence: list[dict]) -> dict:
    """Cloud Action Layer: propose bounded experiments, never instructions or model writes."""
    key = cloud_key()
    system = '''You are Heka's Action Layer. A user has explicitly confirmed they want help with a problem. Using only the supplied evidence, propose exactly 3 bounded options in concise Chinese. One option must be "继续观察 / 暂不行动". Do not diagnose, issue medical/legal/financial directives, or claim the problem is caused by a stable trait. Each option must include: title, action, cost_risk, success_signal, disconfirming_signal, review_after. Return JSON only: {"problem_frame":"...","evidence_boundary":"...","options":[{...},{...},{...}]}.'''
    body = {"model": os.getenv("HEKA_MODEL", "deepseek-chat"), "messages": [{"role":"system","content":system},{"role":"user","content":"用户确认的问题：\n"+problem+"\n\n有限证据：\n"+json.dumps(evidence,ensure_ascii=False)}], "response_format":{"type":"json_object"}, "temperature":0.25, "max_tokens":1400}
    request = Request(cloud_endpoint(), data=json.dumps(body).encode("utf-8"), headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"}, method="POST")
    try:
        with urlopen(request, timeout=90) as response: data=json.loads(response.read().decode("utf-8"))
    except HTTPError as error: raise RuntimeError(f"Cloud model returned HTTP {error.code}") from error
    except URLError as error: raise RuntimeError(f"Could not reach cloud model: {error.reason}") from error
    content=data.get("choices",[{}])[0].get("message",{}).get("content")
    plan=json.loads(content or "{}")
    options=plan.get("options")
    required={"title","action","cost_risk","success_signal","disconfirming_signal","review_after"}
    if not isinstance(options,list) or len(options)!=3 or not all(isinstance(item,dict) and required <= set(item) for item in options):
        raise RuntimeError("行动方案没有通过结构校验，请重新生成。")
    return plan


def mock_analysis(raw_text: str) -> dict:
    """A deterministic offline path for checking the data and review flow."""
    return validate_analysis({
        "trace": {
            "event_type": "reflection",
            "observable_facts": ["The user recorded: " + raw_text],
            "candidate_interpretations": ["One record alone is insufficient to infer a stable preference."],
            "confidence": 0.35,
        },
        "proposal": {
            "kind": "hypothesis",
            "statement": "A future pattern may be present, but more observations are required.",
            "reason": "This is an offline test proposal, not a conclusion about the person.",
            "evidence": ["One self-reported record"],
            "confidence": 0.2,
            "needs_user_confirmation": True,
            "next_validation": "Collect at least two comparable records with different outcomes.",
        },
    })
