import pathlib
import shutil
import sys
import pytest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN_ROOTS = (
    REPO_ROOT / "plugins" / "academia-perks-claude",
    REPO_ROOT / "plugins" / "academia-perks-openai",
)


def remove_plugin_bytecode():
    for root in PLUGIN_ROOTS:
        if not root.exists():
            continue
        for cache_dir in root.rglob("__pycache__"):
            shutil.rmtree(cache_dir)
        for pyc in root.rglob("*.pyc"):
            pyc.unlink()


@pytest.fixture(autouse=True)
def clean_plugin_bytecode():
    remove_plugin_bytecode()
    yield
    remove_plugin_bytecode()

@pytest.fixture
def example_docx() -> pathlib.Path:
    matches = list((REPO_ROOT / "input_examples").glob("*.docx"))
    assert matches, "no example .docx found in input_examples/"
    return matches[0]
