"""Load social conversation snippets from seeds or exported JSON."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from common.config import get_settings
from common.models import SourceType
from ingestion.connectors.seed_loader import load_seed_records
from ingestion.schemas import RawRecord

logger = logging.getLogger(__name__)


def fetch_social_records(*, export_path: str | None = None) -> list[RawRecord]:
    """Load social mentions from configured export path, falling back to seeds."""
    settings = get_settings()
    path = Path(export_path or settings.social_export_path)
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            logger.info("Loaded %s social records from %s", len(payload), path)
            return load_seed_records(SourceType.social, seed_path=path)

    return load_seed_records(SourceType.social)
