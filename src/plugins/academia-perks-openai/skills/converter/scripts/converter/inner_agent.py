"""Lean OpenAI Agents SDK adapter for one converter pass."""
from __future__ import annotations

import asyncio
import os
import pathlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from tools import build_tools


@dataclass(frozen=True)
class PassResult:
    session_id: str | None
    last_text: str


def log_status(message: str, body: str | None = None) -> None:
    stamp = datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="seconds")
    line = f"[converter] {stamp} {message}"
    print(line, flush=True)
    path = os.environ.get("PAPERFLOW_EXECUTION_LOG")
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


_DELAY_RE = re.compile(
    r"(?:try again in|retry after)\s*([0-9]+(?:\.[0-9]+)?)\s*(ms|s|seconds?)",
    re.IGNORECASE,
)


def _header(headers, name: str):
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    return getter(name) if getter else None


def _seconds(value) -> float | None:
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    try:
        return max(0.0, float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _rate_limit_delay(exc: Exception, consecutive_errors: int = 0) -> float | None:
    code = getattr(exc, "code", None)
    body = getattr(exc, "body", None)
    if not code and isinstance(body, dict):
        error = body.get("error") if isinstance(body.get("error"), dict) else body
        code = error.get("code")
    is_rate_limit = (
        type(exc).__name__ == "RateLimitError"
        or code == "rate_limit_exceeded"
        or getattr(exc, "status_code", None) == 429
    )
    if not is_rate_limit:
        return None

    delay = _seconds(getattr(exc, "retry_after", None))
    if delay is not None:
        return delay * (1 + consecutive_errors)
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or getattr(exc, "headers", None)
    delay = _seconds(_header(headers, "retry-after"))
    if delay is not None:
        return delay * (1 + consecutive_errors)
    match = _DELAY_RE.search(str(exc))
    if not match:
        return None
    delay = float(match.group(1))
    delay = delay / 1000 if match.group(2).lower() == "ms" else delay
    return delay * (1 + consecutive_errors)


def build_input_messages(seed_assistant: str | None, user_order: str) -> list[dict]:
    messages: list[dict] = []
    if seed_assistant:
        messages.append(
            {
                "role": "assistant",
                "content": (
                    "<previous_pass_recap>\n"
                    f"{seed_assistant}\n"
                    "</previous_pass_recap>"
                ),
            }
        )
    messages.append({"role": "user", "content": user_order})
    return messages


def _pass_context(pass_no: int | None, max_ralph: int | None) -> str:
    return f"pass_no={pass_no if pass_no is not None else '?'} max_ralph={max_ralph if max_ralph is not None else '?'}"


def _field(value, name: str):
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def _as_input_item(item) -> dict:
    payload = dict(item) if isinstance(item, dict) else item.model_dump(exclude_unset=True)
    if payload.get("type") in {"tool_search_call", "tool_search_output"}:
        payload.pop("created_by", None)
    return payload


def _response_text(response) -> str:
    texts = []
    for item in _field(response, "output") or []:
        if _field(item, "type") != "message":
            continue
        for part in _field(item, "content") or []:
            text = _field(part, "text")
            if isinstance(text, str):
                texts.append(text)
    return "\n".join(texts)


def _has_action_item(response) -> bool:
    return any(
        _field(item, "type") not in {"message", "reasoning"}
        for item in (_field(response, "output") or [])
    )


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
    from agents import Agent, ModelSettings, Runner
    from openai.types.shared import Reasoning

    agent = Agent(
        name="converter",
        instructions=system_prompt,
        model=model,
        model_settings=ModelSettings(reasoning=Reasoning(effort="medium")),
        tools=build_tools(cwd),
    )

    context = _pass_context(ralph_pass_no, ralph_max_passes)
    current_input = build_input_messages(seed_assistant, user_order)
    event_no = 0
    for item in current_input:
        event_no += 1
        role = item["role"]
        source = "recap_seed" if role == "assistant" else "paper_order"
        log_status(
            f"inner_agent_event {context} turn=0 event_no={event_no} "
            f"event=input_message role={role} source={source} chars={len(item['content'])}"
        )

    turn_no = 0
    turn_offset = 0
    consecutive_rate_limit_errors = 0
    while True:
        resume_after_max_output = False
        result = None
        stream_turn = 0
        try:
            result = Runner.run_streamed(agent, list(current_input), max_turns=max_turns)
            async for event in result.stream_events():
                current_turn = getattr(result, "current_turn", None)
                if isinstance(current_turn, int):
                    stream_turn = current_turn
                    turn_no = max(turn_no, turn_offset + current_turn)

                if getattr(event, "type", None) == "raw_response_event":
                    data = getattr(event, "data", None)
                    event_type = _field(data, "type")
                    if event_type not in {
                        "response.completed",
                        "response.failed",
                        "response.incomplete",
                    }:
                        continue
                    response = _field(data, "response")
                    if response is None:
                        continue
                    current_input.extend(
                        _as_input_item(item) for item in (_field(response, "output") or [])
                    )
                    text = _response_text(response)
                    final_output = (
                        event_type == "response.completed"
                        and bool(text.strip())
                        and not _has_action_item(response)
                    )
                    event_no += 1
                    log_status(
                        f"inner_agent_event {context} turn={turn_no} event_no={event_no} "
                        f"event=ModelResponse final_output={'true' if final_output else 'false'} "
                        f"output_chars={len(text)}",
                        f"output_text=\n{text}" if text else None,
                    )
                    if event_type == "response.completed":
                        consecutive_rate_limit_errors = 0
                    resume_after_max_output = (
                        event_type == "response.incomplete"
                        and _field(_field(response, "incomplete_details"), "reason")
                        == "max_output_tokens"
                    )
                elif getattr(event, "type", None) == "run_item_stream_event":
                    item = getattr(event, "item", None)
                    if type(item).__name__ != "ToolCallOutputItem":
                        continue
                    current_input.append(item.to_input_item())
                    event_no += 1
                    log_status(
                        f"inner_agent_event {context} turn={turn_no} event_no={event_no} "
                        "event=ToolCallOutputItem"
                    )
            if failure := getattr(result, "run_loop_exception", None):
                raise failure
        except Exception as exc:
            if result is not None:
                current_turn = getattr(result, "current_turn", None)
                if isinstance(current_turn, int):
                    stream_turn = current_turn
                    turn_no = max(turn_no, turn_offset + current_turn)
            delay = _rate_limit_delay(exc, consecutive_rate_limit_errors)
            if delay is not None:
                if stream_turn > 0:
                    turn_offset += stream_turn - 1
                log_status(
                    f"inner_agent_rate_limit_wait {context} turn={turn_no} "
                    f"seconds={delay:.3f} input_items={len(current_input)}"
                )
                consecutive_rate_limit_errors += 1
                await asyncio.sleep(delay)
                continue
            if resume_after_max_output:
                turn_offset += stream_turn
                consecutive_rate_limit_errors = 0
                continue
            raise
        if resume_after_max_output:
            turn_offset += stream_turn
            consecutive_rate_limit_errors = 0
            continue
        consecutive_rate_limit_errors = 0
        break

    return PassResult(result.last_response_id, str(result.final_output or ""))
