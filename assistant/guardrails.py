"""Grounding guardrails: evidence checks and citation validation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from assistant.schemas import Citation
from common.config import get_settings
from storage.schemas import RetrievedChunk


@dataclass(frozen=True, slots=True)
class EvidenceAssessment:
    sufficient: bool
    reason: str
    chunk_count: int
    top_score: float
    avg_score: float


def assess_evidence(chunks: list[RetrievedChunk]) -> EvidenceAssessment:
    """Decide whether retrieved evidence is strong enough to answer."""
    settings = get_settings()

    if not chunks:
        return EvidenceAssessment(
            sufficient=False,
            reason="No relevant evidence was retrieved from the corpus.",
            chunk_count=0,
            top_score=0.0,
            avg_score=0.0,
        )

    if len(chunks) < settings.rag_min_chunks:
        return EvidenceAssessment(
            sufficient=False,
            reason=(
                f"Only {len(chunks)} evidence excerpt(s) matched; "
                f"at least {settings.rag_min_chunks} are required."
            ),
            chunk_count=len(chunks),
            top_score=chunks[0].score,
            avg_score=sum(chunk.score for chunk in chunks) / len(chunks),
        )

    top_score = chunks[0].score
    avg_score = sum(chunk.score for chunk in chunks) / len(chunks)

    if top_score < settings.rag_min_top_score:
        return EvidenceAssessment(
            sufficient=False,
            reason=(
                "Retrieved evidence similarity is too low to support a grounded answer."
            ),
            chunk_count=len(chunks),
            top_score=top_score,
            avg_score=avg_score,
        )

    if avg_score < settings.rag_min_avg_score:
        return EvidenceAssessment(
            sufficient=False,
            reason="Average retrieval relevance is below the confidence threshold.",
            chunk_count=len(chunks),
            top_score=top_score,
            avg_score=avg_score,
        )

    return EvidenceAssessment(
        sufficient=True,
        reason="Sufficient evidence retrieved.",
        chunk_count=len(chunks),
        top_score=top_score,
        avg_score=avg_score,
    )


def build_insufficient_evidence_answer(question: str, assessment: EvidenceAssessment) -> str:
    """Return an honest refusal when evidence is too weak."""
    return (
        "I cannot provide a grounded answer to this question with the available corpus. "
        f"{assessment.reason} "
        "Try broadening the question, removing filters, or adding more source data."
    )


# Vocabulary that signals a question is within this assistant's domain:
# wishlist behavior, shopping/conversion, and fashion e-commerce.
#
# Deliberately excludes ultra-generic words that frequently appear in unrelated
# questions (e.g. "price", "cost", "user", "return") so that a query like
# "the price of Bitcoin" is not mistaken for an in-domain question. Domain
# price/return questions almost always also carry a stronger term below
# (wishlist, buy, sale, purchase, discount, product, ...).
#
# Weaker commerce phrasing ("order", "save", "item", "complete") is handled
# via _WEAK_DOMAIN_TERMS: those tokens only count when two or more co-occur,
# so "complete their online orders after saving items" passes while
# "complete my homework" alone does not.
_DOMAIN_TERMS: frozenset[str] = frozenset(
    {
        "wishlist", "wish list", "wishlisted", "bookmark", "shortlist",
        "cart", "checkout", "buy", "buying", "bought", "purchase", "purchasing",
        "purchased", "convert", "conversion", "abandon", "abandoned",
        "shop", "shopper", "shoppers", "shopping", "customer", "customers",
        "fashion", "apparel", "clothing", "clothes", "outfit", "dress", "dresses",
        "footwear", "sneakers", "accessory", "accessories", "beauty",
        "sizing", "fit", "fitting", "discount", "sale", "coupon", "promo",
        "brand", "brands", "product", "products", "review", "reviews",
        "myntra", "nykaa", "ajio", "flipkart", "occasion", "wedding", "festive",
        "delivery", "styling", "stylist", "assortment", "catalog",
        "recommend", "recommendation",
        "online order", "online orders", "saved items", "saving items",
        "save items",
    }
)

# Generic on their own; require ≥2 distinct hits to count as in-domain.
_WEAK_DOMAIN_TERMS: frozenset[str] = frozenset(
    {
        "order", "orders", "complete", "completing", "completed",
        "save", "saving", "saved", "item", "items", "online",
    }
)

_WORD_RE = re.compile(r"[a-z']+")


def question_in_scope(question: str) -> bool:
    """Return True if the question uses any in-domain vocabulary.

    Retrieval always returns the corpus's nearest chunks, so score thresholds
    alone cannot reject off-topic questions (e.g. "weather on Mars"). This
    lexical gate ensures we refuse rather than fabricate a wishlist answer.
    """
    lowered = question.lower()
    if any(" " in term and term in lowered for term in _DOMAIN_TERMS):
        return True
    tokens = set(_WORD_RE.findall(lowered))
    if tokens & _DOMAIN_TERMS:
        return True
    return len(tokens & _WEAK_DOMAIN_TERMS) >= 2


def build_out_of_scope_answer(question: str) -> str:
    """Return an honest refusal when a question is outside the assistant's domain."""
    return (
        "That question is outside what this assistant can answer. I only cover "
        "wishlist behavior, purchase conversion, and fashion e-commerce insights "
        "(e.g. Myntra, Nykaa, Ajio) grounded in shopper feedback. "
        "Try asking about why users wishlist items, what blocks purchases, or how "
        "platforms compare."
    )


