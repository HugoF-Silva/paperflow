"""Per-paper ralph loop. Re-runs a fresh inner pass with the SAME order until the
promise or max_ralph. Continuity: the inner agent reads its prior ranking.json,
and between passes a flat inline summarizer (compact_recap) resumes the just-
finished session and compacts it into a recap seeded as the next pass's first
assistant turn. run_pass / compact_recap are injectable for testing."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import pathlib
import re
import tempfile
import time
from dataclasses import dataclass

from logging_utils import log_status
import prompts
import inner_agent


@dataclass
class RalphResult:
    success: bool
    passes: int
    last_reason: str


_FATAL_PASS_EXCEPTIONS = {"AuthenticationError", "PermissionDeniedError"}
_RATE_LIMIT_WAIT_RE = re.compile(r"try again in ([0-9]+(?:\.[0-9]+)?)s", re.IGNORECASE)
_RATE_LIMIT_DEFAULT_WAIT = 30.0
_LOCK_POLL_SECONDS = 0.1
_LOCK_STALE_SECONDS = 120.0


def has_promise(text: str) -> bool:
    return prompts.PROMISE_TAG in (text or "")


def _one_line(value, limit: int = 160) -> str:
    text = " ".join(str(value or "").split()).replace('"', "'")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _error_field(value) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    text = str(value)
    if any(ch.isspace() for ch in text) or '"' in text or "'" in text:
        return json.dumps(text, ensure_ascii=False)
    return text


def _exception_details(exc: Exception) -> str:
    parts = [f"error={type(exc).__name__}"]
    message = getattr(exc, "message", None) or str(exc)
    if message:
        parts.append(f"message={_error_field(message)}")
    for attr, name in (
        ("status_code", "status"),
        ("request_id", "request_id"),
        ("type", "type"),
        ("code", "code"),
        ("param", "param"),
    ):
        value = getattr(exc, attr, None)
        if value:
            parts.append(f"{name}={_error_field(value)}")
    body = getattr(exc, "body", None)
    if body is not None:
        parts.append(f"body={_error_field(body)}")
    return " ".join(parts)


def _body_field(body, key: str):
    if not isinstance(body, dict):
        return None
    if body.get(key) is not None:
        return body.get(key)
    error = body.get("error")
    if isinstance(error, dict):
        return error.get(key)
    return None


def _rate_limit_wait_seconds(exc: Exception) -> float | None:
    body = getattr(exc, "body", None)
    code = getattr(exc, "code", None) or _body_field(body, "code")
    if code != "rate_limit_exceeded":
        return None
    message = " ".join(
        str(part) for part in (
            getattr(exc, "message", None),
            _body_field(body, "message"),
            str(exc),
        ) if part
    )
    match = _RATE_LIMIT_WAIT_RE.search(message)
    return max(0.0, float(match.group(1))) if match else _RATE_LIMIT_DEFAULT_WAIT


def _rate_limit_paths(out_dir: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    for key_name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        key_value = os.environ.get(key_name)
        if key_value:
            root = pathlib.Path(tempfile.gettempdir()) / "paperflow-rate-limits"
            digest = hashlib.sha256(f"{key_name}:{key_value}".encode()).hexdigest()[:24]
            return root / f"{digest}.json", root / f"{digest}.lock"
    root = pathlib.Path(out_dir).parent
    return root / "_rate_limit.json", root / "_rate_limit.lock"


def _acquire_lock(path: pathlib.Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            return os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > _LOCK_STALE_SECONDS:
                    path.unlink()
            except OSError:
                pass
            time.sleep(_LOCK_POLL_SECONDS)


def _read_rate_limit_state(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_rate_limit_state(path: pathlib.Path, state: dict) -> None:
    path.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")


def _record_rate_limit_delay(out_dir: pathlib.Path, seconds: float) -> float:
    state_path, lock_path = _rate_limit_paths(out_dir)
    fd = _acquire_lock(lock_path)
    try:
        now = time.time()
        spacing = max(0.0, float(seconds))
        state = _read_rate_limit_state(state_path)
        slot_at = max(float(state.get("next_at", 0) or 0), now + spacing)
        _write_rate_limit_state(state_path, {
            "next_at": slot_at + spacing,
            "spacing": spacing,
        })
        return max(0.0, slot_at - now)
    finally:
        os.close(fd)
        lock_path.unlink(missing_ok=True)


def _reserve_rate_limit_delay(out_dir: pathlib.Path) -> float:
    state_path, lock_path = _rate_limit_paths(out_dir)
    fd = _acquire_lock(lock_path)
    try:
        now = time.time()
        state = _read_rate_limit_state(state_path)
        next_at = float(state.get("next_at", 0) or 0)
        spacing = float(state.get("spacing", 0) or 0)
        if next_at <= now or spacing <= 0:
            return 0.0
        _write_rate_limit_state(state_path, {
            "next_at": next_at + spacing,
            "spacing": spacing,
        })
        return max(0.0, next_at - now)
    finally:
        os.close(fd)
        lock_path.unlink(missing_ok=True)


def _sleep_rate_limit(out_dir: pathlib.Path, pass_no: int, max_ralph: int, delay: float) -> None:
    if delay <= 0:
        return
    log_status(
        f"ralph_rate_limit_wait paper={out_dir.name} pass={pass_no}/{max_ralph} "
        f"seconds={delay:.3f}"
    )
    time.sleep(delay)


def _log_recap_result(out_dir: pathlib.Path, pass_no: int, max_ralph: int, recap: str) -> None:
    recap = recap or ""
    if not recap.strip():
        log_status(f"ralph_recap_result paper={out_dir.name} pass={pass_no}/{max_ralph} empty=True")
        return
    log_status(
        f"ralph_recap_result paper={out_dir.name} pass={pass_no}/{max_ralph} "
        f"chars={len(recap)} text={json.dumps(recap)}"
    )


def _artifact_snapshot(out_dir: pathlib.Path) -> tuple[bool, str, str]:
    path = out_dir / "ranking.json"
    if not path.exists():
        return False, "artifact_missing", "artifact=ranking.json status=missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return (
            False,
            "artifact_unreadable",
            f"artifact=ranking.json status=unreadable error={type(exc).__name__}",
        )

    paper = data.get("paper") if isinstance(data, dict) else {}
    open_now = data.get("open_now") if isinstance(data, dict) else []
    opening_soon = data.get("opening_soon") if isinstance(data, dict) else []
    closest_misses = data.get("closest_misses") if isinstance(data, dict) else []
    candidates = open_now or opening_soon or closest_misses or []
    top = candidates[0].get("name") if candidates and isinstance(candidates[0], dict) else ""
    notes = data.get("agent_notes", "") if isinstance(data, dict) else ""
    parts = ["artifact=ranking.json status=present"]
    if isinstance(paper, dict) and paper.get("is_statement"):
        parts.append(f'paper_is="{_one_line(paper.get("is_statement"))}"')
    if top:
        parts.append(f'top_venue="{_one_line(top, 80)}"')
    if isinstance(notes, str):
        parts.append(f"agent_notes_chars={len(notes)}")
    return True, "success", " ".join(parts)


async def _compact_recap(session_id: str | None, model: str) -> str:
    """Flat, tool-less, single-turn summarizer. Resumes the just-finished inner
    session so it inherits full memory (dead-ends included), and returns a terse
    bullet recap. Never neurotic, never verbose."""
    if not session_id:
        return ""
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage
    options = ClaudeAgentOptions(
        resume=session_id, allowed_tools=[], max_turns=1, model=model,
    )
    recap = ""
    async for message in query(prompt=prompts.SUMMARY_INSTRUCTION, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                text = getattr(block, "text", None)
                if isinstance(text, str):
                    recap = text
        elif isinstance(message, ResultMessage):
            recap = message.result or recap
    return recap


def run_for_paper(
    paper_text: str,
    soon_days: int,
    out_dir: pathlib.Path,
    max_ralph: int,
    inner_max_turns: int,
    model: str,
    *,
    run_pass=inner_agent.run_pass,
    compact_recap=_compact_recap,
) -> RalphResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    system_prompt = prompts.build_system_prompt()
    user_order = prompts.build_user_order(paper_text, soon_days)

    async def _run() -> RalphResult:
        recap: str | None = None
        last_reason = "max_ralph_exhausted"
        for pass_no in range(1, max_ralph + 1):
            log_status(
                f"ralph_pass_start paper={out_dir.name} pass={pass_no}/{max_ralph} "
                f"recap_seeded={bool(recap)}"
            )
            result = None
            waited_for_retry = False
            while result is None:
                if waited_for_retry:
                    waited_for_retry = False
                else:
                    _sleep_rate_limit(out_dir, pass_no, max_ralph, _reserve_rate_limit_delay(out_dir))
                try:
                    result = await run_pass(
                        system_prompt, user_order, recap, out_dir, inner_max_turns, model,
                        ralph_pass_no=pass_no, ralph_max_passes=max_ralph,
                    )
                except Exception as exc:  # deterministic failure → next pass may recover
                    log_status(
                        f"ralph_pass_error paper={out_dir.name} pass={pass_no}/{max_ralph} "
                        f"{_exception_details(exc)}"
                    )
                    wait_seconds = _rate_limit_wait_seconds(exc)
                    if wait_seconds is not None:
                        _sleep_rate_limit(
                            out_dir, pass_no, max_ralph,
                            _record_rate_limit_delay(out_dir, wait_seconds),
                        )
                        waited_for_retry = True
                        continue
                    last_reason = f"pass_exception:{type(exc).__name__}"
                    if type(exc).__name__ in _FATAL_PASS_EXCEPTIONS:
                        log_status(
                            f"ralph_abort paper={out_dir.name} pass={pass_no}/{max_ralph} "
                            f"reason={last_reason}"
                        )
                        return RalphResult(False, pass_no, last_reason)
                    break
            if result is None:
                continue
            promised = has_promise(result.last_text)
            artifact_ok, artifact_reason, artifact_snapshot = _artifact_snapshot(out_dir)
            log_status(
                f"ralph_pass_finish paper={out_dir.name} pass={pass_no}/{max_ralph} "
                f"promised={promised} output_chars={len(result.last_text or '')} "
                f"{artifact_snapshot}"
            )
            if promised and artifact_ok:
                return RalphResult(True, pass_no, "success")
            if promised:
                last_reason = artifact_reason
            if pass_no < max_ralph:                # final pass's recap would be discarded
                log_status(f"ralph_recap_start paper={out_dir.name} pass={pass_no}/{max_ralph}")
                recap = await compact_recap(result.session_id, model)
                log_status(
                    f"ralph_recap_finish paper={out_dir.name} pass={pass_no}/{max_ralph} "
                    f"chars={len(recap or '')}"
                )
                _log_recap_result(out_dir, pass_no, max_ralph, recap or "")
        log_status(f"ralph_exhausted paper={out_dir.name} max_ralph={max_ralph}")
        return RalphResult(False, max_ralph, last_reason)

    return asyncio.run(_run())
