"""Inner-agent prompts. The system prompt is assembled from the bundled
guidance/ markdown so the neurotic mindset/how-to is editable as docs but
delivered to the inner agent (which can't read skill files) via the system
prompt."""
from __future__ import annotations

from datetime import date
import pathlib

PROMISE_TAG = "<promise>VENUE-MATCH-COMPLETE</promise>"

_GUIDANCE_FILES = ("mindset.md", "venue-anatomy.md")

CONCISION_POLICY = (
    "Reason deeply; write briefly. Search iterations are working steps, not "
    "deliverables: do not write "
    "long prose while investigating, and do not preserve every thought in chat. "
    "Use terse notes to decide fit, then Rerank after each verified candidate. "
    "Long prose belongs only in ranking.md; ranking.json should stay structured "
    "and concise.\n"
)

SUMMARY_INSTRUCTION = (
    "Em tópicos sucintos, em português brasileiro, recapitule o que você "
    "acabou de fazer nesta passagem: o que você buscou, o que encontrou, o que "
    "descartou e por quê, e o que ainda está em aberto. Sem prosa, sem "
    "preâmbulo — apenas os tópicos."
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
        f"{CONCISION_POLICY}\n"
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
        "Use exatamente um escopo geográfico de audiência alvo: use o escopo "
        "declarado se houver um; se houver uma lista ou mais de um, use apenas o "
        "primeiro declarado; se não houver, use International. Nunca amplie a "
        "busca para um escopo declarado depois do primeiro.\n\n"
        f"Parâmetro soon_days: {soon_days}\n"
        f"Data de hoje: {date.today().isoformat()}\n\n"
        "Esquema de ranking.json (chaves em inglês): "
        "{\"paper\": {\"path\": str, \"is_statement\": str, "
        "\"isnt_statement\": str}, \"params\": {\"soon_days\": int, "
        "\"audience_scope\": str, \"as_of\": str}, \"open_now\": [{\"rank\": int, "
        "\"name\": str, \"kind\": str, \"url\": str, \"audience_scope\": str, "
        "\"deadline\": str, \"topics_matched\": [str], \"rationale\": str}], "
        "\"opening_soon\": [...same...], \"closest_misses\": [...], "
        "\"agent_notes\": str}\n\n"
        "Texto do artigo (preserve exatamente como está; não traduza):\n"
        f"{paper_text}\n"
    )
