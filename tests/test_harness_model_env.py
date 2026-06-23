import asyncio

import pytest

from harness import cli, outer_agent


def _clear_model_env(monkeypatch):
    for key in ("OPENAI_MODEL", "ANTHROPIC_MODEL", "VENUE_MATCHER_MODEL"):
        monkeypatch.delenv(key, raising=False)


def test_openai_harness_uses_default_model_when_provider_model_env_is_missing(
    monkeypatch, tmp_path
):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    captured = {}

    async def fake_run(prompt, repo_root, extra_skill_paths=None, model=None, api="anthropic"):
        captured.update(prompt=prompt, model=model, api=api)
        return 0

    monkeypatch.setattr(outer_agent, "run", fake_run)

    rc = cli.main([
        "--api", "openai",
        "--repo-root", str(tmp_path),
        "--local-config", str(tmp_path / ".paperflow.local.toml"),
    ])

    assert rc == 0
    assert captured["api"] == "openai"
    assert captured["model"] == "gpt-5.4-mini"
    assert "- Model value: gpt-5.4-mini" in captured["prompt"]


def test_cli_passes_provider_model_as_inner_agent_model(monkeypatch, tmp_path):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test-model")
    captured = {}

    async def fake_run(prompt, repo_root, extra_skill_paths=None, model=None, api="anthropic"):
        captured.update(prompt=prompt, repo_root=repo_root, model=model, api=api)
        return 0

    monkeypatch.setattr(outer_agent, "run", fake_run)

    rc = cli.main([
        "--api", "openai",
        "--repo-root", str(tmp_path),
        "--local-config", str(tmp_path / ".paperflow.local.toml"),
    ])

    assert rc == 0
    assert captured["api"] == "openai"
    assert captured["model"] == "gpt-test-model"
    assert "- Model env var: VENUE_MATCHER_MODEL" in captured["prompt"]
    assert "- Model value: gpt-test-model" in captured["prompt"]


@pytest.mark.parametrize(
    ("api", "runner_name", "expected_model"),
    [
        ("openai", "_run_openai", "gpt-test-model"),
        ("anthropic", "_run_anthropic", "claude-test-model"),
    ],
)
def test_outer_agent_resolves_model_from_selected_api_env(
    monkeypatch, tmp_path, api, runner_name, expected_model
):
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test-model")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-test-model")
    captured = {}

    async def fake_runner(prompt, repo_root, extra_skill_paths, model):
        captured["model"] = model
        return 0

    monkeypatch.setattr(outer_agent, runner_name, fake_runner)

    rc = asyncio.run(outer_agent.run("prompt", tmp_path, api=api))

    assert rc == 0
    assert captured["model"] == expected_model


@pytest.mark.parametrize(
    ("api", "runner_name", "expected_model"),
    [
        ("openai", "_run_openai", "gpt-5.4-mini"),
        ("anthropic", "_run_anthropic", "claude-sonnet-4-6"),
    ],
)
def test_outer_agent_resolves_default_model_when_selected_api_env_is_missing(
    monkeypatch, tmp_path, api, runner_name, expected_model
):
    _clear_model_env(monkeypatch)
    captured = {}

    async def fake_runner(prompt, repo_root, extra_skill_paths, model):
        captured["model"] = model
        return 0

    monkeypatch.setattr(outer_agent, runner_name, fake_runner)

    rc = asyncio.run(outer_agent.run("prompt", tmp_path, api=api))

    assert rc == 0
    assert captured["model"] == expected_model
