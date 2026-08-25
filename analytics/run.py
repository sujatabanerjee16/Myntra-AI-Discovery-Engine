"""CLI for the semantic analytics layer (Phase 3)."""

from __future__ import annotations

import argparse
import logging
import sys

from analytics.pipeline import (
    export_analytics_json,
    run_semantic_analytics,
    run_semantic_analytics_db,
)
from common.config import get_settings
from common.db import SessionLocal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run semantic analytics (Phase 3)")
    parser.add_argument("--run-version", default=None, help="Version tag for this analytics run")
    parser.add_argument(
        "--json-path",
        default=None,
        help="Analyze chunks from JSON corpus instead of PostgreSQL",
    )
    parser.add_argument(
        "--export-json",
        default=None,
        help="Write analytics output to this JSON file",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Analyze/export JSON only; do not write to PostgreSQL",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not replace existing insights for the same run_version",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    json_path = args.json_path or settings.scraped_json_path

    if args.json_only or args.export_json:
        from analytics.pipeline import _load_chunks_from_json

        raw = _load_chunks_from_json(json_path)
        result = run_semantic_analytics(raw, run_version=args.run_version)
        if args.export_json:
            out = export_analytics_json(result, args.export_json)
            print(f"Exported analytics to {out.resolve()}")
        print(
            f"Run {result.run_version}: chunks={result.chunks_analyzed}, "
            f"insights={result.insights_created}, reasons={result.reason_aggregates}, "
            f"clusters={result.theme_clusters}"
        )
        if args.json_only:
            return 0

    with SessionLocal() as session:
        result = run_semantic_analytics_db(
            session,
            run_version=args.run_version,
            replace_existing=not args.keep_existing,
            json_path=json_path if args.json_path else None,
        )

    print(
        f"Persisted analytics {result.run_version}: chunks={result.chunks_analyzed}, "
        f"insights={result.insights_created}, reasons={result.reason_aggregates}, "
        f"clusters={result.theme_clusters}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
