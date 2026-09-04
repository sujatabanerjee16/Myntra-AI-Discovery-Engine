"""Tests for deterministic grounded answer synthesis."""

from uuid import uuid4

from assistant.query import understand_query
from assistant.schemas import AggregateContext
from assistant.synthesis import (
    _as_mid_sentence,
    _normalize_answer,
    _truncate_at_word,
    collect_survey_signals,
    parse_qa_pairs,
    synthesize_grounded_answer,
)
from common.models import SourceType
from storage.schemas import RetrievedChunk

_SURVEY_TEXT = (
    "Q: Timestamp A: 2026-08-21 18:16:[phone] "
    "Q: 1. Do you currently use Myntra? A: Yes, regularly "
    "Q: 3. How often do you add items to your Myntra wishlist? A: A few times a week "
    "Q: 5. What types of products do you usually save? A: Clothing, Footwear, Accessories "
    "Q: 6. How long do you usually keep items in your wishlist before deciding what to do? "
    "A: 1–4 weeks "
    "Q: 7. How often do you eventually purchase items from your wishlist? A: Often "
    "Q: 8. What usually stops you from buying wishlist items? "
    "A: The price is too high, I am waiting for a sale"
)

_SURVEY_TEXT_2 = (
    "Q: Timestamp A: 2026-08-21 18:20:[phone] "
    "Q: 1. Do you currently use Myntra? A: Yes, occasionally "
    "Q: 3. How often do you add items to your Myntra wishlist? A: A few times a month "
    "Q: 5. What types of products do you usually save? A: Clothing, Footwear, Accessories "
    "Q: 6. How long do you usually keep items in your wishlist before deciding what to do? "
    "A: I usually do not revisit them "
    "Q: 8. What usually stops you from buying wishlist items? "
    "A: I am waiting for a sale, I change my mind "
    "Q: 9. What is the single biggest reason you do not purchase wishlist items? "
    "A: I do not need the item anymore"
)


def _chunk(text: str, score: float = 0.68) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        text=text,
        score=score,
        source=SourceType.research,
        source_ref="research:row:1",
        category=None,
        occasion=None,
        price_band=None,
        segment=None,
        matched_signals=["wishlist_usage"],
        quality_score=0.85,
        document_created_at=None,
    )


def test_parse_qa_pairs_extracts_survey_fields():
    pairs = parse_qa_pairs(_SURVEY_TEXT)
    assert len(pairs) >= 5
    assert any("Clothing" in answer for _, answer in pairs)


def test_synthesize_add_motivation_is_concise_prose():
    answer = synthesize_grounded_answer(
        "Why do users add fashion products to their wishlist?",
        [_chunk(_SURVEY_TEXT), _chunk(_SURVEY_TEXT_2, score=0.62)],
    )

    lowered = answer.lower()
    assert "based on retrieved corpus evidence" not in lowered
    assert "strongest signal" not in lowered
    assert "q: timestamp" not in lowered
    assert "save items" in lowered or "later consideration" in lowered
    assert "clothing" in lowered
    assert len(answer.split(".")) <= 7


def test_synthesize_blockers_focuses_on_non_conversion_reasons():
    answer = synthesize_grounded_answer(
        "What prevents wishlisted products from being purchased?",
        [_chunk(_SURVEY_TEXT), _chunk(_SURVEY_TEXT_2, score=0.61)],
    )

    lowered = answer.lower()
    assert "price" in lowered or "sale" in lowered
    assert "q:" not in lowered
    assert "additional supporting excerpts" not in lowered


def test_collect_survey_signals_aggregates_common_answers():
    signals = collect_survey_signals([_chunk(_SURVEY_TEXT), _chunk(_SURVEY_TEXT_2)])
    assert signals.fields["product_types"]["Clothing"] >= 1
    assert signals.fields["myntra_usage"]["regularly"] >= 1


def test_as_mid_sentence_preserves_pronoun_i():
    assert _as_mid_sentence("I am waiting for a sale") == "I am waiting for a sale"
    assert _as_mid_sentence("i change my mind") == "I change my mind"
    assert _as_mid_sentence("I'm unsure about sizing") == "I'm unsure about sizing"
    assert _as_mid_sentence("Clothing, Footwear") == "clothing, footwear"


def test_normalize_answer_strips_trailing_orphan_letter():
    assert _normalize_answer("I do not need the item anymore q") == "I do not need the item anymore"
    assert _normalize_answer("I do not need the item anymore Q") == "I do not need the item anymore"
    assert _normalize_answer("I do not need the item anymore") == "I do not need the item anymore"
    assert _normalize_answer("I change my mind") == "I change my mind"
    assert _normalize_answer("I usually d") == ""
    assert _normalize_answer("1-4 wee") == "1-4 weeks"
    assert _normalize_answer("I am unsure about the fit") == "I am unsure about the fit"
    assert _normalize_answer("a") == "a"
    assert _normalize_answer("I") == "I"
    assert _normalize_answer("I do not ne") == ""
    assert _normalize_answer("the price is too high") == "the price is too high"
    assert _normalize_answer("ht a wishlisted item") == "a wishlisted item"


