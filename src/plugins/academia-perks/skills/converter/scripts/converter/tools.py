"""Workspace-confined tools for one converter inner agent."""
from __future__ import annotations

import ctypes
import email.message
import hashlib
import http.client
import ipaddress
import json
import os
import pathlib
import re
import socket
import subprocess
import sys
import tempfile
import urllib.parse
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable


_FETCH_TIMEOUT = 20
_MAX_FETCH_BYTES = 500_000
_MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
_MAX_TOOL_OUTPUT = 20_000
_MAX_GREP_MATCHES = 100
_MAX_GREP_LINE = 500
_MAX_OVERFULL = 20
_SHELL_TIMEOUT = 120
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_MAX_REDIRECTS = 5
_COMPILE_ATTESTATION = ".paperflow-compile.json"
_COMPILE_ATTESTATIONS: dict[pathlib.Path, dict] = {}
_CHILD_ENV_BLOCKLIST = {
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "CONVERTER_MODEL",
    "VENUE_MATCHER_MODEL",
}


def _set_process_nondumpable(*, platform=sys.platform, prctl=None) -> None:
    if platform != "linux":
        return
    try:
        operation = prctl if prctl is not None else ctypes.CDLL(None, use_errno=True).prctl
        result = operation(4, 0, 0, 0, 0)  # PR_SET_DUMPABLE
    except (AttributeError, OSError) as exc:
        raise RuntimeError("PR_SET_DUMPABLE boundary could not be established") from exc
    if result != 0:
        raise RuntimeError(
            f"PR_SET_DUMPABLE boundary could not be established (errno {ctypes.get_errno()})"
        )


def _child_env() -> dict[str, str]:
    child = {
        key: value
        for key, value in os.environ.items()
        if key.upper() not in _CHILD_ENV_BLOCKLIST
    }
    if wslenv := child.get("WSLENV"):
        entries = [
            entry for entry in wslenv.split(":")
            if entry.partition("/")[0].upper() not in _CHILD_ENV_BLOCKLIST
        ]
        if entries:
            child["WSLENV"] = ":".join(entries)
        else:
            child.pop("WSLENV")
    return child


@dataclass(frozen=True)
class HttpResponse:
    body: bytes
    final_url: str
    status: int
    content_type: str
    charset: str | None
    content_disposition: str | None


class _HTMLTextParser(HTMLParser):
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
        hidden = (
            tag in self._HIDDEN_TAGS
            or "hidden" in attributes
            or attributes.get("aria-hidden", "").lower() == "true"
        )
        if hidden:
            if tag in self._VOID_TAGS:
                return
            self._hidden_tags.append(tag)
        if self._hidden_tags:
            return
        if tag in self._BLOCK_TAGS:
            self._append_text(" ")
        if tag == "a" and attributes.get("href"):
            self._link = (urllib.parse.urljoin(self.base_url, attributes["href"]), [])

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._hidden_tags:
            return
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self._hidden_tags:
            if tag == self._hidden_tags[-1]:
                self._hidden_tags.pop()
            return
        if tag == "a" and self._link is not None:
            href, parts = self._link
            pair = [_normalize_text(parts), href]
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


def _normalize_text(parts: list[str]) -> str:
    return " ".join("".join(parts).split())


def _parse_html(body: bytes, base_url: str, charset: str | None) -> dict:
    parser = _HTMLTextParser(base_url)
    parser.feed(body.decode(charset or "utf-8", errors="replace"))
    parser.close()
    return {"text": _normalize_text(parser.text_parts), "links": parser.links}


def _safe_path(root: pathlib.Path, raw_path: str) -> pathlib.Path:
    root = root.resolve()
    target = (root / raw_path).resolve()
    if not target.is_relative_to(root):
        raise ValueError("path must stay inside the working directory")
    return target


def _edit_exact(target: pathlib.Path, old: str, new: str) -> str:
    content = target.read_text(encoding="utf-8")
    if content.count(old) != 1:
        raise ValueError("old text must occur exactly once")
    target.write_text(content.replace(old, new, 1), encoding="utf-8")
    return f"edited {target.name}"


