"""Inner-agent prompts. The system prompt is assembled from the bundled
guidance/ markdown so the neurotic mindset/how-to is editable as docs but
delivered to the inner agent (which can't read skill files) via the system
prompt."""
from __future__ import annotations

from datetime import date
import pathlib

PROMISE_TAG = "<promise>VENUE-MATCH-COMPLETE</promise>"

_GUIDANCE_FILES = ("mindset.md", "venue-anatomy.md", "tips.md")

CONCISION_POLICY = (
    "Reason deeply; write briefly. Search iterations are working steps, not "
    "deliverables: do not write "
    "long prose while investigating, and do not preserve every thought in chat. "
    "Use terse notes to decide fit, then Rerank after each verified candidate. "
    "Long prose belongs only in ranking.md.\n"
)

SUMMARY_INSTRUCTION = (
    "Em tópicos sucintos, em português brasileiro, recapitule o que você "
    "acabou de fazer nesta passagem: o que você buscou, o que encontrou, o que "
    "descartou e por quê, e o que ainda está em aberto. Sem prosa, sem "
    "preâmbulo — apenas os tópicos. Inclua uma recapitulação cumulativa: "
    "preserve os pontos ainda relevantes de <previous_pass_recap> e "
    "acrescente/substitua com o que foi aprendido nesta passagem. Não descarte "
    "fatos úteis de <previous_pass_recap> só porque eles não foram pesquisados "
    "novamente agora."
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
        "pertence e escreva somente ranking.md no seu diretório de trabalho, "
        "em português brasileiro. Não traduza nomes oficiais de venues, nem URLs.\n\n"
        "Use exatamente um escopo geográfico de audiência alvo: use o escopo "
        "declarado se houver um; se houver uma lista ou mais de um, use apenas o "
        "primeiro declarado; se não houver, use International. Nunca amplie a "
        "busca para um escopo declarado depois do primeiro.\n\n"
        "Não inclua venues que exigem pagamento de taxa para submissão.\n\n"
        f"Parâmetro soon_days: {soon_days}\n"
        f"Data de hoje: {date.today().isoformat()}\n\n"
        "Estruture ranking.md com estas seções:\n"
        "## Artigo\n"
        "- Caminho ou origem do artigo.\n"
        "- O que este artigo é.\n"
        "- O que este artigo não é.\n\n"
        "## Parâmetros\n"
        "- soon_days.\n"
        "- Escopo geográfico de audiência alvo considerado.\n"
        "- Data de referência.\n\n"
        "## Abertos agora\n"
        "Liste, em uma única lista ranqueada em ordem de encaixe, venues com nome, "
        "tipo, URL dos tópicos de interesse, URL do template latex da venue, escopo "
        "de audiência, prazo, tópicos citados e justificativa específica para o "
        "artigo.\n\n"
        "## Abrindo em breve\n"
        "Mesmo formato dos abertos agora, apenas para venues que abrem dentro "
        "de soon_days.\n\n"
        "## Quase encaixes\n"
        "Liste os melhores descartados quando nenhum encaixe forte estiver "
        "aberto ou abrindo em breve, explicando a limitação.\n\n"
        "## Notas do agente\n"
        "Registre buscas importantes, decisões e incertezas que afetam o "
        "resultado.\n\n"
        "---\n"
        "## Texto do artigo:\n"
        f"{paper_text}\n"
    )


def build_pass_user_order(user_order: str, pass_no: int, x: int) -> str:
    if pass_no == x:
        pass_order = (
            f"você está na tentativa {x}/{x} de achar o melhor fit, essa é sua "
            "última chance, entre em fase de polimento/encerramento para que não "
            "deixe nada pra depois e entregue o resultado do ranking.md. Garanta "
            "que entregue o ranking.md que mais o satisfaz por mais que esteja "
            "insatisfeito"
        )
    else:
        pass_order = (
            f"você está na tentativa {(x + 1) // 2}/{x} de achar o melhor fit pro "
            "paper. Você já fez 50% das tentativas de exploração (buscas) "
            "disponiveis e pode fazer mais metade das tentativas disponíveis. "
            "Aproveite pra pesquisar profundamente enquanto ainda não está perto "
            "do fim."
        )
    return f"{pass_order}\n\n{user_order}"
