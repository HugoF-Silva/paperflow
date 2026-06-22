import os
from harness import cli

def test_parse_defaults(monkeypatch):
    for k in ("MAX_RALPH", "MAX_PARALLEL", "INNER_MAX_TURNS"):
        monkeypatch.delenv(k, raising=False)
    ns = cli.parse_args([])
    assert ns.input_dir.as_posix() == "/work/papers"
    assert ns.soon_days == 31 and ns.max_ralph == 8 and ns.max_parallel == "1"
    assert ns.api == "anthropic"

def test_parse_api_limited_to_supported_values():
    assert cli.parse_args(["--api", "openai"]).api == "openai"
    assert cli.parse_args(["--api", "anthropic"]).api == "anthropic"
    try:
        cli.parse_args(["--api", "claude"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("unsupported --api value should fail argparse validation")

def test_parse_extra_skill_paths_list():
    ns = cli.parse_args(["--extra-skill-paths", "/a", "--extra-skill-paths", "/b"])
    assert [p.as_posix() for p in ns.extra_skill_paths] == ["/a", "/b"]

def test_apply_env_sets_dev_only_vars():
    ns = cli.parse_args(["--max-ralph", "5", "--max-parallel", "auto"])
    env = {}
    cli.apply_env(ns, env)
    assert env["MAX_RALPH"] == "5" and env["MAX_PARALLEL"] == "auto"

def test_env_knobs_respected_not_clobbered(monkeypatch):
    monkeypatch.setenv("MAX_PARALLEL", "4")
    monkeypatch.setenv("MAX_RALPH", "12")
    ns = cli.parse_args([])                      # compose passes no knob flags
    assert ns.max_parallel == "4"
    assert ns.max_ralph == 12
    env = {}
    cli.apply_env(ns, env)
    assert env["MAX_PARALLEL"] == "4"            # preserved, not reset to "1"
    assert env["MAX_RALPH"] == "12"

def test_required_keys_follow_selected_api():
    assert cli.required_keys_for_api("anthropic") == ["ANTHROPIC_API_KEY"]
    assert cli.required_keys_for_api("openai") == ["OPENAI_API_KEY"]

def test_main_requires_selected_openai_key(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    rc = cli.main(["--api", "openai"])

    err = capsys.readouterr().err
    assert rc == 2
    assert "OPENAI_API_KEY" in err
    assert "ANTHROPIC_API_KEY" not in err

def test_main_passes_selected_api_to_outer_agent(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    local_config = tmp_path / "local.toml"
    local_config.write_text("", encoding="utf-8")
    seen = {}

    async def fake_run(prompt, repo_root, extras, model="claude-sonnet-4-6", api="anthropic"):
        seen["prompt"] = prompt
        seen["repo_root"] = repo_root
        seen["extras"] = extras
        seen["api"] = api
        return 0

    monkeypatch.setattr(cli.outer_agent, "run", fake_run)

    rc = cli.main([
        "--api", "openai",
        "--local-config", str(local_config),
        "--repo-root", str(tmp_path),
    ])

    assert rc == 0
    assert seen["api"] == "openai"
    assert seen["repo_root"] == tmp_path
    assert seen["extras"] == []
    assert "OPENAI_API_KEY" in seen["prompt"]
    assert "openai-key" in seen["prompt"]
    assert "ANTHROPIC_API_KEY" not in seen["prompt"]

def test_main_loads_api_key_from_repo_dotenv(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    dotenv = tmp_path / ".env"
    dotenv.write_text("OPENAI_API_KEY=from-dotenv\n", encoding="utf-8")
    local_config = tmp_path / "local.toml"
    local_config.write_text("", encoding="utf-8")
    seen = {}

    async def fake_run(prompt, repo_root, extras, model=None, api="anthropic"):
        seen["prompt"] = prompt
        seen["api"] = api
        return 0

    monkeypatch.setattr(cli.outer_agent, "run", fake_run)

    rc = cli.main([
        "--api", "openai",
        "--repo-root", str(tmp_path),
        "--local-config", str(local_config),
    ])

    assert rc == 0
    assert seen["api"] == "openai"
    assert "OPENAI_API_KEY" in seen["prompt"]
    assert "from-dotenv" in seen["prompt"]