def _grep(
    root: pathlib.Path,
    pattern: str,
    path: str = ".",
    *,
    max_matches: int = _MAX_GREP_MATCHES,
    max_line_length: int = _MAX_GREP_LINE,
) -> str:
    root = root.resolve()
    start = _safe_path(root, path)
    files = [start] if start.is_file() else sorted(
        (item for item in start.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(root).as_posix(),
    )
    matches = []
    for file_path in files:
        resolved = file_path.resolve()
        if not resolved.is_relative_to(root):
            continue
        try:
            lines = resolved.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        for line_no, line in enumerate(lines, start=1):
            if pattern in line:
                relative = resolved.relative_to(root).as_posix()
                matches.append(f"{relative}:{line_no}:{line[:max_line_length]}")
                if len(matches) == max_matches:
                    return "\n".join(matches)
    return "\n".join(matches)


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


def _fetch_once(url: str, limit: int) -> tuple[HttpResponse, str | None]:
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
        record = HttpResponse(
            body=response.read(limit + 1),
            final_url=url,
            status=response.status,
            content_type=response.headers.get_content_type(),
            charset=response.headers.get_content_charset(),
            content_disposition=response.headers.get("Content-Disposition"),
        )
        location = (
            response.headers.get("Location")
            if response.status in _REDIRECT_STATUSES
            else None
        )
        return record, location
    finally:
        conn.close()


def _fetch_public_url(url: str, limit: int) -> HttpResponse:
    current = url
    for _ in range(_MAX_REDIRECTS + 1):
        response, location = _fetch_once(current, limit)
        if location:
            current = urllib.parse.urljoin(current, location)
            continue
        if not 200 <= response.status < 300:
            raise ValueError(f"HTTP status {response.status}")
        return response
    raise ValueError("too many redirects")


def _content_disposition_name(value: str | None) -> str | None:
    if not value:
        return None
    message = email.message.Message()
    message["content-disposition"] = value
    return message.get_filename()


def _safe_filename(response: HttpResponse) -> str:
    name = _content_disposition_name(response.content_disposition)
    if not name:
        name = urllib.parse.unquote(urllib.parse.urlparse(response.final_url).path.rsplit("/", 1)[-1])
    name = (name or "download").replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[^\w.-]+", "_", name).strip(". ")
    return name or "download"


def _sniff_kind(body: bytes) -> str:
    if body.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "zip"
    if body.startswith(b"\x1f\x8b"):
        return "gzip"
    if body.startswith(b"%PDF-"):
        return "pdf"
    stripped = body.lstrip().lower()
    if stripped.startswith((b"<!doctype html", b"<html")):
        return "html"
    try:
        body.decode("utf-8")
    except UnicodeDecodeError:
        return "binary"
    return "plain-text"


def _download(
    root: pathlib.Path,
    url: str,
    fetch: Callable[[str, int], HttpResponse] = _fetch_public_url,
    *,
    limit: int = _MAX_DOWNLOAD_BYTES,
) -> dict:
    response = fetch(url, limit)
    if not 200 <= response.status < 300:
        raise ValueError(f"HTTP status {response.status}")
    if len(response.body) > limit:
        raise ValueError("download exceeds 100 MiB limit")
    downloads = _safe_path(root, "downloads")
    downloads.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(response)
    initial = downloads / filename
    suffix = initial.suffix
    stem = initial.name.removesuffix(suffix)
    collision = 0
    while True:
        target = initial if collision == 0 else downloads / f"{stem}-{collision}{suffix}"
        try:
            output = target.open("xb")
        except FileExistsError:
            collision += 1
            continue
        created_stat = os.fstat(output.fileno())
        try:
            with output:
                output.write(response.body)
        except BaseException:
            try:
                current_stat = os.lstat(target)
            except FileNotFoundError:
                pass
            else:
                if (current_stat.st_dev, current_stat.st_ino) == (
                    created_stat.st_dev,
                    created_stat.st_ino,
                ):
                    target.unlink()
            raise
        break
    return {
        "path": target.relative_to(root.resolve()).as_posix(),
        "final_url": response.final_url,
        "content_type": response.content_type,
        "kind": _sniff_kind(response.body),
        "size_bytes": len(response.body),
    }


def _output_tail(stream, limit: int) -> str:
    stream.flush()
    size = stream.tell()
    stream.seek(max(0, size - max(1, limit) * 4))
    return stream.read().decode("utf-8", errors="replace")


def _run_process(
    args: list[str],
    cwd: pathlib.Path,
    timeout: int,
    run,
    output_limit: int,
) -> subprocess.CompletedProcess:
    _set_process_nondumpable()
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        result = run(
            args,
            cwd=cwd,
            shell=False,
            timeout=timeout,
            stdout=stdout,
            stderr=stderr,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_child_env(),
        )
        captured_stdout = (
            result.stdout
            if isinstance(result.stdout, str)
            else _output_tail(stdout, output_limit)
        )
        captured_stderr = (
            result.stderr
            if isinstance(result.stderr, str)
            else _output_tail(stderr, output_limit)
        )
    return subprocess.CompletedProcess(
        getattr(result, "args", args),
        result.returncode,
        captured_stdout,
        captured_stderr,
    )


def _process_output(result: subprocess.CompletedProcess, limit: int) -> str:
    return f"{result.stdout or ''}\n{result.stderr or ''}".strip()[-limit:]


_OVERFULL = re.compile(
    r"Overfull \\[hv]box \((?P<points>\d+(?:\.\d+)?)pt too (?:wide|high)\)"
)


def _overfull_boxes(output: str, limit: int = _MAX_OVERFULL) -> list[str]:
    """Report the worst overfull boxes Tectonic named in one compile's output.

    TeX already measures every box that spills outside the text block — a table
    wider than the column, text that cannot break — and Tectonic prints each one
    with its source file and line. That verdict is a handful of lines among
    hundreds of font notes and harmless underfull warnings, so it is lifted out
    here into its own field. Underfull boxes are deliberately excluded: they are
    cosmetic, and they outnumber the real defects badly enough to make the field
    worthless. Reruns of TeX repeat each warning verbatim, hence the dedup.
    """
    worst: dict[str, float] = {}
    for line in output.splitlines():
        match = _OVERFULL.search(line)
        if match:
            worst[line.strip()] = float(match.group("points"))
    return sorted(worst, key=lambda line: -worst[line])[:limit]


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_real_pdf(path: pathlib.Path) -> bool:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            return False
        with path.open("rb") as source:
            return source.read(5) == b"%PDF-"
    except OSError:
        return False


def _write_compile_attestation(
    root: pathlib.Path,
    tex: pathlib.Path,
    pdf: pathlib.Path,
) -> None:
    payload = {
        "tex": {"path": tex.relative_to(root).as_posix(), "sha256": _sha256(tex)},
        "pdf": {"path": pdf.relative_to(root).as_posix(), "sha256": _sha256(pdf)},
    }
    fd, temporary_name = tempfile.mkstemp(
        dir=root,
        prefix=".paperflow-compile-",
        suffix=".tmp",
    )
    temporary = pathlib.Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as destination:
            json.dump(payload, destination, ensure_ascii=False, separators=(",", ":"))
            destination.write("\n")
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary, root / _COMPILE_ATTESTATION)
        _COMPILE_ATTESTATIONS[root] = payload
    finally:
        temporary.unlink(missing_ok=True)


