const $ = (selector) => document.querySelector(selector);

async function api(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "请求没有完成。");
  return body;
}

function renderCase(item) {
  const plan = item.plan || {};
  const options = (plan.options || []).map((option, index) => {
    const selected = item.selected_option === index;
    return `<div class="case-option"><b>${option.title || `方案 ${index + 1}`}${selected ? " · 已选择" : ""}</b><span>${option.action || ""}</span>${item.selected_option == null ? `<button class="quiet" data-case="${item.id}" data-option="${index}">选择此方案</button>` : ""}</div>`;
  }).join("");
  return `<article class="case"><p class="case-meta">${item.status || "proposed"}</p><h3>${item.problem}</h3><p>${plan.problem_frame || "等待行动框架。"}</p><div class="case-options">${options}</div>${item.selected_option != null && !item.result_note ? `<button class="quiet review" data-review="${item.id}">记录真实结果</button>` : ""}${item.result_note ? `<p>复盘：${item.result_note}</p>` : ""}</article>`;
}

async function load() {
  const [runtime, cases] = await Promise.all([api("/api/v1/runtime"), api("/api/v1/actions")]);
  $("#runtime").textContent = `本地 ${runtime.local_model} · 云端 ${runtime.cloud_model}`;
  $("#action-list").innerHTML = cases.length ? cases.map(renderCase).join("") : '<p class="empty">你还没有启动一个问题实验。</p>';
  document.querySelectorAll("[data-case]").forEach((button) => button.onclick = async () => {
    await api(`/api/v1/actions/${button.dataset.case}/select`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({option_index:Number(button.dataset.option)})});
    load();
  });
  document.querySelectorAll("[data-review]").forEach((button) => button.onclick = async () => {
    const result = window.prompt("这次行动发生了什么？也可以写下反证。");
    if (!result) return;
    await api(`/api/v1/actions/${button.dataset.review}/review`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({result_note:result})});
    load();
  });
}

$("#generate-actions").onclick = async () => {
  const problem = $("#problem").value.trim();
  const feedback = $("#feedback");
  try {
    feedback.textContent = "正在用有限证据生成方案…";
    const result = await api("/api/v1/actions", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({problem, confirmed:$("#confirm-problem").checked})});
    feedback.textContent = `方案已建立 #${result.case_id}。请选择一个可复盘的选项。`;
    $("#problem").value = "";
    load();
  } catch (error) { feedback.textContent = error.message; }
};
load().catch((error) => { $("#runtime").textContent = error.message; });
