const $ = (selector) => document.querySelector(selector);
const today = new Date().toISOString().slice(0, 10);
const transcript = [];
let hasGuide = false;
let localOrganizerReady = false;
let guideAsked = false;
let isSubmitting = false;
let continuation = null;

async function api(url, options) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) throw new Error("当前页面没有连接到 Heka 后台。请从 Heka 应用中重新打开。 ");
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "请求没有完成。");
  return body;
}

function setTraceAvailability(ready) {
  localOrganizerReady = ready;
  $("#trace-input").disabled = !ready;
  $("#record-trace").disabled = !ready;
}

async function refreshLocalOrganizer() {
  const setup = $("#local-model-setup"); const title = $("#local-model-title"); const message = $("#local-model-message"); const actions = $("#local-model-actions");
  const status = await api("/api/v1/local-model/status");
  if (status.state === "ready") { setup.hidden = true; setTraceAvailability(true); return; }
  setTraceAvailability(false); setup.hidden = false; message.textContent = status.message; actions.innerHTML = "";
  if (status.state === "ollama_unavailable") {
    title.textContent = "先准备本地整理器";
    const link = document.createElement("a"); link.className = "primary setup-link"; link.href = "https://ollama.com/download"; link.target = "_blank"; link.rel = "noreferrer"; link.textContent = "安装 Ollama ↗"; actions.append(link);
    const retry = document.createElement("button"); retry.className = "quiet"; retry.textContent = "我已打开 Ollama，重新检查"; retry.onclick = () => refreshLocalOrganizer().catch((error) => { message.textContent = error.message; }); actions.append(retry);
  } else {
    title.textContent = `下载 ${status.model}`;
    const install = document.createElement("button"); install.className = "primary"; install.textContent = "下载本地模型"; install.onclick = async () => { install.disabled = true; message.textContent = "正在下载本地模型；这可能需要几分钟。"; try { const result = await api("/api/v1/local-model/install", {method:"POST", headers:{"Content-Type":"application/json"}, body:"{}"}); message.textContent = result.message; await refreshLocalOrganizer(); } catch (error) { message.textContent = error.message; install.disabled = false; } }; actions.append(install);
  }
}

function addMessage(role, text) {
  const article = document.createElement("article");
  article.className = role === "guide" ? "guide-message" : "user-message";
  article.innerHTML = `<span>${role === "guide" ? "HEKA / LOCAL" : "你"}</span><p></p>`;
  article.querySelector("p").textContent = text;
  $("#trace-thread").append(article);
  article.scrollIntoView({behavior:"smooth", block:"nearest"});
}

function addCloudJudgment(result) {
  const article = document.createElement("article"); article.className = "cloud-judgment-card";
  article.innerHTML = `<span>HEKA / 云端深入理解</span><p class="cloud-observed"></p><p class="cloud-interpretation"></p><p class="cloud-alternative"></p><p class="cloud-revision"></p><p class="cloud-boundary"></p>`;
  article.querySelector(".cloud-observed").textContent = `依据：${result.observed.join("；")}`;
  article.querySelector(".cloud-interpretation").textContent = `深入判断：${result.interpretation}`;
  article.querySelector(".cloud-alternative").textContent = `另一种可能：${result.alternative}`;
  article.querySelector(".cloud-revision").textContent = result.recommended_question ? `最关键的问题：${result.recommended_question}` : `什么会改变判断：${result.what_would_change_it}`;
  article.querySelector(".cloud-boundary").textContent = `边界：${result.boundary}`;
  $("#trace-thread").append(article); article.scrollIntoView({behavior:"smooth", block:"nearest"});
}

