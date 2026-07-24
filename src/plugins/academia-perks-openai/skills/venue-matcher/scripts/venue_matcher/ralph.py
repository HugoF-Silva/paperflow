"""Per-paper ralph loop. Re-runs a fresh inner pass until the promise or
max_ralph. Continuity: the inner agent reads its prior ranking.md, and between
passes a flat inline summarizer (compact_recap) resumes the just-finished
session and compacts it into a recap seeded as the next pass's first assistant
turn. run_pass / compact_recap are injectable for testing."""
from __future__ import annotations

import asyncio
import pathlib
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
    produced_agent_result: bool = False


_FATAL_PASS_EXCEPTIONS = {"AuthenticationError", "PermissionDeniedError"}


def has_promise(text: str) -> bool:
    return prompts.PROMISE_TAG in (text or "")


def _one_line(value, limit: int = 160) -> str:
    text = " ".join(str(value or "").split()).replace('"', "'")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _error_field(value) -> str:
    text = _one_line(value, 500)
    if any(ch.isspace() for ch in text) or '"' in text or "'" in text or "=" in text:
        return f'"{text}"'
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
        f'chars={len(recap)} text="{_one_line(recap, 600)}"'
    )


def _artifact_snapshot(out_dir: pathlib.Path) -> tuple[bool, str, str]:
    path = out_dir / "ranking.md"
    if not path.exists():
        return False, "artifact_missing", "artifact=ranking.md status=missing"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return (
            False,
            "artifact_unreadable",
            f"artifact=ranking.md status=unreadable error={type(exc).__name__}",
        )
    if not text.strip():
        return False, "artifact_empty", "artifact=ranking.md status=empty"
    return True, "success", f"artifact=ranking.md status=present chars={len(text)}"


async def _compact_recap(session_id: str | None, model: str) -> str:
    """Flat, tool-less, single-turn summarizer over the just-finished response."""
    if not session_id:
        return ""
    from agents import Agent, ModelSettings, Runner
    from openai.types.shared import Reasoning

    agent = Agent(
        name="venue-matcher-recap",
        instructions="Retorne somente a recapitulação compacta solicitada.",
        model=model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium"),
            verbosity="low",
        ),
    )
    result = await Runner.run(
        agent,
        prompts.SUMMARY_INSTRUCTION,
        previous_response_id=session_id,
        max_turns=1,
    )
    return str(result.final_output or "")


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
    x = max_ralph

    async def _run() -> RalphResult:
        recap: str | None = None
        last_reason = "max_ralph_exhausted"
        produced_agent_result = False
        for pass_no in range(1, max_ralph + 1):
            pass_user_order = prompts.build_pass_user_order(user_order, pass_no, x)
            log_status(
                f"ralph_pass_start paper={out_dir.name} pass={pass_no}/{max_ralph} "
                f"recap_seeded={bool(recap)}"
            )
            result = None
            consecutive_rate_limit_errors = 0
            while result is None:
                try:
                    result = await run_pass(
                        system_prompt, pass_user_order, recap, out_dir, inner_max_turns, model,
                        ralph_pass_no=pass_no, ralph_max_passes=max_ralph,
                    )
                    consecutive_rate_limit_errors = 0
                except Exception as exc:  # deterministic failure → next pass may recover
                    log_status(
                        f"ralph_pass_error paper={out_dir.name} pass={pass_no}/{max_ralph} "
                        f"{_exception_details(exc)}"
                    )
                    wait_seconds = inner_agent._rate_limit_wait_seconds(
                        exc, consecutive_rate_limit_errors
                    )
                    if wait_seconds is not None:
                        consecutive_rate_limit_errors += 1
                        _sleep_rate_limit(out_dir, pass_no, max_ralph, wait_seconds)
                        continue
                    last_reason = f"pass_exception:{type(exc).__name__}"
                    if type(exc).__name__ in _FATAL_PASS_EXCEPTIONS:
                        log_status(
                            f"ralph_abort paper={out_dir.name} pass={pass_no}/{max_ralph} "
                            f"reason={last_reason}"
                        )
                        return RalphResult(False, pass_no, last_reason, produced_agent_result)
                    break
            if result is None:
                continue
            produced_agent_result = True
            promised = has_promise(result.last_text)
            artifact_ok, artifact_reason, artifact_snapshot = _artifact_snapshot(out_dir)
            log_status(
                f"ralph_pass_finish paper={out_dir.name} pass={pass_no}/{max_ralph} "
                f"promised={promised} output_chars={len(result.last_text or '')} "
                f"{artifact_snapshot}"
            )
            if promised and artifact_ok:
                return RalphResult(True, pass_no, "success", produced_agent_result)
            if promised:
                last_reason = artifact_reason
            if pass_no < max_ralph:                # final pass's recap would be discarded
                log_status(f"ralph_recap_start paper={out_dir.name} pass={pass_no}/{max_ralph}")
                try:
                    recap = await compact_recap(result.session_id, model)
                except Exception as exc:
                    last_reason = f"recap_exception:{type(exc).__name__}"
                    log_status(
                        f"ralph_recap_error paper={out_dir.name} pass={pass_no}/{max_ralph} "
                        f"{_exception_details(exc)}"
                    )
                    return RalphResult(False, pass_no, last_reason, produced_agent_result)
                log_status(
                    f"ralph_recap_finish paper={out_dir.name} pass={pass_no}/{max_ralph} "
                    f"chars={len(recap or '')}"
                )
                _log_recap_result(out_dir, pass_no, max_ralph, recap or "")
        log_status(f"ralph_exhausted paper={out_dir.name} max_ralph={max_ralph}")
        return RalphResult(False, max_ralph, last_reason, produced_agent_result)

    return asyncio.run(_run())
