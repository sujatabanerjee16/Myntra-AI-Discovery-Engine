# Deployment Plan — Wishlist Conversion Discovery Engine

> Target topology requested: **React frontend on Vercel** + **Python API backend**.  
> This repo’s backend is **FastAPI** (not Streamlit). Streamlit Community Cloud cannot host a FastAPI REST API that a separate Vercel SPA can call. The plan below uses **Vercel for the frontend** and **Render for the FastAPI backend** (closest free/easy Python host that actually works for this stack). See [§2](#2-why-not-streamlit-for-the-backend).

---

## 1. Target architecture

```
┌────────────────────────────┐         HTTPS          ┌─────────────────────────────┐
│  Vercel (frontend)         │ ─────────────────────▶ │  Render (FastAPI backend)   │
│  web/  → React + Vite SPA  │   VITE_API_BASE        │  api.main:app (uvicorn)     │
│  wishlist-*.vercel.app     │                        │  JSON fallback corpus       │
│  (static bootstrap)        │                        │  + Groq; template fallback  │
└────────────────────────────┘                        │    if the model 404s        │
                                                      └──────────────┬──────────────┘
                                                                     │ optional later
                                                      ┌──────────────▼──────────────┐
                                                      │  Managed Postgres+pgvector  │
                                                      │  (Neon / Render / Supabase) │
                                                      └─────────────────────────────┘
```

| Layer | Host | What deploys |
| ----- | ---- | ------------ |
| Frontend | **Vercel** | `web/` (Vite build → static assets + `dashboard-bootstrap.json`) |
| Backend API | **Render** (Web Service) | FastAPI via `uvicorn api.main:app` |
| Data (Phase 1 demo) | Bundled with backend | `data/insights.json`, `data/scraped_corpus.json` (`USE_JSON_FALLBACK=true`) |
| LLM | Groq (external) | `GROQ_API_KEY` on the backend only |

Local path mapping (important for env wiring):

- Vite **dev** proxies `/api/*` → backend `/*` (strips `/api`).
- Production should set `VITE_API_BASE` to the **backend origin with no `/api` suffix**, e.g. `https://wishlist-api.onrender.com`, because FastAPI routes are `/insights/...`, `/assistant/...`, `/health`.

---

## 2. Why not Streamlit for the backend

| Requirement | Streamlit Community Cloud | This project |
| ----------- | ------------------------- | ------------ |
| Host a React SPA separately | No (Streamlit is the UI) | Frontend is on Vercel |
| Expose stable REST (`/insights`, `/assistant`) | No public uvicorn port | FastAPI is the API |
| CORS for browser calls from Vercel | N/A | Required |
| Long-running API + JSON corpus | Not supported as API host | Required |

**Conclusion:** Do **not** deploy the FastAPI service to Streamlit. Use Render (or Railway / Fly.io / Hugging Face Spaces with Docker) for the API.

If you specifically need a Streamlit surface later, treat it as an **optional ops/demo UI** that *calls* the Render API — never as the API host itself.

---

## 3. Prerequisites

- GitHub repo with this monorepo pushed (Vercel + Render both pull from Git).
- Accounts: [Vercel](https://vercel.com), [Render](https://render.com), [Groq](https://console.groq.com).
- Local tools (optional CLI path): Node 18+, `npm i -g vercel`, Render dashboard or `render` CLI.
- Demo data present at deploy time:
  - `data/insights.json`
  - `data/scraped_corpus.json`  
  These live under `data/` (gitignored). For the demo deploy they must be **force-added** or copied into an allowed path before push (see [§6](#6-include-demo-json-in-the-backend-image)).

---

## 4. Environment variables

### 4.1 Backend (Render)

| Variable | Demo value | Notes |
| -------- | ---------- | ----- |
| `ENVIRONMENT` | `production` | |
| `LOG_LEVEL` | `INFO` | |
| `USE_JSON_FALLBACK` | `true` | Free-tier hosted demo uses keyword JSON RAG. Set `false` only with Neon/Postgres **and** full `requirements.txt` on a paid instance |
| `DATABASE_URL` | *(optional / local)* | Used locally with Neon. Not required on free Render while `USE_JSON_FALLBACK=true` |
| `INSIGHTS_JSON_PATH` | `data/insights.json` | |
| `SCRAPED_JSON_PATH` | `data/scraped_corpus.json` | |
| `GROQ_API_KEY` | *(secret)* | Preferred for Discovery Chat; template synthesis still answers if Groq is down |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | |
| `CORS_ORIGINS` | `https://myntra-ai-discovery-engine-five.vercel.app` | Comma-separated; include preview URLs if needed |
| `PYTHON_VERSION` | `3.12.8` | Required — Render’s default (e.g. 3.14) breaks `pydantic-core` |
| `EMBEDDING_MODEL` | `BAAI/bge-large-en-v1.5` | Used locally with Neon; unused on free Render JSON path |

Do **not** put `GROQ_API_KEY` or `DATABASE_URL` in the Vercel frontend.

### 4.1.1 Neon (local proof only on free Render)

Free Render cannot load BGE/torch, so production stays on JSON fallback. Neon + pgvector remains valid for **local** verification (`USE_JSON_FALLBACK=false` in `.env`). To put Neon on Render later you need a paid plan, `requirements.txt`, and `USE_JSON_FALLBACK=false`.

### 4.2 Frontend (Vercel)

| Variable | Example | Notes |
| -------- | ------- | ----- |
| `VITE_API_BASE` | `/api` | Preferred. Same-origin calls; `web/vercel.json` rewrites `/api/*` → Render. Avoids browser CORS. |

Alternative (direct): `https://myntra-ai-discovery-engine.onrender.com` — then Render `CORS_ORIGINS` must allow the Vercel domain (or `*`).

Rebuild the frontend after changing `VITE_*` (Vite inlines them at build time).

Public app URL for this project: `https://myntra-ai-discovery-engine-five.vercel.app`

---

## 5. Backend deploy (Render)

Repo already includes:

- [`render.yaml`](../render.yaml) — Blueprint for a free web service (JSON keyword RAG)
- [`requirements-deploy.txt`](../requirements-deploy.txt) — Lean API runtime **without** `sentence-transformers` / torch
- [`requirements.txt`](../requirements.txt) — Full local/dev stack (Neon + BGE); not for free Render
- Start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`

### 5.1 Dashboard steps

1. Push this branch to GitHub.
2. Render → **New** → **Blueprint** → select the repo (uses `render.yaml`), **or** New Web Service:
   - Root directory: repo root
   - Runtime: Python 3.12
   - Build: `pip install -r requirements-deploy.txt`
   - Start: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
3. Set env vars from §4.1 (especially `GROQ_API_KEY`, `CORS_ORIGINS`, `USE_JSON_FALLBACK=true`).
4. Deploy. Note the public URL, e.g. `https://wishlist-api.onrender.com`.
5. Smoke test:
   - `GET /health`
   - `GET /insights/filters`
   - `GET /docs`

### 5.2 Free-tier caveats

- Render free web services **spin down** after idle; first request can take ~30–60s.
- Do not install full `requirements.txt` on free tier (torch + BGE will exceed build/memory limits). Use `requirements-deploy.txt` for the JSON demo.
- For production RAG with pgvector, move to a paid instance + managed Postgres and run Alembic + ingestion offline.

---

## 6. Include demo JSON in the backend image

`data/` is gitignored. Before the first backend deploy:

```bash
git add -f data/insights.json data/scraped_corpus.json data/insight_feedback.json
git add -f data/seeds/*.json
git commit -m "Include demo JSON corpus for deployed API fallback"
git push
```

Without these files, insights routes return empty / errors even when the service is healthy.

---

## 7. Frontend deploy (Vercel)

Repo already includes [`web/vercel.json`](../web/vercel.json).

### 7.1 Dashboard steps

1. Vercel → **Add New Project** → import the GitHub repo.
2. Configure:
   - **Root Directory:** `web`
   - **Framework Preset:** Vite
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
   - **Install Command:** `npm install`
3. Environment variable:
   - `VITE_API_BASE` = `https://<your-render-service>.onrender.com`
4. Deploy. Note the URL, e.g. `https://wishlist-discovery.vercel.app`.
5. Update Render `CORS_ORIGINS` to that Vercel URL and **redeploy** the backend.

### 7.2 CLI steps (optional)

```bash
cd web
npm install
npx vercel login
npx vercel link
npx vercel env add VITE_API_BASE production
# paste https://<render-host>
npx vercel --prod
```

---

## 8. End-to-end cutover checklist

1. Backend `/health` returns OK on Render.
2. Backend `/insights/reasons` returns non-empty reasons (JSON present).
3. Vercel site loads; browser Network tab shows API calls to the Render host (not `/api` on Vercel).
4. Dashboard scrape strip shows **1,217 shopper comments** (no Google Form tile). Opportunity Matrix and Competitive tab load.
5. Discovery Chat returns a grounded answer with **platform chips + Confidence: N%**. Groq is preferred; template synthesis is the local fallback if the model is unavailable.
6. PM walkthrough plays at `http://127.0.0.1:8010/walkthrough` (or `/pm-demo/wishlist-intelligence-pm-walkthrough.html` on the API host).
7. CORS: no browser `blocked by CORS policy` errors.
8. Secrets: `.env` never committed; only platform secret stores used.

---

## 9. Recommended deploy order

```text
1. Force-add demo JSON → push
2. Deploy Render backend → confirm /health + /insights/filters
3. Deploy Vercel frontend with VITE_API_BASE → backend URL
4. Set CORS_ORIGINS on Render → redeploy backend
5. Run checklist §8
```

---

## 10. Later: production hardening

| Item | Action |
| ---- | ------ |
| Database | Provision Postgres + pgvector; set `DATABASE_URL`; `USE_JSON_FALLBACK=false` |
| Migrations | `alembic upgrade head` in a release job |
| Ingestion | Run connectors on a worker/cron, not on the web dyno |
| Embeddings | Install full `requirements.txt` on a larger instance; warm BGE once |
| CORS | Lock `CORS_ORIGINS` to exact Vercel production + preview domains |
| Auth | Add API auth / SSO before exposing internal metrics |
| Observability | Wire Render logs + `/observability` routes |
| Custom domains | `api.yourdomain.com` (Render) + `app.yourdomain.com` (Vercel) |

---

## 11. Rollback

- **Frontend:** Vercel → Deployments → Promote previous production deployment.
- **Backend:** Render → Events → Redeploy previous successful deploy.
- Keep `VITE_API_BASE` pointing at a known-good API until both sides are healthy.

---

## 12. Decision log

| Decision | Choice | Rationale |
| -------- | ------ | --------- |
| Frontend host | Vercel | Native Vite/React static hosting |
| Backend host | Render (not Streamlit) | FastAPI needs a real ASGI host; Streamlit Cloud does not provide one |
| Data mode (v1) | JSON fallback | Avoid Postgres/pgvector/torch on free tier |
| LLM | Groq | Already integrated; key stays server-side |
| API base URL | Absolute Render origin | Matches FastAPI paths; Vite `/api` proxy is local-only |
