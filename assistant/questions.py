"""Canonical PM questions the assistant must always treat as in-domain."""

from __future__ import annotations

import re

KEY_QUESTIONS = [
    "Why do users add fashion products to their wishlist?",
    "What prevents wishlisted products from eventually being purchased?",
    "What uncertainties remain after users have identified a product they like?",
    "What causes users to postpone a purchase?",
    "How do users compare multiple shortlisted products?",
    "What information do users seek outside Myntra/AJIO before purchasing?",
    "What role do fit, size, styling, price, reviews, occasion and social validation play?",
    "When do users use the wishlist as genuine purchase intent versus "
    "simply as a bookmarking mechanism?",
    "What unmet needs emerge consistently across user conversations?",
]

_SPACE_RE = re.compile(r"\s+")


def normalize_question(question: str) -> str:
    """Collapse whitespace so canned prompts match typed/suggested copies."""
    return _SPACE_RE.sub(" ", question.strip()).lower()


_CANNED = frozenset(normalize_question(item) for item in KEY_QUESTIONS)


def is_key_business_question(question: str) -> bool:
    """True for the Explore / Discovery Chat starter questions."""
    return normalize_question(question) in _CANNED
