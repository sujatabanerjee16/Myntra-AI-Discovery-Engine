"""Streaming ingestion interface (Phase 8 scale-out path)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from common.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StreamEvent:
    source: str
    payload: dict


EventHandler = Callable[[StreamEvent], None]


class StreamingIngestionBus:
    """In-memory event bus placeholder for future Kafka/Kinesis integration."""

    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def publish(self, event: StreamEvent) -> int:
        for handler in self._handlers:
            handler(event)
        return len(self._handlers)


def iter_seed_stream(events: list[dict], *, source: str) -> Iterator[StreamEvent]:
    """Yield stream events from a static list (dev/test helper)."""
    for payload in events:
        yield StreamEvent(source=source, payload=payload)


def streaming_status() -> dict[str, bool | str]:
    settings = get_settings()
    return {
        "enabled": settings.streaming_ingestion_enabled,
        "mode": "batch" if not settings.streaming_ingestion_enabled else "streaming-ready",
    }
