"""Per-paper ralph loop. Re-runs a fresh inner pass with the SAME order until the
promise or max_ralph. Continuity: the inner agent reads its prior ranking.json,
and between passes a flat inline summarizer (compact_recap) resumes the just-
finished session and compacts it into a recap seeded as the next pass's first
assistant turn. run_pass / compact_recap are injectable for testing."""
from __future__ import annotations

import asyncio
import logging
import pathlib
from dataclasses import dataclass

import prompts
import inner_agent


@dataclass
class RalphResult:
    success: bool
    passes: int
    last_reason: str


def has_promise(text: str) -> bool:
    return prompts.PROMISE_TAG in (text or "")


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
            try:
                result = await run_pass(
                    system_prompt, user_order, recap, out_dir, inner_max_turns, model,
                )
            except Exception as exc:  # deterministic failure → next pass may recover
                logging.exception("inner pass %d failed", pass_no)
                last_reason = f"pass_exception:{type(exc).__name__}"
                continue
            if has_promise(result.last_text):
                return RalphResult(True, pass_no, "success")
            if pass_no < max_ralph:                # final pass's recap would be discarded
                recap = await compact_recap(result.session_id, model)
        return RalphResult(False, max_ralph, last_reason)

    return asyncio.run(_run())
