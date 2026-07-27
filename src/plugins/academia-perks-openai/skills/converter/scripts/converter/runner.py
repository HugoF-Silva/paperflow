"""Select converter work units and size their worker pool."""
from __future__ import annotations

import os
import pathlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import multiprocessing as mp
from tools import _set_process_nondumpable

EST_BYTES_PER_WORKER = 800 * 1024 * 1024
CPU_SAFETY = 0.8
MEM_SAFETY = 0.7


@dataclass(frozen=True)
class WorkUnit:
    paper: pathlib.Path
    workspace: pathlib.Path
    mode: str
    source: str


def _resolve_workspace(root: pathlib.Path, workspace: pathlib.Path) -> pathlib.Path:
    root = root.resolve()
    if workspace.is_symlink():
        raise ValueError(f"Converter workspace must not be a symlink: {workspace}")
    resolved = workspace.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Converter workspace resolves outside {root}: {workspace}")
    return resolved


def select_work_units(
    input_dir: pathlib.Path,
    output_dir: pathlib.Path,
    *,
    results_dir: pathlib.Path | None,
    chosen_venue: str | None,
    template_path: pathlib.Path | None,
) -> tuple[pathlib.Path, list[WorkUnit]]:
    papers = sorted(input_dir.glob("*.docx"))
    if not papers:
        raise ValueError(f"No .docx papers found in {input_dir}")

    if results_dir is not None:
        results_dir = results_dir.resolve()
        papers_by_stem = {paper.stem: paper for paper in papers}
        units = []
        for workspace in sorted(results_dir.iterdir()):
            if not workspace.is_dir():
                continue
            workspace = _resolve_workspace(results_dir, workspace)
            paper = papers_by_stem.get(workspace.name)
            if paper is None:
                continue
            units.append(
                WorkUnit(paper, workspace, "results", (workspace / "ranking.md").as_posix())
            )
        if not units:
            raise ValueError(f"No converter workspaces found in {results_dir}")
        return results_dir, units

    paper = papers[0]
    output_dir = output_dir.resolve()
    workspace = _resolve_workspace(output_dir, output_dir / paper.stem)
    if chosen_venue is not None:
        return output_dir, [WorkUnit(paper, workspace, "chosen-venue", chosen_venue)]
    return output_dir, [
        WorkUnit(paper, workspace, "template-path", template_path.as_posix())
    ]


def resolve_max_parallel(raw: str | None) -> int | str:
    if raw is None or raw.strip() == "":
        return 1
    if raw.strip().lower() == "auto":
        return "auto"
    value = int(raw)
    if value < 1:
        raise ValueError("MAX_PARALLEL must be a positive integer or auto")
    return value


def compute_pool_size(
    num_papers: int,
    max_parallel: int | str,
    cpu_count: int,
    cpu_used_pct: float,
    mem_free_bytes: int,
    est_bytes_per_worker: int,
) -> int:
    cpu_free = max(0.0, cpu_count * (1 - cpu_used_pct / 100))
    cpu_workers = max(1, int(cpu_free * CPU_SAFETY) - 1)
    mem_workers = max(1, int(mem_free_bytes * MEM_SAFETY) // est_bytes_per_worker)
    resource_cap = min(cpu_workers, mem_workers)
    upper = min(max_parallel, resource_cap) if isinstance(max_parallel, int) else resource_cap
    return max(1, min(num_papers, upper))


def _auto_inputs() -> tuple[int, float, int]:
    import psutil

    return os.cpu_count() or 1, psutil.cpu_percent(interval=1.0), psutil.virtual_memory().available


def _process_one(unit, max_ralph, inner_max_turns, model):
    _set_process_nondumpable()
    import extraction
    import prompts
    import ralph

    extracted_text = extraction.extract_paper(unit.paper, unit.workspace)
    prompts.build_system_prompt(unit.workspace)
    prompts.build_user_order(unit, extracted_text)
    return ralph.run_for_paper(
        extracted_text, unit, max_ralph, inner_max_turns, model
    )


def _result_status(result) -> tuple[str, str]:
    status = getattr(result, "status", None)
    if status is None:
        status = "complete" if result else "failed"
    if status not in {"complete", "blocked"}:
        status = "failed"
    return status, str(getattr(result, "last_reason", status))


def _append_progress(
    path: pathlib.Path, done: int, total: int, unit: WorkUnit, status: str, reason: str
) -> None:
    detail = " ".join(reason.split())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{done}/{total} {unit.paper.name}: {status}")
        if status != "complete":
            handle.write(f" ({detail})")
        handle.write("\n")


def run_batch(
    units: list[WorkUnit],
    batch_root: pathlib.Path,
    max_ralph: int,
    inner_max_turns: int,
    max_parallel: int | str,
    model: str,
    *,
    process_one=_process_one,
    resource_probe=_auto_inputs,
) -> dict:
    batch_root.mkdir(parents=True, exist_ok=True)
    progress = batch_root / "_converter_progress.log"
    progress.write_text("", encoding="utf-8")
    total = len(units)
    setting = max_parallel if max_parallel == "auto" else int(max_parallel)
    pool = 1
    if setting != 1:
        cpu_count, cpu_used, mem_free = resource_probe()
        pool = compute_pool_size(
            total, setting, cpu_count, cpu_used, mem_free, EST_BYTES_PER_WORKER
        )

    counts = {"complete": 0, "blocked": 0, "failed": 0}

    def record(unit, result=None, error=None):
        if error is None:
            status, reason = _result_status(result)
        else:
            status, reason = "failed", f"{type(error).__name__}: {error}"
        counts[status] += 1
        _append_progress(progress, sum(counts.values()), total, unit, status, reason)

    if pool == 1:
        for unit in units:
            try:
                record(
                    unit,
                    process_one(unit, max_ralph, inner_max_turns, model),
                )
            except Exception as exc:
                record(unit, error=exc)
    else:
        context = mp.get_context("spawn")
        with ProcessPoolExecutor(max_workers=pool, mp_context=context) as executor:
            futures = {
                executor.submit(
                    process_one, unit, max_ralph, inner_max_turns, model
                ): unit
                for unit in units
            }
            for future in as_completed(futures):
                try:
                    record(futures[future], future.result())
                except Exception as exc:
                    record(futures[future], error=exc)

    with progress.open("a", encoding="utf-8") as handle:
        handle.write(f"BATCH COMPLETE: {total}/{total}\n")
    return {
        "total": total,
        "succeeded": counts["complete"],
        "blocked": counts["blocked"],
        "failed": counts["failed"],
    }
