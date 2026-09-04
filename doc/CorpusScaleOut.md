# Phase 7 — Corpus Scale-Out

Phase 7 broadens the ingestion pipeline to **all six source types** with incremental refresh, cross-source validation, and an optional vector-backend migration path.

---

## Source Types

| Source | Connector | Default data |
| --- | --- | --- |
| `research` | Dual Excel surveys + interviews | `Myntra Wishlist.xlsx` + `Your Wishlist Habits (Responses).xlsx` — RAG only, not a dashboard tile |
| `play_store` | Google Play Store scraper | Live scrape (filtered) |
| `reddit` | Public Reddit search JSON | `data/seeds/reddit.json` |
| `youtube` | YouTube Data API (optional) | `data/seeds/youtube.json` |
| `product_review` | Exported review JSON | `data/seeds/product_review.json` |
| `social` | Exported social mention JSON | `data/seeds/social.json` |

Live Reddit/YouTube fetching is **disabled by default**; enable via `.env` when API/network access is available.

---

## Full corpus run

```bash
# All six sources → JSON export (no DB)
python -m ingestion.run --json-only --skip-embed

# Persist to PostgreSQL + refresh aggregates
python -m ingestion.run
```

---

## Incremental refresh

Per-source refresh intervals (hours) are configurable in `.env`:

| Variable | Default |
| --- | --- |
| `SOURCE_REFRESH_RESEARCH_HOURS` | 168 |
| `SOURCE_REFRESH_PLAY_STORE_HOURS` | 24 |
| `SOURCE_REFRESH_REDDIT_HOURS` | 12 |
| `SOURCE_REFRESH_YOUTUBE_HOURS` | 24 |
| `SOURCE_REFRESH_PRODUCT_REVIEW_HOURS` | 72 |
| `SOURCE_REFRESH_SOCIAL_HOURS` | 12 |

```bash
# Refresh only sources that are due
python -m ingestion.refresh

# Force refresh specific sources
python -m ingestion.refresh --sources reddit,social --force
```

When `RECOMPUTE_ANALYTICS_ON_REFRESH=true` (default), semantic analytics and confidence scores are recomputed after each refresh.

---

## API

| Endpoint | Description |
| --- | --- |
| `GET /ingestion/sources` | Supported sources, refresh state, coverage |
| `POST /ingestion/refresh` | Trigger incremental refresh |

---

## Cross-source validation

Each pipeline run produces a validation report:

- records per source
- cross-source duplicate fingerprints
- records missing priority signals
- average text length by source

Reports are included in pipeline stats and refresh API responses.

---

## Vector backend migration path

`VECTOR_BACKEND=pgvector` (default) uses PostgreSQL + pgvector.

Set `VECTOR_BACKEND=qdrant` to prepare for a dedicated vector DB; the Qdrant adapter raises a clear `NotImplementedError` until the migration is completed.

---

## Exit criteria

- [x] All six source types have connectors and seed/live paths
- [x] Public sources power the scrape strip; research stays off the dashboard KPI
- [x] Incremental per-source refresh scheduling
- [x] Cross-source dedupe/quality validation
- [x] Analytics/confidence recompute on refresh
- [x] Optional vector DB migration abstraction
