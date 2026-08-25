# Phase 2 — Storage & Data Layer

PostgreSQL + pgvector backs three logical stores:

| Store | Tables | Purpose |
| --- | --- | --- |
| **Document / metadata** | `documents`, `chunks` | Raw text, provenance, chunk lineage |
| **Vector** | `chunks.embedding` + HNSW index | Semantic top-k retrieval |
| **Analytical** | `source_aggregates`, `signal_aggregates`, `dimension_aggregates` | Dashboard-ready counts |

## Migrations

```bash
alembic upgrade head   # applies 0003_phase2_storage (HNSW index + analytical tables)
```

## Load JSON corpus into PostgreSQL

```bash
python -m storage.load_corpus --json-path data/scraped_corpus.json
```

## Retrieval API

`POST /retrieval/search`

```json
{
  "query": "why do users hesitate to buy wishlisted items",
  "top_k": 8,
  "filters": {
    "source": "research",
    "segment": "price_sensitive",
    "signals": ["price_sensitivity_waiting"],
    "min_quality_score": 0.5
  }
}
```

Metadata filters: `source`, `category`, `occasion`, `price_band`, `segment`, `signals`, `min_quality_score`.

## Storage API

| Endpoint | Description |
| --- | --- |
| `GET /storage/stats` | Document/chunk counts by source |
| `GET /storage/documents` | Paginated document list |
| `GET /storage/aggregates/sources` | Source-level analytical aggregates |
| `GET /storage/aggregates/signals` | Priority-signal counts |
| `GET /storage/aggregates/dimensions` | Segment/category heatmap inputs |

See OpenAPI docs at `/docs` when the API is running.
