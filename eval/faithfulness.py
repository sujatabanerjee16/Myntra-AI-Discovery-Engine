"""Grounding faithfulness checks for assistant answers."""

from __future__ import annotations

import re

from eval.metrics import tokenize
from eval.schemas import FaithfulnessEvalCase, MetricResult

# Template framing that adds little grounded content but dilutes token-overlap
# scores when counted as full answer sentences.
_BOILERPLATE_SENTENCE_RE = re.compile(
    r"^(?:"
    r"try broadening the question|"
    r"answers are based on public|"
    r"evidence sources in this answer|"
    r"limited number of supporting excerpts|"
    r"treat conclusions cautiously|"
    r"analytics run version"
    r")\b",
    re.IGNORECASE,
)

_CONNECTOR_PREFIX_RE = re.compile(
    r"^(?:"
    r"across retrieved evidence,?\s*(?:recurring themes include\s*)?|"
    r"recurring themes include\s*|"
    r"public feedback also notes that\s*|"
    r"based on (?:the )?(?:retrieved )?evidence,?\s*"
    r")",
    re.IGNORECASE,
)


def _is_refusal(answer: str) -> bool:
    lowered = answer.lower()
    markers = (
        "cannot provide a grounded answer",
        "don't have a clear enough match",
        "do not have a clear enough match",
        "insufficient evidence",
        "not enough evidence",
        "no relevant evidence",
        "outside what this assistant",
        "i can help with wishlist",
    )
    return any(marker in lowered for marker in markers)


def _normalize_scorable_sentence(sentence: str) -> str | None:
    """Drop framing-only sentences; strip connector prefixes from the rest."""
    text = sentence.strip()
    if not text:
        return None
    if _BOILERPLATE_SENTENCE_RE.search(text):
        return None
    stripped = _CONNECTOR_PREFIX_RE.sub("", text).strip(" ,:;.-")
    if not stripped:
        return None
    # If stripping left almost nothing meaningful, skip the sentence.
    if len(tokenize(stripped)) < 2:
        return None
    return stripped


def score_answer_faithfulness(
    answer: str,
    evidence_texts: list[str],
    *,
    should_refuse: bool = False,
) -> float:
    """Score how well an answer is supported by cited evidence (0–1)."""
    if should_refuse:
        return 1.0 if _is_refusal(answer) else 0.0

    if not evidence_texts:
        return 0.0

    evidence_tokens = set()
    for text in evidence_texts:
        evidence_tokens.update(tokenize(text))

    if not evidence_tokens:
        return 0.0

    raw_sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", answer.strip())
        if sentence.strip()
    ]
    sentences = [
        normalized
        for sentence in raw_sentences
        if (normalized := _normalize_scorable_sentence(sentence)) is not None
    ]
    if not sentences:
        # All framing / empty — fall back to raw sentences so empty answers score 0.
        sentences = raw_sentences
    if not sentences:
        return 0.0

    supported = 0
    scored = 0
    for sentence in sentences:
        sentence_tokens = tokenize(sentence)
        if not sentence_tokens:
            continue
        scored += 1
        overlap = len(sentence_tokens & evidence_tokens) / len(sentence_tokens)
        if overlap >= 0.25:
            supported += 1

    if scored == 0:
        return 0.0
    return supported / scored


def compute_faithfulness_metrics(
    cases: list[FaithfulnessEvalCase],
    *,
    target: float,
) -> MetricResult:
    """Average faithfulness score across labeled answer/evidence pairs."""
    if not cases:
        return MetricResult(
            name="grounding_faithfulness",
            value=0.0,
            target=target,
            passed=False,
            details={"error": "No faithfulness eval cases configured"},
        )

    scores: list[float] = []
    per_case: list[dict[str, float | bool | str]] = []

    for case in cases:
        score = score_answer_faithfulness(
            case.answer,
            case.evidence_texts,
            should_refuse=case.should_refuse,
        )
        scores.append(score)
        per_case.append(
            {
                "question": case.question[:80],
                "score": round(score, 4),
                "should_refuse": case.should_refuse,
            }
        )

    average = sum(scores) / len(scores)
    return MetricResult(
        name="grounding_faithfulness",
        value=round(average, 4),
        target=target,
        passed=average >= target,
        details={
            "average": round(average, 4),
            "cases": len(cases),
            "per_case": per_case,
        },
    )
