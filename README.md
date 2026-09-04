# AI-Powered Wishlist Conversion Discovery Engine

An evidence-grounded discovery engine that helps Myntra understand **why users wishlist fashion
products but do not purchase them within 30 days**. The app has three tabs: a scrape-only
**Dashboard** (1,217 public comments + Opportunity Matrix), **Competitive Analysis**, and
**Discovery Chat** (platform chips + `Confidence: N%`). Research surveys stay in RAG — they are
not a dashboard tile.

See the planning docs in [`doc/`](./doc):

- [`doc/ProblemStatement.md`](./doc/ProblemStatement.md)
- [`doc/context.md`](./doc/context.md)
- [`doc/architecture.md`](./doc/architecture.md)
- [`doc/ImplementationPlan.md`](./doc/ImplementationPlan.md)
- [`doc/deployment-plan.md`](./doc/deployment-plan.md) — Vercel (frontend) + Render (FastAPI backend)

---

## Repository Layout (monorepo)

```
.
├── common/         # Shared config, DB session, and SQLAlchemy data models
├── ingestion/      # Ingestion pipeline (connectors → clean → embed → enrich)
├── analytics/      # Semantic analytics layer (taxonomy, clustering, confidence)
├── assistant/      # Grounded RAG orchestrator (retrieve → rerank → generate)
├── api/            # FastAPI backend (Insights API + RAG Orchestrator)
├── web/            # React (Vite) frontend: dashboard + assistant
├── db/migrations/  # Alembic migrations
├── tests/          # Python tests
└── doc/            # Project documentation
```

Technology (Phase 1): **Python**, **PostgreSQL + pgvector**, **FastAPI**, **React**,
**BGE** embeddings, and **Groq**-hosted LLM (template fallback if Groq is unavailable). See [`doc/architecture.md`](./doc/architecture.md) §6.

---

## Prerequisites

- Python 3.11+ (developed on 3.12)
- Docker + Docker Compose (for PostgreSQL + pgvector)
- Node.js 18+ (for the `web/` frontend)

---

## Quick Start (Phase 0)

1. **Clone & create a virtual environment**

```bash
py -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
```

2. **Install Python dependencies**

```bash
pip install -r requirements.txt
```

3. **Configure environment**

Copy `.env.example` to `.env` and fill in values (never commit `.env`):

```bash
copy .env.example .env   # Windows
# cp .env.example .env    # macOS/Linux
```

4. **Start the database (PostgreSQL + pgvector)**

```bash
docker compose up -d db
```

5. **Run migrations**

```bash
alembic upgrade head
```

6. **Run the API**

```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8010
```

Visit http://127.0.0.1:8010/health and http://127.0.0.1:8010/docs. Vite (`npm run dev`) proxies `/api` to this port.

7. **Run the web shell** (optional in Phase 0)

```bash
cd web
npm install
npm run dev
```

---

## Development

```bash
ruff check .        # lint
ruff format .       # format
pytest              # tests
```

CI runs the same checks on every push/PR (see `.github/workflows/ci.yml`).

---

## Phase 1 — Ingestion Pipeline

Sources enabled in this phase:

| Source | Connector | Notes |
| --- | --- | --- |
| **Play Store / Reddit / YouTube / reviews / social** | scrape | Dashboard KPI (1,217 comments) |
| **Research Excel + interviews** | `research` | RAG only — not a dashboard tile |

Only feedback related to these priority signals is kept from public sources:

- wishlist usage
- purchase hesitation / delayed decision-making
- fit, size, styling, quality, review trust, occasion uncertainty
- price sensitivity and waiting behavior
- external information seeking and product comparison

Run the pipeline:

```bash
# Full run (research Excel + filtered Play Store reviews + BGE embeddings)
python -m ingestion.run

# Research Excel only (no network scrape)
python -m ingestion.run --sources research

# Quick test without loading the embedding model
python -m ingestion.run --sources research --skip-embed
```

Re-running is **idempotent**: documents with the same `(source, source_ref)` are skipped.

### JSON export (no database required)

```bash
python -m ingestion.run --json-only --skip-embed --export-json data/scraped_corpus.json
```

Output is written to `data/scraped_corpus.json` by default (see `SCRAPED_JSON_PATH` in `.env`).

---

## Phase 2 — Storage & Data Layer

