# Heka Personal Evidence Protocol · HPEP v0.1

HPEP 是 Heka 的内部数据契约：它不定义“人是什么”，只定义个人研究中的资料如何被追溯、检验与修正。

```text
Source → Evidence → Claim → Problem → Experiment → Review
```

| Object | Meaning | Can update model directly? |
| --- | --- | --- |
| `source` | 原始来源，如 Obsidian、手动记录 | 否 |
| `evidence` | 可核验事实与最小原文引用 | 否 |
| `claim` | 有范围、反证与状态的判断 | 仅用户确认后 |
| `problem` | 用户明确确认希望处理的问题 | 否 |
| `experiment` | 为检验问题而选择的行动方案 | 否 |
| `review` | 行动后的结果、支持或反证 | 只触发新提案 |

每个对象都应包含：`id`、`schema_version: hpep/0.1`、`created_at`、`created_by`、`source_ids`、`scope` 与 `status`。`claim` 还必须有 `counter_evidence_ids` 与 `next_validation`。

现有 SQLite 映射：`entries/source_documents` 是 Source；`trace_facts` 是 Evidence；`proposals` 与 `model_snapshots` 是 Claim；`action_cases.problem/plan/result_note` 分别是 Problem、Experiment、Review。

适配器只能写入 Source 与 Evidence；任何适配器都不能直接写 Confirmed Model。
