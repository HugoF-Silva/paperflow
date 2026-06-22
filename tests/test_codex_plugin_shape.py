import json
import os
import pathlib
import subprocess
import sys

import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "plugins" / "academia-perks-openai"


def test_codex_plugin_manifest_points_at_isolated_skill_tree():
    manifest_path = PLUGIN_DIR / ".codex-plugin" / "plugin.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["name"] == "academia-perks-openai"
    assert manifest["version"] == "0.1.0"
    assert manifest["skills"] == "./skills/"
    assert (PLUGIN_DIR / "skills" / "venue-matcher" / "SKILL.md").exists()
    assert manifest["interface"]["displayName"] == "Academia Perks OpenAI"
    assert manifest["interface"]["category"] == "Education & Research"


def test_codex_skill_frontmatter_is_valid_yaml():
    skill_path = PLUGIN_DIR / "skills" / "venue-matcher" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]

    data = yaml.safe_load(frontmatter)

    assert data["name"] == "venue-matcher"
    assert "bundled venue-matcher program" in data["description"]


def test_codex_skill_keeps_provider_neutral_orchestrator_wording():
    skill_path = PLUGIN_DIR / "skills" / "venue-matcher" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")

    assert "# venue-matcher (orchestrator guide)" in text
    assert "You are the **outer agent**." in text
    assert "spawns a fresh neurotic agent which web-searches" in text
    assert "what is happening - excellent service." in text
    assert "## What the system is (explain this to the user when useful)" in text
    assert "- **Inner agent:** one fresh agent per paper, runs a *ralph loop*" in text
    assert "- **Codex 5-minute reality:** one paper's full loop is built to finish under" in text
    assert "More papers run sequentially and may exceed the sandbox cap" in text
    assert "fresh neurotic OpenAI inner agent" not in text
    assert "# venue-matcher (Codex orchestrator guide)" not in text


def test_repo_marketplace_exposes_isolated_plugin_folder():
    marketplace_path = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"

    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    plugin = marketplace["plugins"][0]

    assert marketplace["name"] == "paperflow"
    assert plugin["name"] == "academia-perks-openai"
    assert plugin["source"] == {"source": "local", "path": "./plugins/academia-perks-openai"}
    assert plugin["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }
    assert plugin["category"] == "Education & Research"


def test_codex_plugin_payload_excludes_repository_dev_files():
    dev_only = {
        "harness",
        "input_examples",
        "tests",
        "docs",
        "Dockerfile",
        "docker-compose.yml",
        "Makefile",
        "pyproject.toml",
    }

    assert PLUGIN_DIR.exists()
    assert not any((PLUGIN_DIR / name).exists() for name in dev_only)
    assert not any(
        path.name == "__pycache__" or path.suffix == ".pyc"
        for path in PLUGIN_DIR.rglob("*")
    )


def test_codex_plugin_runtime_uses_openai_dependencies():
    requirements = (
        PLUGIN_DIR
        / "skills"
        / "venue-matcher"
        / "scripts"
        / "requirements.txt"
    ).read_text(encoding="utf-8")
    inner_agent = (
        PLUGIN_DIR
        / "skills"
        / "venue-matcher"
        / "scripts"
        / "venue_matcher"
        / "inner_agent.py"
    ).read_text(encoding="utf-8")

    assert "openai-agents" in requirements
    assert "claude-agent-sdk" not in requirements
    assert "from agents import" in inner_agent
    assert "claude_agent_sdk" not in inner_agent


def test_codex_plugin_cli_reports_missing_openai_key(tmp_path):
    cli_path = (
        PLUGIN_DIR
        / "skills"
        / "venue-matcher"
        / "scripts"
        / "venue_matcher"
        / "cli.py"
    )
    env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    proc = subprocess.run(
        [sys.executable, str(cli_path), "--input-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        env=env,
    )

    assert proc.returncode == 2
    assert "The following API keys are not set: OPENAI_API_KEY" in (
        proc.stdout + proc.stderr
    )
