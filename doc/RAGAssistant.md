# Phase 4 — Grounded RAG Assistant

Answers business questions using only retrieved corpus evidence and dashboard aggregates, with citations and confidence.

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
uvicorn api.main:app --reload
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
curl -X POST http://localhost:8000/assistant/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"What prevents wishlisted products from being purchased?\"}"
```

Optional body fields:

- `filters` — same metadata filters as `POST /retrieval/search`
- `persist_trace` — store an `AnswerTrace` row (default `true`)

## Guardrails

- Refuses or flags answers when retrieval scores are below configured thresholds.
- Requires citations linked to retrieved chunk IDs.
- Surfaces source limitations and aggregate run version on every response.
- No Groq key → template synthesis from top excerpts (still grounded, no speculation).

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `RETRIEVAL_TOP_K` | 8 | Initial vector retrieval count |
| `RAG_RERANK_TOP_K` | 6 | Excerpts passed to the LLM |
| `RAG_MIN_CHUNKS` | 1 | Minimum retrieved excerpts |
| `RAG_MIN_TOP_SCORE` | 0.40 | Minimum best-match score |
| `RAG_MIN_AVG_SCORE` | 0.35 | Minimum average retrieval score |
| `GROQ_API_KEY` | — | Groq API key for generation |
| `GROQ_MODEL` | llama-3.3-70b-versatile | Groq model name |

## Key questions supported

The assistant is designed to answer the nine stakeholder questions in [`doc/context.md`](./context.md) §9, for example:

1. Why do users add fashion products to their wishlist?
2. What prevents wishlisted products from being purchased?
3. When is the wishlist real purchase intent vs casual bookmarking?

Each answer includes supporting excerpts, confidence, and explicit limitations about public-evidence coverage.
