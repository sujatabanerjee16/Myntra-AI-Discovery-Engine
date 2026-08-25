"""Load product-review feedback from seeds or exported JSON."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from common.config import get_settings
from common.models import SourceType
from ingestion.connectors.seed_loader import load_seed_records
from ingestion.schemas import RawRecord

logger = logging.getLogger(__name__)


def fetch_product_review_records(*, export_path: str | None = None) -> list[RawRecord]:
    """Load product reviews from configured export path, falling back to seeds."""
    settings = get_settings()
    path = Path(export_path or settings.product_review_export_path)
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            logger.info("Loaded %s product review records from %s", len(payload), path)
            return load_seed_records(
                SourceType.product_review,
                seed_path=path,
            )

    return load_seed_records(SourceType.product_review)
