"""Command-line validation for the OpenAI paper converter."""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

from inner_agent import EXECUTION_LOG_ENV
import runner
from tools import _set_process_nondumpable


MODEL_ENV = "CONVERTER_MODEL"
REQUIRED_ENV = ["OPENAI_API_KEY", MODEL_ENV]
DEFAULT_OUTPUT_DIR = pathlib.Path("results")
EXECUTION_LOG_NAME = "_execution.log"


def missing_env_vars(env, required) -> list[str]:
    return [name for name in required if not env.get(name)]


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="converter")
    parser.add_argument("--input-dir", type=pathlib.Path, required=True)
    parser.add_argument("--results-dir", type=pathlib.Path)
    parser.add_argument("--chosen-venue")
    parser.add_argument("--template-path", type=pathlib.Path)
    return parser.parse_args(argv)


def _source_count(args) -> int:
    return sum(
        value is not None
        for value in (args.results_dir, args.chosen_venue, args.template_path)
    )


def _error(message: str, code: int) -> int:
    print(message, file=sys.stderr, flush=True)
    return code


def main(argv=None) -> int:
    _set_process_nondumpable()
    args = parse_args(argv)
    missing = missing_env_vars(os.environ, REQUIRED_ENV)
    if missing:
        return _error(
            f"The following environment variables are not set: {', '.join(missing)}", 2
        )
    if _source_count(args) != 1:
        return _error("Exactly one converter source must be provided", 2)
    invocation_cwd = pathlib.Path.cwd()
    args.input_dir = (invocation_cwd / args.input_dir).resolve()
    if args.results_dir is not None:
        args.results_dir = (invocation_cwd / args.results_dir).resolve()
    if args.template_path is not None:
        args.template_path = (invocation_cwd / args.template_path).resolve()
    if not args.input_dir.is_dir():
        return _error(f"Input directory does not exist: {args.input_dir}", 2)
    if args.chosen_venue is not None and not args.chosen_venue.strip():
        return _error("Chosen venue must not be empty", 2)

    output_dir = (
        invocation_cwd
        / pathlib.Path(os.environ.get("OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)))
    ).resolve()
    execution_log = output_dir / EXECUTION_LOG_NAME
    execution_log.parent.mkdir(parents=True, exist_ok=True)
    execution_log.touch(exist_ok=True)
    os.environ[EXECUTION_LOG_ENV] = str(execution_log)
    try:
        max_ralph = int(os.environ.get("MAX_RALPH", "4"))
        inner_max_turns = max(50, int(os.environ.get("INNER_MAX_TURNS", "50")))
        max_parallel = runner.resolve_max_parallel(os.environ.get("MAX_PARALLEL", "auto"))
    except (TypeError, ValueError) as exc:
        return _error(str(exc), 2)

    try:
        batch_root, units = runner.select_work_units(
            args.input_dir,
            output_dir,
            results_dir=args.results_dir,
            chosen_venue=args.chosen_venue,
            template_path=args.template_path,
        )
    except (OSError, TypeError, ValueError) as exc:
        return _error(str(exc), 1)

    try:
        summary = runner.run_batch(
            units,
            batch_root,
            max_ralph,
            inner_max_turns,
            max_parallel,
            os.environ[MODEL_ENV],
        )
    except Exception as exc:
        return _error(str(exc), 1)
    print(
        f"Converter results: {summary['succeeded']}/{summary['total']} succeeded, "
        f"{summary['blocked']} blocked, {summary['failed']} failed; "
        f"directory: {batch_root}",
        flush=True,
    )
    return 0 if summary["blocked"] == summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
