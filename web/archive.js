const $ = (selector) => document.querySelector(selector);
async function api(url, options) { const response = await fetch(url, options); const body = await response.json(); if (!response.ok) throw new Error(body.error || "请求没有完成。"); return body; }
async function load() { const status = await api("/api/v1/obsidian/status"); $("#obsidian-status").textContent = status.configured ? `已配置每日资料目录 · 已导入 ${status.imported_count} 份来源` : "尚未配置。请在本地 .env 填写 HEKA_OBSIDIAN_DAILY_DIR。"; }
$("#sync-obsidian").onclick = async () => { const feedback = $("#sync-feedback"); try { feedback.textContent = "正在仅从本地目录同步…"; const result = await api("/api/v1/obsidian/sync", {method:"POST", headers:{"Content-Type":"application/json"}, body:"{}"}); feedback.textContent = `已同步：新增 ${result.imported || 0}，跳过 ${result.skipped || 0}。`; load(); } catch (error) { feedback.textContent = error.message; } };
load().catch((error) => { $("#obsidian-status").textContent = error.message; });
