"""Dispatch one process per paper (sequential by default), with resource-aware
sizing when MAX_PARALLEL=auto, and a progress log the outer agent polls."""
from __future__ import annotations

import os
import pathlib
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
from datetime import datetime, timezone

import extraction
import ralph

EST_BYTES_PER_WORKER = 800 * 1024 * 1024
CPU_SAFETY = 0.8
MEM_SAFETY = 0.7


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


def write_sentinel(path: pathlib.Path, total: int) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"BATCH COMPLETE: {total}/{total}\n")


def _process_one(paper, out_dir, soon_days, max_ralph, inner_max_turns) -> bool:
    text = extraction.extract_text(paper)
    res = ralph.run_for_paper(text, soon_days, out_dir / paper.stem,
                              max_ralph, inner_max_turns)
    if not res.success:
        fail = out_dir / "_failures.log"
        stamp = datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="seconds")
        with fail.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp}  {paper.name}  {res.last_reason}\n")
    return res.success


def run_batch(papers, out_dir, soon_days, max_ralph, inner_max_turns,
              max_parallel, *, process_one=_process_one) -> dict:
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    progress = out_dir / "_progress.log"
    total = len(papers)

    cpu_count, cpu_used, mem_free = _auto_inputs()
    mp_setting = max_parallel if max_parallel == "auto" else int(max_parallel)
    pool = compute_pool_size(total, mp_setting, cpu_count, cpu_used, mem_free,
                             EST_BYTES_PER_WORKER)
    print(f"pool size: {pool} (papers={total}, max_parallel={max_parallel})", flush=True)

    succeeded = 0
    done = 0
    if pool <= 1:
        for paper in papers:
            ok = process_one(paper, out_dir, soon_days, max_ralph, inner_max_turns)
            succeeded += int(bool(ok))
            done += 1
            append_progress(progress, done, total)
    else:
        ctx = mp.get_context("spawn")
        with ProcessPoolExecutor(max_workers=pool, mp_context=ctx) as ex:
            futs = {ex.submit(process_one, p, out_dir, soon_days, max_ralph,
                              inner_max_turns): p for p in papers}
            from concurrent.futures import as_completed
            for fut in as_completed(futs):
                succeeded += int(bool(fut.result()))
                done += 1
                append_progress(progress, done, total)

    write_sentinel(progress, total)
    return {"total": total, "succeeded": succeeded, "failed": total - succeeded}
