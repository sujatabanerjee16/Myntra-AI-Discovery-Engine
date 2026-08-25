"""Export processed corpus records to JSON."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def export_corpus_json(
    corpus: dict[str, Any],
    output_path: str | Path,
    *,
    indent: int = 2,
) -> Path:
    """Write *corpus* to *output_path*, creating parent directories as needed."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(corpus, indent=indent, ensure_ascii=False), encoding="utf-8")
    return path


def build_corpus_payload(
    *,
    run_version: str,
    sources: list[str],
    documents: list[dict[str, Any]],
    stats: dict[str, Any],
) -> dict[str, Any]:
    return {
        "run_version": run_version,
        "exported_at": datetime.now(UTC).isoformat(),
        "sources": sources,
        "stats": stats,
        "documents": documents,
    }
