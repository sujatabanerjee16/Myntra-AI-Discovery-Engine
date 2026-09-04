# Phase 4 — Grounded RAG Assistant

Answers business questions using retrieved corpus evidence and dashboard aggregates. Every in-scope answer shows **public source chips** and a **Confidence: N%** badge.

## Pipeline

```
user question
  → query understanding (filters + reason hints)
  → vector retrieval (pgvector + metadata filters)
  → rerank (vector score + quality + keyword overlap)
  → inject aggregates (ranked reasons, theme clusters)
  → guardrails (evidence threshold)
  → Groq LLM grounded generation (or template fallback)
  → AnswerTrace audit record
```

## Prerequisites

Load corpus and run semantic analytics first (Phases 2–3):

```bash
alembic upgrade head
python -m storage.load_corpus --json-path data/scraped_corpus.json
python -m analytics.run
uvicorn api.main:app --reload --host 127.0.0.1 --port 8010
```

Set `GROQ_API_KEY` in `.env` for LLM generation. Without it, the assistant uses a deterministic template synthesizer (useful for local dev and tests).

## API endpoints

| Endpoint | Description |
| --- | --- |
| `GET /assistant/questions` | Key business questions (`context.md` §9) |
| `POST /assistant/ask` | Grounded Q&A with citations + confidence |
| `GET /assistant/traces` | List `AnswerTrace` audit records |
| `GET /assistant/traces/{id}` | Fetch a single trace |

### Example: ask a question

```bash
curl -X POST http://127.0.0.1:8010/assistant/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"What prevents wishlisted products from being purchased?\"}"
```

Optional body fields:

- `filters` — same metadata filters as `POST /retrieval/search`
- `persist_trace` — store an `AnswerTrace` row (default `true`)

## Guardrails

- Refuses in plain English when retrieval scores are below configured thresholds.
- Requires citations linked to retrieved chunk IDs. Chat chips are **public sources only** (Play Store, Reddit, YouTube, reviews, social). Research/interviews may inform the answer; they do not appear in Show evidence.
- Confidence is a **percentage badge**, never `(confidence 0.84, volume 397)` in the prose.
- No Groq key (or model 404) → template synthesis from top excerpts (still grounded, no speculation).

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `RETRIEVAL_TOP_K` | 8 | Initial vector retrieval count |
| `RAG_RERANK_TOP_K` | 6 | Excerpts passed to the LLM |
| `RAG_MIN_CHUNKS` | 1 | Minimum retrieved excerpts |
| `RAG_MIN_TOP_SCORE` | 0.38 | Minimum best-match score |
| `RAG_MIN_AVG_SCORE` | 0.32 | Minimum average retrieval score |
| `GROQ_API_KEY` | — | Groq API key for generation |
| `GROQ_MODEL` | llama-3.3-70b-versatile | Groq model name |

## Key questions supported

The assistant always treats the nine starter questions in [`assistant/questions.py`](../assistant/questions.py) / [`doc/context.md`](./context.md) §9 as in-domain, for example:

1. Why do users add fashion products to their wishlist?
2. What prevents wishlisted products from eventually being purchased?
3. What unmet needs emerge consistently across user conversations?

It does **not** treat “How do 18–24 vs 25–35 differ?” as a starter question. Each in-scope answer includes public excerpts plus `Confidence: N%`.
