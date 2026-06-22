"""One inner ralph pass. Uses the SDK streaming-input session so we can seed the
prior pass's compacted recap as the FIRST assistant turn of message history
(ahead of the user order). The recap-as-assistant-turn is the maintainer's
tested mechanism; the build is isolated in build_input_messages so it is unit-
tested without the SDK, and verified live against claude-agent-sdk 0.2.106."""
from __future__ import annotations

import pathlib
from dataclasses import dataclass

import prompts


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


async def run_pass(
    system_prompt: str,
    user_order: str,
    seed_assistant: str | None,
    cwd: pathlib.Path,
    max_turns: int,
    model: str = prompts.DEFAULT_MODEL,
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
    )

    messages = build_input_messages(seed_assistant, user_order)

    async def _gen():
        for m in messages:
            yield m

    session_id: str | None = None
    last_text = ""
    async with ClaudeSDKClient(options) as client:
        await client.query(_gen())
        async for message in client.receive_response():
            if isinstance(message, SystemMessage) and getattr(message, "subtype", "") == "init":
                session_id = message.data.get("session_id")
            elif isinstance(message, AssistantMessage):
                for block in message.content:
                    text = getattr(block, "text", None)
                    if isinstance(text, str):
                        last_text = text
            elif isinstance(message, ResultMessage):
                last_text = message.result or last_text
    return PassResult(session_id=session_id, last_text=last_text)
