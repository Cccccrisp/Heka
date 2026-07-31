const q = (selector) => document.querySelector(selector);
const questions = [
  ["opportunity","决策 / 新机会", "1. 一个新机会出现时，你通常先怎么做？", ["尽快做一个小尝试","先收集信息和判断标准","先完成正在做的事","等机会更清楚再说"]],
  ["ambiguity","决策 / 信息不足", "2. 信息不够、但必须做选择时，你更接近？", ["先做一个可逆的小决定","继续查资料，降低不确定性","找可信的人讨论","暂时不做决定"]],
  ["tradeoff","决策 / 取舍", "3. 新方向和已有投入冲突时，你通常如何取舍？", ["优先守住已有投入","优先探索新方向","给新方向一个小规模实验","先看外部反馈"]],
  ["deadline","决策 / 截止期", "4. 临近截止期但方案还不满意时，你通常会？", ["先交付一个可用版本","继续打磨到满意","缩小范围重做关键部分","找人帮助判断取舍"]],
  ["feedback","决策 / 外部意见", "5. 别人强烈反对你的判断时，你第一反应更像？", ["重新检查事实和假设","先解释自己的逻辑","保留判断，继续观察","快速改变方向"]],
  ["role","工作 / 角色", "6. 在一个新项目里，你最自然承担的角色是？", ["提出方向并推动开始","研究问题和搭建框架","连接人和表达故事","稳定执行并完善细节"]],
  ["starting","工作 / 启动", "7. 面对一个模糊的大任务时，你通常从哪里开始？", ["立刻做一个原型","先定义问题和边界","先列完整计划","先找类似案例"]],
  ["stuck","工作 / 卡住", "8. 一个项目卡住时，你最常做的是？", ["换一种做法继续试","回到问题本身重新拆解","暂时转去做别的事","找外部反馈"]],
  ["quality_speed","工作 / 质量", "9. 质量和速度冲突时，你更常偏向？", ["先发出去再迭代","先做到自己认可","按影响大小分层处理","看是否有明确反馈再决定"]],
  ["output","工作 / 对外输出", "10. 完成一个阶段后，你更容易？", ["马上公开或找人测试","先自己复盘再说","继续完善，不急着发布","开启下一个方向"]],
  ["pressure","压力 / 动作", "11. 压力大或事情很多时，什么最能让你重新动起来？", ["把问题拆小，先完成一步","先独自整理清楚","找人讨论或获得反馈","暂停，等状态恢复"]],
  ["emotion","压力 / 情绪", "12. 遇到挫折时，你最接近哪种反应？", ["分析原因，马上调整","情绪会持续影响一段时间","先做其他能完成的事","想找人说一说"]],
  ["recovery","压力 / 恢复", "13. 连续高投入之后，你最有效的恢复方式是？", ["独处和减少输入","与熟悉的人相处","运动或去外面走走","换一个新鲜的任务"]],
  ["conflict","关系 / 冲突", "14. 与重要的人出现分歧时，你通常会？", ["尽快把问题说开","先想清楚再沟通","先退一步避免冲突","希望对方先理解我的感受"]],
  ["support","关系 / 支持", "15. 你遇到重要决定时，更希望别人提供？", ["不同视角和事实","明确的鼓励和支持","一起行动的陪伴","不干预、给我空间"]],
  ["success","价值 / 成功", "16. 未来两年，哪一种成果最让你觉得值得？", ["做出真正有用的产品","获得更大的自由与选择权","成为某个领域的专家","建立稳定可靠的生活"]],
  ["sacrifice","价值 / 代价", "17. 为了一个长期目标，你最愿意承受什么代价？", ["短期收入不稳定","大量独处和投入","被误解或不确定","放弃一些其他机会"]],
  ["security","价值 / 安全感", "18. 钱、稳定和成长发生冲突时，你现在最在意？", ["可持续的收入","快速成长和能力积累","时间自主权","更大的影响力"]],
  ["meaning","价值 / 意义", "19. 什么会让你觉得一件事不值得继续？", ["没有真实用户或结果","不能让我学到新东西","不能按自己的方式做","长期消耗却没有回报"]],
  ["focus","当下 / 优先级", "20. 接下来三个月，你最想优先解决哪类问题？", ["明确自己的长期方向","让一个项目真正跑起来","改善关系或生活状态","建立更稳定的节奏"]]
];

