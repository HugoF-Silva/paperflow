import os
from harness import cli

def test_parse_defaults():
    ns = cli.parse_args([])
    assert str(ns.input_dir) == "/work/papers"
    assert ns.soon_days == 31 and ns.max_ralph == 8 and ns.max_parallel == "1"

def test_parse_extra_skill_paths_list():
    ns = cli.parse_args(["--extra-skill-paths", "/a", "--extra-skill-paths", "/b"])
    assert [str(p) for p in ns.extra_skill_paths] == ["/a", "/b"]

def test_apply_env_sets_dev_only_vars():
    ns = cli.parse_args(["--max-ralph", "5", "--max-parallel", "auto"])
    env = {}
    cli.apply_env(ns, env)
    assert env["MAX_RALPH"] == "5" and env["MAX_PARALLEL"] == "auto"
