import json
import pathlib

import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "plugins" / "academia-perks-claude"


def test_claude_plugin_manifest_points_at_isolated_skill_tree():
    manifest_path = PLUGIN_DIR / ".claude-plugin" / "plugin.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["name"] == "academia-perks-claude"
    assert manifest["version"] == "0.1.0"
    assert (PLUGIN_DIR / "skills" / "venue-matcher" / "SKILL.md").exists()


def test_claude_skill_frontmatter_is_valid_yaml():
    skill_path = PLUGIN_DIR / "skills" / "venue-matcher" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]

    data = yaml.safe_load(frontmatter)

    assert data["name"] == "venue-matcher"
    assert "bundled venue-matcher program" in data["description"]


def test_claude_plugin_payload_excludes_repository_dev_files():
    dev_only = {
        "harness",
        "input_examples",
        "tests",
        "docs",
        "Dockerfile",
        "docker-compose.yml",
        "Makefile",
        "pyproject.toml",
        ".codex-plugin",
    }

    assert PLUGIN_DIR.exists()
    assert not any((PLUGIN_DIR / name).exists() for name in dev_only)
    assert not any(
        path.name == "__pycache__" or path.suffix == ".pyc"
        for path in PLUGIN_DIR.rglob("*")
    )


def test_repository_root_does_not_keep_duplicate_claude_skill_tree():
    assert not (REPO_ROOT / "skills").exists()


def test_claude_plugin_runtime_uses_anthropic_dependencies():
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

    assert "claude-agent-sdk" in requirements
    assert "openai-agents" not in requirements
    assert "claude_agent_sdk" in inner_agent
    assert "from agents import" not in inner_agent
