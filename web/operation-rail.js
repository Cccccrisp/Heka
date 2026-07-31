(() => {
  const rail = document.querySelector('.shared-operation-rail');
  if (!rail) return;
  const escape = (value) => String(value || '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
  const activeProjectId = Number(sessionStorage.getItem('heka.activeProjectId') || 0) || null;
  const activeConversationId = Number(sessionStorage.getItem('heka.activeConversationId') || 0) || null;
  const openTalk = () => { location.href = 'index.html'; };
  rail.querySelector('[data-rail-inbox]').classList.toggle('active', !activeProjectId);
  async function request(url) { const response = await fetch(url); const body = await response.json(); if (!response.ok) throw Error(body.error || '无法读取本地资料。'); return body; }
  async function load() {
    const [projects, conversations] = await Promise.all([request('/api/v1/projects'), request(`/api/v1/conversations${activeProjectId ? `?project_id=${activeProjectId}` : ''}`)]);
    const projectList = rail.querySelector('[data-rail-projects]');
    const conversationList = rail.querySelector('[data-rail-conversations]');
    projectList.innerHTML = projects.map((project) => `<button class="project-item ${activeProjectId === project.id ? 'active' : ''}" data-project-id="${project.id}"><span class="project-mark">◇</span><span><b>${escape(project.title)}</b><small>${project.trace_count} 条 Trace · ${project.conversation_count} 段对话</small></span></button>`).join('') || '<p class="empty-list">还没有长期项目。</p>';
    conversationList.innerHTML = conversations.map((item) => `<button class="conversation-item ${activeConversationId === item.id ? 'active' : ''}" data-conversation-id="${item.id}"><b>${escape(item.title)}</b><small>${new Date(item.updated_at).toLocaleDateString('zh-CN',{month:'numeric',day:'numeric'})}</small></button>`).join('') || '<p class="empty-list">这里还没有对话。</p>';
    rail.querySelectorAll('[data-project-id]').forEach((button) => button.onclick = () => { sessionStorage.setItem('heka.activeProjectId', button.dataset.projectId); sessionStorage.removeItem('heka.activeConversationId'); openTalk(); });
    rail.querySelectorAll('[data-conversation-id]').forEach((button) => button.onclick = () => { sessionStorage.setItem('heka.activeConversationId', button.dataset.conversationId); openTalk(); });
  }
  rail.querySelector('[data-rail-inbox]').onclick = () => { sessionStorage.removeItem('heka.activeProjectId'); sessionStorage.removeItem('heka.activeConversationId'); openTalk(); };
  load().catch((error) => { rail.querySelector('[data-rail-projects]').innerHTML = `<p class="empty-list">${escape(error.message)}</p>`; });
})();
