"""CLI for internal data integration and conversion metric computation."""

from __future__ import annotations

import argparse
import logging
import sys

from common.config import get_settings
from common.db import SessionLocal
from internal.pipeline import run_internal_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase 8 internal data pipeline")
    parser.add_argument("--events-path", default=None, help="Path to internal events JSON")
    parser.add_argument("--run-version", default=None, help="Version tag for this run")
    parser.add_argument(
        "--analytics-run-version",
        default=None,
        help="Reason aggregate run version to corroborate against",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    with SessionLocal() as session:
        result = run_internal_pipeline(
            session,
            events_path=args.events_path,
            run_version=args.run_version,
            analytics_run_version=args.analytics_run_version,
        )
        session.commit()

    print(
        f"Internal run {result.run_version}: events={result.events_loaded}, "
        f"conversion_rate={result.conversion_rate:.2%}, "
        f"corroborations={result.corroborations}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
