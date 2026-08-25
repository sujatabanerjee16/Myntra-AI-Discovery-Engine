# Phase 5 — Insight Dashboard + Ask AI (Single Page)

Interactive React **unified page**: wishlist non-conversion insight dashboard with **Ask AI** (suggested questions + grounded chat) on the same page.

## Prerequisites

```bash
alembic upgrade head
python -m storage.load_corpus --json-path data/scraped_corpus.json
python -m analytics.run
uvicorn api.main:app --reload
```

Set `GROQ_API_KEY` in `.env` for live assistant answers (you've already configured this).

## Run the dashboard

```bash
cd web
npm install
npm run dev
```

Open http://127.0.0.1:5173 (Vite dev) or http://127.0.0.1:8000 (integrated API + built UI).

To start both servers on Windows:

```powershell
.\scripts\start-dev.ps1
```

If port 5173 is not running, use **http://127.0.0.1:8000** — the API serves the built dashboard from `web/dist` automatically.

## Dashboard + Ask AI features (single page)

| View | Description |
| --- | --- |
| **Ranked reasons** | Top non-conversion categories with confidence + evidence volume |
| **Intent chart** | Active shortlist vs passive bookmarking by reason |
| **Segment comparison** | Evidence volume across user segments |
| **Friction heatmap** | Reason × segment intensity grid |
| **Evidence drill-down** | Source excerpts for a selected reason |
| **Emerging themes** | Theme clusters from semantic analytics |
| **Ask AI panel** | Suggested questions + grounded Q&A with citations, **docked on the same page** (not a separate primary route) |

Filters: segment, category, occasion, price band, reason category.

## Insights API (Phase 5 additions)

| Endpoint | Description |
| --- | --- |
| `GET /insights/filters` | Available filter values |
| `GET /insights/comparisons` | Segment/category comparisons |
| `GET /insights/heatmap` | Friction heatmap cells |
| `GET /insights/intent` | Intent-type breakdown |
| `GET /insights/trends` | Journey stages + emerging themes |
| `GET /insights/evidence` | Evidence excerpts for drill-down |

Existing endpoints (`/insights/reasons`, `/insights/clusters`) now accept optional dashboard filter query params where applicable.
