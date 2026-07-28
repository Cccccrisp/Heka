const pendingList = document.querySelector('#pending-list');
const proposalCount = document.querySelector('#proposal-count');
const modelContent = document.querySelector('#model-content');
const record = document.querySelector('#record');
const capture = document.querySelector('#capture');
const feedback = document.querySelector('#capture-feedback');
const runtime = document.querySelector('#runtime');
const question = document.querySelector('#question');
const askButton = document.querySelector('#ask-button');
const answer = document.querySelector('#answer');
const evolutionList = document.querySelector('#evolution-list');
const evolutionCheck = document.querySelector('#evolution-check');
const obsidianSync = document.querySelector('#obsidian-sync');
const obsidianStatus = document.querySelector('#obsidian-status');
const obsidianLabel = document.querySelector('#obsidian-label');
const calibrationStatus = document.querySelector('#calibration-status');
const saveCalibration = document.querySelector('#save-calibration');
const actionProblem = document.querySelector('#action-problem');
const actionGenerate = document.querySelector('#action-generate');
const actionList = document.querySelector('#action-list');
const actionConfirm = document.querySelector('#action-confirm');

async function request(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || '请求没有完成。');
  return body;
}

function asText(items) { return Array.isArray(items) ? items.map(item => typeof item === 'string' ? item : item.statement).join('；') : '—'; }
function excerpt(text, limit = 140) { return text.length > limit ? `${text.slice(0, limit)}…` : text; }

function renderPending(items) {
  pendingList.innerHTML = '';
  proposalCount.textContent = items.length;
  if (!items.length) { pendingList.innerHTML = '<p class="empty">还没有待确认的提案。<br>写下一条真实记录，Heka 会先把它留在观察层。</p>'; return; }
  const template = document.querySelector('#proposal-template');
  items.forEach(item => {
    const node = template.content.cloneNode(true);
    node.querySelector('.proposal-record').textContent = item.source_title ? `来自 Obsidian · ${item.source_title}` : excerpt(item.raw_text);
    node.querySelector('.facts').textContent = asText(item.trace.observable_facts);
    node.querySelector('.interpretations').textContent = asText(item.trace.candidate_interpretations);
    node.querySelector('.proposal-reason').textContent = item.payload.kind === 'no_change' ? '本次不建议改变模型。' : item.payload.reason;
    node.querySelector('.accept').addEventListener('click', () => review(item.id, 'accept'));
    node.querySelector('.reject').addEventListener('click', () => review(item.id, 'reject'));
    pendingList.append(node);
  });
}

function renderModel(model) {
  modelContent.innerHTML = '';
  const dimensions = Object.entries(model.confirmed_dimensions || {});
  const hypotheses = model.hypotheses || [];
  if (!dimensions.length && !hypotheses.length) { modelContent.innerHTML = '<p class="empty">模型仍是空白的。<br>这不是缺失，而是它还没有获得你的确认。</p>'; return; }
  dimensions.forEach(([key, value]) => {
    const item = document.createElement('article'); item.className = 'dimension';
    item.innerHTML = `<h3>${key}</h3><p>${Math.round(value.value * 100)}% <small>· 置信度 ${Math.round(value.confidence * 100)}%</small></p>`;
    modelContent.append(item);
  });
  hypotheses.forEach(value => {
    const item = document.createElement('article'); item.className = 'hypothesis';
    item.innerHTML = `<h3>待验证假设</h3><p>${value.statement}<br><small>下一次验证：${value.next_validation}</small></p>`;
    modelContent.append(item);
  });
}

