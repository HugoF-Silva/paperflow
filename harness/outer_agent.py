"""The dev outer agent: an Agent SDK agent that loads the academia-perks plugin,
uses the venue-matcher skill, and runs the bundled CLI via Bash. API keys are
formatted into its prompt so it can export them before running."""
from __future__ import annotations

import pathlib
import shutil


def build_outer_prompt(input_dir: str, soon_days: int, api_keys: dict[str, str]) -> str:
    keys = "\n".join(f"- {k}={v}" for k, v in api_keys.items())
    return (
        "Use the venue-matcher skill to find publication venues for the papers.\n\n"
        f"Input directory (papers are here): {input_dir}\n"
        f"soon-days to pass to the program: {soon_days}\n\n"
        "Before running the program, ensure these API keys are exported in the "
        "environment (export each via Bash):\n"
        f"{keys}\n\n"
        "Then follow the skill: install deps, run the bundled CLI in the "
        "background with --input-dir and --soon-days, poll results/_progress.log "
        "until BATCH COMPLETE, and report the result files plus a human-friendly "
        "summary. If the input directory has no papers, say so and stop. "
        "Pass ONLY --input-dir and --soon-days to the program; never set "
        "MAX_PARALLEL, INNER_MAX_TURNS, or any other environment-variable knob "
        "— those are fixed by the developer and are not yours to change."
    )


def stage_extra_skills(paths, dest_dir: pathlib.Path) -> list[str]:
    """Copy each extra skill dir into dest_dir/<name> (outer agent only). Returns
    the staged skill names. Fatal on a name collision with venue-matcher."""
    dest_dir = pathlib.Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    staged: list[str] = []
    for raw in paths or []:
        src = pathlib.Path(raw)
        if not (src / "SKILL.md").exists():
            print(f"warn: extra skill path has no SKILL.md, skipping: {src}", flush=True)
            continue
        name = src.name
        if name == "venue-matcher":
            raise SystemExit("FATAL: extra skill 'venue-matcher' conflicts with the plugin skill")
        shutil.copytree(src, dest_dir / name, dirs_exist_ok=True)
        staged.append(name)
    return staged


async def run(prompt: str, repo_root: pathlib.Path, extra_skill_paths=None,
              model: str = "claude-sonnet-4-6") -> int:
    from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

    repo_root = pathlib.Path(repo_root)
    stage_extra_skills(extra_skill_paths, repo_root / ".claude" / "skills")

    options = ClaudeAgentOptions(
        cwd=str(repo_root),
        plugins=[{"type": "local", "path": str(repo_root)}],
        setting_sources=["project"],
        allowed_tools=["Bash", "Read", "Glob", "Grep"],
        permission_mode="acceptEdits",
        max_turns=600,
        model=model,
    )
    rc = 0
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            print(message.result or "", flush=True)
            rc = 0 if getattr(message, "subtype", "") == "success" else 1
    return rc
