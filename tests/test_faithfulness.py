"""Unit tests for faithfulness scoring."""

from eval.faithfulness import score_answer_faithfulness


def test_boilerplate_connectors_do_not_dilute_grounded_content():
    evidence = [
        "Users wait for sales and discounts before buying wishlist items.",
        "Fit and sizing uncertainty blocks checkout for apparel.",
    ]
    answer = (
        "Across retrieved evidence, recurring themes include fit sizing uncertainty. "
        "Users wait for sales and discounts before buying wishlist items."
    )
    score = score_answer_faithfulness(answer, evidence)
    assert score >= 0.85


def test_refusal_scores_one_when_expected():
    score = score_answer_faithfulness(
        "I cannot provide a grounded answer to this question with the available corpus.",
        evidence_texts=[],
        should_refuse=True,
    )
    assert score == 1.0
