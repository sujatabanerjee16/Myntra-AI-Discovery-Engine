"""BUG-01 spot-check: two queries should differ under vector retrieval."""

from __future__ import annotations

from common.config import get_settings
from common.db import SessionLocal, database_available
from assistant.orchestrator import answer_question
from storage.retrieval import search_chunks


def main() -> None:
    get_settings.cache_clear()
    database_available.cache_clear()
    assert database_available(), "Neon not available"
    settings = get_settings()
    session = SessionLocal()
    queries = [
        "why does no one buy the stuff they save",
        "help me understand my wishlist users",
    ]
    try:
        print("=== top chunks ===", flush=True)
        for q in queries:
            chunks = search_chunks(
                session,
                query_text=q,
                top_k=settings.retrieval_top_k,
                filters=None,
            )
            print(q, flush=True)
            for i, c in enumerate(chunks[:3], 1):
                snippet = c.text.replace("\n", " ")[:120]
                print(f"  {i}. score={c.score:.3f} {snippet}", flush=True)
            print(flush=True)

        print("=== answers ===", flush=True)
        answers: list[str] = []
        for q in queries:
            r = answer_question(session, question=q, filters=None, persist_trace=False)
            answers.append(r.answer)
            print(q, flush=True)
            print(r.answer[:200].replace("\n", " "), flush=True)
            print(flush=True)

        same_open = answers[0][:80] == answers[1][:80]
        print("openings_identical:", same_open, flush=True)
    finally:
        session.close()


if __name__ == "__main__":
    main()