async function request(url, options) { let response; try { response = await fetch(url, options); } catch (_) { throw Error("无法连接到 Heka 本地服务。请从 Heka 应用中重新打开。"); } const contentType = response.headers.get("content-type") || ""; if (!contentType.includes("application/json")) throw Error("当前网页没有连接到 Heka 后台。请从 Heka 应用中重新打开。"); const body = await response.json(); if (!response.ok) throw Error(body.error || "请求失败。"); return body; }
function renderQuestions() { q("#onboarding-questions").innerHTML = questions.map(([key, group, title, options]) => `<fieldset><legend><span>${group}</span>${title}</legend>${options.map((option) => `<label><input name="${key}" type="radio" value="${option}" required> ${option}</label>`).join("")}</fieldset>`).join(""); }
function displayName(name) { return String(name || "观察维度").replace(/_/g, " · "); }

function renderModel(model) {
  const area = q("#model-content"); const dimensions = Object.entries(model.confirmed_dimensions || {});
  q("#model-version").innerHTML = `<b>V${model.version || 0}</b><span>${dimensions.length} 个已确认维度</span>`;
  area.innerHTML = dimensions.length ? dimensions.map(([name, item]) => `<article class="model-dimension"><div><p class="dimension-name">${displayName(name)}</p><p class="dimension-scope">${item.scope}</p></div><div class="dimension-metrics"><span>观测强度 ${Math.round(item.value * 100)}</span><small>置信度 ${Math.round(item.confidence * 100)}%</small></div><div class="evidence-line"><b>依据</b><span>${(item.evidence || []).join("；")}</span></div></article>`).join("") : '<p class="empty">还没有被你确认的模型维度。</p>';
  const hypotheses = model.hypotheses || []; const section = q("#model-hypotheses"); const list = q("#hypotheses-list");
  section.hidden = !hypotheses.length;
  list.innerHTML = hypotheses.map((item) => `<article><b>${item.statement}</b><p>${item.scope || "待验证范围"}</p><small>下一步验证：${item.next_validation || "继续记录可比较的证据"}</small></article>`).join("");
  q("#current-model-note").textContent = model.history_note || "只包含你确认过、且仍可被反证的判断。";
}

