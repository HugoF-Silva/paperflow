"""Inner-agent prompts. The system prompt is assembled from the bundled
guidance/ markdown so the neurotic mindset/how-to is editable as docs but
delivered to the inner agent (which can't read skill files) via the system
prompt."""
from __future__ import annotations

from datetime import date
import pathlib

PROMISE_TAG = "<promise>VENUE-MATCH-COMPLETE</promise>"

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
        "Classifique os veículos de publicação aos quais este artigo realmente "
        "pertence e escreva ranking.json e ranking.md no seu diretório de "
        "trabalho, em português brasileiro.\n\n"
        "Mantenha as chaves de ranking.json em inglês exatamente como no "
        "esquema. Escreva os valores textuais de ranking.json e todo o "
        "ranking.md em português brasileiro. Não traduza nomes oficiais de "
        "venues, URLs nem o texto do artigo.\n\n"
        f"Parâmetro soon_days: {soon_days}\n"
        f"Data de hoje: {date.today().isoformat()}\n\n"
        "Esquema de ranking.json (chaves em inglês): "
        "{\"paper\": {\"path\": str, \"is_statement\": str, "
        "\"isnt_statement\": str}, \"params\": {\"soon_days\": int, "
        "\"countries\": [str], \"as_of\": str}, \"open_now\": [{\"rank\": int, "
        "\"name\": str, \"kind\": str, \"url\": str, \"country\": str, "
        "\"deadline\": str, \"topics_matched\": [str], \"rationale\": str}], "
        "\"opening_soon\": [...same...], \"closest_misses\": [...], "
        "\"agent_notes\": str}\n\n"
        "Texto do artigo (preserve exatamente como está; não traduza):\n"
        f"{paper_text}\n"
    )
