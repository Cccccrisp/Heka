# Heka Measurement Protocol v0.1

> 数字不是对人的“真实分数”。它们是当前证据下、可追溯且可反驳的工作参数。

Heka 中所有数字必须回答四个问题：**它代表什么？来自哪里？如何更新？何时失效？**

## 1. 三种数字，不混用

| 数字 | 含义 | 例子 | 是否与其他项相加为 1 |
| --- | --- | --- | --- |
| `weight` | 在同一取舍中，一个因素的相对重要性 | 成长 0.34、收入 0.27 | 是 |
| `evidence_count` | 支持或反驳该条目的有效证据量 | 2.8 条有效支持、0.9 条有效反证 | 否 |
| `confidence` | 当前结论值得暂时相信到什么程度 | 0.58 | 否 |

禁止把 MBTI、情绪强度、目标权重和置信度混成同一种“分数”。

## 2. 每一条证据如何计数

每条记录不会机械地算作 `1`。它先转换为有效证据量：

```text
effective_evidence = source × clarity × context_match × freshness
```

所有因子在 `0–1`：

| 因子 | 规则 |
| --- | --- |
| `source` | 用户明确确认 1.00；真实选择且记录理由 0.90；事后自述 0.65；模型推断 0.30 |
| `clarity` | 明确说出取舍 / 原因 1.00；只知道结果 0.70；语义模糊 0.40 |
| `context_match` | 同一类场景 1.00；相近场景 0.65；跨领域类比 0.35 |
| `freshness` | `2^(-days / half_life)`，随时间衰减 |

半衰期按对象不同：

| 对象 | 半衰期 |
| --- | --- |
| 当前状态、压力、精力 | 30 天 |
| 决策偏好 | 90 天 |
| 目标与价值排序 | 180 天 |
| 行动介入偏好 | 120 天 |
| MBTI / 自我标签 | 不衰减，但永远只作为自述，不转成行为结论 |

正向证据加到 `support`，反向证据加到 `counter_evidence`。同一事件不得同时为同一结论贡献两次。

## 2.1 原始 Trace 的存储粒度

原始记录不会只存成一块模型 JSON。一次处理会拆为：`entries`（原文）→ `traces`（处理批次）→ `trace_events`（事件）→ `trace_facts`（可核验事实）→ `trace_tags`（分类）→ `trace_interpretations`（候选解释）→ `trace_decisions` / `trace_decision_options`（决策与选项）→ `trace_actions`（行动）→ `trace_emotions`（情绪）→ `proposals`（待确认更新）。完整 JSON 同时保留在 `traces.payload` 作为审计副本。

候选解释、情绪和决策结构均来自模型整理，不能覆盖原文；每一项都保留关联事实或原文摘录。没有明确决策、行动或情绪时，表中不会制造一条空记录。

## 3. 初始设置如何变成初始权重

初始设置只提供**弱先验**，全部目标合计等价于 6 条有效证据；它不能把任何结论的置信度推高到 `0.55` 以上。

### 3.1 目标权重

用户先在 6 个目标间分配 12 枚筹码，再做 4 个具体情境选择。

```text
prior(goal) = 0.5 + chips(goal) / 4
scenario_support(goal) = Σ effective_evidence of selected scenario reasons
raw(goal) = prior(goal) + scenario_support(goal)
weight(goal) = raw(goal) / Σ raw(all_goals)
```

目标池固定为：`income`、`growth`、`autonomy`、`stability`、`creation_impact`、`relationship_health`。

“不能接受”的内容不是目标权重，而是 `constraint`。例如现金流下限、健康底线、不可接受的工作模式，进入决策模型的硬约束，不参与归一化。

### 3.2 决策因素权重

每一个真实选择记录为一个 `decision_case`：

```text
选择是什么？
有哪些选项？
你最后选了什么？
你最在意的两个理由是什么？
什么条件改变会让你改选？
结果怎样？
```

理由只能从可解释的因素中选择，也可补充：

`cash_flow`、`skill_compounding`、`autonomy`、`reversibility`、`feedback_speed`、`certainty`、`time_cost`、`relationship_impact`。

对每个因素：

```text
factor_score = prior + support - counter_evidence
factor_weight = max(0, factor_score) / Σ max(0, all_factor_scores)
```

只有累计 `3` 个以上相近决策案例后，才向用户展示“你在这类场景中更重视 X”；否则只能说“初始倾向”。

### 3.3 MBTI 和自由描述

MBTI 不参与任何权重计算。它被保存为：

