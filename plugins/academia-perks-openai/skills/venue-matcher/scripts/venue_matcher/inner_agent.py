"""One OpenAI Agents SDK inner ralph pass.

The public contract preserves the existing ralph interface: seed the prior
pass's compacted recap as the FIRST assistant turn, then send the same user
order. The build is isolated in build_input_messages so tests do not need the
SDK installed.
"""
from __future__ import annotations

import ipaddress
import pathlib
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import prompts


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


def _safe_path(root: pathlib.Path, raw_path: str) -> pathlib.Path:
    target = (root / raw_path).resolve()
    if not target.is_relative_to(root):
        raise ValueError("path must stay inside the working directory")
    return target


def _host_is_private(hostname: str | None) -> bool:
    if not hostname:
        return True
    host = hostname.strip("[]").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror:
            return False
        addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
    return any(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        for ip in addresses
    )


def _validate_public_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("url must use http or https")
    if _host_is_private(parsed.hostname):
        raise ValueError("url host must be public")
    return url


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
        """Fetch a public URL and return the first 200000 text characters."""
        try:
            safe_url = _validate_public_url(url)
        except ValueError as exc:
            return f"fetch rejected: {exc}"
        req = urllib.request.Request(safe_url, headers={"User-Agent": "paperflow/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                data = response.read(500_000)
        except urllib.error.URLError as exc:
            return f"fetch failed: {exc}"
        return data.decode(charset, errors="replace")[:200_000]

    return [WebSearchTool(), read_file, write_file, fetch_url]


async def run_pass(
    system_prompt: str,
    user_order: str,
    seed_assistant: str | None,
    cwd: pathlib.Path,
    max_turns: int,
    model: str = prompts.DEFAULT_MODEL,
) -> PassResult:
    from agents import Agent, Runner

    agent = Agent(
        name="venue-matcher",
        instructions=system_prompt,
        model=model,
        tools=build_tools(cwd),
    )

    result = await Runner.run(
        agent,
        build_input_messages(seed_assistant, user_order),
        max_turns=max_turns,
    )
    return PassResult(
        session_id=getattr(result, "last_response_id", None),
        last_text=str(result.final_output or ""),
    )
