"""Prompt contracts for one paper-conversion agent."""
from __future__ import annotations

import pathlib

from runner import WorkUnit


COMPLETE_PROMISE = "<promise>CONVERSION-COMPLETE</promise>"
BLOCKED_PROMISE = "<promise>CONVERSION-BLOCKED</promise>"
SUMMARY_INSTRUCTION = (
    "In brief bullet points, in en-US, summarize what you have just done in this "
    "pass: what you were looking for, what you found, what you decided and why, "
    "what you fixed, how far along the conversion is, and what still needs to be "
    "done to ensure that the paper is converted and compliant with the LaTeX "
    "template required by the venue. No prose, no preamble—just the bullet points."
)


def build_system_prompt(cwd: pathlib.Path) -> str:
    downloads = pathlib.Path(cwd) / "downloads"
    return f"""You are a paper-conversion agent. Only LaTeX templates are in scope. Every successful source mode must converge on a verified, usable local LaTeX package.

For ranking and chosen-venue URL modes:
1. Identify the targeted venue; in results mode, use only the ranking top-1 venue.
2. Verify whether the supplied URL is a real template or a page linking to one.
3. Verify the venue/track/workshop identity and reject sibling-event templates.
4. Search closely related official venue pages when the first evidence is unclear or wrong.
5. Download the right template into {downloads}.
6. Return to the venue source for missing mandatory files before declaring the template incomplete.

For template-path mode, first verify that the supplied path is an extractable archive or usable LaTeX package. A usable user-supplied path is treated as the right venue template; the agent does not re-search the venue.

At the start of every pass, inspect existing downloads and conversion artifacts before searching. Trust the previous-pass recap, do not repeat settled searches, and continue adaptively from whatever point prior work reached. After obtaining a template, inspect the directory contents before deciding what to do and recursively extract nested archives. A usable package normally requires .cls and/or .sty files, plus a .bst file when the venue mandates its reference style. A sample .tex is useful but not required; create a minimal main.tex when it is absent.

Copy only the minimal required submission set into converted/. For every agent-initiated copy, first create the mandated sibling copy beside the source using the same parent and a -copy-{{i}} suffix, then use that copy as the source for the final minimal submission tree. Fix text you wrote in place. Restore mangled template files by re-extracting them rather than reconstructing them.

Use write_file only for file creation or a full rewrite and edit_file for small exact changes. Use run_shell for inspection, extraction, copying, and deletion. After every download or extraction, list the directory recursively before making the next decision. Keep all shell activity inside this workspace or the explicitly supplied template path.

The expected happy sequences are:
- ranking/chosen: search -> fetch_url -> download_file -> inspect -> edit/write -> compile
- template path: inspect -> edit/write -> compile
The real sequence is adaptive and may resume halfway through work.

Re-check every mandatory venue structure and compile with the compile tool before promising. Never claim success from plausible LaTeX text or partial compliance. Emit {COMPLETE_PROMISE} only after verifying every mandatory template requirement and confirming that converted/main.tex exists beside a non-empty converted/main.pdf.

Emit {BLOCKED_PROMISE} only after writing a non-empty conversion-status.md with the verified reason for one genuine terminal gate: no venue-specific LaTeX template exists after thorough venue-accurate search; a found template cannot be downloaded, with the progress recorded; a user-provided path is missing, corrupt, non-LaTeX, or unusable; a downloaded template is incomplete and missing required pieces cannot be recovered from the venue source; or the paper cannot meet a mandatory minimum page count without inventing content. Do not use the blocked promise for any other difficulty.

Authentication/permission errors abort immediately. For a rate limit, retry the current pass after the server-provided delay. Other pass exceptions advance to the next pass. Do not produce a recap after the final pass."""


def build_user_order(unit: WorkUnit, paper_text: str) -> str:
    if unit.mode == "results":
        source_instruction = (
            "Use the top-1 venue's LaTeX template URL/evidence from the mapped "
            f"ranking.md at {unit.source}, and verify the true venue template."
        )
    elif unit.mode == "chosen-venue":
        source_instruction = (
            "Download and verify the strict venue LaTeX template described in this "
            f"chosen-venue paragraph: {unit.source}"
        )
    elif unit.mode == "template-path":
        source_instruction = (
            f"Inspect and use the LaTeX template at the supplied path: {unit.source}"
        )
    else:
        raise ValueError(f"Unsupported converter source mode: {unit.mode}")

    strict_conversion_order = (
        "Convert the paper to 100% of the venue's mandatory LaTeX template "
        "requirements. Keep the paper's original language regardless of the "
        "order or search language. Preserve paragraph wording and terminology "
        "exactly and retain all content faithfully. Drop a whole section only "
        "when mandatory template section names make the original section "
        "structurally impossible to retain. Summarize only after a successful "
        "compile proves that the paper exceeds a mandatory page limit; preserve "
        "wording and terminology while shortening long-winded text, then cut only "
        "material outside the main point if still necessary. Never claim success "
        "at partial compliance. Re-check every mandatory structural requirement "
        "and compile before promising."
    )
    return f"{source_instruction}\n\n{strict_conversion_order}\n\n---\nPAPER CONTENT:\n{paper_text}"


def build_pass_user_order(order: str, pass_no: int, max_passes: int) -> str:
    if pass_no == max_passes:
        pass_order = (
            f"Ralph pass {pass_no}/{max_passes}. This is the final pass: finish all "
            "remaining verification and conversion work now; leave nothing for a "
            "later pass."
        )
    else:
        pass_order = (
            f"Ralph pass {pass_no}/{max_passes}. Continue adaptively from existing "
            "downloads, artifacts, and the previous-pass recap without repeating "
            "settled work."
        )
    source_instruction, remaining_order = order.split("\n\n", 1)
    return f"{source_instruction}\n\n{pass_order}\n\n{remaining_order}"
