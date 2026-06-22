import os, subprocess, sys, pathlib
import cli

CLI = pathlib.Path(
    "plugins/academia-perks-claude/skills/venue-matcher/scripts/venue_matcher/cli.py"
).resolve()

def test_missing_api_keys():
    assert cli.missing_api_keys({}, ["ANTHROPIC_API_KEY"]) == ["ANTHROPIC_API_KEY"]
    assert cli.missing_api_keys({"ANTHROPIC_API_KEY": "x"}, ["ANTHROPIC_API_KEY"]) == []

def test_parse_args_defaults():
    ns = cli.parse_args(["--input-dir", "/p"])
    assert ns.input_dir.as_posix() == "/p" and ns.soon_days == 31

def test_cli_subprocess_reports_missing_key(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([sys.executable, str(CLI), "--input-dir", str(tmp_path)],
                          capture_output=True, text=True, env=env)
    assert proc.returncode != 0
    assert "The following API keys are not set: ANTHROPIC_API_KEY" in (proc.stdout + proc.stderr)
