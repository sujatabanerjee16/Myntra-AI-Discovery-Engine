"""Tests for deterministic grounded answer synthesis."""

from uuid import uuid4

from assistant.synthesis import collect_survey_signals, parse_qa_pairs, synthesize_grounded_answer, _as_mid_sentence
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


def test_synthesize_blockers_preserves_capital_i():
    answer = synthesize_grounded_answer(
        "What prevents wishlisted products from being purchased?",
        [_chunk(_SURVEY_TEXT), _chunk(_SURVEY_TEXT_2, score=0.61)],
    )
    assert " i " not in f" {answer} "
    assert "I am waiting" in answer or "I do not need" in answer or "I change" in answer
