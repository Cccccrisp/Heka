# Heka · Personal Intelligence Loop

[中文介绍](INTRO.zh-CN.md) · [English introduction](INTRO.en.md) · [API v1](docs/api-v1.md)

> Heka 不试图“记住你”。它尝试持续建立、检验并修正一个关于你的个人模型。

Heka V0.1 是一个混合式个人观察 Agent 原型：你写下一条真实记录，本地模型将它转成可核验的 Trace 与**待确认提案**；当你主动提问时，云端模型再基于经过筛选的证据包给出最终判断。只有你确认，系统才会更新个人模型。

第一次运行时模型是空的，这是刻意的设计：它还没有获得你的确认。

## 它现在能做什么

1. **收集一条生活 / 决策记录**：例如一次选择、情绪、行动或反思。
2. **本地生成结构化 Trace**：Qwen 负责分类、打标签，并严格区分可观察事实和候选解释。
   如果输出不符合 Trace 契约，系统只在本地要求它修复一次；仍不合格则拒绝写入，而不是静默存入坏数据。
3. **提出而非执行模型更新**：本地模型只能给出“维度更新 / 待验证假设 / 不更新”的建议。
4. **由你确认或否决**：接受才会生成新的个人模型版本；否决保留记录，但模型不变。
5. **保存完整本地历史**：原始记录、Trace、提案、确认状态与每个模型版本都保存在 SQLite。
6. **按需云端综合**：只有在你提问时，DeepSeek 才会对当前模型和最近的证据包给出最终判断。
7. **本地检查候选变化**：Evolution Event 只比较跨时间的已确认案例，保留反证，并等你确认后才标记为变化。
8. **通过极简观测台使用**：写记录、审阅提案、查看已确认模型、检查候选变化与主动提问。
9. **接入 Obsidian 每日记录**：只读取你指定的每日记录目录；每份 Markdown 会保留路径、标题、日期与内容指纹，后续仅导入新增或修改的版本。

## 它刻意不做什么

- 不把一次表达当作稳定人格。
- 不让任何 LLM 直接执行 SQL 或自由修改数据库。
- 不把聊天历史当成“理解”。
- 不做多智能体、自主执行、复杂 RAG 或行为监控。

## 架构

```text
你的记录
  ↓
Qwen（本地整理：分类、Trace、候选关联）
  ↓
SQLite（本地状态源：记录、提案、版本、审计）
  ↓
你确认 / 否决
  ↓
Confirmed Personal Model（仅确认后更新）
  ↓ 仅在你主动提问时
DeepSeek（云端综合：最终判断）
```

### 职责边界

| 层 | 责任 | 不能做什么 |
| --- | --- | --- |
| 本地 Qwen | 分类、打标签、抽取 Trace 和低层候选关联 | SQL 执行、最终人格判断、直接更新模型 |
| SQLite | 保存原始证据、待确认提案和版本历史 | 判断你是谁 |
| DeepSeek | 基于有限证据包回答跨日问题、给出最终判断 | 读取整个数据库、直接写数据库 |
| Heka 程序 | 校验 JSON、执行确定性写入、维护版本 | 擅自接受提案 |
| 用户 | 确认、否决、补充反证 | 被系统替代判断 |

这就是“本地整理、云端判断、本地保存状态”：模型可替换，个人模型和它的演化历史不依赖任何一家模型提供商。

## 开始使用

需要 Python 3.11+、Ollama 和 Qwen3 4B；Python 部分不依赖第三方包。每位使用者自己创建 `.env` 并填自己的云端 Key，仓库不包含任何人的密钥或个人数据库。

```bash
git clone <your-repository-url>
cd heka-v0.1
cp .env.example .env
# 在 .env 中填入 HEKA_CLOUD_API_KEY（默认使用 DeepSeek，也兼容 OpenAI 格式接口）
# 从 https://ollama.com/download 安装并启动 Ollama 后：
bash scripts/setup-local-model.sh
python3 server.py
```

然后打开 <http://127.0.0.1:8787>。

完整的本地 API 与“自带模型”配置见 [API v1](docs/api-v1.md)。

## 没有 Obsidian 或 Qwen，怎么办？

### 没有 Obsidian：直接使用即可

Obsidian **不是必需品**。打开「观察资料」页面，直接写下一条真实记录，就能完成：记录 → 本地 Trace → 你的审阅 → 模型提案 / 行动复盘。Obsidian 只是给已有日记用户准备的**可选资料源**；不配置 `HEKA_OBSIDIAN_DAILY_DIR` 不会影响任何核心功能。

### 没有 Qwen：安装或换一个本地模型

