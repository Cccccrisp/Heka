"""Local Heka dashboard server. Run: python3 server.py"""

from __future__ import annotations

import json
import os
import sys
import webbrowser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from heka.db import HekaStore
from heka.deepseek import analyse_record as cloud_analyse_record, answer_question, assess_trace_readiness, converse_with_harness, deepen_trace, load_dotenv, propose_action_experiments, propose_initial_model_cloud
from heka.local import install_local_model, local_model_status
from heka.obsidian import import_daily_records
from heka.schema import apply_confirmed_proposal, apply_initial_model_seed


ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
WEB_ROOT = ROOT / "web"
DATA_ROOT = Path(os.getenv("HEKA_DATA_DIR", str(ROOT))).expanduser()
DATABASE = DATA_ROOT / "heka.db"
MODEL_SETTING_KEYS = ("OLLAMA_BASE_URL", "OLLAMA_MODEL", "HEKA_CLOUD_BASE_URL", "HEKA_MODEL", "HEKA_CLOUD_API_KEY")


def config_path() -> Path:
    return Path(os.getenv("HEKA_CONFIG_FILE", str(ROOT / ".env"))).expanduser()


def _safe_setting(value: object, label: str, *, allow_empty: bool = False) -> str:
    text = str(value or "").strip()
    if (not text and not allow_empty) or "\n" in text or "\r" in text or len(text) > 500:
        raise ValueError(f"{label} 格式不正确。")
    return text


