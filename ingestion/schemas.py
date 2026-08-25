"""Raw ingestion record passed between connectors and pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from common.models import SourceType


@dataclass(slots=True)
class RawRecord:
    """Normalized raw document before cleaning and persistence."""

    source: SourceType
    source_ref: str
    text: str
    author_hash: str | None = None
    language: str | None = "en"
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    matched_signals: list[str] = field(default_factory=list)
