"""CLI entry point. Two subcommands:

- `run`             — process a directory of .docx papers end-to-end.
- `validate-skills` — resolve the requested skill set and exit. No agents fire.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from batch_venue_matcher.compose import CliArgs, build_orchestrator, resolve_skills


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s  %(levelname)-7s  %(message)s",
    )
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print(
                "FATAL: ANTHROPIC_API_KEY is not set. Put it in .env or pass "
                "it via the environment before running.",
                file=sys.stderr,
                flush=True,
            )
            return 2
        cli_args = _to_cli_args(args)
        orchestrator = build_orchestrator(cli_args)
        return orchestrator.run()

    if args.command == "validate-skills":
        cli_args = _to_cli_args(args, require_io=False)
        plan = resolve_skills(cli_args)
        for warning in plan.warnings:
            print(f"warn: {warning}", flush=True)
        print(
            "ok: resolved skills -> "
            + ", ".join(name for _, name in plan.entries),
            flush=True,
        )
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="batch-venue-matcher")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="process a directory of .docx papers")
    _add_common_args(run_p, require_io=True)

    val_p = sub.add_parser(
        "validate-skills",
        help="resolve the requested skill set and exit without running",
    )
    _add_common_args(val_p, require_io=False)

    return parser


def _add_common_args(p: argparse.ArgumentParser, *, require_io: bool) -> None:
    p.add_argument(
        "--input-dir",
        type=Path,
        required=require_io,
        help="directory of .docx papers",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        required=require_io,
        help="directory where per-paper rankings are written",
    )
    p.add_argument(
        "--soon-days",
        type=int,
        default=31,
        help="upper bound on 'opening soon' (default: 31)",
    )
    p.add_argument(
        "--countries",
        default="BR",
        help="comma-separated ISO-3166 country codes (default: BR)",
    )
    p.add_argument(
        "--max-parallel",
        default="auto",
        help="upper bound on workers; 'auto' to derive from machine resources",
    )
    p.add_argument(
        "--max-iterations",
        type=int,
        default=8,
        help="hard safety net for the outer ralph-style loop (default: 8)",
    )
    p.add_argument(
        "--extra-skills-dir",
        action="append",
        default=[],
        type=Path,
        help="extra search path (repeatable); only skills named in --extra-skill-name are pulled",
    )
    p.add_argument(
        "--extra-skill-name",
        action="append",
        default=[],
        help="name of an extra skill to pull from --extra-skills-dir (repeatable)",
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        default=Path(os.environ.get("PAPERFLOW_ROOT", "/app")),
        help="repo root path (default: /app inside the container, or $PAPERFLOW_ROOT)",
    )
    p.add_argument(
        "--local-config",
        type=Path,
        default=None,
        help="path to .paperflow.local.toml (default: <repo-root>/.paperflow.local.toml)",
    )


def _to_cli_args(args: argparse.Namespace, *, require_io: bool = True) -> CliArgs:
    repo_root = args.repo_root.resolve()
    local_config = (args.local_config or (repo_root / ".paperflow.local.toml")).resolve()

    max_parallel: int | None
    if args.max_parallel == "auto":
        max_parallel = None
    else:
        try:
            max_parallel = int(args.max_parallel)
        except ValueError:
            print(
                f"--max-parallel must be 'auto' or an integer; got {args.max_parallel!r}",
                file=sys.stderr,
            )
            raise SystemExit(2)

    countries = [c.strip() for c in args.countries.split(",") if c.strip()]

    return CliArgs(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        soon_days=args.soon_days,
        countries=countries,
        max_parallel=max_parallel,
        max_iterations=args.max_iterations,
        extra_skill_dirs=list(args.extra_skills_dir),
        extra_skill_names=list(args.extra_skill_name),
        repo_root=repo_root,
        local_config_path=local_config,
    )


if __name__ == "__main__":
    raise SystemExit(main())
