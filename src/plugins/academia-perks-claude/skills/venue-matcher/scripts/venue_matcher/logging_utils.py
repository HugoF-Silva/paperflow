from __future__ import annotations

from datetime import datetime, timezone
import os
import pathlib


EXECUTION_LOG_ENV = "PAPERFLOW_EXECUTION_LOG"


def log_status(message: str) -> None:
    stamp = datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="seconds")
    line = f"[venue-matcher] {stamp} {message}"
    print(line, flush=True)
    _append_execution_log(line)


def _append_execution_log(line: str) -> None:
    path = os.environ.get(EXECUTION_LOG_ENV)
    if not path:
        return
    try:
        target = pathlib.Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        return


def one_line(value, limit: int = 600) -> str:
    text = " ".join(str(value or "").split()).replace('"', "'")
    return text if len(text) <= limit else text[: limit - 3] + "..."