def _run_shell(
    root: pathlib.Path,
    command: str,
    run=subprocess.run,
    *,
    output_limit: int = _MAX_TOOL_OUTPUT,
) -> dict:
    root = root.resolve()
    result = _run_process(
        ["bash", "-lc", command], root, _SHELL_TIMEOUT, run, output_limit
    )
    return {"exit_code": result.returncode, "output": _process_output(result, output_limit)}


def _compile(
    root: pathlib.Path,
    directory: str,
    main: str,
    run=subprocess.run,
) -> dict:
    root = root.resolve()
    _COMPILE_ATTESTATIONS.pop(root, None)
    (root / _COMPILE_ATTESTATION).unlink(missing_ok=True)
    build_dir = _safe_path(root, directory)
    main_file = _safe_path(build_dir, main)
    pdf = main_file.with_suffix(".pdf")
    backup = None
    if pdf.exists():
        if not pdf.is_file():
            raise RuntimeError(f"expected PDF path is not a file: {pdf.name}")
        backup = pdf.with_name(f".{pdf.name}.paperflow-backup")
        collision = 1
        while backup.exists():
            backup = pdf.with_name(f".{pdf.name}.paperflow-backup-{collision}")
            collision += 1
        pdf.replace(backup)
    try:
        result = _run_process(
            ["tectonic", "--untrusted", "--keep-logs", main_file.relative_to(build_dir).as_posix()],
            build_dir,
            300,
            run,
            _MAX_TOOL_OUTPUT,
        )
        output = _process_output(result, _MAX_TOOL_OUTPUT)
        if result.returncode != 0:
            raise RuntimeError(f"Tectonic exited with exit code {result.returncode}: {output}")
        if not _is_real_pdf(pdf):
            raise RuntimeError(f"Tectonic did not create a non-empty PDF at {pdf.name}")
        _write_compile_attestation(root, main_file, pdf)
    except BaseException:
        if pdf.is_file():
            pdf.unlink()
        if backup is not None:
            backup.replace(pdf)
        raise
    if backup is not None:
        backup.unlink()
    return {
        "exit_code": result.returncode,
        "overfull": _overfull_boxes(output),
        "output": output,
        "pdf": pdf.relative_to(root).as_posix(),
    }


