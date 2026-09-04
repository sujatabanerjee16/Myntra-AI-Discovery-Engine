# Phase 8 — Internal Data & Ground-Truth Metric

Phase 8 integrates **Myntra internal behavioral data** with public-evidence insights, computes the **wishlist-to-purchase 30-day conversion** metric, and adds a **PM feedback loop** to validate or flag reason categories.

---

## Internal Event Connector

Load wishlist/funnel events from JSON (sample: `data/seeds/internal_wishlist_events.json`):

| Field | Description |
| --- | --- |
| `user_hash` | Anonymized user identifier |
| `product_id` | Wishlisted/purchased SKU |
| `event_type` | `wishlist_add`, `purchase`, `product_view`, … |
| `segment` | Behavioral tag when present (price_sensitive, fit_uncertain, …). Research age bands may exist on events; they are **not** dashboard cards. |
| `event_at` | Event timestamp (ISO-8601) |

```bash
python -m internal.run
```

---

## Ground-Truth Metric

**Wishlist-to-purchase conversion (30 days)** = share of users with at least one `wishlist_add` who purchase the same product within 30 days.

The pipeline:
1. Ingests internal events into `wishlist_events`
2. Computes and stores a `conversion_snapshots` row
3. Joins public `reason_aggregates` with internal segment non-conversion rates
4. Writes `reason_corroborations` with corroboration scores

---

## PM Feedback Loop

PMs can validate or flag reason categories via:

- `POST /internal/feedback` — record verdict (`validated`, `flagged`, `needs_review`)
- `GET /internal/feedback` — list feedback history

Verdicts adjust confidence:
- **Validated** +0.05
- **Flagged** −0.12
- **Needs review** −0.03

---

## API Endpoints

| Endpoint | Description |
| --- | --- |
| `GET /internal/conversion` | Latest 30-day conversion snapshot |
| `GET /internal/corroboration` | Public reason vs internal behavior join |
| `POST /internal/compute` | Run full internal pipeline |
| `POST /internal/feedback` | Submit PM feedback |
| `GET /internal/feedback` | List PM feedback |

---

## Dashboard

The live app has three tabs. There is **no Conversion tab**.

- 30-day conversion and corroboration stay on the internal API (`GET /internal/conversion`, `GET /internal/corroboration`).
- PM feedback (validate / flag a reason) is the **PM calibration** block on the Dashboard.

---

## Scale-Out Hooks

- `VECTOR_BACKEND=qdrant` — vector DB migration path (stub from Phase 7)
- `ingestion/streaming.py` — streaming ingestion bus placeholder for Kafka/Kinesis
- `STREAMING_INGESTION_ENABLED` — feature flag for future real-time refresh

---

## Exit Criteria

- [x] Internal event connector into analytical store
- [x] Computed wishlist-to-purchase 30-day conversion metric
- [x] Public-evidence reasons joined with observed conversion behavior
- [x] PM feedback loop for taxonomy/confidence refinement
- [x] Scale-out hooks for vector DB and streaming ingestion
