---
title: Enterprise Agents Platform API
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8000
pinned: false
---

# Enterprise Agents Platform

A modular-monolith multi-agent platform built on the Google Agent Development Kit (ADK), pluggable across model providers (OpenAI by default, Gemini / Anthropic / Bedrock optional via LiteLLM), with bearer-token auth, persistent HITL approvals, structured logging, and durable agent telemetry.

One **orchestrator** routes requests to five specialist worker agents over the A2A protocol:

- **Inventory** — product database lookups (name / SKU / category, low-stock).
- **Policy** — RAG over policy docs via pgvector (`vecs`).
- **Analytics** — price-band filters, valuations, EOQ-style demand math, anomaly detection.
- **Orders** — purchase orders, supplier compliance, sourcing, EOQ calculations grounded in real PO history.
- **Notification** — drafts emails with HITL approval; SMTP send (or simulated send on HF Spaces / demo mode).

## Architecture

```
        ┌─────────────────────┐
        │   React + Vite UI   │  (Vercel)
        └──────────┬──────────┘
                   │  POST /orchestrator/chat
                   │  Authorization: Bearer $PLATFORM_API_KEY
                   ▼
        ┌─────────────────────┐
        │   FastAPI gateway   │
        │   • bearer-auth mw  │
        │   • request-id mw   │
        │   • CORS + slowapi  │
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐                ┌──────────────────┐
        │   Orchestrator      │  intent-class. │  OpenAI / LiteLlm │
        │   (ADK LlmAgent)    ├───────────────►│  (chat + embed)   │
        └──────────┬──────────┘                └──────────────────┘
                   │  A2A JSON-RPC over HTTP
        ┌──────────┼──────────┬──────────┬──────────┐
        ▼          ▼          ▼          ▼          ▼
   inventory   policy    analytics    orders   notification
        │          │          │          │          │
        ▼          ▼          ▼          ▼          ▼
   ┌──────────────────────────────────────────────────┐
   │  Supabase: inventory · suppliers · policy_docs   │
   │            hitl_approvals · agent_metrics        │
   │            vecs.policy_documents (pgvector)      │
   └──────────────────────────────────────────────────┘
```

## Tech stack

**Backend** — Python 3.12, FastAPI, Google ADK + LiteLLM, OpenAI SDK (chat + embeddings), Supabase REST + Postgres, `vecs` for pgvector RAG, structlog, OpenTelemetry, slowapi, pytest.

**Frontend** — React 19, Vite 7, Tailwind 4, react-markdown, vanilla `fetch` with localStorage persistence and AbortController.

**Infra** — Docker (multi-stage; backend last for HF Spaces), Hugging Face Spaces (backend), Vercel (frontend), Supabase (data + RAG).

## Configuration

All configuration is environment-driven. Copy this template into `backend/.env` (or set as Space / Vercel env vars).

```bash
# --- Models ---------------------------------------------------------------
OPENAI_API_KEY=sk-proj-...
LLM_MODEL=openai/gpt-4o-mini                    # any LiteLLM-supported model
EMBEDDING_MODEL=text-embedding-3-small          # 1536 dims; -3-large is 3072
# EMBEDDING_DIM=                                # override only if needed

# --- Auth (set to enable) -------------------------------------------------
PLATFORM_API_KEY=                               # CSV of accepted bearer tokens

# --- Supabase -------------------------------------------------------------
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_KEY=<service-role-jwt>
SUPABASE_DB_URL=postgresql://postgres.<ref>:<pwd>@aws-0-<region>.pooler.supabase.com:5432/postgres

# --- Server ---------------------------------------------------------------
BASE_URL=http://localhost:8000                  # MUST be the public URL in prod
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
DEFAULT_RATE_LIMIT=60/minute
MAX_PROMPT_CHARS=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# --- HITL -----------------------------------------------------------------
ENABLE_HITL=true
HITL_APPROVAL_TTL_MINUTES=30

# --- Email ----------------------------------------------------------------
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
FROM_EMAIL=
EMAIL_DEMO_MODE=false                           # forces simulated send
EMAIL_ALLOWED_DOMAINS=                          # CSV; empty = open
EMAIL_ALLOWED_RECIPIENTS=                       # CSV; empty = open
COMPANY_NAME=Company
EMAIL_SIGNATURE=Best regards\nCompany

# --- Observability --------------------------------------------------------
ENABLE_OTEL=false
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
OTEL_SERVICE_NAME=enterprise-agents-platform
```

`PLATFORM_API_KEY` is **the** auth toggle. When unset, every endpoint is open (dev convenience). When set, every `/orchestrator/*` and `/{agent}/a2a/*` request requires `Authorization: Bearer <key>`. Multiple comma-separated keys are accepted to allow rotation.

## Database setup

Open the Supabase SQL Editor and run, in order:

1. `backend/setup_database.sql` — `vector` extension, `inventory`, `policy_documents` (with sample rows).
2. `backend/setup_orders_tables.sql` — `suppliers`, `purchase_orders` (with sample rows).
3. `superbase/migrations/202604290001_observability_tables.sql` — `hitl_approvals`, `agent_metrics`.

Then seed the policy RAG (vecs collection) once:

```bash
cd backend
source venv/bin/activate
python seed_policies.py
```

The seeder embeds each policy doc with `EMBEDDING_MODEL` (default OpenAI 1536-dim) and writes them to the `vecs.policy_documents` collection. If a collection of a different dimension already exists from an earlier run, it is automatically dropped and recreated.

## Quick start (local)

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python validate_config.py        # sanity-check env + DB
python seed_policies.py          # one-time RAG seed
python main.py                   # serves on :8000

