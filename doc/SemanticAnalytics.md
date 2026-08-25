# Phase 3 — Semantic Analytics Layer

Transforms ingested chunks into structured, confidence-scored insights.

## Capabilities

| Module | Purpose |
| --- | --- |
| `analytics/taxonomy.py` | Classify non-conversion reasons (9-category taxonomy) |
| `analytics/intent.py` | Detect active shortlist vs passive bookmarking |
| `analytics/journey.py` | Map wishlist→purchase journey stage |
| `analytics/confidence.py` | Score insights by evidence, source reliability, quality |
| `analytics/clustering.py` | Group emerging themes by signal/text similarity |
| `analytics/pipeline.py` | Orchestrate analysis and persist `insights` + aggregates |

## Run analytics

```bash
# From existing JSON corpus (no DB required)
python -m analytics.run --json-only --export-json data/insights.json

# Against PostgreSQL chunks
alembic upgrade head
python -m storage.load_corpus --json-path data/scraped_corpus.json
python -m analytics.run
```

## API endpoints

| Endpoint | Description |
| --- | --- |
| `POST /analytics/run` | Run semantic analytics on stored chunks |
| `GET /insights` | List structured insight records |
| `GET /insights/reasons` | Ranked non-conversion reasons |
| `GET /insights/clusters` | Emerging theme clusters |

## Output tables

- `insights` — categorized, tagged, evidence-linked insight records
- `reason_aggregates` — ranked reason categories for dashboard
- `theme_clusters` — emerging theme groupings

Every insight includes: `reason_category`, `intent_type`, `journey_stage`, `segment`, `category`, `evidence_chunk_ids`, `confidence`, and `sources`.