def model_settings() -> dict:
    """Return runtime config without ever exposing a cloud credential."""
    return {
        "local": {
            "base_url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            "model": os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        },
        "cloud": {
            "base_url": os.getenv("HEKA_CLOUD_BASE_URL", "https://api.deepseek.com"),
            "model": os.getenv("HEKA_MODEL", "deepseek-chat"),
            "api_key_configured": bool(os.getenv("HEKA_CLOUD_API_KEY") or os.getenv("DEEPSEEK_API_KEY")),
        },
    }


def save_model_settings(payload: dict) -> dict:
    """Persist selected model settings locally and apply them to this process."""
    local = payload.get("local") if isinstance(payload.get("local"), dict) else {}
    cloud = payload.get("cloud") if isinstance(payload.get("cloud"), dict) else {}
    values = {
        "OLLAMA_BASE_URL": _safe_setting(local.get("base_url", os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")), "本地模型地址"),
        "OLLAMA_MODEL": _safe_setting(local.get("model", os.getenv("OLLAMA_MODEL", "qwen3:8b")), "本地模型名称"),
        "HEKA_CLOUD_BASE_URL": _safe_setting(cloud.get("base_url", os.getenv("HEKA_CLOUD_BASE_URL", "https://api.deepseek.com")), "云端地址"),
        "HEKA_MODEL": _safe_setting(cloud.get("model", os.getenv("HEKA_MODEL", "deepseek-chat")), "云端模型名称"),
    }
    clear_key = cloud.get("clear_api_key") is True
    new_key = _safe_setting(cloud.get("api_key", ""), "云端 API Key", allow_empty=True)
    path = config_path()
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    replacements = dict(values)
    if new_key:
        replacements["HEKA_CLOUD_API_KEY"] = new_key
    elif clear_key:
        replacements["HEKA_CLOUD_API_KEY"] = ""
    written: set[str] = set()
    output: list[str] = []
    for line in existing:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else ""
        if key in replacements:
            output.append(f"{key}={replacements[key]}")
            written.add(key)
        else:
            output.append(line)
    for key, value in replacements.items():
        if key not in written:
            output.append(f"{key}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    for key, value in replacements.items():
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)
    return model_settings()


def obsidian_daily_dir() -> str:
    """Resolve after .env has loaded, so local path changes take effect on restart."""
    return os.getenv("HEKA_OBSIDIAN_DAILY_DIR", "").strip()


class HekaHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _store(self) -> HekaStore:
        store = HekaStore(DATABASE)
        store.initialise()
        return store

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/v1/health":
            self._json(HTTPStatus.OK, {"status": "ok", "api_version": "v1", "storage": "local_sqlite"})
            return
        if path.startswith("/api/v1/"):
            path = "/api/" + path[len("/api/v1/"):]
        if path == "/api/model":
            store = self._store()
            try:
                self._json(HTTPStatus.OK, store.current_model())
            finally:
                store.close()
            return
        if path == "/api/pending":
            store = self._store()
            try:
                self._json(HTTPStatus.OK, store.pending_proposals())
            finally:
                store.close()
            return
        if path == "/api/runtime":
            self._json(HTTPStatus.OK, {"local_model": os.getenv("OLLAMA_MODEL", "qwen3:8b"), "cloud_model": os.getenv("HEKA_MODEL", "deepseek-chat")})
            return
        if path == "/api/settings/model":
            self._json(HTTPStatus.OK, model_settings())
            return
        if path.startswith("/api/conversations/"):
            conversation_id = int(path.rsplit("/", 1)[-1]); store = self._store()
            try: self._json(HTTPStatus.OK, {"messages": store.conversation_messages(conversation_id)})
            finally: store.close()
            return
        if path == "/api/local-model/status":
            self._json(HTTPStatus.OK, local_model_status())
            return
        if path == "/api/evolution":
            store = self._store()
            try:
                self._json(HTTPStatus.OK, store.evolution_events())
            finally:
                store.close()
            return
        if path == "/api/obsidian/status":
            store = self._store()
            try:
                configured = bool(obsidian_daily_dir())
                self._json(HTTPStatus.OK, {
                    "configured": configured,
                    "label": "每日" if configured else "未设置资料目录",
                    "imported_count": store.source_document_count(),
                })
            finally:
                store.close()
            return
        if path == "/api/onboarding":
            store = self._store()
            try:
                self._json(HTTPStatus.OK, store.latest_initial_self_report())
            finally:
                store.close()
            return
        if path == "/api/actions":
            store = self._store()
            try: self._json(HTTPStatus.OK, store.action_cases())
            finally: store.close()
            return
        if path == "/api/traces/calendar":
            store = self._store()
            try:
                self._json(HTTPStatus.OK, store.trace_calendar())
            finally:
                store.close()
            return
        if path.startswith("/api/traces/day/"):
            day = path.rsplit("/", 1)[-1]
            if len(day) != 10:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "日期格式应为 YYYY-MM-DD。"})
                return
            store = self._store()
            try:
                self._json(HTTPStatus.OK, store.traces_for_day(day))
            finally:
                store.close()
            return
        return super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/v1/"):
            path = "/api/" + path[len("/api/v1/"):]
        try:
            body = self._body()
            if path == "/api/capture":
                text = str(body.get("text", "")).strip()
                if not text:
                    raise ValueError("请先写下一条真实记录。")
                source = "dashboard_continuation" if body.get("continuation_of") else "dashboard"
                store = self._store()
                try:
                    analysis, analyzer = cloud_analyse_record(text, store.current_model())
                    proposal_id = store.add_analysis(text, source, analysis, analyzer)
                    self._json(HTTPStatus.CREATED, {"proposal_id": proposal_id, "analysis": analysis})
                finally:
                    store.close()
                return
            if path == "/api/conversations/chat":
                text = str(body.get("text", "")).strip()
                if not text: raise ValueError("先写下你想和 Heka 讨论的事。")
                store = self._store()
                try:
                    conversation_id = int(body.get("conversation_id") or 0) or store.create_conversation(text[:36])
                    store.add_conversation_message(conversation_id, "user", text)
                    result = converse_with_harness(store.conversation_messages(conversation_id), store.current_model(), store.search_evidence)
                    store.add_conversation_message(conversation_id, "assistant", result["content"], result["used_tools"])
                    readiness = assess_trace_readiness(store.conversation_messages(conversation_id))
                    self._json(HTTPStatus.OK, {"conversation_id":conversation_id, **result, "trace_readiness":readiness})
                finally: store.close()
                return
            if path.startswith("/api/conversations/") and path.endswith("/trace-candidate"):
                conversation_id = int(path.split("/")[3]); store = self._store()
                try:
                    messages = store.conversation_messages(conversation_id, 30)
                    user_messages = [item for item in messages if item["role"] == "user"]
                    if not user_messages: raise ValueError("这段对话还没有足够的用户记录可以形成 Trace。")
                    transcript = "\n".join(("你：" if item["role"] == "user" else "Heka：") + item["content"] for item in messages)
                    analysis, analyzer = cloud_analyse_record(transcript, store.current_model())
                    proposal_id = store.add_analysis(transcript, "cloud_conversation", analysis, analyzer)
                    self._json(HTTPStatus.CREATED, {"proposal_id":proposal_id, "message":"已生成一条待审阅的 Trace 候选；它尚未改变模型。"})
                finally: store.close()
                return
            if path == "/api/settings/model":
                self._json(HTTPStatus.OK, {"settings": save_model_settings(body), "message": "模型设置已只保存在这台设备上。"})
                return
            if path == "/api/trace-guide":
                transcript = str(body.get("transcript", "")).strip()
                if len(transcript) < 2:
                    raise ValueError("先写下一点真实发生的事，Heka 才能追问。")
                result = deepen_trace(transcript)
                self._json(HTTPStatus.OK, {"judgment":{"observed":"；".join(result["observed"]),"interpretation":result["interpretation"],"confidence":result["confidence"],"what_would_change_it":result["what_would_change_it"]},"question":result["recommended_question"],"options":["我自己补充"],"should_end":not bool(result["recommended_question"]),"note":"这是云端对当前事件的暂定理解，不是人格结论。"})
                return
            if path == "/api/trace/deepen":
                transcript = str(body.get("transcript", "")).strip()
                if len(transcript) < 2:
                    raise ValueError("先留下当前 Trace 的内容，才能请求深入理解。")
                self._json(HTTPStatus.OK, deepen_trace(transcript))
                return
            if path == "/api/local-model/install":
                self._json(HTTPStatus.OK, install_local_model())
                return
            if path == "/api/model/bootstrap":
                store = self._store()
                try:
                    evidence = store.recent_evidence(12)
                    if len(evidence) < 3:
                        raise ValueError("至少需要 3 条 Trace，才能建立初始模型。")
                    report = store.latest_initial_self_report()
                    if report is None:
                        raise ValueError("请先完成初始问卷，再建立第一个模型版本。")
                    self._json(HTTPStatus.OK, {"seed": propose_initial_model_cloud(evidence, report["answers"]), "source_count": len(evidence)})
                finally:
                    store.close()
                return
            if path == "/api/model/bootstrap/confirm":
                seed = body.get("seed")
                if not isinstance(seed, dict) or not isinstance(seed.get("dimensions"), list):
                    raise ValueError("初始模型内容不完整。")
                store = self._store()
                try:
                    model = apply_initial_model_seed(store.current_model(), seed)
                    store.add_model_snapshot(model, None)
                    self._json(HTTPStatus.OK, {"model": model, "message": "已将这周的模型起点写入本地版本历史。"})
                finally:
                    store.close()
                return
            if path == "/api/ask":
                question = str(body.get("question", "")).strip()
                if not question:
                    raise ValueError("请先写下你想判断的问题。")
                store = self._store()
                try:
                    answer = answer_question(question, store.current_model(), store.recent_evidence())
                    self._json(HTTPStatus.OK, {"answer": answer})
                finally:
                    store.close()
                return
            if path == "/api/obsidian/sync":
                folder = obsidian_daily_dir()
                if not folder:
                    raise ValueError("还没有设置 Obsidian 每日记录目录。请在 .env 中填写 HEKA_OBSIDIAN_DAILY_DIR。")
                store = self._store()
                try:
                    result = import_daily_records(store, Path(folder))
                    self._json(HTTPStatus.OK, {**result, "imported_count": store.source_document_count()})
                finally:
                    store.close()
                return
            if path == "/api/onboarding":
                answers = body.get("answers")
                required = {"opportunity", "ambiguity", "tradeoff", "pressure", "support"}
                if not isinstance(answers, dict) or not required <= set(answers) or not all(isinstance(answers[key], str) and answers[key] for key in required):
                    raise ValueError("请完成五个初始校准问题。")
                summary = "这是你主动提供的初始自述，用于生成待验证的观察方向，不是已确认的人格结论。"
                store = self._store()
                try:
                    store.save_initial_self_report(answers, summary)
                    self._json(HTTPStatus.CREATED, {"message": "已保存为初始自述；它不会直接改变个人模型。", "summary": summary})
                finally:
                    store.close()
                return
            if path == "/api/actions":
                problem = str(body.get("problem", "")).strip()
                confirmed = body.get("confirmed") is True
                if len(problem) < 12: raise ValueError("请先用一句具体的话确认你想处理的问题。")
                if not confirmed: raise ValueError("请先确认：这是你希望 Heka 帮你处理的问题。")
                store = self._store()
                try:
                    evidence = store.recent_evidence(12)
                    if not evidence: raise ValueError("至少需要一条本地记录后，Heka 才能提出方案。")
                    plan = propose_action_experiments(problem, evidence)
                    case_id = store.add_action_case(problem, evidence, plan)
                    self._json(HTTPStatus.CREATED, {"case_id":case_id,"plan":plan})
                finally: store.close()
                return
            if path.startswith("/api/actions/") and path.endswith("/select"):
                case_id = int(path.split("/")[3]); option_index=int(body.get("option_index", -1))
                if option_index not in {0,1,2}: raise ValueError("请选择一个方案。")
                store=self._store()
                try:
                    case=store.select_action_option(case_id, option_index)
                    if case is None: self._json(HTTPStatus.NOT_FOUND,{"error":"没有找到可选择的方案。"})
                    else: self._json(HTTPStatus.OK,{"case":case,"message":"已选定。到复盘日再记录真实结果。"})
                finally: store.close()
                return
            if path.startswith("/api/actions/") and path.endswith("/review"):
                case_id=int(path.split("/")[3]); result_note=str(body.get("result_note", "")).strip()
                if len(result_note)<8: raise ValueError("请留下至少一句真实结果或反证。")
                store=self._store()
                try:
                    case=store.review_action_case(case_id,result_note)
                    if case is None:self._json(HTTPStatus.NOT_FOUND,{"error":"没有找到待复盘的行动方案。"})
                    else:self._json(HTTPStatus.OK,{"case":case,"message":"已记录结果。下一次模型更新仍需单独审阅。"})
                finally:store.close()
                return
            if path == "/api/evolution/review":
                days = int(body.get("days", 90))
                store = self._store()
                try:
                    self._json(HTTPStatus.OK, {"events": store.generate_evolution_candidates(days)})
                finally:
                    store.close()
                return
            if path.startswith("/api/evolution/") and path.endswith("/review"):
                event_id = int(path.split("/")[3])
                decision = str(body.get("decision", ""))
                note = str(body.get("note", ""))
                store = self._store()
                try:
                    event = store.review_evolution_event(event_id, decision, note)
                    if event is None:
                        self._json(HTTPStatus.NOT_FOUND, {"error": "没有找到这个演化事件。"})
                    else:
                        self._json(HTTPStatus.OK, {"event": event})
                finally:
                    store.close()
                return
            if path.startswith("/api/proposals/") and path.endswith("/review"):
                proposal_id = int(path.split("/")[3])
                decision = body.get("decision")
                if decision not in {"accept", "reject"}:
                    raise ValueError("decision 必须是 accept 或 reject")
                store = self._store()
                try:
                    proposal = store.proposal(proposal_id)
                    if not proposal or proposal["status"] != "proposed":
                        self._json(HTTPStatus.NOT_FOUND, {"error": "没有找到待确认的提案。"})
                        return
                    if decision == "accept":
                        model = apply_confirmed_proposal(store.current_model(), proposal["payload"])
                        store.add_model_snapshot(model, proposal_id)
                        store.set_proposal_status(proposal_id, "accepted")
                        self._json(HTTPStatus.OK, {"message": "已写入新的模型版本。", "model": model})
                    else:
                        store.set_proposal_status(proposal_id, "rejected")
                        self._json(HTTPStatus.OK, {"message": "已保留记录，但没有改变模型。"})
                finally:
                    store.close()
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "找不到这个接口。"})
        except (ValueError, json.JSONDecodeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except Exception as error:  # keep the browser error useful without leaking the API key
            self._json(HTTPStatus.BAD_GATEWAY, {"error": str(error)})

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/v1/"):
            path = "/api/" + path[len("/api/v1/"):]
        if not path.startswith("/api/traces/"):
            self._json(HTTPStatus.NOT_FOUND, {"error": "找不到这个接口。"})
            return
        try:
            entry_id = int(path.rsplit("/", 1)[-1])
            if entry_id < 1:
                raise ValueError("无效的 Trace。")
            store = self._store()
            try:
                deleted = store.delete_trace_entry(entry_id)
            finally:
                store.close()
            if deleted is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "这条 Trace 已不存在。"})
                return
            note = "已删除这条 Trace 及其候选分析。"
            if deleted["proposal_status"] == "accepted":
                note += " 已确认的历史模型版本会保留，不会自动回滚。"
            self._json(HTTPStatus.OK, {"message": note})
        except (ValueError, json.JSONDecodeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except Exception as error:
            self._json(HTTPStatus.BAD_GATEWAY, {"error": str(error)})


def run_server() -> None:
    load_dotenv(Path(os.getenv("HEKA_CONFIG_FILE", str(ROOT / ".env"))))
    port = int(os.getenv("HEKA_PORT", "8787"))
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", port), HekaHandler)
    address = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"HEKA_READY={address}", flush=True)
    if os.getenv("HEKA_OPEN_BROWSER", "1") != "0":
        webbrowser.open(address)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
