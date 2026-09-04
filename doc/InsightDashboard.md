# Phase 5 — Insight Dashboard + Discovery Chat

Interactive React **three-tab** app: scrape-only dashboard, competitive comparison, and cited chat.

## Prerequisites

```bash
alembic upgrade head
python -m storage.load_corpus --json-path data/scraped_corpus.json
python -m analytics.run
uvicorn api.main:app --reload --host 127.0.0.1 --port 8010
```

Set `GROQ_API_KEY` in `.env` for Groq synthesis. Without it (or if the model 404s), Discovery Chat uses template synthesis.

## Run the dashboard

```bash
cd web
npm install
npm run dev
```

Open http://127.0.0.1:5173 (Vite, proxies `/api` → 8010) or http://127.0.0.1:8010 after `npm run build`.

Windows: `.\scripts\start-dev.ps1`

PM walkthrough: http://127.0.0.1:8010/walkthrough

## What the UI shows

| Tab / surface | Description |
| --- | --- |
| **Scrape strip** | **1,217 shopper comments** by source (Play Store 971, Reddit 208, …). Not mixed with the Google Form. |
| **Opportunity Matrix** | Ranked reasons: volume, 0–10 confidence, share. Min-confidence slider (default ≥50%). |
| **Shopper comments** | One public line per reason (YouTube, Play Store, reviews). |
| **Filters** | Category, scrape source, min-confidence. **No age / segment dropdown.** |
| **PM calibration** | Validate or flag a reason. Internal notes only. |
| **Competitive Analysis** | Myntra vs Nykaa vs Ajio motives and barriers. |
| **Discovery Chat** | Starter questions. Every in-scope answer: platform chips + `Confidence: N%`. |

UI labels: **Research & Comparison** (`external_comparison`), **Proof / Photos** (`review_trust`).

Research workbooks stay in the corpus for RAG. They are **not** a dashboard tile or age board.

## Insights API

| Endpoint | Description |
| --- | --- |
| `GET /insights/filters` | Available filter values |
| `GET /insights/reasons` | Ranked reasons (`min_confidence`, sources) |
| `GET /insights/heatmap` | Friction heatmap |
| `GET /insights/heatmap` | Friction heatmap cells |
| `GET /insights/evidence` | Public evidence excerpts |
| `GET /insights/corpus-stats` | Scraped document counts by source |

Vercel first-paints from `web/public/dashboard-bootstrap.json` so launch does not wait on a sleeping API.
