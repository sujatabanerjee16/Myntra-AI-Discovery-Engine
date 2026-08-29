"""Grounding guardrails: evidence checks and citation validation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from assistant.query import is_age_segment_compare_question
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
    unsupported_terms: tuple[str, ...] = ()


def assess_evidence(
    chunks: list[RetrievedChunk],
    *,
    question: str | None = None,
) -> EvidenceAssessment:
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
            reason=("Retrieved evidence similarity is too low to support a grounded answer."),
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

    # Topical similarity is not enough: refuse when the question asserts
    # specific entities/claims that never appear in retrieved evidence
    # (e.g. "left-handed users … on Tuesdays").
    # Age-cohort compare questions are anaphoric ("these behaviors") and
    # should be judged on retrieved age-tagged evidence, not those verbs.
    if question and not is_age_segment_compare_question(question):
        distinctive = distinctive_question_terms(question)
        if distinctive:
            evidence_tokens = _evidence_token_set(chunks)
            evidence_text = " ".join(chunk.text.lower() for chunk in chunks)
            supported = [
                term
                for term in distinctive
                if _term_supported(term, evidence_tokens, evidence_text)
            ]
            if not supported:
                unsupported = sorted(distinctive)
                shown = ", ".join(unsupported[:6])
                return EvidenceAssessment(
                    sufficient=False,
                    reason=(
                        "Retrieved excerpts are topically related but do not mention "
                        f"the question's specific claims ({shown})."
                    ),
                    chunk_count=len(chunks),
                    top_score=top_score,
                    avg_score=avg_score,
                    unsupported_terms=tuple(unsupported),
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
        "wishlist",
        "wish list",
        "wishlisted",
        "bookmark",
        "shortlist",
        "cart",
        "checkout",
        "buy",
        "buying",
        "bought",
        "purchase",
        "purchasing",
        "purchased",
        "convert",
        "conversion",
        "abandon",
        "abandoned",
        "shop",
        "shopper",
        "shoppers",
        "shopping",
        "customer",
        "customers",
        "fashion",
        "apparel",
        "clothing",
        "clothes",
        "outfit",
        "dress",
        "dresses",
        "footwear",
        "sneakers",
        "accessory",
        "accessories",
        "beauty",
        "sizing",
        "fit",
        "fitting",
        "discount",
        "sale",
        "coupon",
        "promo",
        "brand",
        "brands",
        "product",
        "products",
        "review",
        "reviews",
        "myntra",
        "nykaa",
        "ajio",
        "flipkart",
        "occasion",
        "wedding",
        "festive",
        "delivery",
        "styling",
        "stylist",
        "assortment",
        "catalog",
        "recommend",
        "recommendation",
        "online order",
        "online orders",
        "saved items",
        "saving items",
        "save items",
        # Common fashion descriptors that appear in Indian e-commerce questions
        "ethnic",
        "kurta",
        "kurtas",
        "saree",
        "sari",
        "lehenga",
        "segment",
        "segments",
        "cohort",
        "cohorts",
    }
)

# Transliterated Hinglish/Hindi shopping terms (scope gate only — not translation).
_HINGLISH_DOMAIN_TERMS: frozenset[str] = frozenset(
    {
        # buy / purchase
        "kharid",
        "kharida",
        "kharidna",
        "kharidte",
        "kharidti",
        "kharidenge",
        "kharidari",
        "kharido",
        # cheap / expensive
        "sasta",
        "saste",
        "sasti",
        "mehnga",
        "mehngi",
        "mehange",
        "mehengi",
        "mehanga",
        # discount
        "chhoot",
        "chhot",
        # clothes / wear
        "kapda",
        "kapde",
        "libaas",
        "poshak",
        "kapdon",
        # like / preference (wishlist-adjacent intent)
        "pasand",
        "pasanda",
    }
)

# Generic on their own; require ≥2 distinct hits to count as in-domain.
_WEAK_DOMAIN_TERMS: frozenset[str] = frozenset(
    {
        "order",
        "orders",
        "complete",
        "completing",
        "completed",
        "save",
        "saving",
        "saved",
        "item",
        "items",
        "online",
    }
)

_WORD_RE = re.compile(r"[a-z']+")

# Framing / stop language skipped when extracting "specific claims" from a question.
# Domain vocabulary is also skipped — those terms are almost always present and do
# not distinguish fabricated premises from legitimate wishlist questions.
_CLAIM_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "then",
        "so",
        "as",
        "at",
        "by",
        "for",
        "from",
        "in",
        "into",
        "of",
        "on",
        "onto",
        "to",
        "with",
        "without",
        "about",
        "after",
        "before",
        "between",
        "over",
        "under",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "am",
        "do",
        "does",
        "did",
        "doing",
        "have",
        "has",
        "had",
        "having",
        "can",
        "could",
        "would",
        "should",
        "will",
        "shall",
        "may",
        "might",
        "must",
        "not",
        "no",
        "nor",
        "too",
        "very",
        "just",
        "only",
        "also",
        "than",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "they",
        "them",
        "their",
        "there",
        "here",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "when",
        "where",
        "why",
        "how",
        "i",
        "me",
        "my",
        "mine",
        "we",
        "our",
        "ours",
        "you",
        "your",
        "yours",
        "he",
        "him",
        "his",
        "she",
        "her",
        "hers",
    }
)

_CLAIM_FRAME_TERMS: frozenset[str] = frozenset(
    {
        "help",
        "understand",
        "explain",
        "tell",
        "show",
        "please",
        "thanks",
        "analyze",
        "analyse",
        "analysis",
        "insight",
        "insights",
        "pattern",
        "patterns",
        "behavior",
        "behaviors",
        "behaviour",
        "behaviours",
        "differ",
        "differs",
        "different",
        "difference",
        "differences",
        "reason",
        "reasons",
        "cause",
        "causes",
        "prevent",
        "prevents",
        "preventing",
        "block",
        "blocks",
        "blocking",
        "stop",
        "stops",
        "stopping",
        "make",
        "makes",
        "making",
        "get",
        "gets",
        "getting",
        "give",
        "gives",
        "need",
        "needs",
        "want",
        "wants",
        "know",
        "knows",
        "find",
        "finds",
        "see",
        "sees",
        "look",
        "looking",
        "ask",
        "asking",
        "question",
        "questions",
        "answer",
        "someone",
        "somebody",
        "people",
        "person",
        "persons",
        "user",
        "users",
        "folks",
        "stuff",
        "thing",
        "things",
        "something",
        "anything",
        "everything",
        "nothing",
        "finally",
        "still",
        "often",
        "always",
        "never",
        "really",
        "actually",
        "basically",
        "generally",
        "usually",
        "maybe",
        "perhaps",
        "like",
        "vs",
        "versus",
        "compare",
        "compared",
        "comparison",
        "across",
        "among",
        "within",
        "using",
        "based",
        "related",
        "regarding",
        "around",
        "drive",
        "drives",
        "driving",
        "lead",
        "leads",
        "leading",
        "happen",
        "happens",
        "happening",
        "keep",
        "keeps",
        "keeping",
    }
)


def _claim_skip_terms() -> frozenset[str]:
    domain_tokens = {
        term
        for term in (_DOMAIN_TERMS | _WEAK_DOMAIN_TERMS | _HINGLISH_DOMAIN_TERMS)
        if " " not in term
    }
    return frozenset(_CLAIM_STOPWORDS | _CLAIM_FRAME_TERMS | domain_tokens)


def distinctive_question_terms(question: str) -> set[str]:
    """Extract specific/rare tokens that look like factual claims in the question."""
    skip = _claim_skip_terms()
    tokens = _WORD_RE.findall(question.lower())
    return {token for token in tokens if len(token) >= 4 and token not in skip}


def _evidence_token_set(chunks: list[RetrievedChunk]) -> set[str]:
    text = " ".join(chunk.text.lower() for chunk in chunks)
    return set(_WORD_RE.findall(text))


def _term_supported(term: str, evidence_tokens: set[str], evidence_text: str) -> bool:
    if term in evidence_tokens or term in evidence_text:
        return True
    if term.endswith("s") and len(term) > 4 and term[:-1] in evidence_tokens:
        return True
    if f"{term}s" in evidence_tokens:
        return True
    return False


def unsupported_claim_terms(
    question: str,
    chunks: list[RetrievedChunk],
) -> list[str]:
    """Return distinctive question terms that never appear in retrieved evidence."""
    distinctive = distinctive_question_terms(question)
    if not distinctive:
        return []
    evidence_tokens = _evidence_token_set(chunks)
    evidence_text = " ".join(chunk.text.lower() for chunk in chunks)
    return sorted(
        term for term in distinctive if not _term_supported(term, evidence_tokens, evidence_text)
    )


def question_in_scope(question: str) -> bool:
    """Return True if the question uses any in-domain vocabulary.

    Retrieval always returns the corpus's nearest chunks, so score thresholds
    alone cannot reject off-topic questions (e.g. "weather on Mars"). This
    lexical gate ensures we refuse rather than fabricate a wishlist answer.
    """
    lowered = question.lower()
    # Canned segment Qs are anaphoric ("these behaviors") and omit "wishlist".
    if is_age_segment_compare_question(question):
        return True
    if any(" " in term and term in lowered for term in _DOMAIN_TERMS):
        return True
    tokens = set(_WORD_RE.findall(lowered))
    if tokens & _DOMAIN_TERMS:
        return True
    if tokens & _HINGLISH_DOMAIN_TERMS:
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
    return [f"[{item.source}] {item.excerpt} (chunk_id={item.chunk_id})" for item in citations]


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
        parts.append("Question hints at categories: " + ", ".join(reason_categories) + ".")
    if len(chunks) < 3:
        parts.append("Limited number of supporting excerpts; treat conclusions cautiously.")

    return " ".join(parts)
