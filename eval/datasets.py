"""Golden evaluation datasets for retrieval, faithfulness, and taxonomy."""

from __future__ import annotations

import json
from pathlib import Path

from eval.schemas import FaithfulnessEvalCase, RetrievalEvalCase, TaxonomyEvalCase

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "eval"


def _load_json(name: str) -> list[dict]:
    path = DATA_DIR / name
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def load_retrieval_cases() -> list[RetrievalEvalCase]:
    return [RetrievalEvalCase.model_validate(item) for item in _load_json("retrieval.json")]


def load_taxonomy_cases() -> list[TaxonomyEvalCase]:
    return [TaxonomyEvalCase.model_validate(item) for item in _load_json("taxonomy.json")]


def load_faithfulness_cases() -> list[FaithfulnessEvalCase]:
    return [FaithfulnessEvalCase.model_validate(item) for item in _load_json("faithfulness.json")]


def default_retrieval_cases() -> list[RetrievalEvalCase]:
    """Built-in cases used when no dataset file is present."""
    return [
        RetrievalEvalCase(
            query="Why do users wait for sales before buying wishlist items?",
            expected_reason_categories=["price_sensitivity_waiting"],
            expected_keywords=["sale", "price", "discount", "wait"],
        ),
        RetrievalEvalCase(
            query="What fit and sizing concerns stop users from purchasing?",
            expected_reason_categories=["fit_sizing_uncertainty"],
            expected_keywords=["fit", "size", "sizing"],
        ),
        RetrievalEvalCase(
            query="Do users compare Myntra prices with Amazon or Flipkart?",
            expected_reason_categories=["external_comparison"],
            expected_keywords=["compare", "amazon", "flipkart"],
        ),
        RetrievalEvalCase(
            query="Why do users bookmark items without buying?",
            expected_reason_categories=["passive_bookmarking", "styling_decision_uncertainty"],
            expected_keywords=["bookmark", "save", "wishlist"],
        ),
        RetrievalEvalCase(
            query="What delivery or return policy issues cause hesitation?",
            expected_reason_categories=["logistics_friction"],
            expected_keywords=["delivery", "return", "policy"],
        ),
    ]


def default_taxonomy_cases() -> list[TaxonomyEvalCase]:
    return [
        TaxonomyEvalCase(
            text="The price is too high and I am waiting for a sale.",
            expected_category="price_sensitivity_waiting",
            signals=["price_sensitivity_waiting"],
        ),
        TaxonomyEvalCase(
            text="My preferred size is unavailable and I am unsure about the fit.",
            expected_category="fit_sizing_uncertainty",
            signals=["fit_size_styling_quality_trust_occasion"],
        ),
        TaxonomyEvalCase(
            text="I compare prices on Amazon and Flipkart before purchasing.",
            expected_category="external_comparison",
            signals=["external_comparison_seeking"],
        ),
        TaxonomyEvalCase(
            text="I save items for inspiration and do not revisit often.",
            expected_category="passive_bookmarking",
            signals=["wishlist_usage"],
        ),
        TaxonomyEvalCase(
            text="Delivery was delayed and the return policy is unclear.",
            expected_category="logistics_friction",
        ),
        TaxonomyEvalCase(
            text="Too few reviews and I do not trust the quality.",
            expected_category="review_trust",
        ),
        TaxonomyEvalCase(
            text="I cannot decide which option to buy and keep changing my mind.",
            expected_category="styling_decision_uncertainty",
            signals=["purchase_hesitation"],
        ),
        TaxonomyEvalCase(
            text="Not needed yet for the upcoming occasion.",
            expected_category="timing_occasion",
            signals=["delayed_decision"],
        ),
    ]


def default_faithfulness_cases() -> list[FaithfulnessEvalCase]:
    return [
        FaithfulnessEvalCase(
            question="Why do users wait to buy?",
            answer=("Users often wait for sales and price drops before purchasing wishlist items."),
            evidence_texts=[
                "I am waiting for a sale before buying items on my wishlist.",
                "The price is too high right now.",
            ],
        ),
        FaithfulnessEvalCase(
            question="What sizing issues appear?",
            answer="Fit uncertainty and unavailable preferred sizes delay purchase.",
            evidence_texts=[
                "My preferred size is unavailable and I am unsure about the fit.",
            ],
        ),
        FaithfulnessEvalCase(
            question="Is there evidence about Mars colonization?",
            answer=(
                "I don't have a clear enough match in shopper comments to answer that yet."
            ),
            evidence_texts=[],
            should_refuse=True,
        ),
    ]
