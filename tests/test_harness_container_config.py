import pathlib

import yaml


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_docker_image_includes_both_provider_plugins():
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY plugins/academia-perks-claude /app/plugins/academia-perks-claude" in dockerfile
    assert "COPY plugins/academia-perks-openai /app/plugins/academia-perks-openai" in dockerfile


def test_compose_exposes_both_provider_api_keys():
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

    environment = compose["services"]["matcher"]["environment"]
    assert environment["ANTHROPIC_API_KEY"] == "${ANTHROPIC_API_KEY}"
    assert environment["OPENAI_API_KEY"] == "${OPENAI_API_KEY}"


def test_harness_installs_both_outer_agent_sdks():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "claude-agent-sdk" in pyproject
    assert "openai-agents" in pyproject
