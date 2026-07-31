"""A minimal OpenAI-compatible cloud judge built with the Python standard library."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable
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


CONVERSATION_TOOLS = [
    {"type":"function","function":{"name":"read_confirmed_model","description":"Read the user-confirmed personal model. Use it only when it helps answer the current question.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"search_relevant_traces","description":"Search a bounded set of local Trace evidence relevant to the current question. Never infer from a Trace that is not returned.","parameters":{"type":"object","properties":{"query":{"type":"string"},"limit":{"type":"integer","minimum":1,"maximum":4}},"required":["query"]}}},
]

def converse_with_harness(history: list[dict], current_model: dict, search: Callable[[str, int], list[dict]]) -> dict:
    """Cloud reasoning can request bounded read tools; it never writes local state."""
    system = '''You are Heka, a personal reflection agent. Talk naturally in Chinese, but distinguish 已确认事实, 基于证据的推测, and 待验证问题 when relevant. You may use tools to inspect only the confirmed model or relevant local Trace records. Do not claim to know the user beyond returned evidence. Do not write data, make a permanent model update, or treat one conversation as a stable personality conclusion.

Question policy is strict: do not ask questions by default. Ask at most ONE concise follow-up only if its answer would materially change the conclusion, determine whether a Trace can be formed, or resolve a real contradiction. Never repeat information the user already gave. Never ask for timestamps, bodily details, or generic self-reflection merely to make the record feel complete. If the current material is sufficient, give the bounded answer and stop.'''
    messages = [{"role":"system","content":system}] + [{"role": item["role"], "content": item["content"]} for item in history[-14:]]
    used: list[str] = []
    for _ in range(3):
        body = {"model":os.getenv("HEKA_MODEL", "deepseek-chat"),"messages":messages,"tools":CONVERSATION_TOOLS,"tool_choice":"auto","temperature":0.35,"max_tokens":1300}
        request = Request(cloud_endpoint(), data=json.dumps(body).encode("utf-8"), headers={"Authorization":f"Bearer {cloud_key()}","Content-Type":"application/json"}, method="POST")
        try:
            with urlopen(request, timeout=90) as response: data=json.loads(response.read().decode("utf-8"))
        except HTTPError as error: raise RuntimeError(f"Cloud model returned HTTP {error.code}") from error
        except URLError as error: raise RuntimeError(f"Could not reach cloud model: {error.reason}") from error
        message = data.get("choices", [{}])[0].get("message", {})
        calls = message.get("tool_calls") or []
        if not calls:
            content = str(message.get("content") or "").strip()
            if not content: raise RuntimeError("云端模型没有返回对话内容。")
            return {"content":content,"used_tools":used}
        messages.append({"role":"assistant","content":message.get("content") or "","tool_calls":calls})
        for call in calls:
            name = call.get("function", {}).get("name", ""); raw = call.get("function", {}).get("arguments", "{}")
            try: arguments = json.loads(raw)
            except json.JSONDecodeError: arguments = {}
            if name == "read_confirmed_model": result = current_model; used.append("当前确认模型")
            elif name == "search_relevant_traces":
                query = str(arguments.get("query", "")).strip()[:160]; result = search(query, int(arguments.get("limit", 4))); used.append("相关 Trace")
            else: result = {"error":"这个工具不可用"}
            messages.append({"role":"tool","tool_call_id":call.get("id", ""),"content":json.dumps(result, ensure_ascii=False)})
    raise RuntimeError("云端推理调用工具次数过多，请换一种问法。")

def _fallback_trace_readiness(history: list[dict]) -> dict:
    """A conservative local fallback when a second cloud request is unavailable.

    The conversation itself has already been saved and answered by the cloud. This
    prevents a transient JSON-mode failure from turning a successful conversation
    into a failed one. It only unlocks a *candidate* Trace, which still requires
    the user's review before it can affect the model.
    """
    user_text = "\n".join(str(item.get("content") or "") for item in history if item.get("role") == "user").strip()
    concrete_cues = ("决定", "选择", "做了", "没有", "完成", "开始", "停止", "拒绝", "接受", "发生", "因为", "所以", "今天", "昨天")
    ready = len(user_text) >= 28 and any(cue in user_text for cue in concrete_cues)
    if ready:
        return {"ready": True, "reason": "这段对话已包含一个具体选择或经历，可先形成候选 Trace 并在审阅页确认。", "next_question": ""}
    return {"ready": False, "reason": "还需要一件具体发生的事，或你最后做出的选择。", "next_question": "这件事最后你做了什么选择，主要因为什么？"}


def _read_json_object(content: object) -> dict:
    text = str(content or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Cloud readiness response did not contain a JSON object.")
    value = json.loads(text[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("Cloud readiness response was not an object.")
    return value


def assess_trace_readiness(history: list[dict]) -> dict:
    """Ask the cloud for a bounded Trace decision, with a safe local fallback."""
    prompt = '''判断这段 Heka 对话是否已经足够形成一条“待审阅 Trace 候选”。只以用户自己的表达为准，不把助手的推测当作事实。

判断标准：用户已经说清“发生或选择了什么”以及“一个关键原因或语境”时，就应 ready=true。例如“我决定继续做 Heka，因为想先验证个人模型是否有价值”已经足够形成候选 Trace；不要要求用户解释项目定义、补充时间地点、数据，或进行泛泛自我反思。候选 Trace 仍须用户审阅，ready=true 不代表永久模型结论。

只有在没有具体经历、选择或关键原因时才 ready=false。此时 next_question 只能问一个最必要的问题。返回 JSON：{"ready":false,"reason":"...","next_question":"..."}'''
    body={"model":os.getenv("HEKA_MODEL","deepseek-chat"),"messages":[{"role":"system","content":prompt}]+[{"role":item["role"],"content":item["content"]} for item in history[-16:]],"response_format":{"type":"json_object"},"temperature":0.15,"max_tokens":300}
    request=Request(cloud_endpoint(),data=json.dumps(body).encode("utf-8"),headers={"Authorization":f"Bearer {cloud_key()}","Content-Type":"application/json"},method="POST")
    try:
        with urlopen(request,timeout=60) as response:
            payload=json.loads(response.read().decode("utf-8"))
        result=_read_json_object(payload.get("choices", [{}])[0].get("message", {}).get("content"))
    except (HTTPError, URLError, json.JSONDecodeError, IndexError, KeyError, TypeError, ValueError):
        return _fallback_trace_readiness(history)
    return {"ready":result.get("ready") is True,"reason":str(result.get("reason") or "需要更多可核验信息。"),"next_question":str(result.get("next_question") or "")}

def propose_initial_model_cloud(evidence: list[dict], self_report: dict) -> dict:
    """Cloud reasoning proposes the initial model; local code only validates and stores it."""
    from .local import _validate_initial_model_seed
    system='''你是 Heka 的初始模型推理层。只根据给出的初始自述与有限 Trace 提出 1-6 个有范围的候选维度和最多 3 个假设；不得诊断人格。每个维度必须有具体 evidence，confidence 不得超过 0.7。返回 JSON：{"dimensions":[{"name":"snake_case","value":0.0,"confidence":0.0,"scope":"...","evidence":["..."]}],"hypotheses":[],"boundary":"..."}'''
    body={"model":os.getenv("HEKA_MODEL","deepseek-chat"),"messages":[{"role":"system","content":system},{"role":"user","content":"Trace 证据包：\n"+json.dumps(evidence,ensure_ascii=False)+"\n\n初始自述：\n"+json.dumps(self_report,ensure_ascii=False)}],"response_format":{"type":"json_object"},"temperature":0.2,"max_tokens":1400}
    request=Request(cloud_endpoint(),data=json.dumps(body).encode("utf-8"),headers={"Authorization":f"Bearer {cloud_key()}","Content-Type":"application/json"},method="POST")
    try:
        with urlopen(request,timeout=90) as response: content=json.loads(response.read().decode("utf-8")).get("choices",[{}])[0].get("message",{}).get("content")
        return _validate_initial_model_seed(json.loads(content or "{}"))
    except (HTTPError, URLError, json.JSONDecodeError, ValueError) as error: raise RuntimeError("云端没有形成可审阅的初始模型，请重试。") from error


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

Question policy: the recommended question must be empty by default. Ask at most one question only when the answer would materially change the event-level judgment or determine whether a Trace is ready. Do not repeat facts, ask for timestamps, or request generic elaboration.

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
