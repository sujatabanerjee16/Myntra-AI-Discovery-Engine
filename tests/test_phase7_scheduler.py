"""Tests for incremental refresh scheduling."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from common.models import SourceType
from ingestion.scheduler import refresh_interval_for, sources_due_for_refresh


def test_refresh_interval_defaults():
    assert refresh_interval_for(SourceType.research).total_seconds() == 168 * 3600


def test_sources_due_when_never_run():
    session = MagicMock()
    state = MagicMock()
    state.last_success_at = None
    session.execute.return_value.scalar_one_or_none.return_value = state
    session.add = MagicMock()
    session.flush = MagicMock()

    due = sources_due_for_refresh(session, sources=["reddit"], force=False)
    assert due == ["reddit"]


def test_sources_not_due_after_recent_run():
    session = MagicMock()
    state = MagicMock()
    state.last_success_at = datetime.now(UTC)
    session.execute.return_value.scalar_one_or_none.return_value = state

    due = sources_due_for_refresh(session, sources=["reddit"], force=False)
    assert due == []