```json
{
  "type": "self_description",
  "label": "INTP",
  "source": "onboarding",
  "confidence": 0.2,
  "status": "unvalidated"
}
```

它的作用是帮助 Heka 选择更自然的提问方式和生成候选假设；它不能推出“因此你风险偏好低”一类结论。

自由描述同样是 `self_report`，先进入待验证叙述，不直接改变目标或决策权重。

## 4. 置信度如何计算

置信度不是权重。它衡量“该条结论是否有足够、稳定且不矛盾的证据”。

```text
coverage = 1 - exp(-(prior_evidence + support + counter_evidence) / 5)
agreement = (prior_evidence + support) / (prior_evidence + support + counter_evidence + 1)
confidence = min(cap, coverage × (0.5 + 0.5 × agreement))
```

其中：

- `cap = 0.55`：只来自初始设置或一次记录；
- `cap = 0.75`：至少 3 个相近真实选择，且有明确理由；
- `cap = 0.90`：至少 5 个跨时间案例，且出现结果回写；
- 反证增加时，`agreement` 降低，置信度立即下降；
- 每个结论都必须记录 `scope`，例如“在职业机会判断中”，不能泛化成全人格。

`prior_evidence` 只来自用户亲自完成的初始设置；它与后续真实行为证据分开存储，便于在足够行为出现后逐渐降低初始自述的影响。

## 5. 七层分别计量什么

| 层 | 计量对象 | 主要数字 | 更新依据 |
| --- | --- | --- | --- |
| 观察 | 记录是否完整、事实是否可核验 | completeness、source | 原始输入与用户修正 |
| 解释 | 候选解释是否站得住 | support、counter、confidence | 追问、反例、结果 |
| 信念与目标图 | 目标优先级、信念间支持/冲突 | goal_weight、edge_strength | 筹码、情境选择、真实取舍 |
| 自我模型 | 当前自述与已显现模式 | confidence、scope、status | 用户确认与跨日行为 |
| 决策模型 | 场景中的取舍因素 | factor_weight、constraint | decision_case 与结果回写 |
| 行动层 | 希望如何被介入，以及介入是否有效 | preference、helpfulness_rate | 设置、采纳/跳过、评分 |
| 演化模型 | 某模式是否真正变化 | delta、trend_confidence | 两个时间窗的有效证据差 |

## 6. 行动层的效果也要计数

用户选择“关键选择时提问”是一项偏好，不是人格结论。

```text
helpfulness_rate = helpful_actions / rated_actions
adoption_rate = completed_experiments / proposed_experiments
```

若连续 5 次被跳过，Heka 应降低该介入方式的优先级，而不是重复提醒。

## 7. 演化：什么才算真正变化

演化层比较两个时间窗，而不是比较两次聊天。

```text
delta = recent_weight - baseline_weight
trend_confidence = min(recent_confidence, baseline_confidence)
```

只有同时满足以下条件，才标记“变化”：

1. `abs(delta) >= 0.12`；
2. 最近窗口至少有 3 条有效证据；
3. `trend_confidence >= 0.60`；
4. 至少有一条结果回写或用户确认。

否则只标记为“短期波动”或“待验证变化”。

### 7.1 Evolution Event

系统生成的 `Evolution Event` 不是模型更新。它是本地 SQLite 根据已接受的 `dimension_update` 提案产生的一张待审卡：同一维度在最近 90 天内至少有 3 个已确认案例、首尾跨度至少 14 天、且数值差异至少为 `0.12`，才会出现。

事件保存：变化前后数值、支持提案、同维度被否决的提案（反证）、适用范围和用户结论。它永远不会自动修改个人模型；用户确认后，才标为“已确认变化”。

## 8. 初始设置的输出样例

```json
{
  "goal_weights": {
    "growth": {"weight": 0.31, "confidence": 0.49, "source": "onboarding"},
    "income": {"weight": 0.26, "confidence": 0.49, "source": "onboarding"}
  },
  "constraints": ["cash_flow_floor", "recovery_time"],
  "decision_priors": {
    "reversibility": {"weight": 0.22, "confidence": 0.43},
    "skill_compounding": {"weight": 0.29, "confidence": 0.43}
  },
  "action_preference": {"mode": "ask_before_suggesting", "confidence": 0.90},
  "self_descriptions": [{"label": "INTP", "confidence": 0.20, "status": "unvalidated"}]
}
```

这份输出是“可被现实推翻的起点”，不是用户画像。
