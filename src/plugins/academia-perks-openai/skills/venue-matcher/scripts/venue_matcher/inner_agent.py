"""One OpenAI Agents SDK inner ralph pass.

The public contract preserves the existing ralph interface: seed the prior
pass's compacted recap as the FIRST assistant turn, then send the same user
order. The build is isolated in build_input_messages so tests do not need the
SDK installed.
"""
from __future__ import annotations

import http.client
import ipaddress
import pathlib
import socket
import urllib.parse
from dataclasses import dataclass

from logging_utils import log_status, one_line

_FETCH_TIMEOUT = 20
_MAX_FETCH_BYTES = 500_000
_MAX_REDIRECTS = 5
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


@dataclass
class PassResult:
    session_id: str | None
    last_text: str


def build_input_messages(seed_assistant: str | None, user_order: str) -> list[dict]:
    """Responses input items, optionally seeding recap before the user order."""
    msgs: list[dict] = []
    if seed_assistant:
        msgs.append({"role": "assistant", "content": seed_assistant})
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


def _response_text(response) -> str:
    chunks = []
    for item in getattr(response, "output", None) or []:
        chunks.append(_content_text(getattr(item, "content", None)))
    return "\n".join(chunk for chunk in chunks if chunk)


def _run_item_text(item) -> str:
    raw = getattr(item, "raw_item", item)
    return _content_text(getattr(raw, "content", None))


def _raw_response_status(response) -> str:
    status = getattr(response, "status", None)
    incomplete = getattr(response, "incomplete_details", None)
    if incomplete:
        return f"{status}:{one_line(incomplete, 120)}"
    return str(status or "unknown")


def _log_input_turns(
    messages: list[dict],
    ralph_pass_no: int | None,
    ralph_max_passes: int | None,
) -> int:
    turn_no = 0
    for item in messages:
        turn_no += 1
        content = _input_content(item)
        role = item.get("role", "unknown")
        source = "recap_seed" if role == "assistant" else "paper_order"
        log_status(
            f"inner_agent_turn {_pass_context(ralph_pass_no, ralph_max_passes)} "
            f"agent_iteration=0 turn={turn_no} event=input_message role={role} "
            f"source={source} chars={len(content)}"
        )
    return turn_no


def _safe_path(root: pathlib.Path, raw_path: str) -> pathlib.Path:
    target = (root / raw_path).resolve()
    if not target.is_relative_to(root):
        raise ValueError("path must stay inside the working directory")
    return target


def _is_unsafe_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
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


def _fetch_once(url: str) -> tuple[bytes, str | None, str | None]:
    """One hop: pin-and-fetch url, returning (body, redirect_location, charset)."""
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
        body = response.read(_MAX_FETCH_BYTES)
        location = (
            response.headers.get("Location") if response.status in _REDIRECT_STATUSES else None
        )
        return body, location, response.headers.get_content_charset()
    finally:
        conn.close()


def _fetch_public_url(url: str) -> str:
    """Follow redirects up to _MAX_REDIRECTS, re-validating every hop so a
    redirect cannot be used to reach a private target the start URL avoided."""
    current = url
    for _ in range(_MAX_REDIRECTS + 1):
        body, location, charset = _fetch_once(current)
        if not location:
            return body.decode(charset or "utf-8", errors="replace")
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
        return the first 200000 text characters."""
        try:
            text = _fetch_public_url(url)
        except ValueError as exc:
            return f"fetch rejected: {exc}"
        except (OSError, http.client.HTTPException) as exc:
            return f"fetch failed: {exc}"
        return text[:200_000]

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
    from agents import Agent, Runner

    context = _pass_context(ralph_pass_no, ralph_max_passes)
    log_status(
        f"inner_agent_pass_start {context} model={model} max_turns={max_turns} "
        f"recap_seeded={bool(seed_assistant)}"
    )
    agent = Agent(
        name="venue-matcher",
        instructions=system_prompt,
        model=model,
        tools=build_tools(cwd),
    )

    input_messages = build_input_messages(seed_assistant, user_order)
    turn_no = _log_input_turns(input_messages, ralph_pass_no, ralph_max_passes)
    agent_iteration = 0
    result = Runner.run_streamed(
        agent,
        input_messages,
        max_turns=max_turns,
    )
    async for event in result.stream_events():
        turn_no += 1
        event_type = getattr(event, "type", type(event).__name__)
        active_iteration = agent_iteration + 1
        if event_type == "raw_response_event":
            data = getattr(event, "data", None)
            raw_type = getattr(data, "type", type(data).__name__)
            detail = ""
            delta = getattr(data, "delta", None)
            if isinstance(delta, str):
                detail = f" delta_chars={len(delta)}"
            log_status(
                f"inner_agent_turn {context} agent_iteration={active_iteration} "
                f"turn={turn_no} event={raw_type}{detail}"
            )
            if raw_type in {"response.completed", "response.failed", "response.incomplete"}:
                agent_iteration += 1
                response = getattr(data, "response", None)
                text = _response_text(response)
                status = _raw_response_status(response)
                log_status(
                    f"inner_agent_iteration_finish {context} "
                    f"agent_iteration={agent_iteration} turn={turn_no} "
                    f"stop_event={raw_type} status={status} output_chars={len(text)} "
                    f'output_preview="{one_line(text)}"'
                )
        elif event_type == "run_item_stream_event":
            item_text = _run_item_text(getattr(event, "item", None))
            name = getattr(event, "name", "unknown")
            detail = f" item_output_chars={len(item_text)}" if item_text else ""
            log_status(
                f"inner_agent_turn {context} agent_iteration={active_iteration} "
                f"turn={turn_no} event={name}{detail}"
            )
        else:
            log_status(
                f"inner_agent_turn {context} agent_iteration={active_iteration} "
                f"turn={turn_no} event={event_type}"
            )

    last_text = str(result.final_output or "")
    log_status(
        f"inner_agent_pass_finish {context} agent_iterations={agent_iteration} "
        f"turns={turn_no} output_chars={len(last_text)} "
        f'output_preview="{one_line(last_text)}"'
    )
    return PassResult(
        session_id=getattr(result, "last_response_id", None),
        last_text=last_text,
    )
