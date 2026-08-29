"""CLI entrypoint for the ingestion pipeline."""

from __future__ import annotations

import argparse
import logging
import sys

from common.config import get_settings
from common.db import SessionLocal
from ingestion.connectors.registry import ALL_SOURCES
from ingestion.export.json_exporter import export_corpus_json
from ingestion.pipeline import prepare_corpus, run_pipeline


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the discovery ingestion pipeline")
    parser.add_argument(
        "--sources",
        default=None,
        help=f"Comma-separated sources ({', '.join(ALL_SOURCES)}). Defaults to all six types.",
    )
    parser.add_argument(
        "--research-path",
        default=None,
        help="Path to Myntra Wishlist research Excel file",
    )
    parser.add_argument("--run-version", default=None, help="Version tag for this pipeline run")
    parser.add_argument(
        "--play-store-limit",
        type=int,
        default=None,
        help="Max Play Store reviews to fetch before relevance filtering",
    )
    parser.add_argument(
        "--skip-embed",
        action="store_true",
        help="Skip BGE embedding (useful for quick local tests)",
    )
    parser.add_argument(
        "--export-json",
        default=None,
        help="Write processed corpus to this JSON file path",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Export JSON only; do not persist to PostgreSQL",
    )
    parser.add_argument(
        "--include-embeddings",
        action="store_true",
        help="Include full embedding vectors in JSON export (large files)",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Logging level (DEBUG, INFO, ...)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, (args.log_level or settings.log_level).upper(), logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.sources:
        sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    else:
        sources = settings.default_source_list
    invalid = [s for s in sources if s.lower() not in ALL_SOURCES]
    if invalid:
        logging.error("Invalid sources: %s", invalid)
        return 1

    research_path = args.research_path or settings.research_excel_path
    research_paths = settings.research_excel_path_list
    if args.research_path:
        research_paths = [research_path, *[p for p in research_paths if p != research_path]]
    json_path = args.export_json or settings.scraped_json_path

    if args.json_only or args.export_json:
        corpus, result = prepare_corpus(
            sources=sources,
            research_excel_path=research_path,
            research_excel_paths=research_paths,
            run_version=args.run_version,
            play_store_limit=args.play_store_limit,
            skip_embed=args.skip_embed,
            include_embeddings=args.include_embeddings,
        )
        out = export_corpus_json(corpus, json_path)
        print(f"Exported JSON corpus to {out.resolve()}")
        print(
            f"Run {result.run_version}: fetched={result.fetched}, "
            f"kept={result.after_filter}, documents={result.documents_created}, "
            f"chunks={result.chunks_created}, sources={result.sources}"
        )
        if args.json_only:
            return 0

    if not args.json_only:
        with SessionLocal() as session:
            result = run_pipeline(
                session,
                sources=sources,
                research_excel_path=research_path,
                research_excel_paths=research_paths,
                run_version=args.run_version,
                play_store_limit=args.play_store_limit,
                skip_embed=args.skip_embed,
            )

        print(
            f"Run {result.run_version}: fetched={result.fetched}, "
            f"kept={result.after_filter}, docs_created={result.documents_created}, "
            f"docs_skipped={result.documents_skipped}, chunks={result.chunks_created}, "
            f"sources={result.sources}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
