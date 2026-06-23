"""src/ holds the operational tree (harness + plugins) and is bind-mounted into
the matcher container at /app/src, so the container tree mirrors the host's
(no synthetic /work). Because src/ always exists (it holds tracked code), Docker
never has to auto-create a missing bind-mount dir, and results are created on the
fly inside it with no tracked empty dir. These tests lock that contract."""
import pathlib
import subprocess

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

_NO_WORK_FILES = (
    "src/harness/cli.py",
    "Dockerfile",
    "docker-compose.yml",
    "src/plugins/academia-perks-claude/skills/venue-matcher/SKILL.md",
    "src/plugins/academia-perks-openai/skills/venue-matcher/SKILL.md",
    "src/plugins/academia-perks-claude/skills/venue-matcher/scripts/venue_matcher/cli.py",
    "src/plugins/academia-perks-openai/skills/venue-matcher/scripts/venue_matcher/cli.py",
)


def _tracked(rel: str) -> bool:
    return subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel],
        cwd=REPO_ROOT, capture_output=True,
    ).returncode == 0


def _ignored(rel: str) -> bool:
    out = subprocess.run(
        ["git", "check-ignore", rel],
        cwd=REPO_ROOT, capture_output=True, text=True,
    ).stdout.strip()
    return out == rel


def test_operational_code_lives_under_src():
    assert _tracked("src/harness/cli.py")
    assert _tracked("src/plugins/academia-perks-claude/skills/venue-matcher/SKILL.md")


def test_compose_mounts_src_mirroring_the_host_tree():
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    volumes = compose["services"]["matcher"]["volumes"]
    assert "./src:/app/src" in [v for v in volumes if isinstance(v, str)]


def test_no_synthetic_work_path_remains():
    for rel in _NO_WORK_FILES:
        assert "/work/results" not in (REPO_ROOT / rel).read_text(encoding="utf-8"), rel


def test_results_created_on_the_fly_never_tracked():
    assert _ignored("src/results/ranking.json")
    assert _ignored("src/results/_progress.log")
    assert not _tracked("src/results/.gitkeep")


def test_papers_input_dir_kept_present_via_keepfile():
    assert _tracked("src/papers/.gitkeep")
    assert _ignored("src/papers/some-paper.docx")
