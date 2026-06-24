"""One inner ralph pass. Uses the SDK streaming-input session so we can seed the
prior pass's compacted recap as the FIRST assistant turn of message history
(ahead of the user order). The recap-as-assistant-turn is the maintainer's
tested mechanism; the build is isolated in build_input_messages so it is unit-
tested without the SDK, and verified live against claude-agent-sdk 0.2.106."""
from __future__ import annotations

import pathlib
from dataclasses import dataclass

from logging_utils import log_status, one_line


@dataclass
class PassResult:
    session_id: str | None
    last_text: str


def build_input_messages(seed_assistant: str | None, user_order: str) -> list[dict]:
    """Streaming-input message list. When a recap exists it is seeded as a
    pre-filled assistant turn BEFORE the user order; otherwise just the order."""
    msgs: list[dict] = []
    if seed_assistant:
        msgs.append({
            "type": "assistant",
            "message": {"role": "assistant", "content": seed_assistant},
        })
    msgs.append({
        "type": "user",
        "message": {"role": "user", "content": user_order},
    })
    return msgs


def _pass_context(ralph_pass_no: int | None, ralph_max_passes: int | None) -> str:
    if ralph_pass_no is None:
        return "pass_no=? max_ralph=?"
    if ralph_max_passes is None:
        return f"pass_no={ralph_pass_no} max_ralph=?"
    return f"pass_no={ralph_pass_no} max_ralph={ralph_max_passes}"


def _message_content(item: dict) -> str:
    message = item.get("message") or {}
    return str(message.get("content") or "")


def _log_input_events(
    messages: list[dict],
    ralph_pass_no: int | None,
    ralph_max_passes: int | None,
) -> int:
    event_no = 0
    for item in messages:
        event_no += 1
        message = item.get("message") or {}
        role = message.get("role", item.get("type", "unknown"))
        source = "recap_seed" if role == "assistant" else "paper_order"
        content = _message_content(item)
        log_status(
            f"inner_agent_event {_pass_context(ralph_pass_no, ralph_max_passes)} "
            f"turn=0 event_no={event_no} event=input_message role={role} "
            f"source={source} chars={len(content)}"
        )
    return event_no


async def run_pass(
    system_prompt: str,
    user_order: str,
    seed_assistant: str | None,
    cwd: pathlib.Path,
    max_turns: int,
    model: str,
    *,
    ralph_pass_no: int | None = None,
    ralph_max_passes: int | None = None,
) -> PassResult:
    from claude_agent_sdk import (
        ClaudeSDKClient,
        ClaudeAgentOptions,
        AssistantMessage,
        ResultMessage,
        SystemMessage,
    )

    options = ClaudeAgentOptions(
        cwd=str(cwd),
        setting_sources=[],                       # inner agent gets NO skills
        allowed_tools=["Read", "Write", "WebSearch", "WebFetch"],
        disallowed_tools=["Agent"],
        system_prompt=system_prompt,
        max_turns=max_turns,
        model=model,
        effort="high",
    )

    messages = build_input_messages(seed_assistant, user_order)
    context = _pass_context(ralph_pass_no, ralph_max_passes)
    log_status(
        f"inner_agent_pass_start {context} model={model} max_turns={max_turns} "
        f"recap_seeded={bool(seed_assistant)}"
    )
    event_no = _log_input_events(messages, ralph_pass_no, ralph_max_passes)
    turn_no = 0

    async def _gen():
        for m in messages:
            yield m

    session_id: str | None = None
    last_text = ""
    async with ClaudeSDKClient(options) as client:
        await client.query(_gen())
        async for message in client.receive_response():
            message_type = type(message).__name__
            if isinstance(message, SystemMessage) and getattr(message, "subtype", "") == "init":
                session_id = (getattr(message, "data", None) or {}).get("session_id")
                event_no += 1
                log_status(
                    f"inner_agent_event {context} turn={turn_no} "
                    f"event_no={event_no} event={message_type}"
                )
            elif isinstance(message, AssistantMessage):
                turn_no += 1
                chunks = []
                for block in message.content:
                    event_no += 1
                    log_status(
                        f"inner_agent_event {context} turn={turn_no} "
                        f"event_no={event_no} event={type(block).__name__}"
                    )
                    text = getattr(block, "text", None)
                    if isinstance(text, str):
                        last_text = text
                        chunks.append(text)
                assistant_text = "\n".join(chunks)
                log_status(
                    f"inner_agent_turn_finish {context} turn={turn_no} "
                    f"event={message_type} output_chars={len(assistant_text)} "
                    f'output_preview="{one_line(assistant_text)}"'
                )
            elif isinstance(message, ResultMessage):
                last_text = message.result or last_text
                event_no += 1
                log_status(
                    f"inner_agent_event {context} turn={turn_no} "
                    f"event_no={event_no} event={message_type}"
                )
            else:
                event_no += 1
                log_status(
                    f"inner_agent_event {context} turn={turn_no} "
                    f"event_no={event_no} event={message_type}"
                )
    log_status(
        f"inner_agent_pass_finish {context} turns={turn_no} events={event_no} "
        f"output_chars={len(last_text or '')} "
        f'output_preview="{one_line(last_text)}"'
    )
    return PassResult(session_id=session_id, last_text=last_text)
