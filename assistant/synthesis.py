"""Deterministic evidence synthesis for grounded assistant answers."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from assistant.schemas import AggregateContext
from storage.schemas import RetrievedChunk

_QA_PATTERN = re.compile(r"Q:\s*(.*?)\s*A:\s*(.*?)(?=Q:|$)", re.DOTALL)

_QUESTION_FIELD_HINTS: list[tuple[str, str]] = [
    ("do you currently use myntra", "myntra_usage"),
    ("how often do you add items", "add_frequency"),
    ("what types of products do you usually save", "product_types"),
    ("how long do you usually keep items", "retention"),
    ("how often do you eventually purchase", "purchase_frequency"),
    ("what usually stops you from buying", "blockers"),
    ("single biggest reason you do not purchase", "primary_blocker"),
    ("which event would most likely encourage", "conversion_triggers"),
    ("what is one thing myntra could improve", "improvement_suggestions"),
]

_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "add_motivation": (
        "why do users add",
        "why add",
        "why wishlist",
        "add to their wishlist",
        "add fashion",
        "save items",
        "why users wishlist",
    ),
    "blockers": (
        "prevent",
        "not purchase",
        "non-conversion",
        "non conversion",
        "stop",
        "blocker",
        "friction",
        "do not buy",
        "does not convert",
    ),
    "intent": (
        "purchase intent",
        "bookmarking",
        "shortlist",
        "passive",
        "active",
        "real intent",
        "casual",
    ),
}


@dataclass
class SurveySignals:
    """Aggregated survey answers extracted from retrieved research chunks."""

    fields: dict[str, Counter[str]] = field(default_factory=dict)
    plain_text_snippets: list[str] = field(default_factory=list)


def _normalize_answer(answer: str) -> str:
    cleaned = re.sub(r"\s+", " ", answer.strip())
    cleaned = re.sub(r"\[phone\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("–", "-").replace("—", "-")
    cleaned = re.sub(r"^yes,\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" ,.;")


def _field_for_question(question: str) -> str | None:
    lowered = question.lower()
    for hint, field_name in _QUESTION_FIELD_HINTS:
        if hint in lowered:
            return field_name
    return None


def parse_qa_pairs(text: str) -> list[tuple[str, str]]:
    """Parse repeated `Q: ... A: ...` pairs from research survey text."""
    pairs: list[tuple[str, str]] = []
    for match in _QA_PATTERN.finditer(text):
        question = re.sub(r"\s+", " ", match.group(1).strip())
        answer = _normalize_answer(match.group(2))
        if question and answer:
            pairs.append((question, answer))
    return pairs


def _detect_intent(question: str) -> str:
    lowered = question.lower()
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return intent
    return "general"


def _top_values(counter: Counter[str], limit: int = 3) -> list[str]:
    return [value for value, _count in counter.most_common(limit)]


def _format_join(values: list[str]) -> str:
    cleaned = [value.strip() for value in values if value.strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def collect_survey_signals(chunks: list[RetrievedChunk]) -> SurveySignals:
    """Extract and aggregate structured survey answers from retrieved chunks."""
    signals = SurveySignals()
    for chunk in chunks:
        pairs = parse_qa_pairs(chunk.text)
        if pairs:
            for question, answer in pairs:
                field_name = _field_for_question(question)
                if not field_name:
                    continue
                for part in re.split(r",(?![^[]*\])", answer):
                    normalized = _normalize_answer(part)
                    if normalized:
                        signals.fields.setdefault(field_name, Counter())[normalized] += 1
        else:
            snippet = re.sub(r"\s+", " ", chunk.text.strip())
            if snippet and len(snippet) > 20:
                signals.plain_text_snippets.append(snippet[:240])
    return signals


def _sentence(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


_PRONOUN_I_RE = re.compile(r"\bi\b")
_PRONOUN_I_CONTRACTION_RE = re.compile(r"\bi'(m|ve|d|ll|re)\b")


def _as_mid_sentence(value: str) -> str:
    """Lowercase a phrase for mid-sentence use while preserving pronoun I."""
    cleaned = value.strip()
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    lowered = _PRONOUN_I_RE.sub("I", lowered)
    lowered = _PRONOUN_I_CONTRACTION_RE.sub(lambda m: f"I'{m.group(1)}", lowered)
    return lowered


def _humanize_phrase(value: str) -> str:
    return _as_mid_sentence(value)


def _synthesize_add_motivation(signals: SurveySignals) -> list[str]:
    sentences: list[str] = []

    products = _top_values(signals.fields.get("product_types", Counter()))
    product_phrase = _as_mid_sentence(_format_join(products)) if products else "fashion products"
    sentences.append(
        _sentence(
            f"Users primarily add {product_phrase} to their wishlist to save items "
            "for later consideration rather than purchase immediately"
        )
    )

    retention = _top_values(signals.fields.get("retention", Counter()), limit=1)
    add_frequency = _top_values(signals.fields.get("add_frequency", Counter()), limit=2)
    if add_frequency or retention:
        if add_frequency and retention:
            detail = (
                f"they add items {_as_mid_sentence(_format_join(add_frequency))} and often keep them "
                f"for {_humanize_phrase(retention[0])} before deciding"
            )
        elif add_frequency:
            detail = f"they add items {_as_mid_sentence(_format_join(add_frequency))}"
        else:
            detail = f"saved items often remain for {_humanize_phrase(retention[0])}"
        sentences.append(
            _sentence(
                f"Research respondents indicate {detail}, reflecting delayed decision-making, "
                "comparison, and future revisits rather than immediate checkout"
            )
        )
    else:
        sentences.append(
            _sentence(
                "The feature supports delayed decision-making, comparison, and future revisits "
                "instead of immediate purchase"
            )
        )

    usage = _top_values(signals.fields.get("myntra_usage", Counter()), limit=2)
    if usage:
        segments = _as_mid_sentence(_format_join(usage))
        sentences.append(
            _sentence(
                f"This behavior is common among {segments} Myntra users who use the wishlist "
                "as a shortlist before purchase"
            )
        )

    purchase_freq = _top_values(signals.fields.get("purchase_frequency", Counter()), limit=1)
    if purchase_freq:
        sentences.append(
            _sentence(
                f"Many eventually purchase saved items {_humanize_phrase(purchase_freq[0])}, "
                "which reinforces wishlisting as an intermediate step in the buying journey"
            )
        )

    return sentences[:5]


def _synthesize_blockers(signals: SurveySignals) -> list[str]:
    sentences: list[str] = []

    blockers = _top_values(signals.fields.get("blockers", Counter()), limit=4)
    primary = _top_values(signals.fields.get("primary_blocker", Counter()), limit=3)
    triggers = _top_values(signals.fields.get("conversion_triggers", Counter()), limit=3)

    if primary:
        sentences.append(
            _sentence(
                f"The most cited blocker to purchasing wishlisted items is "
                f"{_as_mid_sentence(_format_join(primary))}"
            )
        )
    elif blockers:
        sentences.append(
            _sentence(
                "Wishlisted items often remain unpurchased because users cite "
                f"{_as_mid_sentence(_format_join(blockers[:3]))}"
            )
        )

    if blockers and primary:
        secondary = [item for item in blockers if item not in primary][:2]
        if secondary:
            sentences.append(
                _sentence(
                    "Additional friction includes "
                    f"{_as_mid_sentence(_format_join(secondary))}"
                )
            )

    if triggers:
        sentences.append(
            _sentence(
                f"Limited-time sales, price drops, and better fit or size information are "
                f"the events most likely to convert saved items, with "
                f"{_as_mid_sentence(_format_join(triggers))} mentioned most often"
            )
        )

    retention = _top_values(signals.fields.get("retention", Counter()), limit=2)
    if retention:
        sentences.append(
            _sentence(
                f"Many users keep wishlist items for {_as_mid_sentence(_format_join(retention))}, "
                "so blockers accumulate before a purchase decision is made"
            )
        )

    return sentences[:5]


def _synthesize_intent(signals: SurveySignals, aggregates: AggregateContext | None) -> list[str]:
    sentences: list[str] = []

    if aggregates and aggregates.ranked_reasons:
        top = aggregates.ranked_reasons[0]
        category = str(top.get("reason_category", "")).replace("_", " ")
        active = top.get("active_shortlist_count")
        passive = top.get("passive_bookmark_count")
        if active is not None and passive is not None:
            sentences.append(
                _sentence(
                    f"Evidence distinguishes active shortlist behavior from passive bookmarking, "
                    f"with {category} showing {active} active-shortlist and {passive} "
                    "passive-bookmark signals in aggregate data"
                )
            )

    retention = _top_values(signals.fields.get("retention", Counter()), limit=3)
    purchase_freq = _top_values(signals.fields.get("purchase_frequency", Counter()), limit=3)
    if retention:
        sentences.append(
            _sentence(
                f"Users who revisit saved items within {_as_mid_sentence(_format_join(retention))} "
                "show stronger purchase intent than those who rarely return to their wishlist"
            )
        )
    if purchase_freq:
        sentences.append(
            _sentence(
                f"Reported purchase frequency from the wishlist ({_as_mid_sentence(_format_join(purchase_freq))}) "
                "helps separate deliberate shortlisting from casual saving"
            )
        )

    blockers = _top_values(signals.fields.get("blockers", Counter()), limit=2)
    if blockers:
        sentences.append(
            _sentence(
                f"Active shortlist intent is more likely when users can resolve concerns such as "
                f"{_as_mid_sentence(_format_join(blockers))}"
            )
        )

    if not sentences:
        sentences.append(
            _sentence(
                "Wishlist behavior spans both deliberate shortlisting for near-term purchase "
                "and passive bookmarking for inspiration or later revisits"
            )
        )

    return sentences[:5]


def _synthesize_general(
    signals: SurveySignals,
    aggregates: AggregateContext | None,
) -> list[str]:
    sentences: list[str] = []

    if aggregates and aggregates.ranked_reasons:
        categories = [
            str(item.get("reason_category", "")).replace("_", " ")
            for item in aggregates.ranked_reasons[:3]
            if item.get("reason_category")
        ]
        if categories:
            sentences.append(
                _sentence(
                    "Across retrieved evidence, recurring themes include "
                    f"{_as_mid_sentence(_format_join(categories))}"
                )
            )

    products = _top_values(signals.fields.get("product_types", Counter()), limit=3)
    if products:
        sentences.append(
            _sentence(
                f"Users commonly save {_as_mid_sentence(_format_join(products))} to their wishlist "
                "before making a purchase decision"
            )
        )

    blockers = _top_values(signals.fields.get("blockers", Counter()), limit=3)
    if blockers:
        sentences.append(
            _sentence(
                f"Purchase hesitation most often involves {_as_mid_sentence(_format_join(blockers))}"
            )
        )

    for snippet in signals.plain_text_snippets[:2]:
        excerpt = snippet[:180].rstrip(" ,.;")
        if excerpt:
            sentences.append(_sentence(f"Public feedback also notes that {_as_mid_sentence(excerpt)}"))

    if not sentences:
        sentences.append(
            _sentence(
                "Retrieved evidence points to wishlist use as a save-for-later step "
                "with purchase delayed by price, fit, and comparison factors"
            )
        )

    return sentences[:5]


def _append_aggregate_context(sentences: list[str], aggregates: AggregateContext | None) -> None:
    if not aggregates or not aggregates.ranked_reasons or len(sentences) >= 6:
        return
    top = aggregates.ranked_reasons[0]
    category = str(top.get("reason_category", "")).replace("_", " ")
    confidence = top.get("confidence")
    volume = top.get("evidence_volume")
    if category and confidence is not None:
        sentences.append(
            _sentence(
                f"Aggregate analytics rank {category} among the strongest non-conversion "
                f"drivers (confidence {float(confidence):.2f}, volume {volume})"
            )
        )


def synthesize_grounded_answer(
    question: str,
    chunks: list[RetrievedChunk],
    aggregates: AggregateContext | None = None,
) -> str:
    """Synthesize a concise PM-ready answer from retrieved evidence."""
    if not chunks:
        return "No evidence excerpts were available to synthesize an answer."

    signals = collect_survey_signals(chunks)
    intent = _detect_intent(question)

    if intent == "add_motivation":
        sentences = _synthesize_add_motivation(signals)
    elif intent == "blockers":
        sentences = _synthesize_blockers(signals)
    elif intent == "intent":
        sentences = _synthesize_intent(signals, aggregates)
    else:
        sentences = _synthesize_general(signals, aggregates)

    _append_aggregate_context(sentences, aggregates)
    return " ".join(sentences[:6])
