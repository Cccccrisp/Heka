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
async function request(url, options) { let response; try { response = await fetch(url, options); } catch (_) { throw Error("无法连接到 Heka 本地服务。请双击“启动 Heka.command”后，从它自动打开的页面进入。"); } const contentType = response.headers.get('content-type') || ''; if (!contentType.includes('application/json')) { throw Error("当前网页没有连接到 Heka 后台。请关闭这个标签页，双击“启动 Heka.command”，并使用它自动打开的新页面。"); } const body = await response.json(); if (!response.ok) throw Error(body.error || "请求失败。"); return body; }
function renderQuestions() { q('#onboarding-questions').innerHTML = questions.map(([key, group, title, options]) => `<fieldset><legend><span>${group}</span>${title}</legend>${options.map((option) => `<label><input name="${key}" type="radio" value="${option}" required> ${option}</label>`).join('')}</fieldset>`).join(''); }
function renderModel(model) { const area=q('#model-content'); const dimensions=Object.entries(model.confirmed_dimensions||{}); area.innerHTML=dimensions.length ? dimensions.map(([name,item])=>`<article class="dimension"><h3>${name}</h3><p>${Math.round(item.value*100)}% · 置信度 ${Math.round(item.confidence*100)}%</p><p>${item.scope}</p></article>`).join('') : '<p class="empty">模型仍是空白的。先完成初始自述，再建立一个由你确认的起点。</p>'; }
function renderEvolution(events) { q('#evolution-list').innerHTML=events.length ? events.map((item)=>`<article class="evolution-event"><p>${item.dimension}：${Math.round(item.delta*100)}%</p><p class="evolution-detail">依据 ${item.evidence.length} 条已确认案例</p></article>`).join('') : '<p class="empty">还没有足够的跨时间证据。</p>'; }
async function refresh() { const [model, events, report]=await Promise.all([request('/api/v1/model'),request('/api/v1/evolution'),request('/api/v1/onboarding')]); renderModel(model); q('#onboarding-panel').hidden=Boolean(report); q('#migration-panel').hidden=!report; renderEvolution(events); }
q('#onboarding-form').onsubmit=async(event)=>{ event.preventDefault(); const form=new FormData(event.currentTarget); const answers=Object.fromEntries(questions.map(([key])=>[key,form.get(key)])); answers.mbti=form.get('mbti')||''; answers.current_focus=form.get('current_focus')||''; const feedback=q('#onboarding-feedback'); try { await request('/api/v1/onboarding',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({answers})}); feedback.textContent='已保存。现在可以用本周 Trace 建立初始模型。'; refresh(); } catch(error) { feedback.textContent=error.message; } };
q('#evolution-check').onclick=async()=>{ renderEvolution((await request('/api/v1/evolution/review',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"days":90}'})).events); };
q('#build-seed').onclick=async()=>{ const feedback=q('#seed-feedback'); const preview=q('#seed-preview'); try { feedback.textContent='本地模型正在整理初始自述与本周 Trace…'; const result=await request('/api/v1/model/bootstrap',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}); const seed=result.seed; preview.innerHTML=`<div class="seed-preview"><p class="eyebrow">初始自述 + ${result.source_count} 条本地 Trace</p><p>${seed.boundary}</p>${seed.dimensions.map((item)=>`<article><b>${item.name} · ${Math.round(item.value*100)}%</b><span>${item.scope}</span><small>${item.evidence.join('；')}</small></article>`).join('')}<button id="confirm-seed" class="primary">确认写入我的当前模型 <b>→</b></button></div>`; q('#confirm-seed').onclick=async()=>{ const confirmed=await request('/api/v1/model/bootstrap/confirm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({seed})}); feedback.textContent=confirmed.message; preview.innerHTML=''; refresh(); }; feedback.textContent='这是候选初始模型；确认后才进入版本历史。'; } catch(error) { feedback.textContent=error.message; } };
if (location.protocol === "file:") q('#server-warning').hidden = false;
renderQuestions(); refresh();
