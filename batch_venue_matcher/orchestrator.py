"""Orchestrator: probes machine resources, sizes the worker pool, dispatches
one process per paper, aggregates results, logs failures."""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import psutil

from batch_venue_matcher.worker import Worker, WorkerConfig, WorkerResult

ESTIMATED_BYTES_PER_WORKER = 800 * 1024 * 1024  # 800 MiB — internal constant
CPU_SAFETY_FRACTION = 0.8
MEM_SAFETY_FRACTION = 0.7


@dataclass
class ResourcePlan:
    """The pool-sizing decision plus its inputs, so the CLI can print
    the math."""

    cpu_count: int
    cpu_used_pct: float
    cpu_workers: int
    mem_free_gib: float
    mem_workers: int
    num_papers: int
    user_max: int | None
    chosen: int

    def explain(self) -> str:
        capped_by = []
        if self.chosen == self.cpu_workers:
            capped_by.append("cpu")
        if self.chosen == self.mem_workers:
            capped_by.append("mem")
        if self.chosen == self.num_papers:
            capped_by.append("papers")
        if self.user_max is not None and self.chosen == self.user_max:
            capped_by.append("user_max_parallel")
        return (
            f"host:    {self.cpu_count} CPUs ({self.cpu_used_pct:.0f}% in use), "
            f"{self.mem_free_gib:.1f} GiB RAM free\n"
            f"budget:  {int(CPU_SAFETY_FRACTION * 100)}% of free CPU, "
            f"{int(MEM_SAFETY_FRACTION * 100)}% of free RAM, ≥1 CPU for the OS\n"
            f"result:  {self.chosen} workers   "
            f"(cpu={self.cpu_workers}, mem={self.mem_workers}, "
            f"papers={self.num_papers}"
            + (
                f", user_max={self.user_max}"
                if self.user_max is not None
                else ""
            )
            + f", capped_by={','.join(capped_by) or 'none'})"
        )


def plan_pool(num_papers: int, user_max: int | None) -> ResourcePlan:
    cpu_count = os.cpu_count() or 1
    cpu_used = psutil.cpu_percent(interval=1.0)
    cpu_free = max(0.0, cpu_count * (1 - cpu_used / 100))
    cpu_workers = max(1, int(cpu_free * CPU_SAFETY_FRACTION) - 1)

    mem_free_bytes = psutil.virtual_memory().available
    mem_workers = max(
        1,
        int(mem_free_bytes * MEM_SAFETY_FRACTION) // ESTIMATED_BYTES_PER_WORKER,
    )

    candidates = [num_papers, cpu_workers, mem_workers]
    if user_max is not None:
        candidates.append(user_max)
    chosen = max(1, min(candidates))

    return ResourcePlan(
        cpu_count=cpu_count,
        cpu_used_pct=cpu_used,
        cpu_workers=cpu_workers,
        mem_free_gib=mem_free_bytes / (1024**3),
        mem_workers=mem_workers,
        num_papers=num_papers,
        user_max=user_max,
        chosen=chosen,
    )


def _run_worker(
    config: WorkerConfig,
    paper: Path,
    output_dir: Path,
    soon_days: int,
    countries: list[str],
) -> WorkerResult:
    """Module-level entry so ProcessPoolExecutor can dispatch it to a child."""
    worker = Worker(config)
    return worker.run(paper, output_dir, soon_days, countries)


@dataclass
class Orchestrator:
    input_dir: Path
    output_dir: Path
    soon_days: int
    countries: list[str]
    user_max_parallel: int | None
    worker_config: WorkerConfig
    skill_staging_dir: Path
    skills_to_stage: list[tuple[Path, str]]  # (source_dir, name)

    def run(self) -> int:
        papers = sorted(self.input_dir.glob("*.docx"))
        if not papers:
            logging.warning("No .docx papers found in %s", self.input_dir)
            return 0

        self._stage_skills()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        plan = plan_pool(len(papers), self.user_max_parallel)
        print(plan.explain(), flush=True)

        successes = 0
        failures = 0

        # spawn start method — predictable across platforms and avoids
        # subtle interactions between asyncio and fork.
        ctx = mp.get_context("spawn")
        with ProcessPoolExecutor(max_workers=plan.chosen, mp_context=ctx) as pool:
            futures = {
                pool.submit(
                    _run_worker,
                    self.worker_config,
                    paper,
                    self.output_dir / paper.stem,
                    self.soon_days,
                    self.countries,
                ): paper
                for paper in papers
            }
            for future in as_completed(futures):
                paper = futures[future]
                try:
                    result = future.result()
                except Exception:
                    logging.exception("Worker process raised for %s", paper.name)
                    self._log_failure(paper, "worker_process_exception")
                    failures += 1
                    continue
                if result.success:
                    successes += 1
                    print(f"OK    {paper.name}  ({result.iterations} iters)", flush=True)
                else:
                    failures += 1
                    self._log_failure(paper, result.last_reason)
                    print(
                        f"FAIL  {paper.name}  ({result.iterations} iters, "
                        f"last={result.last_reason})",
                        flush=True,
                    )

        print(
            f"\nDone. {successes} succeeded, {failures} failed, "
            f"{len(papers)} total.",
            flush=True,
        )
        return 0 if failures == 0 else 1

    def _stage_skills(self) -> None:
        """Rebuild `.claude/skills/` from scratch each run. Conflicts have
        already been validated upstream in compose.py."""

        if self.skill_staging_dir.exists():
            shutil.rmtree(self.skill_staging_dir)
        self.skill_staging_dir.mkdir(parents=True)

        for source_dir, name in self.skills_to_stage:
            dst = self.skill_staging_dir / name
            shutil.copytree(source_dir, dst)
            logging.info("staged skill: %s -> %s", source_dir, dst)

    def _log_failure(self, paper: Path, reason: str) -> None:
        log_path = self.output_dir / "_failures.log"
        stamp = datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="seconds")
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp}  {paper.name}  {reason}\n")
