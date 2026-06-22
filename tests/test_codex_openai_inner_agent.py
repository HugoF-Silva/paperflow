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


def test_openai_fetch_url_rejects_non_public_urls():
    inner_agent = load_openai_inner_agent()

    with pytest.raises(ValueError, match="http or https"):
        inner_agent._validate_public_url("file:///etc/passwd")
    with pytest.raises(ValueError, match="host must be public"):
        inner_agent._validate_public_url("http://localhost:8000")
    with pytest.raises(ValueError, match="host must be public"):
        inner_agent._validate_public_url("http://127.0.0.1:8000")
