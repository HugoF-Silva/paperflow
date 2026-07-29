"""Bundled plugin CLI. Run by file path by the venue-matcher skill:
  python <plugin>/skills/venue-matcher/scripts/venue_matcher/cli.py --input-dir D --soon-days N
Accepts ONLY --input-dir and --soon-days; everything else is env-only."""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

from logging_utils import EXECUTION_LOG_ENV, log_status, print_console
import runner

MODEL_ENV = "VENUE_MATCHER_MODEL"
REQUIRED_ENV = ["OPENAI_API_KEY", MODEL_ENV]
DEFAULT_OUTPUT_DIR = pathlib.Path("results")
EXECUTION_LOG_NAME = "_execution.log"


def missing_env_vars(env, required) -> list[str]:
    return [k for k in required if not env.get(k)]


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="venue-matcher")
    p.add_argument("--input-dir", type=pathlib.Path, required=True)
    p.add_argument("--soon-days", type=int, default=31)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    out_dir = pathlib.Path(os.environ.get("OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)))
    execution_log = (out_dir / EXECUTION_LOG_NAME).resolve()
    execution_log.parent.mkdir(parents=True, exist_ok=True)
    if os.environ.get(EXECUTION_LOG_ENV) != str(execution_log):
        execution_log.write_text("", encoding="utf-8")
    else:
        execution_log.touch(exist_ok=True)
    os.environ[EXECUTION_LOG_ENV] = str(execution_log)

    missing = missing_env_vars(os.environ, REQUIRED_ENV)
    if missing:
        print_console(
            f"The following environment variables are not set: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 2

    papers = sorted(args.input_dir.glob("*.docx"))
    if not papers:
        print_console(f"No .docx papers found in {args.input_dir}", file=sys.stderr)
        return 1

    if os.name == "nt":
        too_deep = runner.workspaces_too_deep(out_dir, papers)
        if too_deep:
            names = "; ".join(paper.name for paper in too_deep)
            longest = max(len(str(out_dir.resolve() / paper.stem)) for paper in too_deep)
            print_console(
                f"Windows path limit: {len(too_deep)} paper workspace path(s) "
                f"exceed the {runner.WORKSPACE_PATH_BUDGET}-char budget "
                f"(longest is {longest}). Place the agent's current working directory "
                f"somewhere shallower than the current results's parent dir "
                f"({out_dir.resolve()}) so it is created inside that higher level directory, "
                f"and paper path end up smaller. Or at least shorten the paper filenames "
                f"to reduce risk of exceeding the windows path char limit. "
                f"Paper filenames: {names}",
                file=sys.stderr,
            )
            return 2

    max_ralph = int(os.environ.get("MAX_RALPH", "4"))
    inner_max_turns = max(50, int(os.environ.get("INNER_MAX_TURNS", "50")))
    max_parallel = runner.resolve_max_parallel(os.environ.get("MAX_PARALLEL", "auto"))
    model = os.environ[MODEL_ENV]
    log_status(
        f"cli_start api=openai input_dir={args.input_dir} papers={len(papers)} "
        f"soon_days={args.soon_days} out_dir={out_dir} max_ralph={max_ralph} "
        f"inner_max_turns={inner_max_turns} max_parallel={max_parallel} model={model}"
    )

    summary = runner.run_batch(papers, out_dir, args.soon_days, max_ralph,
                               inner_max_turns, max_parallel, model)
    log_status(
        f"cli_finish succeeded={summary['succeeded']} total={summary['total']} "
        f"failed={summary['failed']} out_dir={out_dir}"
    )
    print_console(
        f"Done: {summary['succeeded']}/{summary['total']} succeeded "
        f"({summary['failed']} failed). Results in {out_dir}"
    )
    stems = summary["agent_result_stems"]
    print_console(
        f"Completed per-paper matcher-agent results: {len(stems)} "
        f"[{', '.join(stems)}]"
    )
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
