from __future__ import annotations

from datetime import datetime, timezone


def log_status(message: str) -> None:
    stamp = datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="seconds")
    print(f"[venue-matcher] {stamp} {message}", flush=True)


def one_line(value, limit: int = 600) -> str:
    text = " ".join(str(value or "").split()).replace('"', "'")
    return text if len(text) <= limit else text[: limit - 3] + "..."