const dimensionLabels = {information_sufficiency: '信息充分度', risk_preference: '风险偏好', exploration: '探索倾向', execution: '执行投入'};
function labelFor(dimension) { return dimensionLabels[dimension] || dimension.replaceAll('_', ' '); }
function renderEvolution(items) {
  evolutionList.innerHTML = '';
  if (!items.length) { evolutionList.innerHTML = '<p class="empty">还没有足够的已确认、跨时间证据。<br>这表示 Heka 暂时不会把短期波动说成变化。</p>'; return; }
  const template = document.querySelector('#evolution-template');
  items.forEach(item => {
    const node = template.content.cloneNode(true);
    const direction = item.delta > 0 ? '上升' : '下降';
    node.querySelector('.evolution-title').textContent = `在「${item.scope}」中，${labelFor(item.dimension)}可能${direction}了 ${Math.round(Math.abs(item.delta) * 100)}%。`;
    node.querySelector('.evolution-detail').textContent = `依据：${item.evidence.length} 条已确认案例，起点 ${Math.round(item.previous_value * 100)}%，当前 ${Math.round(item.current_value * 100)}%。`;
    node.querySelector('.evolution-counter').textContent = item.counter_evidence.length ? `反证：${item.counter_evidence.length} 条被你否决的相关提案，确认前请一并考虑。` : '暂未发现被你否决的同维度提案。';
    const actions = node.querySelector('.evolution-actions');
    if (item.status === 'proposed') {
      node.querySelector('.evolution-confirm').addEventListener('click', () => reviewEvolution(item.id, 'confirm'));
      node.querySelector('.evolution-reject').addEventListener('click', () => reviewEvolution(item.id, 'reject'));
    } else {
      actions.textContent = item.status === 'confirmed' ? '你已确认这段变化。' : '你认为这不足以说明变化。';
    }
    evolutionList.append(node);
  });
}
function renderActions(cases) {
  actionList.innerHTML = '';
  cases.forEach(item => {
    const card = document.createElement('article'); card.className = 'action-case';
    card.innerHTML = `<h3>问题：${item.problem}</h3><p>${item.plan.problem_frame || '这是待验证的问题框定。'}</p>`;
    const options = document.createElement('div'); options.className='action-options';
    (item.plan.options || []).forEach((option,index) => {
      const box=document.createElement('article'); box.className='action-option';
      box.innerHTML=`<strong>${option.title}</strong><p>${option.action}</p><p>信号：${option.success_signal}</p><p>反证：${option.disconfirming_signal}</p><p>复盘：${option.review_after}</p>`;
      if (item.status === 'proposed') { const button=document.createElement('button');button.className='quiet';button.textContent='选择这个方案';button.onclick=()=>selectAction(item.id,index);box.append(button); }
      else if (item.selected_option === index && item.status === 'selected') { const review=document.createElement('button');review.className='quiet';review.textContent='记录这次结果';review.onclick=()=>reviewAction(item.id);box.append(review); }
      else if (item.selected_option === index) box.innerHTML += `<p><b>已复盘：</b>${item.result_note || '已记录'}</p>`;
      options.append(box);
    }); card.append(options); actionList.append(card);
  });
}

