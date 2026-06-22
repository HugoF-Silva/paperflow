import os
from harness import cli

def test_parse_defaults(monkeypatch):
    for k in ("MAX_RALPH", "MAX_PARALLEL", "INNER_MAX_TURNS"):
        monkeypatch.delenv(k, raising=False)
    ns = cli.parse_args([])
    assert ns.input_dir.as_posix() == "/work/papers"
    assert ns.soon_days == 31 and ns.max_ralph == 8 and ns.max_parallel == "1"

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