Heka 需要一个运行在 Ollama 里的本地模型来整理原始记录；默认推荐中文表现更好的 `qwen3:4b`。没有下载时，安装 Ollama 后运行：

```bash
bash scripts/setup-local-model.sh
```

也可以选择任意能遵循指令并输出 JSON 的 Ollama 模型。先自行下载，再在 `.env` 中替换：

```bash
ollama pull llama3.2:3b
# .env
OLLAMA_MODEL=llama3.2:3b
```

模型越小，速度通常越快，但中文抽取与结构化 JSON 的稳定性可能下降。对于 Heka 的中文 Trace，仍建议优先使用 Qwen。

### 不想运行任何本地模型：当前版本的真实限制

V0.1 **不能只填云端 Key 就完整运行**。本地模型负责把原始记录变成 Trace；云端模型只在你主动提问或生成行动方案时，基于有限证据做最终综合。这样设计是为了不把原始日记默认上传。

如果你暂时不运行本地模型，仍可阅读已有档案和模型历史，但不能从新的原始记录生成 Trace。未来可加入一个明确授权的「Cloud-only Trace」模式；它必须由用户主动打开，并清楚告知原始记录会离开设备。

## 数据对象

| 对象 | 含义 | 是否能直接成为个人模型 |
| --- | --- | --- |
| `entries` | 原始记录 | 否 |
| `source_documents` | Obsidian 原始笔记的路径、标题、日期与内容指纹 | 否 |
| `traces` | 一次本地处理的审计副本 | 否 |
| `trace_events` / `trace_facts` / `trace_tags` | 发生了什么、可核验事实、主题分类 | 否 |
| `trace_interpretations` | 由事实索引支撑、且明确标注不确定性的候选解释 | 否 |
| `trace_decisions` / `trace_decision_options` | 决策问题、选项、选择、可逆性与所依据事实 | 否 |
| `trace_actions` / `trace_emotions` | 已做或计划的行动，以及有原文依据的情绪 | 否 |
| `proposals` | 等待用户审阅的模型建议 | 否 |
| `model_snapshots` | 已确认模型的版本历史 | 是 |
| `evolution_events` | 由已确认证据生成、等待用户确认的跨时间候选变化 | 否 |

这套拆分有一个实际作用：以后问“你在职业机会中最常因为什么延后决策？”时，系统可以查决策、选项和理由事实；它不必重新让模型阅读所有原始日记，也不能把候选解释误当成事实。

## 当前限制与下一步

V0.1 的云端判断只读取最近 12 条证据，没有跨日检索、反证工作流、向量召回或移动端。下一步会先验证：连续一周的 Trace，是否真的能产生稳定、可被用户纠正的个人模型变化；之后才考虑跨日模式、假设失效机制与检索层。

数字如何计算见 [Measurement Protocol](docs/measurement.md)。

跨来源、跨产品的内部数据契约见 [HPEP v0.1](docs/hpep.md)。

HPEP 导出可由 `heka.export.export_hpep(store, target)` 生成本地 JSONL；导出前应由用户选择目标位置。

## Obsidian 接入

Heka 不会扫描整个 Obsidian Vault。你选择一个目录（推荐 `每日/`），它会读取其中直接存放的 Markdown，使用本地 Qwen 将每篇笔记做成一条待审阅 Trace，并保存来源路径与内容指纹。重复运行会跳过未变化的笔记；改过的笔记会以新的版本进入审阅队列，保留审计历史。

在本地 `.env` 加入 `HEKA_OBSIDIAN_DAILY_DIR=/你的绝对路径/每日` 后，观测台会显示资料源状态，并提供“同步 Obsidian”按钮。同步只读取这个目录，不会上传到云端或确认模型更新。

```bash
python3 -m heka.main --db heka.db obsidian-import \
  "/你的 Vault/克里斯皮的观测计划/每日" --dry-run

# 确认清单后，去掉 --dry-run 正式导入（只调用本地 Qwen，不调用云端）
python3 -m heka.main --db heka.db obsidian-import \
  "/你的 Vault/克里斯皮的观测计划/每日"
```

目标如何从一句愿望变成可检验的意图，见 [Goal Contract](docs/goal-contract.md)。

## 隐私

SQLite 数据库默认保存在本地。每次点击“生成观察”时，原始记录只发给本地 Ollama / Qwen；每次“向 Heka 提问”或“生成行动方案”时，当前已确认模型和最近的有限证据包会发送给你在 `.env` 配置的云端模型。API 密钥只放在本地 `.env`，并已被 `.gitignore` 排除，绝不能提交到 GitHub。
