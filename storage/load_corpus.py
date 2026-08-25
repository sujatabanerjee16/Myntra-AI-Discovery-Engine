"""CLI to load JSON corpus into PostgreSQL."""

from __future__ import annotations

import argparse
import logging
import sys

from common.config import get_settings
from common.db import SessionLocal
from storage.loader import load_corpus_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load scraped JSON corpus into PostgreSQL")
    parser.add_argument(
        "--json-path",
        default=None,
        help="Path to scraped_corpus.json (default: SCRAPED_JSON_PATH from settings)",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Attempt to insert even if source_ref already exists (may fail on unique constraint)",
    )
    parser.add_argument(
        "--no-refresh-aggregates",
        action="store_true",
        help="Skip recomputing analytical aggregate tables",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    json_path = args.json_path or settings.scraped_json_path

    with SessionLocal() as session:
        result = load_corpus_json(
            session,
            json_path,
            skip_existing=not args.no_skip_existing,
            refresh_aggregates=not args.no_refresh_aggregates,
        )

    print(
        f"Loaded {json_path}: run={result.run_version}, "
        f"docs_created={result.documents_created}, skipped={result.documents_skipped}, "
        f"chunks={result.chunks_created}, aggregates={result.aggregates}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
