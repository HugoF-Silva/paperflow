"""Composition root: assembles the Orchestrator object graph from CLI args
and the optional local config. Skill resolution and conflict validation
happen here so any entry point (cli.py, future tests, future drivers) get
a fully-wired orchestrator with one call.
"""

from __future__ import annotations

import logging
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from batch_venue_matcher.orchestrator import Orchestrator
from batch_venue_matcher.worker import WorkerConfig

MAIN_SKILL_NAME = "venue-matcher"


@dataclass
class CliArgs:
    """Parsed CLI args, normalized for the composition step."""

    input_dir: Path
    output_dir: Path
    soon_days: int
    countries: list[str]
    max_parallel: int | None
    max_iterations: int
    extra_skill_dirs: list[Path]
    extra_skill_names: list[str]
    repo_root: Path
    local_config_path: Path


@dataclass
class StagingPlan:
    """The resolved set of skills to copy into `.claude/skills/` at run time.

    `entries` is a list of `(source_dir, name)` pairs. The main skill is
    always first. Any extras follow in the order the user requested.
    """

    entries: list[tuple[Path, str]]
    skill_names: list[str]
    warnings: list[str]


def build_orchestrator(args: CliArgs) -> Orchestrator:
    """Resolve extras, validate conflicts, return a ready-to-run orchestrator."""

    plan = resolve_skills(args)
    for warning in plan.warnings:
        logging.warning(warning)

    worker_config = WorkerConfig(
        cwd=args.repo_root,
        skill_names=plan.skill_names,
        max_iterations=args.max_iterations,
    )

    return Orchestrator(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        soon_days=args.soon_days,
        countries=args.countries,
        user_max_parallel=args.max_parallel,
        worker_config=worker_config,
        skill_staging_dir=args.repo_root / ".claude" / "skills",
        skills_to_stage=plan.entries,
    )


def resolve_skills(args: CliArgs) -> StagingPlan:
    """Validate that the main skill exists, resolve each requested extra to
    exactly one source directory, and check for name conflicts.

    Fatal-errors (raise SystemExit) on conflict or missing main skill.
    Warns (returned in `StagingPlan.warnings`) on requested names that
    aren't found in any extra dir.
    """

    extras_from_config = _load_local_config(args.local_config_path)
    merged_dirs = _dedup_paths(args.extra_skill_dirs + extras_from_config["dirs"])
    merged_names = _dedup_strings(args.extra_skill_names + extras_from_config["names"])

    main_source = args.repo_root / "skills" / MAIN_SKILL_NAME
    if not (main_source / "SKILL.md").exists():
        _fatal(f"main skill not found at {main_source}/SKILL.md")

    entries: list[tuple[Path, str]] = [(main_source, MAIN_SKILL_NAME)]
    warnings: list[str] = []

    for name in merged_names:
        if name == MAIN_SKILL_NAME:
            _fatal(f"extra skill '{name}' conflicts with the main skill name")
        matches = [d for d in merged_dirs if (d / name / "SKILL.md").exists()]
        if not matches:
            warnings.append(
                f"requested extra skill '{name}' not found in any of: "
                + ", ".join(str(d) for d in merged_dirs)
            )
            continue
        if len(matches) > 1:
            _fatal(
                f"extra skill '{name}' found in multiple dirs — conflict: "
                + ", ".join(str(d) for d in matches)
            )
        entries.append((matches[0] / name, name))

    return StagingPlan(
        entries=entries,
        skill_names=[name for _, name in entries],
        warnings=warnings,
    )


def _load_local_config(path: Path) -> dict[str, list]:
    if not path.exists() or path.stat().st_size == 0:
        return {"dirs": [], "names": []}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        _fatal(f"could not parse {path}: {exc}")
    extras = data.get("extras", {})
    return {
        "dirs": [Path(d) for d in extras.get("dirs", [])],
        "names": list(extras.get("names", [])),
    }


def _dedup_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:
        resolved = p.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


def _dedup_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for s in items:
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _fatal(msg: str) -> None:
    print(f"FATAL: {msg}", file=sys.stderr, flush=True)
    raise SystemExit(2)