def _json_bounded(page: dict, limit: int = _MAX_TOOL_OUTPUT) -> str:
    payload = {"text": page["text"], "links": list(page["links"])}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    while len(encoded) > limit and payload["text"]:
        payload["text"] = payload["text"][: max(0, len(payload["text"]) - (len(encoded) - limit))]
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    while len(encoded) > limit and payload["links"]:
        payload["links"].pop()
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return encoded


def build_tools(cwd: pathlib.Path) -> list:
    from agents import WebSearchTool, function_tool

    root = pathlib.Path(cwd).resolve()

    @function_tool
    def read_file(path: str) -> str:
        """Read a UTF-8 text file inside the conversion workspace."""
        return _safe_path(root, path).read_text(encoding="utf-8")

    @function_tool
    def write_file(path: str, content: str) -> str:
        """Create or fully rewrite a UTF-8 file inside the conversion workspace."""
        target = _safe_path(root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"wrote {target.relative_to(root).as_posix()}"

    @function_tool
    def edit_file(path: str, old: str, new: str) -> str:
        """Replace old text when it occurs exactly once in a UTF-8 workspace file."""
        target = _safe_path(root, path)
        _edit_exact(target, old, new)
        return f"edited {target.relative_to(root).as_posix()}"

    @function_tool
    def fetch_url(url: str) -> str:
        """Fetch a public HTML page and return bounded visible text and absolute links as JSON."""
        response = _fetch_public_url(url, _MAX_FETCH_BYTES)
        return _json_bounded(_parse_html(response.body, response.final_url, response.charset))

    @function_tool
    def download_file(url: str) -> str:
        """Download a public URL into downloads/ with a 100 MiB hard limit."""
        return json.dumps(_download(root, url), separators=(",", ":"))

    @function_tool
    def grep_files(pattern: str, path: str = ".") -> str:
        """Find literal text in sorted UTF-8 workspace files with bounded results."""
        return _grep(root, pattern, path)

    @function_tool
    def run_shell(command: str) -> str:
        """Run a bounded Bash command from the conversion workspace."""
        return json.dumps(_run_shell(root, command), separators=(",", ":"))

    @function_tool
    def compile(dir: str, main: str) -> str:
        """Compile one workspace-confined TeX main file with Tectonic.

        The overfull field lists content spilling outside the text block, worst
        first, with the source file and line that produced it.
        """
        return json.dumps(_compile(root, dir, main), separators=(",", ":"))

    return [
        WebSearchTool(),
        read_file,
        write_file,
        edit_file,
        fetch_url,
        download_file,
        grep_files,
        run_shell,
        compile,
    ]
