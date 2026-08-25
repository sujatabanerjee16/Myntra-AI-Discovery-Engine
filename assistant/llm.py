"""Grounded answer generation via Groq LLM with a deterministic fallback."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from assistant.schemas import AggregateContext, Citation
from assistant.synthesis import synthesize_grounded_answer
from common.config import get_settings
from storage.schemas import RetrievedChunk

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a grounded research assistant for Myntra wishlist conversion analysis.
Answer ONLY using the provided evidence excerpts and aggregate facts.
Rules:
- Do not speculate or invent facts not present in the context.
- Every claim must be supported by the retrieved excerpts or aggregate facts.
- If evidence is partial, say so explicitly.
- Write a concise executive summary in 5-6 sentences maximum.
- Synthesize patterns across excerpts into clear PM-ready prose.
- Always capitalize the pronoun "I" (never lowercase "i" as a pronoun).
- Do NOT quote raw survey transcripts, timestamps, chunk IDs, or relevance scores.
- Do NOT use meta phrasing such as "Based on retrieved corpus evidence" or
  "The strongest signal indicates".
- Return valid JSON with keys: answer (string), cited_indices (list of integers
  referencing excerpt numbers).
"""


@dataclass(frozen=True, slots=True)
class GeneratedAnswer:
    answer: str
    cited_indices: list[int]


def _truncate(text: str, limit: int = 220) -> str:
    cleaned = text.strip().replace("\n", " ")
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def _template_generate(
    question: str,
    chunks: list[RetrievedChunk],
    aggregates: AggregateContext | None = None,
) -> GeneratedAnswer:
    """Deterministic synthesis used when Groq is unavailable (tests/local dev)."""
    answer = synthesize_grounded_answer(question, chunks, aggregates)
    return GeneratedAnswer(
        answer=_normalize_pronoun_i(answer),
        cited_indices=list(range(1, min(len(chunks), 3) + 1)),
    )


def _groq_generate(question: str, context: str) -> GeneratedAnswer:
    settings = get_settings()
    from groq import Groq

    client = Groq(api_key=settings.groq_api_key)
    user_prompt = (
        f"Question: {question}\n\n"
        f"Grounded context:\n{context}\n\n"
        "Respond with JSON only."
    )

    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    payload = json.loads(raw)
    answer = str(payload.get("answer", "")).strip()
    cited_indices = payload.get("cited_indices") or []
    indices = [int(value) for value in cited_indices if isinstance(value, int | float)]
    if not answer:
        raise ValueError("Groq returned an empty answer")
    return GeneratedAnswer(answer=_normalize_pronoun_i(answer), cited_indices=indices)


_PRONOUN_I_RE = re.compile(r"(?<![A-Za-z])i(?![A-Za-z])")
_PRONOUN_I_CONTRACTION_RE = re.compile(r"(?<![A-Za-z])i'(m|ve|d|ll|re)(?![A-Za-z])", re.IGNORECASE)


def _normalize_pronoun_i(text: str) -> str:
    """Ensure standalone pronoun i / i'm appear as I / I'm."""
    fixed = _PRONOUN_I_RE.sub("I", text)
    return _PRONOUN_I_CONTRACTION_RE.sub(lambda m: f"I'{m.group(1).lower()}", fixed)


def generate_grounded_answer(
    question: str,
    context: str,
    chunks: list[RetrievedChunk],
    aggregates: AggregateContext | None = None,
) -> GeneratedAnswer:
    """Generate a grounded answer; fall back to template synthesis without an API key."""
    settings = get_settings()
    if settings.groq_api_key:
        try:
            return _groq_generate(question, context)
        except Exception:
            logger.exception("Groq generation failed; using template fallback")
    return _template_generate(question, chunks, aggregates)


def select_citations(
    chunks: list[RetrievedChunk],
    cited_indices: list[int],
    *,
    max_citations: int = 5,
) -> list[Citation]:
    """Map LLM cited indices back to chunk citations."""
    if not chunks:
        return []

    selected: list[RetrievedChunk] = []
    for index in cited_indices:
        if 1 <= index <= len(chunks):
            selected.append(chunks[index - 1])

    if not selected:
        selected = chunks[:max_citations]

    citations: list[Citation] = []
    seen: set[str] = set()
    for chunk in selected:
        key = str(chunk.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            Citation(
                chunk_id=chunk.chunk_id,
                source=chunk.source.value,
                excerpt=_truncate(chunk.text, 240),
                score=chunk.score,
            )
        )
        if len(citations) >= max_citations:
            break
    return citations
