import importlib.util
import pathlib
import sys

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN_MODULE_DIR = (
    REPO_ROOT
    / "plugins"
    / "academia-perks-openai"
    / "skills"
    / "venue-matcher"
    / "scripts"
    / "venue_matcher"
)


def load_openai_inner_agent():
    old_prompts = sys.modules.pop("prompts", None)
    old_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(PLUGIN_MODULE_DIR))
    try:
        spec = importlib.util.spec_from_file_location(
            "codex_openai_inner_agent",
            PLUGIN_MODULE_DIR / "inner_agent.py",
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = old_dont_write_bytecode
        sys.path.remove(str(PLUGIN_MODULE_DIR))
        sys.modules.pop("codex_openai_inner_agent", None)
        if old_prompts is None:
            sys.modules.pop("prompts", None)
        else:
            sys.modules["prompts"] = old_prompts


def test_openai_messages_user_only_when_no_seed():
    inner_agent = load_openai_inner_agent()

    assert inner_agent.build_input_messages(None, "ORDER") == [
        {"role": "user", "content": "ORDER"}
    ]


def test_openai_messages_seed_assistant_first():
    inner_agent = load_openai_inner_agent()

    assert inner_agent.build_input_messages("RECAP BULLETS", "ORDER") == [
        {"role": "assistant", "content": "RECAP BULLETS"},
        {"role": "user", "content": "ORDER"},
    ]


def test_openai_default_model_is_openai_model():
    inner_agent = load_openai_inner_agent()

    assert inner_agent.prompts.DEFAULT_MODEL.startswith("gpt-")


def test_openai_file_tools_reject_paths_outside_workdir(tmp_path):
    inner_agent = load_openai_inner_agent()

    with pytest.raises(ValueError, match="inside the working directory"):
        inner_agent._safe_path(tmp_path, "../outside.txt")


def test_openai_fetch_rejects_non_http_scheme():
    inner_agent = load_openai_inner_agent()

    with pytest.raises(ValueError, match="http or https"):
        inner_agent._fetch_once("file:///etc/passwd")


def test_openai_resolve_pinned_ip_rejects_loopback_and_localhost():
    inner_agent = load_openai_inner_agent()

    with pytest.raises(ValueError, match="host must be public"):
        inner_agent._resolve_pinned_ip("localhost")
    with pytest.raises(ValueError, match="host must be public"):
        inner_agent._resolve_pinned_ip("127.0.0.1")


def test_openai_resolve_pinned_ip_fails_closed_when_unresolvable(monkeypatch):
    inner_agent = load_openai_inner_agent()

    def boom(host, port):
        raise inner_agent.socket.gaierror("simulated DNS failure")

    monkeypatch.setattr(inner_agent.socket, "getaddrinfo", boom)

    with pytest.raises(ValueError, match="host must be public"):
        inner_agent._resolve_pinned_ip("example.com")


def test_openai_fetch_redirect_to_private_host_is_rejected(monkeypatch):
    """A redirect must be re-validated, not just the start URL, otherwise a
    public-looking start URL could 302 the fetch into a private network."""
    inner_agent = load_openai_inner_agent()
    hops = {"http://93.184.216.34/start": "http://10.0.0.5/private"}

    def fake_fetch_once(url):
        parsed = inner_agent.urllib.parse.urlparse(url)
        inner_agent._resolve_pinned_ip(parsed.hostname)  # exercises the real check
        return b"ok", hops.get(url), "utf-8"

    monkeypatch.setattr(inner_agent, "_fetch_once", fake_fetch_once)

    with pytest.raises(ValueError, match="host must be public"):
        inner_agent._fetch_public_url("http://93.184.216.34/start")
