from __future__ import annotations

from datetime import datetime, timezone
import os
import pathlib
import sys


EXECUTION_LOG_ENV = "PAPERFLOW_EXECUTION_LOG"


def print_console(message: str, *, file=None) -> None:
    stream = sys.stdout if file is None else file
    encoding = getattr(stream, "encoding", None) or "utf-8"
    print(message.encode(encoding, "backslashreplace").decode(encoding),
          file=stream, flush=True)


def log_status(message: str, body: str | None = None) -> None:
    stamp = datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="seconds")
    line = f"[venue-matcher] {stamp} {message}"
    print_console(line)
    _append_execution_log(line, body)


def _append_execution_log(line: str, body: str | None = None) -> None:
    path = os.environ.get(EXECUTION_LOG_ENV)
    if not path:
        return
    try:
        target = pathlib.Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            if body:
                fh.write(body)
                if not body.endswith("\n"):
                    fh.write("\n")
    except OSError:
        return
