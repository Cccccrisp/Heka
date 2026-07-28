# Heka Local API v1

Heka's browser interface calls the same local API that other local clients can use. The server binds to `127.0.0.1:8787` by default (change `HEKA_PORT` in `.env` if needed): it is intentionally not exposed to a network.

The `/api/v1/` prefix is stable for V0.1. Existing `/api/` routes remain available as backwards-compatible aliases.

## Read routes

| Route | Purpose |
| --- | --- |
| `GET /api/v1/health` | Check that Heka and local SQLite are reachable. |
| `GET /api/v1/runtime` | Selected local and cloud model names; never returns keys. |
| `GET /api/v1/model` | Latest user-confirmed personal-model version. |
| `GET /api/v1/pending` | Trace-derived proposals awaiting review. |
| `GET /api/v1/evolution` | Cross-time candidates and their review state. |
| `GET /api/v1/actions` | Confirmed-problem action cases and reviews. |
| `GET /api/v1/onboarding` | Latest initial self-report. |
| `GET /api/v1/obsidian/status` | Local Obsidian connector status. |

## Write routes

| Route | Body | Boundary |
| --- | --- | --- |
| `POST /api/v1/capture` | `{ "text": "..." }` | Sends the raw record only to local Ollama, then stores a reviewable proposal locally. |
| `POST /api/v1/proposals/:id/review` | `{ "decision": "accept" | "reject" }` | Only an explicit `accept` may create a model version. |
| `POST /api/v1/ask` | `{ "question": "..." }` | Sends a bounded evidence packet to the configured cloud model. |
| `POST /api/v1/actions` | `{ "problem": "...", "confirmed": true }` | Generates three bounded options via the cloud model; it never auto-acts. |
| `POST /api/v1/actions/:id/select` | `{ "option_index": 0..2 }` | Records the user's option. |
| `POST /api/v1/actions/:id/review` | `{ "result_note": "..." }` | Records a real outcome or counterexample. |
| `POST /api/v1/onboarding` | `{ "answers": { ... } }` | Saves self-report as provisional onboarding evidence, not a model update. |
| `POST /api/v1/obsidian/sync` | `{}` | Reads only the local folder set in `.env`. |

## Bring your own models

Copy `.env.example` to `.env`. Set `HEKA_CLOUD_API_KEY`, `HEKA_CLOUD_BASE_URL`, and `HEKA_MODEL` to an OpenAI-compatible cloud provider. These values stay on the user's machine and are ignored by Git.

For local Trace organization, install Ollama and run `bash scripts/setup-local-model.sh`. The script downloads `qwen3:4b` by default; set `HEKA_OLLAMA_MODEL` before running it to choose another compatible Ollama model.

Obsidian is optional. Without `HEKA_OBSIDIAN_DAILY_DIR`, users can write records directly in the Evidence workspace and use every core review/model/action flow. A local Ollama model is currently required for **new** raw records; cloud-only inference is deliberately not an implicit fallback because it would upload the raw record.

Do not bind this development server to `0.0.0.0` without adding authentication, encryption, and a deliberate multi-user data boundary.
