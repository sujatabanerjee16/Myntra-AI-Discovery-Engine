"""Grounded RAG assistant orchestrator (Phase 4)."""

__all__ = ["answer_question"]


def __getattr__(name: str):
    if name == "answer_question":
        from assistant.orchestrator import answer_question

        return answer_question
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
