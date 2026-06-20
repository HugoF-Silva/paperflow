import pathlib
import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

@pytest.fixture
def example_docx() -> pathlib.Path:
    matches = list((REPO_ROOT / "input_examples").glob("*.docx"))
    assert matches, "no example .docx found in input_examples/"
    return matches[0]