function renderEvolution(events) { q("#evolution-list").innerHTML = events.length ? events.map((item) => `<article class="evolution-event"><p>${displayName(item.dimension)}：${Math.round(item.delta * 100)}%</p><p class="evolution-detail">依据 ${item.evidence.length} 条已确认案例 · ${item.scope}</p></article>`).join("") : '<p class="empty">还没有足够的跨时间证据。</p>'; }
function metric(label, value, detail) { return `<article class="validity-metric"><span>${label}</span><b>${value}</b><small>${detail}</small></article>`; }
function escapeHtml(text) { const node = document.createElement("span"); node.textContent = String(text || ""); return node.innerHTML; }
function renderValidity(validity) {
  q("#validity-title").textContent = validity.label || "Hypothesis Model";
  q("#validity-disclaimer").textContent = validity.disclaimer || "当前模型仍等待更多证据。";
  const metrics = validity.metrics || {};
  const fact = metrics.fact || {}; const pattern = metrics.pattern || {}; const prediction = metrics.prediction || {}; const intervention = metrics.intervention || {};
  q("#validity-metrics").innerHTML = [
    metric("事实准确度", fact.reviewed ? `${fact.correct}/${fact.reviewed}` : "尚无样本", fact.reviewed ? "你已校对的事实" : "先审阅一条 Trace 的事实"),
    metric("模式贴合度", pattern.rated ? `${pattern.average}/5` : "待评分", pattern.rated ? `${pattern.rated} 条主张由你评分` : "由你判断“像不像我”"),
    metric("预测准确度", prediction.reviewed ? `${prediction.correct}/${prediction.reviewed}` : "尚无到期预测", prediction.reviewed ? "已到期并回看的预测" : "先留下一条未来预测"),
    metric("行动帮助度", intervention.reviewed ? `${intervention.average}/5` : "尚无回访", intervention.reviewed ? `${intervention.reviewed} 个行动已回访` : "行动后再由你回访"),
  ].join("");
  const claims = validity.claims || [];
  q("#claims-list").innerHTML = claims.length ? claims.map((claim) => {
    const confirmation = claim.confirmation === "confirmed" ? "已由你确认" : "等待确认";
    const counter = claim.counter_evidence_count ? `<span class="counter">${claim.counter_evidence_count} 条反证</span>` : `<span>尚未出现反证</span>`;
    const active = claim.resonance ? `active` : "";
    return `<article class="claim-card"><div><h3>${escapeHtml(claim.statement)}</h3><p class="claim-scope">适用范围：${escapeHtml(claim.scope)}</p></div><div class="claim-confidence"><b>${Math.round(Number(claim.confidence || 0) * 100)}%</b><span>当前置信度 · ${confirmation}</span></div><div class="claim-evidence"><span>${claim.evidence_count} 条支持证据</span><span>${claim.source_diversity} 个独立 Trace</span>${counter}</div><div class="resonance"><span>这条描述像你吗？</span>${[1,2,3,4,5].map((value) => `<button class="${claim.resonance === value ? active : ""}" data-resonance="${value}" data-claim-id="${claim.id}" title="${value}/5">${value}</button>`).join("")}<span>${claim.resonance ? `已评 ${claim.resonance}/5` : "尚未评分"}</span></div></article>`;
  }).join("") : '<p class="empty">当前还没有已确认的模型主张。先审阅并确认一条 Trace，而不是急着建立人格结论。</p>';
  q("#claims-list").querySelectorAll("[data-resonance]").forEach((button) => button.onclick = async () => {
    try { await request(`/api/v1/model/claims/${button.dataset.claimId}/resonance`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({resonance:Number(button.dataset.resonance)})}); await refresh(); } catch (error) { alert(error.message); }
  });
  const predictions = validity.predictions || [];
  q("#prediction-list").innerHTML = predictions.length ? predictions.map((item) => `<article class="case-card"><span class="case-status">${item.status === "pending" ? "WAITING FOR REALITY" : "REVIEWED"}</span><b>${escapeHtml(item.statement)}</b><p>${escapeHtml(item.scope)} · 当前把握 ${Math.round(item.probability * 100)}% · ${item.due_date}</p>${item.status === "pending" ? `<div class="case-actions"><button data-prediction-yes="${item.id}">发生了</button><button data-prediction-no="${item.id}">没有发生</button></div>` : `<p>结果：${item.outcome ? "发生" : "没有发生"}${item.outcome_note ? ` · ${escapeHtml(item.outcome_note)}` : ""}</p>`}</article>`).join("") : '<p class="empty">还没有预测。只写下你愿意在未来核对的判断。</p>';
  q("#prediction-list").querySelectorAll("[data-prediction-yes],[data-prediction-no]").forEach((button) => button.onclick = () => reviewPrediction(button.dataset.predictionYes || button.dataset.predictionNo, Boolean(button.dataset.predictionYes)));
  const actions = validity.actions || [];
  q("#action-list").innerHTML = actions.length ? actions.slice(0, 4).map((item) => {
    const option = item.selected_option !== null && item.plan && item.plan.options ? item.plan.options[item.selected_option] : null;
    return `<article class="case-card"><span class="case-status">${item.status === "reviewed" ? "REVIEWED" : item.status === "selected" ? "IN PROGRESS" : "PROPOSED"}</span><b>${escapeHtml(item.problem)}</b><p>${option ? `已选：${escapeHtml(option.title)}` : "尚未选择行动方案"}</p>${item.status === "reviewed" ? `<div class="case-actions">${[1,2,3,4,5].map((value) => `<button data-helpfulness="${value}" data-action-id="${item.id}">${value}/5</button>`).join("")}</div><p>${item.helpfulness ? `你给出的帮助度：${item.helpfulness}/5` : "请给这次行动的帮助度评分"}</p>` : ""}</article>`;
  }).join("") : '<p class="empty">行动方案会在你确认问题后出现；Heka 不会凭空干预你。</p>';
  q("#action-list").querySelectorAll("[data-helpfulness]").forEach((button) => button.onclick = async () => { try { await request(`/api/v1/actions/${button.dataset.actionId}/helpfulness`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({helpfulness:Number(button.dataset.helpfulness)})}); await refresh(); } catch (error) { alert(error.message); } });
}
async function reviewPrediction(id, outcome) { const note = window.prompt("现实中实际发生了什么？可留空，但请尽量写下支持或推翻它的事实。") ?? ""; try { await request(`/api/v1/predictions/${id}/review`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({outcome, note})}); await refresh(); } catch (error) { alert(error.message); } }
function setPhase(report, model) {
  const confirmed = Number(model.version || 0) > 0; const hasReport = Boolean(report);
  q("#onboarding-panel").hidden = hasReport; q("#migration-panel").hidden = !hasReport || confirmed; q("#model-dashboard").hidden = !confirmed;
  if (!hasReport) { q("#model-kicker").textContent = "03 / FIRST INPUT"; q("#model-title").textContent = "先提供一份主动自述。"; q("#model-description").textContent = "它只是 Heka 的观察起点，不是人格测试；之后仍由真实 Trace 来证实、修正或推翻。"; q("#model-runtime").textContent = "第 1 步 / 主动自述"; return; }
  if (!confirmed) { q("#model-kicker").textContent = "03 / REVIEW A STARTING POINT"; q("#model-title").textContent = "现在把材料变成候选起点。"; q("#model-description").textContent = "生成的只是受范围限制的工作假设。你审阅并确认后，Heka 才会建立第一个模型版本。"; q("#model-runtime").textContent = "第 2 步 / 审阅候选起点"; return; }
  q("#model-kicker").textContent = "03 / CONFIRMED WORKING MODEL"; q("#model-title").textContent = "这是你当前确认过的理解。"; q("#model-description").textContent = "它不是人格结论，而是一组有证据、范围和反证条件的工作假设。"; q("#model-runtime").textContent = `当前版本 V${model.version} · 等待新证据`; }