async function load() {
  try {
    const [pending, model, runtimeInfo, evolution, obsidian, onboarding, actions] = await Promise.all([request('/api/pending'), request('/api/model'), request('/api/runtime'), request('/api/evolution'), request('/api/obsidian/status'), request('/api/onboarding'), request('/api/actions')]);
    renderPending(pending); renderModel(model); renderEvolution(evolution);
    runtime.textContent = `本地整理 · ${runtimeInfo.local_model} / 云端判断 · ${runtimeInfo.cloud_model}`;
    obsidianLabel.textContent = obsidian.label;
    obsidianSync.disabled = !obsidian.configured;
    obsidianStatus.textContent = obsidian.configured ? `已接入 ${obsidian.imported_count} 条原始记录` : '需要先设置本地资料目录';
    if (onboarding) { calibrationStatus.textContent = '已保存为初始自述；等待真实证据校准'; document.querySelectorAll('[data-calibration]').forEach(input => { input.value = onboarding.answers[input.dataset.calibration] || ''; }); }
    renderActions(actions);
  }
  catch (error) { feedback.textContent = error.message; }
}
async function generateAction() { const problem=actionProblem.value.trim(); if(problem.length<12||!actionConfirm.checked){feedback.textContent='写下具体问题，并确认这是你希望处理的事。';return;} actionGenerate.disabled=true;actionGenerate.textContent='正在提出…';try{await request('/api/actions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({problem,confirmed:true})});actionProblem.value='';actionConfirm.checked=false;await load();}catch(error){feedback.textContent=error.message;}finally{actionGenerate.disabled=false;actionGenerate.textContent='提出方案';}}
async function selectAction(caseId,optionIndex){try{const result=await request(`/api/actions/${caseId}/select`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({option_index:optionIndex})});feedback.textContent=result.message;await load();}catch(error){feedback.textContent=error.message;}}
async function reviewAction(caseId){const resultNote=window.prompt('这次行动后，真实发生了什么？什么支持或推翻了原判断？');if(!resultNote)return;try{const result=await request(`/api/actions/${caseId}/review`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({result_note:resultNote})});feedback.textContent=result.message;await load();}catch(error){feedback.textContent=error.message;}}
async function saveInitialCalibration() {
  const answers = Object.fromEntries([...document.querySelectorAll('[data-calibration]')].map(input => [input.dataset.calibration, input.value]));
  if (Object.values(answers).some(value => !value)) { calibrationStatus.textContent = '请先完成五个选择。'; return; }
  saveCalibration.disabled = true;
  try { const result = await request('/api/onboarding', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({answers})}); calibrationStatus.textContent = result.message; }
  catch (error) { calibrationStatus.textContent = error.message; }
  finally { saveCalibration.disabled = false; }
}
async function syncObsidian() {
  obsidianSync.disabled = true; obsidianSync.textContent = '正在同步…'; feedback.textContent = '';
  try {
    const result = await request('/api/obsidian/sync', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    feedback.textContent = result.imported.length ? `已同步 ${result.imported.length} 条新记录；它们正在等待你的判断。` : '没有发现新增或修改的每日记录。';
    await load();
  }
  catch (error) { feedback.textContent = error.message; }
  finally { obsidianSync.textContent = '同步 Obsidian'; if (obsidianLabel.textContent !== '未设置资料目录') obsidianSync.disabled = false; }
}
async function runEvolution() {
  evolutionCheck.disabled = true; evolutionCheck.textContent = '正在检查…';
  try { const result = await request('/api/evolution/review', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({days:90})}); renderEvolution(result.events); }
  catch (error) { feedback.textContent = error.message; }
  finally { evolutionCheck.disabled = false; evolutionCheck.textContent = '检查最近 90 天'; }
}
async function reviewEvolution(id, decision) {
  try { await request(`/api/evolution/${id}/review`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision})}); await load(); }
  catch (error) { feedback.textContent = error.message; }
}
async function review(id, decision) {
  try { const result = await request(`/api/proposals/${id}/review`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision})}); feedback.textContent = result.message; await load(); }
  catch (error) { feedback.textContent = error.message; }
}
capture.addEventListener('click', async () => {
  const text = record.value.trim(); if (!text) { feedback.textContent = '请先写下一条真实记录。'; record.focus(); return; }
  capture.disabled = true; capture.textContent = '正在观察…'; feedback.textContent = '';
  try { const result = await request('/api/capture', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})}); record.value = ''; feedback.textContent = `已经形成待确认提案 #${result.proposal_id}。它还没有改变模型。`; await load(); }
  catch (error) { feedback.textContent = error.message; }
  finally { capture.disabled = false; capture.textContent = '生成观察'; }
});
askButton.addEventListener('click', async () => {
  const text = question.value.trim(); if (!text) { feedback.textContent = '请先写下你想判断的问题。'; question.focus(); return; }
  askButton.disabled = true; askButton.textContent = '正在综合…'; answer.classList.remove('visible');
  try { const result = await request('/api/ask', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:text})}); answer.textContent = result.answer; answer.classList.add('visible'); }
  catch (error) { feedback.textContent = error.message; }
  finally { askButton.disabled = false; askButton.textContent = '生成判断'; }
});
evolutionCheck.addEventListener('click', runEvolution);
obsidianSync.addEventListener('click', syncObsidian);
saveCalibration.addEventListener('click', saveInitialCalibration);
actionGenerate.addEventListener('click', generateAction);
load();
