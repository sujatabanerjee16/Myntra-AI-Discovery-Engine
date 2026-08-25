"""Tests for intent detection and journey-stage mapping."""

from analytics.intent import detect_intent
from analytics.journey import map_journey_stage
from common.models import IntentType, JourneyStage


def test_active_shortlist_intent():
    intent = detect_intent(
        "I add items to my wishlist and wait for a sale before buying.",
        reason_category="price_sensitivity_waiting",
    )
    assert intent == IntentType.active_shortlist


def test_passive_bookmark_intent():
    intent = detect_intent(
        "I bookmark outfits for inspiration and usually do not revisit them.",
        reason_category="passive_bookmarking",
    )
    assert intent == IntentType.passive_bookmark


def test_journey_postponement_for_price_waiting():
    stage = map_journey_stage(
        "Waiting for a discount sale before buying wishlist shoes.",
        reason_category="price_sensitivity_waiting",
    )
    assert stage == JourneyStage.postponement


def test_journey_external_comparison():
    stage = map_journey_stage(
        "I checked the same product on Flipkart before deciding.",
        reason_category="external_comparison",
    )
    assert stage == JourneyStage.external_comparison
