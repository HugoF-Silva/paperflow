"""Regression tests for the overfull-box verdict the compile tool reports.

Tectonic exits 0 and writes a valid PDF even when TeX printed content outside
the text block, so a compile result that only carries an exit code and a PDF
path reads as success. These tests pin the field that says otherwise.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CONVERTER_SCRIPTS = (
    Path(__file__).resolve().parents[2]
    / "src/plugins/academia-perks/skills/converter/scripts"
)
sys.path.insert(0, str(CONVERTER_SCRIPTS))

from converter.tools import _compile, _overfull_boxes


# Verbatim Tectonic stderr from a converted paper whose comparison table ran
# past the column edge, including the rerun that repeats every warning.
TECTONIC_STDERR = """\
note: downloading article.cls
warning: main.tex:72: Overfull \\hbox (66.0pt too wide) in paragraph at lines 72--72
warning: main.tex:236: Overfull \\hbox (6.00002pt too wide) in paragraph at lines 226--236
warning: main.tex:256: Overfull \\hbox (90.28003pt too wide) in paragraph at lines 243--256
warning: main.bbl:62: Underfull \\hbox (badness 2326) in paragraph at lines 57--62
warning: main.tex:72: Overfull \\hbox (66.0pt too wide) in paragraph at lines 72--72
warning: main.tex:236: Overfull \\hbox (6.00002pt too wide) in paragraph at lines 226--236
warning: main.tex:256: Overfull \\hbox (90.28003pt too wide) in paragraph at lines 243--256
warning: warnings were issued by the TeX engine; use --print and/or --keep-logs for details.
"""


def test_overfull_boxes_reports_worst_first_without_rerun_duplicates() -> None:
    boxes = _overfull_boxes(TECTONIC_STDERR)

    assert len(boxes) == 3, boxes
    assert [line.split("Overfull")[0].strip() for line in boxes] == [
        "warning: main.tex:256:",
        "warning: main.tex:72:",
        "warning: main.tex:236:",
    ]


def test_overfull_boxes_ignores_cosmetic_underfull_warnings() -> None:
    assert _overfull_boxes(
        "warning: main.bbl:62: Underfull \\hbox (badness 2326) in paragraph at lines 57--62\n"
        "note: downloading cmr10.tfm\n"
    ) == []


def test_overfull_boxes_reports_a_vbox_running_off_the_page() -> None:
    boxes = _overfull_boxes(
        "warning: main.tex:9: Overfull \\vbox (12.5pt too high) has occurred while \\output is active\n"
    )

    assert len(boxes) == 1
    assert "too high" in boxes[0]


def test_overfull_boxes_keeps_only_the_worst_within_the_limit() -> None:
    lines = "\n".join(
        f"warning: main.tex:{line}: Overfull \\hbox ({line}.0pt too wide) in paragraph"
        for line in range(1, 30)
    )

    boxes = _overfull_boxes(lines, limit=3)

    assert [line.split(":")[2] for line in boxes] == ["29", "28", "27"]


def test_compile_reports_overfull_boxes_beside_a_successful_exit_code(
    tmp_path: Path,
) -> None:
    build = tmp_path / "converted"
    build.mkdir()
    (build / "main.tex").write_text("irrelevant", encoding="utf-8")

    def fake_run(args, **kwargs):
        (build / "main.pdf").write_bytes(b"%PDF-1.5\ncontent")
        return subprocess.CompletedProcess(args, 0, "", TECTONIC_STDERR)

    result = _compile(tmp_path, "converted", "main.tex", run=fake_run)

    assert result["exit_code"] == 0
    assert result["pdf"] == "converted/main.pdf"
    assert len(result["overfull"]) == 3
    assert "90.28003pt too wide" in result["overfull"][0]
