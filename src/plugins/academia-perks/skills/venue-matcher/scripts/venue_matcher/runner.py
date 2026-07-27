"""Dispatch one process per paper (sequential by default), with resource-aware
sizing when MAX_PARALLEL=auto, and a progress log."""
from __future__ import annotations

import os
import pathlib
import shutil
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp

import extraction
from logging_utils import log_status
import ralph

EST_BYTES_PER_WORKER = 800 * 1024 * 1024
CPU_SAFETY = 0.8
MEM_SAFETY = 0.7
# Windows caps directory paths at 247 chars (260 MAX_PATH minus an 8.3 name)
# without long-path support; each paper workspace dir is out_dir/<stem>.
WORKSPACE_PATH_BUDGET = 247


def workspaces_too_deep(out_dir: pathlib.Path, papers) -> list:
    """Papers whose workspace dir paths certainly exceed Windows path limits."""
    root = pathlib.Path(out_dir).resolve()
    return [
        paper for paper in papers
        if len(str(root / paper.stem)) > WORKSPACE_PATH_BUDGET
    ]


def resolve_max_parallel(env_value: str | None) -> int | str:
    if env_value is None or env_value.strip() == "":
        return 1
    if env_value.strip().lower() == "auto":
        return "auto"
    return max(1, int(env_value))


def compute_pool_size(num_papers, max_parallel, cpu_count, cpu_used_pct,
                      mem_free_bytes, est_bytes_per_worker) -> int:
    cpu_free = max(0.0, cpu_count * (1 - cpu_used_pct / 100))
    cpu_workers = max(1, int(cpu_free * CPU_SAFETY) - 1)
    mem_workers = max(1, int(mem_free_bytes * MEM_SAFETY) // est_bytes_per_worker)
    resource_cap = min(cpu_workers, mem_workers)
    if isinstance(max_parallel, int):
        upper = min(max_parallel, resource_cap)   # explicit N is still clamped
    else:  # "auto"
        upper = resource_cap
    return max(1, min(num_papers, upper))


def _auto_inputs():
    import psutil
    return (os.cpu_count() or 1, psutil.cpu_percent(interval=1.0),
            psutil.virtual_memory().available)


def append_progress(path: pathlib.Path, done: int, total: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bar_len = 20
    filled = int(bar_len * done / total) if total else bar_len
    bar = "#" * filled + "-" * (bar_len - filled)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"[{bar}] {done}/{total} papers done\n")


def reset_progress(path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def append_error(path: pathlib.Path, paper: pathlib.Path, error: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    detail = " ".join(str(error or "failed").split())
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"ERROR {paper.name}: {detail}\n")


def write_sentinel(path: pathlib.Path, total: int) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"BATCH COMPLETE: {total}/{total}\n")


def reset_paper_output(out_dir: pathlib.Path, paper: pathlib.Path) -> None:
    shutil.rmtree(out_dir / paper.stem, ignore_errors=True)


def _result_status(result) -> tuple[bool, str, bool]:
    if isinstance(result, tuple):
        ok, reason, *produced = result
        return bool(ok), str(reason or "failed"), bool(produced[0] if produced else ok)
    ok = bool(result)
    return ok, "failed", ok


def _process_one(paper, out_dir, soon_days, max_ralph, inner_max_turns, model):
    log_status(f"paper_start paper={paper.name}")
    try:
        text = extraction.extract_text(paper)
        log_status(f"paper_extracted paper={paper.name} chars={len(text)}")
        res = ralph.run_for_paper(text, soon_days, out_dir / paper.stem,
                                  max_ralph, inner_max_turns, model=model)
    except Exception as exc:
        log_status(f"paper_error paper={paper.name} error={type(exc).__name__}")
        raise
    log_status(
        f"paper_finish paper={paper.name} success={res.success} "
        f"passes={res.passes} reason={res.last_reason}"
    )
    return res.success, res.last_reason, res.produced_agent_result


def run_batch(papers, out_dir, soon_days, max_ralph, inner_max_turns,
              max_parallel, model, *, process_one=_process_one) -> dict:
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    progress = out_dir / "_progress.log"
    total = len(papers)
    reset_progress(progress)
    log_status(f"batch_start papers={total} out_dir={out_dir}")

    mp_setting = max_parallel if max_parallel == "auto" else int(max_parallel)
    if mp_setting == 1:
        pool = 1                                  # sequential: no need to probe resources
    else:
        cpu_count, cpu_used, mem_free = _auto_inputs()
        pool = compute_pool_size(total, mp_setting, cpu_count, cpu_used, mem_free,
                                 EST_BYTES_PER_WORKER)
    log_status(f"pool_size workers={pool} papers={total} max_parallel={max_parallel}")

    succeeded = 0
    done = 0
    agent_result_stems = []
    if pool <= 1:
        for paper in papers:
            reset_paper_output(out_dir, paper)
            try:
                ok, reason, produced_agent_result = _result_status(
                    process_one(paper, out_dir, soon_days, max_ralph,
                                inner_max_turns, model)
                )
            except Exception as exc:
                ok = False
                produced_agent_result = False
                reason = f"{type(exc).__name__}: {exc}"
                append_error(progress, paper, reason)
                log_status(f"batch_error paper={paper.name} error={type(exc).__name__}")
            else:
                if not ok:
                    append_error(progress, paper, reason)
            if produced_agent_result:
                agent_result_stems.append(paper.stem)
            succeeded += int(bool(ok))
            done += 1
            append_progress(progress, done, total)
            log_status(f"batch_progress done={done} total={total} succeeded={succeeded}")
    else:
        ctx = mp.get_context("spawn")
        with ProcessPoolExecutor(max_workers=pool, mp_context=ctx) as ex:
            futs = {}
            for paper in papers:
                reset_paper_output(out_dir, paper)
                futs[ex.submit(process_one, paper, out_dir, soon_days, max_ralph,
                               inner_max_turns, model)] = paper
            from concurrent.futures import as_completed
            for fut in as_completed(futs):
                paper = futs[fut]
                try:
                    ok, reason, produced_agent_result = _result_status(fut.result())
                except Exception as exc:
                    ok = False
                    produced_agent_result = False
                    reason = f"{type(exc).__name__}: {exc}"
                    append_error(progress, paper, reason)
                    log_status(f"batch_error paper={paper.name} error={type(exc).__name__}")
                else:
                    if not ok:
                        append_error(progress, paper, reason)
                if produced_agent_result:
                    agent_result_stems.append(paper.stem)
                succeeded += int(bool(ok))
                done += 1
                append_progress(progress, done, total)
                log_status(f"batch_progress done={done} total={total} succeeded={succeeded}")

    write_sentinel(progress, total)
    log_status(f"batch_complete succeeded={succeeded} total={total} failed={total - succeeded}")
    return {
        "total": total,
        "succeeded": succeeded,
        "failed": total - succeeded,
        "agent_result_stems": sorted(agent_result_stems),
    }