PostgreSQL + pgvector stores documents, chunk embeddings (HNSW index), and analytical aggregates.

```bash
alembic upgrade head
python -m storage.load_corpus --json-path data/scraped_corpus.json
uvicorn api.main:app --reload
```

Key endpoints: `POST /retrieval/search`, `GET /storage/stats`, `GET /storage/aggregates/signals`.

Full details: [`doc/StorageLayer.md`](./doc/StorageLayer.md).

---

## Phase 3 — Semantic Analytics Layer

Classifies chunks into a reason taxonomy, detects intent, maps journey stages, clusters themes, and scores confidence.

```bash
python -m analytics.run --json-only --export-json data/insights.json
# or against PostgreSQL after loading corpus:
python -m analytics.run
```

Key endpoints: `POST /analytics/run`, `GET /insights/reasons`, `GET /insights/clusters`.

Full details: [`doc/SemanticAnalytics.md`](./doc/SemanticAnalytics.md).

---

## Phase 4 — Grounded RAG Assistant

Retrieve → rerank → ground → generate answers with citations, confidence, and `AnswerTrace` audit records.

```bash
# Requires corpus + analytics (Phases 2–3)
uvicorn api.main:app --reload
```

Set `GROQ_API_KEY` in `.env` for LLM synthesis (template fallback works without it).

Key endpoints: `POST /assistant/ask`, `GET /assistant/questions`, `GET /assistant/traces`.

Full details: [`doc/RAGAssistant.md`](./doc/RAGAssistant.md).

---

## Phase 5 — Insight Dashboard + Discovery Chat

Three-tab React app: scrape strip + Opportunity Matrix, Competitive Analysis, Discovery Chat
(public chips + Confidence %). No Google Form tile. No age board.

```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8010
cd web && npm install && npm run dev
```

**Local URLs**

| URL | When to use |
| --- | --- |
| http://127.0.0.1:8010 | API (and built UI from `web/dist` if present) |
| http://127.0.0.1:5173 | Vite dev server with hot reload (`npm run dev`) |
| http://127.0.0.1:8010/walkthrough | PM walkthrough video |

Windows shortcut: `.\scripts\start-dev.ps1`

Key endpoints: `GET /insights/filters`, `GET /insights/heatmap`, `GET /insights/evidence`, plus existing insights routes.

Full details: [`doc/InsightDashboard.md`](./doc/InsightDashboard.md).

---

## Phase 6 — Evaluation & Hardening

Measure retrieval relevance, grounding faithfulness, and taxonomy accuracy; log auditable RAG traces and pipeline metrics; tune guardrails; and control cost via caching.

```bash
# Run evaluation suite (writes data/eval_report.json)
python -m eval.run

# Apply observability migration
alembic upgrade head

uvicorn api.main:app --reload
cd web && npm run dev   # three tabs: Dashboard, Competitive Analysis, Discovery Chat
```

Key endpoints: `GET /observability/quality`, `GET /observability/cost-controls`, `POST /observability/eval/run`.

Full details: [`doc/EvaluationHardening.md`](./doc/EvaluationHardening.md).

---

## Phase 7 — Corpus Scale-Out

All six source types (research, Play Store, Reddit, YouTube, product reviews, social) flow through the ingestion pipeline with incremental per-source refresh and cross-source validation.

```bash
# Full multi-source corpus export
python -m ingestion.run --json-only --skip-embed

# Incremental refresh for due sources (+ analytics recompute)
python -m ingestion.refresh

# Apply refresh-state migration
alembic upgrade head
```

Key endpoints: `GET /ingestion/sources`, `POST /ingestion/refresh`.

Full details: [`doc/CorpusScaleOut.md`](./doc/CorpusScaleOut.md).

---

## Phase 8 — Internal Data & Ground-Truth Metric

Integrate Myntra internal wishlist/funnel events, compute the **30-day conversion metric**, corroborate public-evidence reasons against observed behavior, and enable PM feedback on insights.

```bash
alembic upgrade head
python -m internal.run
uvicorn api.main:app --reload
cd web && npm run dev   # PM calibration lives on the Dashboard, not a Conversion tab
```

Key endpoints: `GET /internal/conversion`, `GET /internal/corroboration`, `POST /internal/feedback`.

Full details: [`doc/InternalDataExtensibility.md`](./doc/InternalDataExtensibility.md).
