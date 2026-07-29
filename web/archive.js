const $ = (selector) => document.querySelector(selector);

async function api(url, options) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) throw new Error("当前页面没有连接到 Heka 后台。请从 Heka 应用中重新打开。");
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "请求没有完成。");
  return body;
}

function openDialog(id) { $("#" + id).showModal(); }
function closeDialog(id) { $("#" + id).close(); }

async function load() {
  const [status, settings] = await Promise.all([api("/api/v1/obsidian/status"), api("/api/v1/settings/model")]);
  $("#obsidian-status").textContent = status.configured ? `已配置每日资料目录 · 已导入 ${status.imported_count} 份来源` : "尚未配置。可以只用 Heka 直接记录；Obsidian 不是必需的。";
  $("#local-base-url").value = settings.local.base_url;
  $("#local-model").value = settings.local.model;
  $("#cloud-base-url").value = settings.cloud.base_url;
  $("#cloud-model").value = settings.cloud.model;
  $("#cloud-api-key").placeholder = settings.cloud.api_key_configured ? "已保存；留空则保持不变" : "例如：你的 API Key";
}

$("#sync-obsidian").onclick = async () => {
  const feedback = $("#sync-feedback");
  try {
    feedback.textContent = "正在仅从本地目录同步…";
    const result = await api("/api/v1/obsidian/sync", {method:"POST", headers:{"Content-Type":"application/json"}, body:"{}"});
    feedback.textContent = `已同步：新增 ${result.imported || 0}，跳过 ${result.skipped || 0}。`;
    load();
  } catch (error) { feedback.textContent = error.message; }
};

$("#open-model-settings").onclick = () => openDialog("model-settings");
$("#open-data-boundary").onclick = () => openDialog("data-boundary");
document.querySelectorAll("[data-close]").forEach((button) => { button.onclick = () => closeDialog(button.dataset.close); });

$("#model-settings-form").onsubmit = async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget); const feedback = $("#model-settings-feedback");
  const submit = event.currentTarget.querySelector("button[type=submit]"); submit.disabled = true;
  try {
    const result = await api("/api/v1/settings/model", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({
      local: {base_url:form.get("local_base_url"), model:form.get("local_model")},
      cloud: {base_url:form.get("cloud_base_url"), model:form.get("cloud_model"), api_key:form.get("cloud_api_key"), clear_api_key:form.get("clear_cloud_key") === "on"},
    })});
    feedback.textContent = result.message;
    $("#cloud-api-key").value = ""; $("#clear-cloud-key").checked = false;
    await load();
  } catch (error) { feedback.textContent = error.message; }
  finally { submit.disabled = false; }
};

load().catch((error) => { $("#obsidian-status").textContent = error.message; });
