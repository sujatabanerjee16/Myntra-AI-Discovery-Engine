"""Choose PostgreSQL or JSON fallback for dashboard and retrieval."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api import json_dashboard, json_retrieval
from api.json_store import json_data_available
from common.config import get_settings
from common.db import database_available

logger = logging.getLogger(__name__)
T = TypeVar("T")


def use_json_backend() -> bool:
    """Prefer exported insights JSON when present so dashboard category data stays in sync."""
    settings = get_settings()
    if not settings.use_json_fallback:
        return False
    if json_data_available():
        return True
    return not database_available()


def call_with_json_fallback(
    session: Session,
    *,
    db_call: Callable[[Session], T],
    json_call: Callable[[], T],
    label: str,
) -> T:
    """Try PostgreSQL first; fall back to exported JSON when the DB is unavailable."""
    if use_json_backend():
        logger.info("Serving %s from JSON fallback (database unavailable)", label)
        return json_call()

    try:
        return db_call(session)
    except SQLAlchemyError as exc:
        if not get_settings().use_json_fallback or not json_data_available():
            raise
        logger.warning("Database error for %s; using JSON fallback: %s", label, exc)
        return json_call()


def search_with_fallback(
    session: Session,
    *,
    query_text: str,
    top_k: int,
    filters,
):
    from storage.retrieval import search_chunks

    if use_json_backend():
        return json_retrieval.search_chunks_json(
            query_text=query_text,
            top_k=top_k,
            filters=filters,
        )

    try:
        return search_chunks(
            session,
            query_text=query_text,
            top_k=top_k,
            filters=filters,
        )
    except SQLAlchemyError as exc:
        if not get_settings().use_json_fallback or not json_data_available():
            raise
        logger.warning("Retrieval DB error; using JSON fallback: %s", exc)
        return json_retrieval.search_chunks_json(
            query_text=query_text,
            top_k=top_k,
            filters=filters,
        )
