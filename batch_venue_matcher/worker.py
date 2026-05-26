"""Per-paper worker: converts a .docx to text, invokes the venue-matcher
skill via the Claude Agent SDK, and re-iterates only on clear deterministic
failure (missing promise, crash, missing/malformed outputs, max_turns hit).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)
from docx import Document

PROMISE_TAG = "<promise>VENUE-MATCH-COMPLETE</promise>"

SYSTEM_PROMPT = """\
You are a venue-matching agent. Your only job: find the publication venue(s) \
where a given academic paper truly belongs.

The user will invoke /venue-matcher with a paper path and search constraints. \
Follow that skill with neurotic care: read the paper, read each candidate \
venue's actual call-for-papers page, and orient the search around recognizing \
fit — never toward filling a quota or counter. Search snippets are never \
sufficient justification for including a venue; you must WebFetch the CFP.

Stopping condition: recognition that you've found the venue(s) the paper \
genuinely belongs to. Then, and only then, emit
<promise>VENUE-MATCH-COMPLETE</promise>
as the last line of your final message.

Do not emit a false promise. Trust the process.
"""


@dataclass
class WorkerResult:
    """Outcome for a single paper across all outer-loop iterations."""

    paper: Path
    success: bool
    iterations: int
    last_reason: str
    output_dir: Path
    failure_log: list[str] = field(default_factory=list)


@dataclass
class WorkerConfig:
    """Static configuration injected by `compose.py`. Per-paper params arrive
    in `run()`; this carries the cross-paper invariants."""

    cwd: Path
    skill_names: list[str]
    system_prompt: str = SYSTEM_PROMPT
    max_turns: int = 80
    max_iterations: int = 8
    allowed_tools: tuple[str, ...] = (
        "Read",
        "Write",
        "WebSearch",
        "WebFetch",
        "Agent",
    )


class Worker:
    """Runs the venue-matcher agent against one paper, with outer-loop
    failure recovery in the spirit of ralph-loop (but only on hard failures —
    no quality-iteration)."""

    def __init__(self, config: WorkerConfig):
        self._config = config

    def run(
        self,
        paper: Path,
        output_dir: Path,
        soon_days: int,
        countries: list[str],
    ) -> WorkerResult:
        """Synchronous entry point so a ProcessPoolExecutor can call it."""

        output_dir.mkdir(parents=True, exist_ok=True)
        paper_text_path = self._extract_paper_text(paper, output_dir)

        result = WorkerResult(
            paper=paper,
            success=False,
            iterations=0,
            last_reason="not_attempted",
            output_dir=output_dir,
        )

        user_prompt = self._build_user_prompt(
            paper, paper_text_path, output_dir, soon_days, countries
        )
        ranking_json = output_dir / "ranking.json"
        ranking_md = output_dir / "ranking.md"

        for iteration in range(1, self._config.max_iterations + 1):
            result.iterations = iteration
            reason = asyncio.run(
                self._one_iteration(user_prompt, ranking_json, ranking_md, iteration)
            )
            result.last_reason = reason
            result.failure_log.append(reason)
            self._append_iteration_log(output_dir, iteration, reason)
            if reason == "success":
                result.success = True
                break

        return result

    @staticmethod
    def _extract_paper_text(paper: Path, output_dir: Path) -> Path:
        """Convert .docx to UTF-8 text the agent can Read. The intermediate
        file is kept inside the per-paper output directory so a re-run can
        skip the conversion."""

        text_path = output_dir / "paper.txt"
        if text_path.exists() and text_path.stat().st_mtime >= paper.stat().st_mtime:
            return text_path

        doc = Document(str(paper))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text_path.write_text("\n\n".join(paragraphs), encoding="utf-8")
        return text_path

    def _build_user_prompt(
        self,
        paper: Path,
        paper_text: Path,
        output_dir: Path,
        soon_days: int,
        countries: list[str],
    ) -> str:
        today = datetime.now(tz=timezone.utc).astimezone().date().isoformat()
        countries_csv = ",".join(countries)
        return (
            "/venue-matcher\n"
            "\n"
            f"Match publication venues for this paper. Its plain text has been "
            f"extracted for you at: {paper_text}\n"
            f"(The source .docx is at {paper}, but you only need the .txt.)\n"
            "\n"
            "Search constraints (these are real web-search constraints, not "
            "opaque flags):\n"
            f"- Today's date: {today}.\n"
            f"- soon_days = {soon_days}. Reject any venue whose registration "
            f"opens after today + {soon_days} days. Venues already accepting "
            f"submissions go in `open_now`; venues opening within the bound go "
            "in `opening_soon`.\n"
            f"- countries = [{countries_csv}]. Strongly prefer venues primarily "
            "affiliated with these countries. Non-matching venues are allowed "
            "only when their thematic fit is markedly stronger than any "
            "in-country alternative AND they accept the paper's language.\n"
            "- The paper's language(s) — detect from the text. Brazilian "
            "Portuguese and/or English are expected.\n"
            "\n"
            "Write your final ranking to:\n"
            f"- {output_dir / 'ranking.json'}\n"
            f"- {output_dir / 'ranking.md'}\n"
            "\n"
            "When — and only when — you have recognized the venue(s) the paper "
            "truly belongs to, emit exactly this text on its own line as the "
            "LAST line of your final message:\n"
            f"{PROMISE_TAG}\n"
            "\n"
            "CRITICAL — do not emit a false promise:\n"
            "- The promise marks 'I did the work and arrived at a genuine "
            "result'.\n"
            "- It does NOT mean 'I gave up' or 'I'm tired' or 'I think I "
            "should stop now'.\n"
            "- Even if you feel stuck or the search seems impossible — you "
            "MUST NOT emit a false promise.\n"
            "- If after honest, thorough search you cannot find a strong fit, "
            "name the closest survivors and explain why none strongly fit — "
            "THEN emit the promise. That is a genuine result.\n"
            "- The orchestrator watching for this promise is designed to "
            "continue until the promise is unambiguously TRUE. Trust the "
            "process.\n"
        )

    async def _one_iteration(
        self,
        user_prompt: str,
        ranking_json: Path,
        ranking_md: Path,
        iteration: int,
    ) -> str:
        """Run one SDK iteration; return a short string reason describing
        the outcome ('success' or a deterministic failure label)."""

        # NOTE: skill discovery is purely filesystem-driven here. The
        # orchestrator stages the resolved set into `<cwd>/.claude/skills/`
        # before any worker fires; with `setting_sources=["project"]` and
        # `cwd` set, the SDK picks them up via project-scope discovery. We
        # deliberately do NOT pass a `skills=...` kwarg — the SDK reference
        # documents it inconsistently across versions, so we keep the call
        # to documented-stable fields only.
        options = ClaudeAgentOptions(
            cwd=str(self._config.cwd),
            setting_sources=["project"],
            allowed_tools=list(self._config.allowed_tools),
            system_prompt=self._config.system_prompt,
            max_turns=self._config.max_turns,
        )

        last_text = ""
        try:
            async for message in query(prompt=user_prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        text = getattr(block, "text", None)
                        if isinstance(text, str):
                            last_text = text
                elif isinstance(message, ResultMessage):
                    last_text = message.result or last_text
        except Exception as exc:
            logging.exception("SDK iteration %d crashed", iteration)
            return f"sdk_exception:{type(exc).__name__}"

        if PROMISE_TAG not in last_text:
            return "no_promise_in_final_message"

        if not ranking_json.exists() or not ranking_md.exists():
            return "missing_output_files"

        try:
            json.loads(ranking_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return "malformed_ranking_json"

        return "success"

    @staticmethod
    def _append_iteration_log(output_dir: Path, iteration: int, reason: str) -> None:
        log_path = output_dir / "iteration.log"
        stamp = datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="seconds")
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp}  iter={iteration}  {reason}\n")
