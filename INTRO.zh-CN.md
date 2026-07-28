# Heka

> 不是更努力地记住你，而是更谨慎地理解你。

Heka 是一个 **Local-First Personal Intelligence Loop（本地优先的个人智能循环）**。它把零散的日记、选择、情绪与行动转成可回看的证据：什么真正发生过，什么只是候选解释，什么还需要你亲自确认。

它不是人格测试，也不把一次表达当成“你就是这样的人”。Heka 的目标是让一个关于你的模型可以被证据支持、被反例推翻，并随着真实行动持续修正。

## 它如何工作

```text
真实记录 / Obsidian
        ↓
本地模型：整理为 Trace（事实、候选解释、提案）
        ↓
本地 SQLite：保存证据、审阅与版本历史
        ↓
你确认或否决
        ↓
Confirmed Personal Model
        ↓ 仅在主动提问或生成实验时
云端模型：基于有限证据做综合判断
```

## 核心原则

- **事实、解释、确认更新分离**：模型不能把推测伪装成事实。
- **本地优先**：原始记录、Trace、SQLite 数据库和模型版本默认留在设备上。
- **用户保有最终判断权**：任何模型更新都必须经过明确确认。
- **行动形成闭环**：对一个确认的问题，Heka 提供可检验选项；真实结果会成为下一次判断的证据。
- **可替换模型**：本地使用 Ollama 组织资料；云端使用你自己的 OpenAI-compatible API Key 做最终综合。

## 当前版本

V0.1 已支持：本地 Trace 整理、待确认模型提案、Obsidian 每日记录导入、行动实验与复盘、跨时间候选变化、HPEP 本地数据导出，以及稳定的本地 API v1。

这还是一个个人研究原型，而不是医疗、心理诊断或自动决策工具。

## 开始使用

```bash
cp .env.example .env
# 在 .env 填写自己的 HEKA_CLOUD_API_KEY
bash scripts/setup-local-model.sh
python3 server.py
```

打开 `http://127.0.0.1:8787`。完整说明见 [README.md](README.md)；API 边界见 [docs/api-v1.md](docs/api-v1.md)。