# Frontend
cd frontend
npm install
npm run dev                      # serves on :5173
```

The dev frontend reads `VITE_API_BASE` (default `http://localhost:8000`) and `VITE_API_TOKEN`. If `PLATFORM_API_KEY` is set on the backend, you must also set `VITE_API_TOKEN` to a matching value.

## Quick start (Docker)

```bash
docker compose up --build
```

Spins up `backend` (port 8000) and `frontend` nginx (port 3000), each from its own stage of the multi-stage `Dockerfile`. Env vars are read from a `.env` next to `docker-compose.yml`.

## API

### Orchestrator

| Method | Path | Description |
| --- | --- | --- |
| POST | `/orchestrator/chat` | Main chat entrypoint. Body: `{session_id, prompt}`. Auth required. |
| GET | `/orchestrator/metrics` | Rolling per-agent stats (also persisted to `agent_metrics` table). |
| GET | `/orchestrator/.well-known/agent-card.json` | A2A agent card. |

### Per-agent (inventory, policy, analytics, orders, notification)

| Method | Path | Description |
| --- | --- | --- |
| POST | `/{agent}/a2a/interact` | A2A JSON-RPC `message/send`. Auth required. |
| GET | `/{agent}/.well-known/agent-card.json` | A2A agent card (public). |

### System

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/` | public | Platform manifest. |
| GET | `/health` | public | Liveness + CPU/memory snapshot. |
| GET | `/ready` | public | Readiness probe. |
| GET | `/docs` | public | Swagger UI. |
| GET | `/redoc` | public | ReDoc. |

Every response carries an `X-Request-ID` header that mirrors the `trace_id` in `ChatResponse`, making it straightforward to follow a single user turn across the orchestrator → A2A → tool boundary in logs.

## Switching model providers

Everything routes through `backend/shared/llm_config.py`. To swap providers, change two env vars:

```bash
# OpenAI (default)
LLM_MODEL=openai/gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# Gemini
LLM_MODEL=gemini/gemini-2.5-flash-lite
EMBEDDING_MODEL=text-embedding-004
GOOGLE_API_KEY=...

# Anthropic
LLM_MODEL=anthropic/claude-sonnet-4-5
EMBEDDING_MODEL=text-embedding-3-small        # Anthropic has no embeddings API
ANTHROPIC_API_KEY=...
```

After changing `EMBEDDING_MODEL`, re-run `python seed_policies.py` — the seeder auto-drops the existing `policy_documents` vecs collection if its dimension doesn't match the new model and rebuilds it.

## Security notes

- **Bearer-token auth** is enforced platform-wide when `PLATFORM_API_KEY` is set. Tokens are compared with `hmac.compare_digest`. CSV form supports rotation.
- **HITL approvals** are scoped by `(user_id, session_id)`. The user_id is sha256-derived from the bearer token, so cross-user approval hijack is not possible.
- **Email recipient allowlist** (`EMAIL_ALLOWED_DOMAINS` / `EMAIL_ALLOWED_RECIPIENTS`) is enforced both at compose time and at SMTP send. Empty values mean "any valid address" for back-compat — set them in production.
- **Email HTML body** is `html.escape`-d before injection; user/agent context cannot inject script tags.
- **PostgREST filter inputs** from agent tools pass through `sanitize_filter_term` to strip operator characters that could re-shape queries.
- **Pydantic size limits** on `ChatRequest.prompt` (8 KB default) prevent unbounded LLM token spend per call.
- **Per-token rate limiting** via slowapi (`DEFAULT_RATE_LIMIT`, default 60/minute) keyed on the user_id derived from the bearer token (with IP fallback for anonymous).

## Observability

- **Structured logs** via `structlog` with request-id, session-id, user-id, agent-name context. Set `LOG_LEVEL=DEBUG` for tool-call detail.
- **Request-ID propagation** — every response carries `X-Request-ID`, every log line and OTel span is bound to it.
- **OpenTelemetry** spans wrap every A2A call when `ENABLE_OTEL=true` and `OTEL_EXPORTER_OTLP_ENDPOINT` is set.
- **Agent metrics** — per-call latency, success/failure, error sample, token count are aggregated in-memory and persisted to the `agent_metrics` Supabase table (queryable across replicas).

## Testing

```bash
cd backend
source venv/bin/activate
python -m pytest tests/ -q
```

Covers: intent-classifier parser repair, bearer-token auth helpers, HITL scoping + TTL, PostgREST filter sanitization, email allowlist + HTML escaping. Tests do not require live Supabase or OpenAI credentials.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `psycopg2.OperationalError: could not translate host name` | Stale `SUPABASE_DB_URL` (the project was deleted/renamed). Update both root and `backend/.env`. |
| `400 INVALID_ARGUMENT API key expired` | `OPENAI_API_KEY` (or `GOOGLE_API_KEY` if using Gemini) expired or wrong project. |
| Browser shows "blocked by CORS policy" | The dev frontend origin is not in `CORS_ORIGINS`. Add `http://localhost:5173`. |
| Chat returns 401 from frontend | Backend has `PLATFORM_API_KEY` set but `VITE_API_TOKEN` is empty/wrong. |
| `MismatchedDimension` from `vecs` | `EMBEDDING_MODEL` changed. Re-run `python seed_policies.py` (it auto-recreates). |
| Tool error envelopes leak into chat reply | A2A handler is concatenating `function_response` parts. Verify routes still skip dicts containing an `error` key. |
| Cold-start request times out | `httpx.AsyncClient(timeout=30.0)` in orchestrator routes. Bump to 60 s for HF Spaces / Render free tier. |

## License

Proprietary — all rights reserved.
