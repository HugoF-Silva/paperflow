"""Per-paper ralph loop. Re-runs a fresh inner pass with the SAME order until the
promise or max_ralph. Continuity: the inner agent reads its prior ranking.json,
and between passes a flat inline summarizer (compact_recap) resumes the just-
finished session and compacts it into a recap seeded as the next pass's first
assistant turn. run_pass / compact_recap are injectable for testing."""
from __future__ import annotations

import asyncio
import json
import logging
import pathlib
from dataclasses import dataclass

from logging_utils import log_status, one_line
import prompts
import inner_agent


@dataclass
class RalphResult:
    success: bool
    passes: int
    last_reason: str


_FATAL_PASS_EXCEPTIONS = {"AuthenticationError", "PermissionDeniedError"}


def has_promise(text: str) -> bool:
    return prompts.PROMISE_TAG in (text or "")


def _one_line(value, limit: int = 160) -> str:
    text = " ".join(str(value or "").split()).replace('"', "'")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _log_recap_result(out_dir: pathlib.Path, pass_no: int, max_ralph: int, recap: str) -> None:
    lines = [line.strip() for line in (recap or "").splitlines() if line.strip()]
    if not lines:
        log_status(f"ralph_recap_result paper={out_dir.name} pass={pass_no}/{max_ralph} empty=True")
        return
    for index, line in enumerate(lines, start=1):
        log_status(
            f"ralph_recap_bullet paper={out_dir.name} pass={pass_no}/{max_ralph} "
            f"bullet={index}/{len(lines)} text=\"{one_line(line)}\""
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
    *,
    run_pass=inner_agent.run_pass,
    compact_recap=_compact_recap,
    model: str = prompts.DEFAULT_MODEL,
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
            try:
                result = await run_pass(
                    system_prompt, user_order, recap, out_dir, inner_max_turns, model,
                    ralph_pass_no=pass_no, ralph_max_passes=max_ralph,
                )
            except Exception as exc:  # deterministic failure → next pass may recover
                logging.exception("inner pass %d failed", pass_no)
                log_status(
                    f"ralph_pass_error paper={out_dir.name} pass={pass_no}/{max_ralph} "
                    f"error={type(exc).__name__}"
                )
                last_reason = f"pass_exception:{type(exc).__name__}"
                if type(exc).__name__ in _FATAL_PASS_EXCEPTIONS:
                    log_status(
                        f"ralph_abort paper={out_dir.name} pass={pass_no}/{max_ralph} "
                        f"reason={last_reason}"
                    )
                    return RalphResult(False, pass_no, last_reason)
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
