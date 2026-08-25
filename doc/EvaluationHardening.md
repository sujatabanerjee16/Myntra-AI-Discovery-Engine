# Phase 6 — Evaluation & Hardening

Phase 6 makes the discovery engine **trustworthy and observable**: it measures retrieval relevance, grounding faithfulness, and taxonomy quality; logs auditable RAG traces and pipeline metrics; tunes guardrails; and adds cost controls via caching.

---

## Evaluation Suite

Golden datasets live in `data/eval/`:

| File | Measures |
| --- | --- |
| `retrieval.json` | Hit@k and MRR for labeled business queries |
| `taxonomy.json` | Reason-category classification accuracy |
| `faithfulness.json` | Answer support against evidence excerpts |

Run from the project root:

```bash
python -m eval.run
python -m eval.run --no-persist --no-live
python -m eval.run --output reports/latest_eval.json
```

The CLI writes `data/eval_report.json` (configurable via `EVAL_REPORT_PATH`) and optionally persists an `EvalRun` row when PostgreSQL is available.

### Targets (defaults)

| Metric | Target | Config |
| --- | --- | --- |
| Retrieval hit@k | ≥ 80% | `EVAL_RETRIEVAL_HIT_TARGET`, `EVAL_RETRIEVAL_HIT_AT_K` |
| Grounding faithfulness | ≥ 85% | `EVAL_FAITHFULNESS_TARGET` |
| Taxonomy accuracy | ≥ 80% | `EVAL_TAXONOMY_ACCURACY_TARGET` |

---

## Guardrails (tuned thresholds)

Based on sample-corpus evaluation, guardrails were relaxed slightly to reduce false refusals while keeping low-evidence questions honest:

| Setting | Value | Purpose |
| --- | --- | --- |
| `RAG_MIN_TOP_SCORE` | 0.38 | Minimum best-chunk similarity |
| `RAG_MIN_AVG_SCORE` | 0.32 | Minimum average reranked score |
| `RAG_MIN_CHUNKS` | 1 | Minimum evidence excerpts |

The assistant still refuses when retrieval scores are below these thresholds and records an `AnswerTrace` with `insufficient_evidence=true`.

---

## Observability

### RAG traces

Every grounded answer persists an `AnswerTrace` with:

- retrieved chunk IDs, citations, confidence, limitations
- `duration_ms` — end-to-end pipeline latency
- `insufficient_evidence` — whether guardrails refused to answer

Structured logs are emitted via `common.observability.log_rag_trace`.

### Pipeline runs

Ingestion runs persist a `PipelineRun` row with duration, success flag, and stats (documents/chunks created, sources).

### API endpoints

| Endpoint | Description |
| --- | --- |
| `GET /observability/quality` | Combined quality dashboard payload |
| `GET /observability/cost-controls` | Cache hit/miss statistics |
| `GET /observability/eval/latest` | Latest eval summary vs targets |
| `POST /observability/eval/run` | Trigger evaluation suite |
| `GET /observability/pipeline-runs` | List pipeline run metrics |
| `GET /observability/eval-runs` | List evaluation runs |
| `GET /observability/traces/{id}` | Full auditable trace detail |

---

## Cost Controls

| Cache | Scope | Config |
| --- | --- | --- |
| **Embedding cache** | Text → vector (SHA-256 keyed, TTL LRU) | `EMBEDDING_CACHE_*` |
| **Retrieval cache** | Query + filters → top-k chunks | `RETRIEVAL_CACHE_*` |

Embedding batching remains in `ingestion/stages/embed.py` (`batch_size=16`). The cache avoids recomputing identical chunk embeddings across pipeline re-runs and repeated retrieval queries.

---

## Quality Dashboard (web)

The React app adds a **Quality** tab showing:

- Latest eval metrics vs targets
- Guardrail thresholds
- Cache hit rates
- Recent RAG traces and pipeline runs

Run the API and web dev server as in Phase 5; open the **Quality** tab or call `GET /observability/quality`.

---

## Exit Criteria (Phase 6)

- [x] Retrieval relevance, faithfulness, and taxonomy quality measured against labeled datasets
- [x] RAG traces and pipeline runs auditable via DB + API
- [x] Guardrail thresholds tuned from eval feedback
- [x] Embedding and retrieval caching for cost control
- [x] Quality/cost dashboard for PM and engineering review
