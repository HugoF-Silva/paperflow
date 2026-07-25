"""Ralph continuation loop for one paper conversion."""
from __future__ import annotations

import asyncio
import json
import pathlib
from dataclasses import dataclass

import inner_agent
import prompts
import tools
from runner import WorkUnit


@dataclass(frozen=True)
class RalphResult:
    status: str
    passes: int
    last_reason: str


_FATAL_ERROR_NAMES = {"AuthenticationError", "PermissionDeniedError"}


def _is_fatal(exc: Exception) -> bool:
    return (
        type(exc).__name__ in _FATAL_ERROR_NAMES
        or getattr(exc, "status_code", None) in {401, 403}
    )


def _complete_artifacts(workspace: pathlib.Path) -> bool:
    converted = workspace / "converted"
    tex = converted / "main.tex"
    pdf = converted / "main.pdf"
    attestation = workspace / tools._COMPILE_ATTESTATION
    try:
        if (
            workspace.is_symlink()
            or converted.is_symlink()
            or not converted.is_dir()
            or tex.is_symlink()
            or not tex.is_file()
            or tex.stat().st_size == 0
            or not tools._is_real_pdf(pdf)
            or attestation.is_symlink()
            or not attestation.is_file()
        ):
            return False
        recorded = json.loads(attestation.read_text(encoding="utf-8"))
        current = {
            "tex": {
                "path": "converted/main.tex",
                "sha256": tools._sha256(tex),
            },
            "pdf": {
                "path": "converted/main.pdf",
                "sha256": tools._sha256(pdf),
            },
        }
        registered = tools._COMPILE_ATTESTATIONS.get(workspace.resolve())
        return recorded == current == registered
    except (OSError, UnicodeError, ValueError, TypeError):
        return False


def _status_snapshot(workspace: pathlib.Path) -> tuple[int, int, int, int, str] | None:
    status = workspace / "conversion-status.md"
    try:
        if status.is_symlink() or not status.is_file():
            return None
        stat = status.stat()
        return (
            stat.st_dev,
            stat.st_ino,
            stat.st_mtime_ns,
            stat.st_size,
            tools._sha256(status),
        )
    except OSError:
        return None


def _blocked_artifact(
    workspace: pathlib.Path,
    previous: tuple[int, int, int, int, str] | None,
) -> bool:
    status = workspace / "conversion-status.md"
    try:
        current = _status_snapshot(workspace)
        return (
            current is not None
            and current != previous
            and bool(status.read_text(encoding="utf-8").strip())
        )
    except (OSError, UnicodeError):
        return False


def _final_promise(text: str) -> str | None:
    for line in reversed((text or "").splitlines()):
        if line.strip():
            return line if line in {prompts.COMPLETE_PROMISE, prompts.BLOCKED_PROMISE} else None
    return None


async def _compact_recap(session_id: str | None, model: str) -> str:
    if not session_id:
        return ""
    from agents import Agent, ModelSettings, Runner

    agent = Agent(
        name="converter-recap",
        instructions="Return only the requested en-US bullet recap.",
        model=model,
        model_settings=ModelSettings(verbosity="low"),
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
    unit: WorkUnit,
    max_ralph: int,
    inner_max_turns: int,
    model: str,
    *,
    run_pass=inner_agent.run_pass,
    compact_recap=_compact_recap,
) -> RalphResult:
    blocked_before = _status_snapshot(unit.workspace)
    unit.workspace.mkdir(parents=True, exist_ok=True)
    system_prompt = prompts.build_system_prompt(unit.workspace)
    order = prompts.build_user_order(unit, paper_text)

    async def _run() -> RalphResult:
        recap: str | None = None
        last_reason = "max_ralph_exhausted"
        for pass_no in range(1, max_ralph + 1):
            pass_order = prompts.build_pass_user_order(order, pass_no, max_ralph)
            result = None
            consecutive_rate_limit_errors = 0
            while result is None:
                try:
                    result = await run_pass(
                        system_prompt,
                        pass_order,
                        recap,
                        unit.workspace,
                        inner_max_turns,
                        model,
                        ralph_pass_no=pass_no,
                        ralph_max_passes=max_ralph,
                    )
                except Exception as exc:
                    last_reason = f"pass_exception:{type(exc).__name__}"
                    if _is_fatal(exc):
                        return RalphResult("failed", pass_no, last_reason)
                    delay = inner_agent._rate_limit_delay(exc, consecutive_rate_limit_errors)
                    if delay is not None:
                        consecutive_rate_limit_errors += 1
                        await asyncio.sleep(delay)
                        continue
                    break
            if result is None:
                continue

            promise = _final_promise(result.last_text)
            if promise == prompts.COMPLETE_PROMISE:
                if _complete_artifacts(unit.workspace):
                    return RalphResult("complete", pass_no, "complete")
                last_reason = "complete_artifact_gate_failed"
            elif promise == prompts.BLOCKED_PROMISE:
                if _blocked_artifact(unit.workspace, blocked_before):
                    return RalphResult("blocked", pass_no, "blocked")
                last_reason = "blocked_artifact_gate_failed"

            if pass_no < max_ralph:
                recap_rate_limit_errors = 0
                while True:
                    try:
                        recap = await compact_recap(result.session_id, model)
                    except Exception as exc:
                        last_reason = f"recap_exception:{type(exc).__name__}"
                        if _is_fatal(exc):
                            return RalphResult("failed", pass_no, last_reason)
                        delay = inner_agent._rate_limit_delay(exc, recap_rate_limit_errors)
                        if delay is not None:
                            recap_rate_limit_errors += 1
                            await asyncio.sleep(delay)
                            continue
                        recap = None
                    break

        return RalphResult("failed", max_ralph, last_reason)

    return asyncio.run(_run())
