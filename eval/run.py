"""CLI entry point for Phase 6 evaluation."""

from __future__ import annotations

import argparse
import logging
import sys

from common.config import get_settings
from common.db import SessionLocal, database_available
from eval.runner import run_evaluation, write_eval_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 6 quality evaluation suite")
    parser.add_argument("--no-persist", action="store_true", help="Skip DB persistence")
    parser.add_argument("--no-live", action="store_true", help="Skip live RAG faithfulness checks")
    parser.add_argument("--output", help="Override eval report JSON path")
    args = parser.parse_args()

    logging.basicConfig(level=get_settings().log_level)

    session = None
    if database_available() and not args.no_persist:
        session = SessionLocal()

    try:
        report = run_evaluation(
            session,
            persist=session is not None,
            include_live_faithfulness=not args.no_live,
        )
        output = write_eval_report(report, args.output)
        print(f"Evaluation {'PASSED' if report.passed else 'FAILED'}")
        print(f"  Retrieval hit@k: {report.retrieval.value:.2%} "
              f"(target {report.retrieval.target:.2%})")
        print(f"  Faithfulness:    {report.faithfulness.value:.2%} "
              f"(target {report.faithfulness.target:.2%})")
        print(f"  Taxonomy acc:    {report.taxonomy.value:.2%} "
              f"(target {report.taxonomy.target:.2%})")
        print(f"Report: {output}")
        return 0 if report.passed else 1
    finally:
        if session is not None:
            session.close()


if __name__ == "__main__":
    sys.exit(main())
