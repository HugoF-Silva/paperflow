"""One OpenAI Agents SDK inner ralph pass.

The public contract preserves the existing ralph interface: seed the prior
pass's compacted recap as the FIRST assistant turn, then send the same user
order. The build is isolated in build_input_messages so tests do not need the
SDK installed.
"""
from __future__ import annotations

import asyncio
import http.client
import ipaddress
import json
import pathlib
import re
import socket
import time
import urllib.parse
from dataclasses import dataclass
from html.parser import HTMLParser

from logging_utils import log_status

_FETCH_TIMEOUT = 20
_MAX_FETCH_BYTES = 50_000
_MAX_REDIRECTS = 5
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_RATE_LIMIT_WAIT_RE = re.compile(r"try again in ([0-9]+(?:\.[0-9]+)?)(ms|s)", re.IGNORECASE)
_RATE_LIMIT_DEFAULT_WAIT = 30.0


@dataclass
class PassResult:
    session_id: str | None
    last_text: str


@dataclass(frozen=True)
class _FetchResponse:
    body: bytes
    final_url: str
    status: int
    charset: str | None


def build_input_messages(seed_assistant: str | None, user_order: str) -> list[dict]:
    """Responses input items, optionally seeding recap before the user order."""
    msgs: list[dict] = []
    if seed_assistant:
        msgs.append({
            "role": "assistant",
            "content": f"<previous_pass_recap>\n{seed_assistant}\n</previous_pass_recap>",
        })
    msgs.append({"role": "user", "content": user_order})
    return msgs


def _pass_context(ralph_pass_no: int | None, ralph_max_passes: int | None) -> str:
    if ralph_pass_no is None:
        return "pass_no=? max_ralph=?"
    if ralph_max_passes is None:
        return f"pass_no={ralph_pass_no} max_ralph=?"
    return f"pass_no={ralph_pass_no} max_ralph={ralph_max_passes}"


def _input_content(item: dict) -> str:
    return str(item.get("content") or "")


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            text = getattr(part, "text", None)
            if text is None and isinstance(part, dict):
                text = part.get("text")
            if isinstance(text, str):
                parts.append(text)
        return "\n".join(parts)
    return ""


def _field(obj, name: str):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _raw_stream_delta(data) -> str:
    raw_type = str(_field(data, "type") or "")
    if not (raw_type.startswith("response.") and raw_type.endswith(".delta")):
        return ""
    delta = _field(data, "delta")
    return delta if isinstance(delta, str) else ""


def _raw_stream_is_reasoning(data) -> bool:
    raw_type = str(_field(data, "type") or "").lower()
    return "reasoning" in raw_type or "summary" in raw_type


def _raw_stream_reasoning_key(data) -> str:
    item_id = _field(data, "item_id")
    if item_id is not None:
        return str(item_id)
    item = _field(data, "item")
    item_id = _field(item, "id")
    if item_id is not None:
        return str(item_id)
    output_index = _field(data, "output_index")
    return str(output_index) if output_index is not None else "reasoning"


def _raw_stream_is_reasoning_item_done(data) -> bool:
    raw_type = str(_field(data, "type") or "").lower()
    return raw_type == "response.output_item.done" and _is_reasoning_item(_field(data, "item"))


