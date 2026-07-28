# Heka

> Not remembering more about you—understanding you more carefully.

Heka is a **local-first personal intelligence loop**. It turns fragmented journals, decisions, emotions, and actions into reviewable evidence: what actually happened, what is only a candidate interpretation, and what still needs your confirmation.

It is not a personality test. One sentence is never treated as a stable trait. Heka is an attempt to make a personal model evidence-backed, falsifiable by counterexamples, and continuously revised through real actions.

## How it works

```text
Personal records / Obsidian
        ↓
Local model: Trace extraction (facts, candidate interpretations, proposals)
        ↓
Local SQLite: evidence, review decisions, and model history
        ↓
Your explicit acceptance or rejection
        ↓
Confirmed Personal Model
        ↓ only when you ask a question or start an experiment
Cloud model: bounded-evidence synthesis
```

## Principles

- **Facts, interpretations, and confirmed updates are separate.** A model cannot turn a guess into a fact.
- **Local-first by default.** Raw records, Traces, SQLite data, and model history stay on the device.
- **The user keeps final judgment.** No model update is written without explicit acceptance.
- **Action closes the loop.** For a confirmed problem, Heka offers testable options; real outcomes become evidence for the next revision.
- **Bring your own models.** Ollama organizes local material; your own OpenAI-compatible cloud API handles final synthesis.

## Current scope

V0.1 supports local Trace organization, reviewable model proposals, Obsidian daily-note import, action experiments and reviews, cross-time change candidates, HPEP local data export, and a stable local API v1.

Heka is a personal-research prototype, not a medical, psychological-diagnostic, or autonomous decision-making system.

## No Obsidian or Qwen?

Obsidian is entirely optional. Use the **Evidence** page to enter a record directly; Obsidian only provides an optional historical-note import source.

Qwen is the recommended local organizer for Chinese Trace extraction, but it is not the only option. Install Ollama and run `bash scripts/setup-local-model.sh`, or pull another instruction-following Ollama model that can reliably return JSON and set `OLLAMA_MODEL` in `.env`. V0.1 still requires one local model to turn new raw records into Traces; the cloud key is only used for user-triggered bounded-evidence synthesis.

## Quick start

```bash
cp .env.example .env
# Add your own HEKA_CLOUD_API_KEY to .env
bash scripts/setup-local-model.sh
python3 server.py
```

Then open `http://127.0.0.1:8787`. See [README.md](README.md) for the full guide and [docs/api-v1.md](docs/api-v1.md) for the API contract.
