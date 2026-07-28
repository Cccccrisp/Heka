const $ = (selector) => document.querySelector(selector);
const today = new Date().toISOString().slice(0, 10);
const transcript = [];
let hasGuide = false;

async function api(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "请求没有完成。");
  return body;
}

function addMessage(role, text) {
  const article = document.createElement("article");
  article.className = role === "guide" ? "guide-message" : "user-message";
  article.innerHTML = `<span>${role === "guide" ? "HEKA / LOCAL" : "你"}</span><p></p>`;
  article.querySelector("p").textContent = text;
  $("#trace-thread").append(article);
  article.scrollIntoView({behavior:"smooth", block:"nearest"});
}

function draftText() { return transcript.map((turn) => `${turn.role === "guide" ? "Heka 追问" : "用户"}：${turn.text}`).join("\n"); }

async function requestGuide() {
  const feedback = $("#trace-feedback");
  feedback.textContent = "本地模型正在整理下一句追问…";
  const guide = await api("/api/v1/trace-guide", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({transcript:draftText()})});
  transcript.push({role:"guide", text:guide.question}); addMessage("guide", guide.question); hasGuide = true;
  const options = $("#guide-options"); options.innerHTML = "";
  guide.options.forEach((option) => {
    const button = document.createElement("button"); button.className = "option"; button.textContent = option;
    button.onclick = async () => { if (option === "我自己补充") { $("#trace-input").focus(); return; } transcript.push({role:"user", text:option}); addMessage("user", option); try { await requestGuide(); } catch (error) { feedback.textContent = error.message; } };
    options.append(button);
  });
  feedback.textContent = guide.note + " 还要补充就继续写；不再补充时，直接点击“记录 Trace”保存。";
}

async function saveTrace() {
  const feedback = $("#trace-feedback");
  feedback.textContent = "正在由本地模型生成可审阅的 Trace…";
  const result = await api("/api/v1/capture", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({text:draftText()})});
  feedback.textContent = `Trace 已同步到本地数据库，并形成待审阅提案 #${result.proposal_id}。`;
  transcript.length = 0; hasGuide = false; $("#guide-options").innerHTML = "";
  $("#trace-thread").innerHTML = '<article class="guide-message"><span>HEKA / LOCAL</span><p>已结束这一条 Trace。还想记录另一件真实发生的事吗？</p></article>';
  loadCalendar(today);
}

$("#record-trace").onclick = async () => {
  const input = $("#trace-input"); const text = input.value.trim(); const feedback = $("#trace-feedback");
  if (text) { transcript.push({role:"user", text}); addMessage("user", text); input.value = ""; try { await requestGuide(); } catch (error) { feedback.textContent = error.message; } return; }
  if (hasGuide && transcript.some((turn) => turn.role === "user")) { try { await saveTrace(); } catch (error) { feedback.textContent = error.message; } return; }
  feedback.textContent = "先写下一点真实发生的事，再点击“记录 Trace”。";
};

function datesForCalendar() { const dates=[]; for (let offset=41; offset>=0; offset--) { const date=new Date(); date.setDate(date.getDate()-offset); dates.push(date.toISOString().slice(0,10)); } return dates; }
async function showDay(day) {
  const traces = await api(`/api/v1/traces/day/${day}`); $("#selected-day").textContent = day;
  $("#day-traces").innerHTML = traces.length ? traces.map((item) => { const facts=(item.trace.observable_facts||[]).map((fact)=>fact.statement).join("；"); const tags=(item.trace.tags||[]).join(" · "); return `<article class="day-trace"><p class="day-trace-meta">${item.created_at.slice(11,16)} · ${tags || item.trace.event_type}</p><p>${facts || item.raw_text}</p><span>${item.proposal_status === "accepted" ? "已纳入模型" : "等待你的审阅"}</span></article>`; }).join("") : '<p class="empty">这一天还没有留下 Trace。</p>';
}
async function loadCalendar(selected = today) {
  const entries = await api("/api/v1/traces/calendar"); const counts = new Map(entries.map((item)=>[item.day,item.count])); const calendar=$("#calendar"); calendar.innerHTML="";
  datesForCalendar().forEach((day) => { const button=document.createElement("button"); const number=Number(day.slice(-2)); const count=counts.get(day)||0; button.className=`calendar-day${count ? " has-trace" : ""}${day===selected ? " selected" : ""}`; button.innerHTML=`<span>${number}</span>${count ? '<i aria-label="有 Trace"></i>' : ""}`; button.onclick=()=>loadCalendar(day); calendar.append(button); });
  showDay(selected);
}

Promise.all([api("/api/v1/runtime"), loadCalendar(today)]).then(([runtime]) => { $("#runtime").textContent = `本地 Trace 引导 · ${runtime.local_model}`; }).catch((error) => { $("#runtime").textContent = error.message; });
