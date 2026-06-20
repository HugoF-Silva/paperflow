"""Inner-agent prompts. The system prompt is assembled from the bundled
guidance/ markdown so the neurotic mindset/how-to is editable as docs but
delivered to the inner agent (which can't read skill files) via the system
prompt."""
from __future__ import annotations

import pathlib

PROMISE_TAG = "<promise>VENUE-MATCH-COMPLETE</promise>"
DEFAULT_MODEL = "claude-sonnet-4-6"

_GUIDANCE_FILES = ("mindset.md", "venue-anatomy.md", "brazilian-ecosystems.md")

SUMMARY_INSTRUCTION = (
    "In <=8 terse bullets, recap what you just did this pass: what you searched, "
    "what you found, what you ruled out and why, and what is still open. "
    "No prose, no preamble — just the bullets."
)


def _guidance_dir(override: pathlib.Path | None) -> pathlib.Path:
    return override or (pathlib.Path(__file__).resolve().parent / "guidance")


def build_system_prompt(guidance_dir: pathlib.Path | None = None) -> str:
    gdir = _guidance_dir(guidance_dir)
    parts: list[str] = []
    for name in _GUIDANCE_FILES:
        path = gdir / name
        parts.append(path.read_text(encoding="utf-8"))
    body = "\n\n---\n\n".join(parts)
    return (
        "You are a venue-matching agent. Follow this guidance exactly.\n\n"
        f"{body}\n"
    )


def build_user_order(paper_text: str, soon_days: int) -> str:
    return (
        "Rank the publication venues this paper truly belongs to, and write "
        "ranking.json and ranking.md in your working directory.\n\n"
        f"soon_days: {soon_days}\n\n"
        "ranking.json schema: {\"paper\": {\"path\": str, \"is_statement\": str, "
        "\"isnt_statement\": str}, \"params\": {\"soon_days\": int, "
        "\"countries\": [str], \"as_of\": str}, \"open_now\": [{\"rank\": int, "
        "\"name\": str, \"kind\": str, \"url\": str, \"country\": str, "
        "\"deadline\": str, \"topics_matched\": [str], \"rationale\": str}], "
        "\"opening_soon\": [...same...], \"closest_misses\": [...], "
        "\"agent_notes\": str}\n\n"
        "PAPER:\n"
        f"{paper_text}\n"
    )