async function refresh() { const [model, events, report, validity] = await Promise.all([request("/api/v1/model"), request("/api/v1/evolution"), request("/api/v1/onboarding"), request("/api/v1/model/validity")]); setPhase(report, model); renderModel(model); renderEvolution(events); renderValidity(validity); }
q("#onboarding-form").onsubmit = async (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); const answers = Object.fromEntries(questions.map(([key]) => [key, form.get(key)])); answers.mbti = form.get("mbti") || ""; answers.current_focus = form.get("current_focus") || ""; const feedback = q("#onboarding-feedback"); try { await request("/api/v1/onboarding", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({answers})}); feedback.textContent = "已保存。下一步是审阅候选起点，而不是立刻给你下结论。"; refresh(); } catch (error) { feedback.textContent = error.message; } };
q("#evolution-check").onclick = async () => { renderEvolution((await request("/api/v1/evolution/review", {method:"POST", headers:{"Content-Type":"application/json"}, body:'{"days":90}'})).events); };
q("#build-seed").onclick = async () => { const feedback = q("#seed-feedback"); const preview = q("#seed-preview"); try { feedback.textContent = "本地模型正在整理初始自述与近期 Trace…"; const result = await request("/api/v1/model/bootstrap", {method:"POST", headers:{"Content-Type":"application/json"}, body:"{}"}); const seed = result.seed; preview.innerHTML = `<div class="seed-preview"><p class="eyebrow">${result.source_count} 条本地 Trace + 初始自述</p><p>${seed.boundary}</p>${seed.dimensions.map((item) => `<article><b>${displayName(item.name)}</b><span>观测强度 ${Math.round(item.value * 100)} · 置信度 ${Math.round(item.confidence * 100)}%</span><small>${item.scope} · ${(item.evidence || []).join("；")}</small></article>`).join("")}<button id="confirm-seed" class="primary">确认这份模型起点 <b>→</b></button></div>`; q("#confirm-seed").onclick = async () => { const confirmed = await request("/api/v1/model/bootstrap/confirm", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({seed})}); feedback.textContent = confirmed.message; preview.innerHTML = ""; refresh(); }; feedback.textContent = "这是候选起点：请先看范围和依据，再决定是否确认。"; } catch (error) { feedback.textContent = error.message; } };
q("#new-prediction").onclick = () => { const dialog = q("#prediction-dialog"); const due = new Date(); due.setDate(due.getDate() + 30); q("#prediction-due-date").value = due.toISOString().slice(0, 10); q("#prediction-feedback").textContent = ""; dialog.showModal(); };
q("#prediction-dialog .dialog-close").onclick = () => q("#prediction-dialog").close();
q("#prediction-form").onsubmit = async (event) => { event.preventDefault(); const feedback = q("#prediction-feedback"); try { await request("/api/v1/predictions", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({statement:q("#prediction-statement").value,scope:q("#prediction-scope").value,probability:Number(q("#prediction-probability").value)/100,due_date:q("#prediction-due-date").value})}); q("#prediction-dialog").close(); event.currentTarget.reset(); await refresh(); } catch (error) { feedback.textContent = error.message; } };
if (location.protocol === "file:") q("#server-warning").hidden = false;
renderQuestions(); refresh();