def _text_from_value(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            text = _text_from_value(item)
            if text:
                parts.append(text)
        return "\n".join(parts)
    for name in ("text", "content"):
        text = _field(value, name)
        if isinstance(text, str):
            return text
    return ""


def _reasoning_text_from_item(item) -> str:
    if not _is_reasoning_item(item):
        return ""
    parts = []
    for name in ("summary", "content", "text"):
        text = _text_from_value(_field(item, name))
        if text:
            parts.append(text)
    return "\n".join(parts)


def _is_reasoning_item(item) -> bool:
    return "reasoning" in str(_field(item, "type") or type(item).__name__).lower()


def _generated_text_from_item(item) -> str:
    text = _content_text(_field(item, "content"))
    if text:
        return text
    for name in ("arguments", "query"):
        value = _field(item, name)
        if isinstance(value, str):
            return value
    action = _field(item, "action")
    for name in ("query", "url"):
        value = _field(action, name)
        if isinstance(value, str):
            return value
    return ""


def _response_log_fields(response) -> str:
    if response is None:
        return ""
    parts = []
    status = _field(response, "status")
    if status:
        parts.append(f"status={status}")
    incomplete = _field(response, "incomplete_details")
    reason = _field(incomplete, "reason")
    if reason:
        parts.append(f"incomplete_reason={reason}")
    usage = _field(response, "usage")
    for name in ("input_tokens", "output_tokens", "total_tokens"):
        value = _field(usage, name)
        if value is not None:
            parts.append(f"{name}={value}")
    details = _field(usage, "output_tokens_details")
    reasoning_tokens = _field(details, "reasoning_tokens")
    if reasoning_tokens is not None:
        parts.append(f"reasoning_tokens={reasoning_tokens}")
    return " ".join(parts)


def _is_max_output_response(response) -> bool:
    incomplete = _field(response, "incomplete_details")
    return _field(incomplete, "reason") == "max_output_tokens"


def _body_field(body, key: str):
    if not isinstance(body, dict):
        return None
    if body.get(key) is not None:
        return body.get(key)
    error = body.get("error")
    if isinstance(error, dict):
        return error.get(key)
    return None


def _rate_limit_wait_seconds(exc: Exception, consecutive_errors: int = 0) -> float | None:
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
    if not match:
        return _RATE_LIMIT_DEFAULT_WAIT * (1 + consecutive_errors)
    seconds = float(match.group(1))
    if match.group(2).lower() == "ms":
        seconds /= 1000
    return max(0.0, seconds * (1 + consecutive_errors))


def _output_as_input_item(item) -> dict:
    if isinstance(item, dict):
        payload = dict(item)
    elif hasattr(item, "model_dump"):
        payload = item.model_dump(exclude_unset=True)
    else:
        raise TypeError(f"unexpected response output item: {type(item).__name__}")
    if payload.get("type") in {"tool_search_call", "tool_search_output"}:
        payload.pop("created_by", None)
    return payload


def _response_input_items(response) -> list[dict]:
    return [_output_as_input_item(item) for item in (_field(response, "output") or [])]


def _tool_output_input_item(item) -> dict:
    to_input_item = getattr(item, "to_input_item", None)
    if callable(to_input_item):
        return to_input_item()
    return _output_as_input_item(_field(item, "raw_item"))


def _response_has_action_item(response) -> bool:
    for item in _field(response, "output") or []:
        item_type = str(_field(item, "type") or type(item).__name__).lower()
        if "reasoning" in item_type or "message" in item_type:
            continue
        return True
    return False


def _response_texts(response) -> tuple[list[str], list[str]]:
    output_texts = []
    reasoning_texts = []
    for item in _field(response, "output") or []:
        reasoning_text = _reasoning_text_from_item(item)
        if reasoning_text:
            reasoning_texts.append(reasoning_text)
        if not _is_reasoning_item(item):
            text = _generated_text_from_item(item)
            if text:
                output_texts.append(text)
    return output_texts, reasoning_texts


def _model_response_body(assistant_text: str, reasoning_texts: list[str]) -> str | None:
    parts = []
    if assistant_text:
        parts.append(f"output_text=\n{assistant_text}")
    for index, text in enumerate((text for text in reasoning_texts if text), start=1):
        label = "reasoning_text" if len(reasoning_texts) == 1 else f"reasoning_text[{index}]"
        parts.append(f"{label}=\n{text}")
    return "\n\n".join(parts) or None


def _log_reasoning_item(data, context: str, turn_no: int, event_no: int, text: str) -> int:
    if not text.strip():
        return event_no
    item = _field(data, "item")
    fields = []
    output_index = _field(data, "output_index")
    if output_index is not None:
        fields.append(f"output_index={output_index}")
    item_id = _field(data, "item_id") or _field(item, "id")
    if item_id is not None:
        fields.append(f"item_id={item_id}")
    fields = f" {' '.join(fields)}" if fields else ""
    event_no += 1
    log_status(
        f"inner_agent_event {context} turn={turn_no} "
        f"event_no={event_no} event=ReasoningItem{fields} "
        f"reasoning_chars={len(text)}",
        f"reasoning_text=\n{text}",
    )
    return event_no


def _log_model_response(
    response,
    context: str,
    turn_no: int,
    raw_type: str,
    streamed_text: str,
    streamed_reasoning_texts: list[str],
    event_no: int,
    include_response_reasoning: bool,
) -> int:
    output_texts, response_reasoning_texts = _response_texts(response)
    assistant_text = "\n".join(output_texts) or streamed_text
    reasoning_texts = (
        response_reasoning_texts
        if include_response_reasoning and response_reasoning_texts
        else streamed_reasoning_texts
    )
    reasoning_chars = sum(len(text) for text in reasoning_texts)
    final_output = (
        raw_type == "response.completed"
        and bool(assistant_text.strip())
        and not _response_has_action_item(response)
    )
    response_fields = _response_log_fields(response)
    response_fields = f" {response_fields}" if response_fields else ""
    event_no += 1
    log_status(
        f"inner_agent_event {context} turn={turn_no} "
        f"event_no={event_no} event=ModelResponse "
        f"final_output={'true' if final_output else 'false'} "
        f"output_chars={len(assistant_text)} "
        f"streamed_output_chars={len(streamed_text)}"
        f" reasoning_chars={reasoning_chars}"
        f"{response_fields}",
        _model_response_body(assistant_text, reasoning_texts),
    )
    return event_no


def _log_input_events(
    messages: list[dict],
    ralph_pass_no: int | None,
    ralph_max_passes: int | None,
) -> int:
    event_no = 0
    for item in messages:
        event_no += 1
        content = _input_content(item)
        role = item.get("role", "unknown")
        source = "recap_seed" if role == "assistant" else "paper_order"
        log_status(
            f"inner_agent_event {_pass_context(ralph_pass_no, ralph_max_passes)} "
            f"turn=0 event_no={event_no} event=input_message role={role} "
            f"source={source} chars={len(content)}"
        )
    return event_no


class _PageParser(HTMLParser):
    _HIDDEN_TAGS = {"head", "script", "style", "noscript", "template"}
    _BLOCK_TAGS = {
        "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt",
        "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3",
        "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre",
        "section", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
    }
    _VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.text_parts: list[str] = []
        self.links: list[list[str]] = []
        self._hidden_tags: list[str] = []
        self._link: tuple[str, list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if (
            tag in self._HIDDEN_TAGS
            or "hidden" in attributes
            or attributes.get("aria-hidden", "").lower() == "true"
        ):
            if tag in self._VOID_TAGS:
                return
            self._hidden_tags.append(tag)
        if self._hidden_tags:
            return
        if tag in self._BLOCK_TAGS:
            self._append_text(" ")
        if tag == "a" and attributes.get("href"):
            self._link = (urllib.parse.urljoin(self.base_url, attributes["href"]), [])

    def handle_endtag(self, tag: str) -> None:
        if self._hidden_tags:
            if tag == self._hidden_tags[-1]:
                self._hidden_tags.pop()
            return
        if tag == "a" and self._link is not None:
            href, parts = self._link
            pair = [_normalize_html_text(parts), href]
            if pair not in self.links:
                self.links.append(pair)
            self._link = None
        if tag in self._BLOCK_TAGS:
            self._append_text(" ")

    def handle_data(self, data: str) -> None:
        if self._hidden_tags:
            return
        self._append_text(data)

    def _append_text(self, data: str) -> None:
        self.text_parts.append(data)
        if self._link is not None:
            self._link[1].append(data)


def _normalize_html_text(parts: list[str]) -> str:
    return " ".join("".join(parts).split())


def _parse_html(text: str, base_url: str) -> dict:
    parser = _PageParser(base_url)
    parser.feed(text)
    parser.close()
    return {"text": _normalize_html_text(parser.text_parts), "links": parser.links}


def _bounded_page_json(page: dict) -> str:
    payload = {"text": page["text"], "links": list(page["links"])}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    while len(encoded) > 20_000 and payload["text"]:
        excess = len(encoded) - 20_000
        payload["text"] = payload["text"][: max(0, len(payload["text"]) - excess)]
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    while len(encoded) > 20_000 and payload["links"]:
        payload["links"].pop()
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return encoded


def _safe_path(root: pathlib.Path, raw_path: str) -> pathlib.Path:
    target = (root / raw_path).resolve()
    if not target.is_relative_to(root):
        raise ValueError("path must stay inside the working directory")
    return target


def _is_unsafe_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        not ip.is_global
        or ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _resolve_pinned_ip(hostname: str) -> str:
    """Resolve hostname to one public IP to connect to directly. Connecting to
    the very IP that was just checked (instead of letting the HTTP client
    re-resolve the hostname at connect time) is what closes the DNS-rebinding
    TOCTOU a separate check-then-connect-by-hostname step would leave open.
    A hostname that fails to resolve is treated as unsafe, not as public."""
    host = hostname.strip("[]").lower()
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror as exc:
            raise ValueError("url host must be public") from exc
        addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
    public = [ip for ip in addresses if not _is_unsafe_ip(ip)]
    if not public:
        raise ValueError("url host must be public")
    return str(public[0])


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, pinned_ip: str, host: str, port: int, timeout: float):
        super().__init__(host, port, timeout=timeout)
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        self.sock = socket.create_connection((self._pinned_ip, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, pinned_ip: str, host: str, port: int, timeout: float):
        super().__init__(host, port, timeout=timeout)
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        sock = socket.create_connection((self._pinned_ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _fetch_once(url: str) -> tuple[_FetchResponse, str | None]:
    """Pin and fetch one URL hop, retaining response metadata."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("url must use http or https")
    if not parsed.hostname:
        raise ValueError("url host must be public")
    pinned_ip = _resolve_pinned_ip(parsed.hostname)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    conn_cls = _PinnedHTTPSConnection if parsed.scheme == "https" else _PinnedHTTPConnection
    conn = conn_cls(pinned_ip, parsed.hostname, port, _FETCH_TIMEOUT)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    try:
        conn.request("GET", path, headers={"User-Agent": "paperflow/0.1"})
        response = conn.getresponse()
        fetched = _FetchResponse(
            body=response.read(_MAX_FETCH_BYTES),
            final_url=url,
            status=response.status,
            charset=response.headers.get_content_charset(),
        )
        location = (
            response.headers.get("Location") if response.status in _REDIRECT_STATUSES else None
        )
        return fetched, location
    finally:
        conn.close()


def _fetch_public_url(url: str) -> _FetchResponse:
    """Follow redirects up to _MAX_REDIRECTS, re-validating every hop so a
    redirect cannot be used to reach a private target the start URL avoided."""
    current = url
    for _ in range(_MAX_REDIRECTS + 1):
        fetched, location = _fetch_once(current)
        if not location:
            if not 200 <= fetched.status < 300:
                raise ValueError(f"HTTP status {fetched.status}")
            return fetched
        current = urllib.parse.urljoin(current, location)
    raise ValueError("too many redirects")


def build_tools(cwd: pathlib.Path):
    from agents import WebSearchTool, function_tool

    root = pathlib.Path(cwd).resolve()

    @function_tool
    def read_file(path: str) -> str:
        """Read a UTF-8 text file inside the working directory."""
        return _safe_path(root, path).read_text(encoding="utf-8")

    @function_tool
    def write_file(path: str, content: str) -> str:
        """Write a UTF-8 text file inside the working directory."""
        target = _safe_path(root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"wrote {target.relative_to(root).as_posix()}"

    @function_tool
    def fetch_url(url: str) -> str:
        """Fetch a public URL, following redirects (each re-validated), and
        return bounded visible text and absolute links as JSON."""
        try:
            response = _fetch_public_url(url)
        except ValueError as exc:
            return f"fetch rejected: {exc}"
        except (OSError, http.client.HTTPException) as exc:
            return f"fetch failed: {exc}"
        text = response.body.decode(response.charset or "utf-8", errors="replace")
        return _bounded_page_json(_parse_html(text, response.final_url))

    return [WebSearchTool(), read_file, write_file, fetch_url]


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

    context = _pass_context(ralph_pass_no, ralph_max_passes)
    log_status(
        f"inner_agent_pass_start {context} model={model} max_turns={max_turns} "
        f"recap_seeded={bool(seed_assistant)}"
    )
    agent = Agent(
        name="venue-matcher",
        instructions=system_prompt,
        model=model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium"),
            verbosity="low",
            max_tokens=4_000,
        ),
        tools=build_tools(cwd),
    )

    current_input = build_input_messages(seed_assistant, user_order)
    event_no = _log_input_events(current_input, ralph_pass_no, ralph_max_passes)
    turn_no = 0
    result = None
    consecutive_rate_limit_errors = 0

    while True:
        streamed_text_chunks: list[str] = []
        streamed_reasoning_chunks: dict[str, list[str]] = {}
        logged_reasoning_items = 0
        resume_current_pass = False

        result = Runner.run_streamed(
            agent,
            list(current_input),
            max_turns=max_turns,
        )

        try:
            async for event in result.stream_events():
                current_turn = getattr(result, "current_turn", None)
                if isinstance(current_turn, int) and current_turn > turn_no:
                    turn_no = current_turn

                event_type = getattr(event, "type", type(event).__name__)
                if event_type == "raw_response_event":
                    data = getattr(event, "data", None)
                    stream_delta = _raw_stream_delta(data)
                    if stream_delta:
                        if _raw_stream_is_reasoning(data):
                            key = _raw_stream_reasoning_key(data)
                            streamed_reasoning_chunks.setdefault(key, []).append(stream_delta)
                        else:
                            streamed_text_chunks.append(stream_delta)
                        continue
                    if _raw_stream_is_reasoning_item_done(data):
                        key = _raw_stream_reasoning_key(data)
                        reasoning_text = "".join(streamed_reasoning_chunks.pop(key, []))
                        if not reasoning_text:
                            reasoning_text = _reasoning_text_from_item(_field(data, "item"))
                        next_event_no = _log_reasoning_item(
                            data, context, turn_no, event_no, reasoning_text
                        )
                        if next_event_no != event_no:
                            logged_reasoning_items += 1
                            event_no = next_event_no
                        continue
                    raw_type = str(_field(data, "type") or type(data).__name__)
                    if raw_type not in {
                        "response.completed",
                        "response.failed",
                        "response.incomplete",
                    }:
                        continue
                    response = _field(data, "response")
                    current_input.extend(_response_input_items(response))
                    resume_current_pass = (
                        raw_type == "response.incomplete" and _is_max_output_response(response)
                    )
                    streamed_text = "".join(streamed_text_chunks)
                    streamed_reasoning_texts = [
                        "".join(chunks) for chunks in streamed_reasoning_chunks.values()
                    ]
                    event_no = _log_model_response(
                        response,
                        context,
                        turn_no,
                        raw_type,
                        streamed_text,
                        streamed_reasoning_texts,
                        event_no,
                        logged_reasoning_items == 0,
                    )
                    streamed_text_chunks = []
                    streamed_reasoning_chunks = {}
                    logged_reasoning_items = 0
                elif event_type == "run_item_stream_event":
                    item = getattr(event, "item", None)
                    item_type = type(item).__name__ if item is not None else type(event).__name__
                    if item_type != "ToolCallOutputItem":
                        continue
                    current_input.append(_tool_output_input_item(item))
                    event_no += 1
                    log_status(
                        f"inner_agent_event {context} turn={turn_no} "
                        f"event_no={event_no} event={item_type}"
                    )
        except asyncio.CancelledError:
            assistant_text = "".join(streamed_text_chunks)
            reasoning_texts = [
                "".join(chunks) for chunks in streamed_reasoning_chunks.values()
            ]
            reasoning_chars = sum(len(text) for text in reasoning_texts)
            if assistant_text or reasoning_chars:
                event_no += 1
                log_status(
                    f"inner_agent_turn_cancelled {context} turn={turn_no} "
                    f"event_no={event_no} output_chars={len(assistant_text)} "
                    f"streamed_output_chars={len(assistant_text)} "
                    f"reasoning_chars={reasoning_chars}",
                    _model_response_body(assistant_text, reasoning_texts),
                )
            raise
        except Exception as exc:
            wait_seconds = _rate_limit_wait_seconds(exc, consecutive_rate_limit_errors)
            if wait_seconds is not None:
                log_status(
                    f"inner_agent_rate_limit_wait {context} turn={turn_no} "
                    f"seconds={wait_seconds:.3f} input_items={len(current_input)}"
                )
                consecutive_rate_limit_errors += 1
                time.sleep(wait_seconds)
                continue
            if resume_current_pass:
                consecutive_rate_limit_errors = 0
                continue
            raise
        consecutive_rate_limit_errors = 0
        break

    last_text = str(result.final_output or "")
    log_status(
        f"inner_agent_pass_finish {context} turns={turn_no} events={event_no} "
        f"output_chars={len(last_text)}"
    )
    return PassResult(
        session_id=getattr(result, "last_response_id", None),
        last_text=last_text,
    )
