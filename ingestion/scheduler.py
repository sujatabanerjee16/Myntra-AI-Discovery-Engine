"""Per-source incremental refresh scheduling."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from common.config import get_settings
from common.models import SourceRefreshState, SourceType
from ingestion.connectors.registry import ALL_SOURCES

logger = logging.getLogger(__name__)


def refresh_interval_for(source: SourceType) -> timedelta:
    settings = get_settings()
    hours = settings.source_refresh_interval_hours.get(source.value)
    if hours is None:
        hours = 24
    return timedelta(hours=hours)


def get_or_create_refresh_state(session: Session, source: SourceType) -> SourceRefreshState:
    row = session.execute(
        select(SourceRefreshState).where(SourceRefreshState.source == source)
    ).scalar_one_or_none()
    if row is not None:
        return row

    row = SourceRefreshState(source=source)
    session.add(row)
    session.flush()
    return row


def sources_due_for_refresh(
    session: Session,
    *,
    sources: list[str] | None = None,
    force: bool = False,
) -> list[str]:
    """Return source keys that should run in this refresh cycle."""
    requested = [s.strip().lower() for s in (sources or list(ALL_SOURCES)) if s.strip()]
    now = datetime.now(UTC)
    due: list[str] = []

    for source_key in requested:
        source = SourceType(source_key)
        state = get_or_create_refresh_state(session, source)
        if force or state.last_success_at is None:
            due.append(source_key)
            continue

        last_run = state.last_success_at
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=UTC)
        if now - last_run >= refresh_interval_for(source):
            due.append(source_key)

    logger.info("Sources due for refresh: %s", due)
    return due


def update_refresh_states(
    session: Session,
    *,
    run_version: str,
    source_stats: dict[str, int],
    success: bool,
    error_message: str | None = None,
) -> None:
    """Persist refresh timestamps and counts per source."""
    now = datetime.now(UTC)
    for source_key, documents_added in source_stats.items():
        source = SourceType(source_key)
        state = get_or_create_refresh_state(session, source)
        state.last_run_at = now
        state.last_run_version = run_version
        state.documents_added = documents_added
        state.success = success
        state.error_message = error_message
        if success:
            state.last_success_at = now
            state.next_refresh_at = now + refresh_interval_for(source)
        session.add(state)
