"""Bundled plugin CLI. Run by file path by the venue-matcher skill:
  python <plugin>/skills/venue-matcher/scripts/venue_matcher/cli.py --input-dir D --soon-days N
Accepts ONLY --input-dir and --soon-days; everything else is env-only."""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

from logging_utils import log_status
import runner

REQUIRED_KEYS = ["ANTHROPIC_API_KEY"]
DEFAULT_OUTPUT_DIR = pathlib.Path("results")


def missing_api_keys(env, required) -> list[str]:
    return [k for k in required if not env.get(k)]


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="venue-matcher")
    p.add_argument("--input-dir", type=pathlib.Path, required=True)
    p.add_argument("--soon-days", type=int, default=31)
    return p.parse_args(argv)


def main(argv=None) -> int:
    missing = missing_api_keys(os.environ, REQUIRED_KEYS)
    if missing:
        print(f"The following API keys are not set: {', '.join(missing)}",
              file=sys.stderr, flush=True)
        return 2

    args = parse_args(argv)
    papers = sorted(args.input_dir.glob("*.docx"))
    if not papers:
        print(f"No .docx papers found in {args.input_dir}", file=sys.stderr, flush=True)
        return 1

    out_dir = pathlib.Path(os.environ.get("OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)))
    max_ralph = int(os.environ.get("MAX_RALPH", "8"))
    inner_max_turns = max(50, int(os.environ.get("INNER_MAX_TURNS", "50")))
    max_parallel = runner.resolve_max_parallel(os.environ.get("MAX_PARALLEL"))
    log_status(
        f"cli_start api=anthropic input_dir={args.input_dir} papers={len(papers)} "
        f"soon_days={args.soon_days} out_dir={out_dir} max_ralph={max_ralph} "
        f"inner_max_turns={inner_max_turns} max_parallel={max_parallel}"
    )

    summary = runner.run_batch(papers, out_dir, args.soon_days, max_ralph,
                               inner_max_turns, max_parallel)
    log_status(
        f"cli_finish succeeded={summary['succeeded']} total={summary['total']} "
        f"failed={summary['failed']} out_dir={out_dir}"
    )
    print(f"Done: {summary['succeeded']}/{summary['total']} succeeded "
          f"({summary['failed']} failed). Results in {out_dir}", flush=True)
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
