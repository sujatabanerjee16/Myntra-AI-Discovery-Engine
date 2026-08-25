"""CLI for scheduled incremental source refresh (Phase 7)."""

from __future__ import annotations

import argparse
import logging
import sys

from analytics.pipeline import run_semantic_analytics_db
from common.config import get_settings
from common.db import SessionLocal
from ingestion.pipeline import run_pipeline
from ingestion.scheduler import sources_due_for_refresh, update_refresh_states


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run incremental ingestion refresh for due sources"
    )
    parser.add_argument(
        "--sources",
        default=None,
        help="Comma-separated sources to consider (defaults to all six source types)",
    )
    parser.add_argument("--force", action="store_true", help="Refresh all requested sources now")
    parser.add_argument("--run-version", default=None, help="Optional pipeline run version tag")
    parser.add_argument("--skip-embed", action="store_true", help="Skip embedding generation")
    parser.add_argument(
        "--skip-analytics",
        action="store_true",
        help="Skip semantic analytics recompute after ingestion",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    requested = (
        [s.strip() for s in args.sources.split(",") if s.strip()]
        if args.sources
        else settings.default_source_list
    )

    with SessionLocal() as session:
        due = sources_due_for_refresh(session, sources=requested, force=args.force)
        if not due:
            print("No sources due for refresh.")
            return 0

        try:
            result = run_pipeline(
                session,
                sources=due,
                research_excel_path=settings.research_excel_path,
                run_version=args.run_version,
                play_store_limit=settings.play_store_review_limit,
                skip_embed=args.skip_embed,
            )
            update_refresh_states(
                session,
                run_version=result.run_version,
                source_stats=result.sources_created or result.sources,
                success=True,
            )
            session.commit()

            if settings.recompute_analytics_on_refresh and not args.skip_analytics:
                analytics = run_semantic_analytics_db(
                    session,
                    run_version=result.run_version,
                    replace_existing=True,
                )
                session.commit()
                print(
                    f"Analytics {analytics.run_version}: insights={analytics.insights_created}, "
                    f"reasons={analytics.reason_aggregates}"
                )
        except Exception as exc:
            update_refresh_states(
                session,
                run_version=args.run_version or "refresh-failed",
                source_stats={source: 0 for source in due},
                success=False,
                error_message=str(exc),
            )
            session.commit()
            raise

    print(
        f"Refresh {result.run_version}: sources={due}, docs_created={result.documents_created}, "
        f"docs_skipped={result.documents_skipped}, chunks={result.chunks_created}, "
        f"by_source={result.sources}"
    )
    if result.validation:
        print(f"Validation: {result.validation.to_dict()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
