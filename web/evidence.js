const q = (selector) => document.querySelector(selector);
async function request(url, options) { const response = await fetch(url, options); const body = await response.json(); if (!response.ok) throw Error(body.error || "请求失败。"); return body; }
async function load() {
  const proposals = await request('/api/v1/pending'); q('#proposal-count').textContent = proposals.length; const list = q('#pending-list'); list.innerHTML = '';
  if (!proposals.length) { list.innerHTML = '<p class="empty">没有待审阅的提案。</p>'; return; }
  proposals.forEach((item) => { const node = q('#proposal-template').content.cloneNode(true); node.querySelector('.proposal-record').textContent = item.source_title ? `来自资料 · ${item.source_title}` : item.raw_text.slice(0, 140); node.querySelector('.facts').textContent = item.trace.observable_facts.map((fact) => fact.statement).join('；'); node.querySelector('.interpretations').textContent = item.trace.candidate_interpretations.map((interpretation) => interpretation.statement).join('；'); node.querySelector('.proposal-reason').textContent = item.payload.reason; node.querySelector('.accept').onclick = () => review(item.id, 'accept'); node.querySelector('.reject').onclick = () => review(item.id, 'reject'); list.append(node); });
}
async function review(id, decision) { await request(`/api/v1/proposals/${id}/review`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({decision})}); load(); }
load();