function addJudgment(judgment) {
  const article = document.createElement("article"); article.className = "judgment-card";
  article.innerHTML = `<span>HEKA / 初步判断</span><p class="judgment-observed"></p><p class="judgment-interpretation"></p><p class="judgment-revision"></p><div class="cloud-deepen"></div>`;
  article.querySelector(".judgment-observed").textContent = `已观察到：${judgment.observed}`;
  article.querySelector(".judgment-interpretation").textContent = `当前理解：${judgment.interpretation}`;
  article.querySelector(".judgment-revision").textContent = `它会因什么改变：${judgment.what_would_change_it}`;
  const deepen = document.createElement("button"); deepen.className = "cloud-deepen-button"; deepen.textContent = "发送这条 Trace 给云端，获得深入判断";
  deepen.onclick = async () => { deepen.disabled = true; deepen.textContent = "云端正在深入理解…"; try { const result = await api("/api/v1/trace/deepen", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({transcript:guideText()})}); addCloudJudgment(result); deepen.textContent = "已生成云端判断"; } catch (error) { deepen.textContent = error.message; deepen.disabled = false; } };
  article.querySelector(".cloud-deepen").append(deepen);
  $("#trace-thread").append(article); article.scrollIntoView({behavior:"smooth", block:"nearest"});
}

function userDraftText() { return transcript.map((turn) => `${turn.role === "guide" ? "Heka 追问" : "用户"}：${turn.text}`).join("\n"); }
function draftText() { return continuation ? `对 ${continuation.label} 的补充：\n${userDraftText()}` : userDraftText(); }
function guideText() { return continuation ? `正在补充的既有 Trace：\n${continuation.rawText}\n\n新的补充对话：\n${userDraftText()}` : userDraftText(); }

async function requestGuide() {
  const feedback = $("#trace-feedback");
  feedback.textContent = "本地模型正在整理下一句追问…";
  const guide = await api("/api/v1/trace-guide", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({transcript:guideText()})});
  addJudgment(guide.judgment); guideAsked = true; hasGuide = true;
  if (!guide.should_end) { transcript.push({role:"guide", text:guide.question}); addMessage("guide", guide.question); }
  const options = $("#guide-options"); options.innerHTML = "";
  guide.options.forEach((option) => {
    const button = document.createElement("button"); button.className = "option"; button.textContent = option;
    button.onclick = async () => { if (option === "我自己补充") { $("#trace-input").focus(); return; } transcript.push({role:"user", text:option}); addMessage("user", option); await saveTrace(); };
    options.append(button);
  });
  feedback.textContent = guide.should_end ? `${guide.note} 信息已足够；点击“记录 Trace”保存。` : `${guide.note} 请回答这个唯一会改变判断的问题；回答后将直接保存。`;
}

async function saveTrace() {
  if (isSubmitting) return; isSubmitting = true;
  const feedback = $("#trace-feedback");
  feedback.textContent = "正在由本地模型生成可审阅的 Trace…";
  let result;
  try { result = await api("/api/v1/capture", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({text:draftText(), continuation_of:continuation?.id || null})}); }
  catch (error) { isSubmitting = false; throw error; }
  feedback.textContent = `Trace 已同步到本地数据库，并形成待审阅提案 #${result.proposal_id}。`;
  const studio = $(".trace-studio");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  studio.classList.add("is-filing");
  if (!reduceMotion) await new Promise((resolve) => window.setTimeout(resolve, 260));
  transcript.length = 0; hasGuide = false; guideAsked = false; isSubmitting = false; continuation = null; $("#guide-options").innerHTML = "";
  $("#trace-input").placeholder = "例如：今天我本来想开始另一个项目，但最后继续修改 Heka……";
  $("#trace-thread").innerHTML = '<article class="guide-message"><span>HEKA / LOCAL</span><p>已结束这一条 Trace。还想记录另一件真实发生的事吗？</p></article>';
  studio.classList.remove("is-filing");
  showToday();
}

$("#record-trace").onclick = async () => {
  if (!localOrganizerReady) return;
  const input = $("#trace-input"); const text = input.value.trim(); const feedback = $("#trace-feedback");
  if (text) { transcript.push({role:"user", text}); addMessage("user", text); input.value = ""; try { if (guideAsked) await saveTrace(); else await requestGuide(); } catch (error) { feedback.textContent = error.message; } return; }
  if (hasGuide && transcript.some((turn) => turn.role === "user")) { try { await saveTrace(); } catch (error) { feedback.textContent = error.message; } return; }
  feedback.textContent = "先写下一点真实发生的事，再点击“记录 Trace”。";
};