def test_collect_survey_signals_merges_orphan_suffix_duplicates():
    complete = (
        "Q: What is the single biggest reason you do not purchase wishlist items? "
        "A: I do not need the item anymore"
    )
    with_orphan = (
        "Q: What is the single biggest reason you do not purchase wishlist items? "
        "A: I do not need the item anymore Q"
    )
    signals = collect_survey_signals([_chunk(complete), _chunk(with_orphan)])
    assert list(signals.fields["primary_blocker"]) == ["I do not need the item anymore"]
    assert signals.fields["primary_blocker"]["I do not need the item anymore"] == 2


def test_collect_survey_signals_collapses_truncated_prefix():
    complete = (
        "Q: How long do you usually keep items in your wishlist before deciding what to do? "
        "A: I usually do not revisit them"
    )
    truncated = (
        "Q: How long do you usually keep items in your wishlist before deciding what to do? "
        "A: I usually"
    )
    signals = collect_survey_signals([_chunk(complete), _chunk(truncated)])
    assert list(signals.fields["retention"]) == ["I usually do not revisit them"]
    assert signals.fields["retention"]["I usually do not revisit them"] == 2


def test_truncate_at_word_does_not_cut_mid_word():
    text = "Users wait 1-4 weeks before buying " + ("saved items " * 20)
    excerpt = _truncate_at_word(text, 180)
    assert len(excerpt) <= 180
    assert not excerpt.endswith("wee")
    rest = text[len(excerpt) :]
    assert not rest or rest[0].isspace()


def test_truncate_at_word_drops_leading_fragment():
    excerpt = _truncate_at_word("ht a wishlisted item somewhere else", 180)
    assert excerpt.startswith("a wishlisted")


def test_user_segment_question_uses_research_without_naming_cohorts():
    young = _chunk(
        "Q: Age band\nA: 18-24\n\nQ: What usually stops you from buying wishlist items?\n"
        "A: I am waiting for a sale, I am waiting for the right occasion"
    )
    young.segment = "age_18_24"
    older = _chunk(
        "Q: Age band\nA: 25-35\n\nQ: What usually stops you from buying wishlist items?\n"
        "A: The price is too high, I am unsure about the fit"
    )
    older.segment = "age_25_35"
    answer = synthesize_grounded_answer(
        "What unmet needs emerge consistently across user conversations?",
        [young, older],
    )
    lowered = answer.lower()
    assert "sale" in lowered or "occasion" in lowered or "price" in lowered or "fit" in lowered
    assert "18–24" not in answer and "18-24" not in lowered
    assert "25–35" not in answer and "25-35" not in lowered


def test_understand_query_does_not_special_case_segment_compare():
    parsed = understand_query("How do these behaviors differ across user segments?")
    assert parsed.intent_hint != "age_segments"
    assert parsed.search_query == "How do these behaviors differ across user segments?"


def test_synthesize_blockers_preserves_capital_i():
    answer = synthesize_grounded_answer(
        "What prevents wishlisted products from being purchased?",
        [_chunk(_SURVEY_TEXT), _chunk(_SURVEY_TEXT_2, score=0.61)],
    )
    assert " i " not in f" {answer} "
    assert "I am waiting" in answer or "I do not need" in answer or "I change" in answer


def test_key_questions_are_plain_english_and_capitalized():
    import re

    from assistant.questions import KEY_QUESTIONS

    chunks = [_chunk(_SURVEY_TEXT), _chunk(_SURVEY_TEXT_2, score=0.62)]
    banned = ("corpus", "retrieved", "grounded", "aggregate analytics", "18-24", "25-35")
    for question in KEY_QUESTIONS:
        answer = synthesize_grounded_answer(question, chunks)
        assert answer, question
        letter = next((char for char in answer if char.isalpha()), "")
        assert letter.isupper(), answer
        for sentence in re.split(r"(?<=[.!?])\s+", answer):
            token = next((char for char in sentence if char.isalpha()), "")
            assert not token or token.isupper(), f"{question} -> {sentence}"
        lowered = answer.lower().replace("–", "-").replace("—", "-")
        for phrase in banned:
            assert phrase not in lowered, f"{phrase} in {answer}"


def test_strip_answer_meta_drops_inline_confidence():
    from assistant.synthesis import strip_answer_meta

    cleaned = strip_answer_meta(
        "The most cited blocker is high price (confidence 0.84, volume 397). "
        "Price sensitivity is also common."
    )
    assert "confidence" not in cleaned.lower()
    assert "volume" not in cleaned.lower()
    assert "high price" in cleaned.lower()
