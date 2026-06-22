import asyncio
import pathlib
import sys
import types

import pytest
from harness import outer_agent

def test_build_outer_prompt_contains_inputs_and_key():
    prompt = outer_agent.build_outer_prompt("/work/papers", 31,
                                            {"ANTHROPIC_API_KEY": "sk-xyz"})
    assert "/work/papers" in prompt
    assert "31" in prompt
    assert "ANTHROPIC_API_KEY" in prompt and "sk-xyz" in prompt
    assert "venue-matcher" in prompt

def test_stage_extra_skills_copies(tmp_path):
    src = tmp_path / "skA"
    (src).mkdir()
    (src / "SKILL.md").write_text("---\nname: skA\n---\n")
    dest = tmp_path / "dest"
    staged = outer_agent.stage_extra_skills([src], dest)
    assert staged == ["skA"]
    assert (dest / "skA" / "SKILL.md").exists()

def test_build_outer_prompt_forbids_env_knobs():
    prompt = outer_agent.build_outer_prompt("/work/papers", 31, {"ANTHROPIC_API_KEY": "k"})
    assert "MAX_PARALLEL" in prompt
    assert "only" in prompt.lower()

def test_resolve_plugin_root_uses_isolated_claude_plugin(tmp_path):
    assert outer_agent.resolve_plugin_root(tmp_path, "anthropic") == (
        tmp_path / "plugins" / "academia-perks-claude"
    )

def test_resolve_plugin_root_uses_isolated_openai_plugin(tmp_path):
    assert outer_agent.resolve_plugin_root(tmp_path, "openai") == (
        tmp_path / "plugins" / "academia-perks-openai"
    )

def test_api_config_is_single_provider_seam():
    anthropic = outer_agent.api_config("anthropic")
    openai = outer_agent.api_config("openai")

    assert anthropic.required_keys == ("ANTHROPIC_API_KEY",)
    assert anthropic.plugin_path.as_posix() == "plugins/academia-perks-claude"
    assert anthropic.default_model == "claude-sonnet-4-6"
    assert openai.required_keys == ("OPENAI_API_KEY",)
    assert openai.plugin_path.as_posix() == "plugins/academia-perks-openai"
    assert openai.default_model == "gpt-5.4-mini"

def test_run_anthropic_loads_plugin_with_claude_sdk(monkeypatch, tmp_path):
    captured = {}

    class ResultMessage:
        subtype = "success"
        result = "ok"

    class ClaudeAgentOptions:
        def __init__(self, **kwargs):
            captured["options"] = kwargs

    async def query(prompt, options):
        captured["prompt"] = prompt
        captured["query_options"] = options
        yield ResultMessage()

    fake_sdk = types.SimpleNamespace(
        query=query,
        ClaudeAgentOptions=ClaudeAgentOptions,
        ResultMessage=ResultMessage,
    )
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", fake_sdk)

    rc = asyncio.run(outer_agent.run("prompt", tmp_path, api="anthropic"))

    assert rc == 0
    assert captured["options"]["plugins"] == [
        {
            "type": "local",
            "path": str(tmp_path / "plugins" / "academia-perks-claude"),
        }
    ]
    assert captured["options"]["model"] == "claude-sonnet-4-6"

def test_run_openai_uses_openai_agents_sdk_not_claude(monkeypatch, tmp_path):
    skill = (
        tmp_path
        / "plugins"
        / "academia-perks-openai"
        / "skills"
        / "venue-matcher"
        / "SKILL.md"
    )
    skill.parent.mkdir(parents=True)
    skill.write_text("OPENAI SKILL BODY\nOPENAI_API_KEY\n", encoding="utf-8")
    captured = {}

    def function_tool(fn):
        return fn

    class Agent:
        def __init__(self, **kwargs):
            captured["agent"] = kwargs
            captured["agent_instance"] = self

    class Runner:
        @staticmethod
        async def run(agent, prompt, max_turns):
            captured["run"] = {
                "agent": agent,
                "prompt": prompt,
                "max_turns": max_turns,
            }
            return types.SimpleNamespace(final_output="openai ok")

    def claude_query(*args, **kwargs):
        raise AssertionError("openai mode must not use claude_agent_sdk")

    monkeypatch.setitem(
        sys.modules,
        "agents",
        types.SimpleNamespace(Agent=Agent, Runner=Runner, function_tool=function_tool),
    )
    monkeypatch.setitem(
        sys.modules,
        "claude_agent_sdk",
        types.SimpleNamespace(query=claude_query),
    )

    rc = asyncio.run(outer_agent.run("outer prompt", tmp_path, api="openai"))

    assert rc == 0
    assert captured["agent"]["name"] == "venue-matcher-outer"
    assert captured["agent"]["model"] == "gpt-5.4-mini"
    assert "OPENAI SKILL BODY" in captured["agent"]["instructions"]
    assert "OPENAI_API_KEY" in captured["agent"]["instructions"]
    assert captured["agent"]["tools"]
    assert captured["run"]["agent"] is captured["agent_instance"]
    assert captured["run"]["prompt"] == "outer prompt"
    assert captured["run"]["max_turns"] == 600

def test_stage_extra_skills_fatal_on_venue_matcher_collision(tmp_path):
    src = tmp_path / "venue-matcher"
    src.mkdir()
    (src / "SKILL.md").write_text("---\nname: venue-matcher\n---\n")
    with pytest.raises(SystemExit):
        outer_agent.stage_extra_skills([src], tmp_path / "dest")

def test_stage_extra_skills_skips_path_without_skill_md(tmp_path):
    src = tmp_path / "notaskill"
    src.mkdir()  # deliberately no SKILL.md
    staged = outer_agent.stage_extra_skills([src], tmp_path / "dest")
    assert staged == []