function startContinuation(item) {
  continuation = {id:item.id, label:`今天 ${item.created_at.slice(11,16)} 的 Trace`, rawText:item.raw_text};
  transcript.length = 0; hasGuide = false; guideAsked = false; $("#guide-options").innerHTML = "";
  const thread = $("#trace-thread"); thread.innerHTML = "";
  const context = document.createElement("article"); context.className = "trace-context";
  context.innerHTML = "<span>已有 Trace / 只作上下文</span><p></p><small>你接下来写的内容会作为一条新的补充 Trace 保存，原记录不会被改写。</small>";
  context.querySelector("p").textContent = item.raw_text; thread.append(context);
  addMessage("guide", "你想补充什么？我会围绕这条既有记录只追问一个关键问题。");
  $("#trace-input").placeholder = "补充当时的原因、结果，或后来发生的变化……";
  $("#trace-feedback").textContent = "这是对已有 Trace 的补充；原记录会保留，新的内容会单独进入本地数据库。";
  $("#trace-input").focus(); document.querySelector(".trace-studio").scrollIntoView({behavior:"smooth", block:"start"});
}

async function deleteTrace(item) {
  const warning = item.proposal_status === "accepted" ? "这条 Trace 已被纳入过模型。删除记录不会自动回滚已确认的历史模型版本。" : "这会删除这条 Trace 及其候选分析。";
  if (!window.confirm(`${warning}\n\n确认删除吗？`)) return;
  const feedback = $("#trace-feedback");
  try { const result = await api(`/api/v1/traces/${item.id}`, {method:"DELETE"}); feedback.textContent = result.message; await showToday(); }
  catch (error) { feedback.textContent = error.message; }
}

function renderTodayTrace(item) {
  const article = document.createElement("article"); article.className = "today-trace";
  const facts = (item.trace.observable_facts || []).map((fact) => fact.statement).join("；");
  const meta = document.createElement("p"); meta.className = "day-trace-meta"; meta.textContent = `${item.created_at.slice(11,16)} · ${(item.trace.tags || []).join(" · ") || item.trace.event_type}`;
  const text = document.createElement("p"); text.textContent = facts || item.raw_text;
  const state = document.createElement("span"); state.textContent = item.proposal_status === "accepted" ? "已纳入模型" : "等待你的审阅";
  const actions = document.createElement("div"); actions.className = "today-trace-actions";
  const continueButton = document.createElement("button"); continueButton.className = "trace-action"; continueButton.textContent = "继续补充"; continueButton.onclick = () => startContinuation(item);
  const deleteButton = document.createElement("button"); deleteButton.className = "trace-action delete"; deleteButton.textContent = "删除"; deleteButton.onclick = () => deleteTrace(item);
  actions.append(continueButton, deleteButton); article.append(meta, text, state, actions); return article;
}

async function showToday() {
  const traces = await api(`/api/v1/traces/day/${today}`); const title=$("#today-title"); const caption=$("#today-caption");
  title.textContent = "今日你的 Trace"; caption.textContent = traces.length ? `这一天共有 ${traces.length} 条记录` : "今天还没有留下 Trace。";
  const list = $("#today-traces"); list.innerHTML = "";
  if (!traces.length) { list.innerHTML = '<p class="empty">还没有记录。左侧写下今天发生的事。</p>'; return; }
  traces.forEach((item) => list.append(renderTodayTrace(item)));
}

Promise.all([api("/api/v1/runtime"), showToday(), refreshLocalOrganizer()]).then(([runtime]) => { $("#runtime").textContent = `本地 Trace 引导 · ${runtime.local_model}`; }).catch((error) => { $("#runtime").textContent = error.message; setTraceAvailability(false); });