def citations_from_chunks(
    chunks: list[RetrievedChunk],
    *,
    max_citations: int = 5,
) -> list[Citation]:
    """Build citation objects from retrieved chunks."""
    citations: list[Citation] = []
    for chunk in chunks[:max_citations]:
        excerpt = chunk.text.strip().replace("\n", " ")
        if len(excerpt) > 240:
            excerpt = excerpt[:237] + "..."
        citations.append(
            Citation(
                chunk_id=chunk.chunk_id,
                source=chunk.source.value,
                excerpt=excerpt,
                score=chunk.score,
            )
        )
    return citations


def format_trace_citations(citations: list[Citation]) -> list[str]:
    """Serialize citations for AnswerTrace storage."""
    return [
        f"[{item.source}] {item.excerpt} (chunk_id={item.chunk_id})"
        for item in citations
    ]


def compute_answer_confidence(
    chunks: list[RetrievedChunk],
    aggregate_confidences: list[float],
) -> float:
    """Blend retrieval scores with aggregate confidence when available."""
    if not chunks:
        return 0.0

    retrieval_score = sum(chunk.score for chunk in chunks) / len(chunks)
    if aggregate_confidences:
        aggregate_score = sum(aggregate_confidences) / len(aggregate_confidences)
        combined = (0.65 * retrieval_score) + (0.35 * aggregate_score)
    else:
        combined = retrieval_score

    return round(min(max(combined, 0.0), 1.0), 3)


def build_limitations(
    chunks: list[RetrievedChunk],
    *,
    run_version: str | None,
    reason_categories: list[str],
) -> str:
    """Describe source coverage caveats for the answer."""
    sources = sorted({chunk.source.value for chunk in chunks})
    source_text = ", ".join(sources) if sources else "none"

    parts = [
        "Answers are based on public/research feedback only (Phase 1); "
        "they are directional, not ground-truth conversion data.",
        f"Evidence sources in this answer: {source_text}.",
    ]
    if run_version:
        parts.append(f"Analytics run version: {run_version}.")
    if reason_categories:
        parts.append(
            "Question hints at categories: "
            + ", ".join(reason_categories)
            + "."
        )
    if len(chunks) < 3:
        parts.append("Limited number of supporting excerpts; treat conclusions cautiously.")

    return " ".join(parts)
