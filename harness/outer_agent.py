"""The dev outer agent: an Agent SDK agent that loads the selected plugin, uses
the venue-matcher skill, and runs the bundled CLI via Bash. API keys are
formatted into its prompt so it can export them before running."""
from __future__ import annotations

from dataclasses import dataclass
import os
import pathlib
import re
import shutil
import subprocess


@dataclass(frozen=True)
class ApiConfig:
    required_keys: tuple[str, ...]
    plugin_path: pathlib.Path
    default_model: str


API_CONFIGS = {
    "anthropic": ApiConfig(
        required_keys=("ANTHROPIC_API_KEY",),
        plugin_path=pathlib.Path("plugins") / "academia-perks-claude",
        default_model="claude-sonnet-4-6",
    ),
    "openai": ApiConfig(
        required_keys=("OPENAI_API_KEY",),
        plugin_path=pathlib.Path("plugins") / "academia-perks-openai",
        default_model="gpt-5.4-mini",
    ),
}
API_CHOICES = tuple(API_CONFIGS)
_TOOL_OUTPUT_LIMIT = 20_000
_FILE_READ_LIMIT = 500_000


def api_config(api: str) -> ApiConfig:
    try:
        return API_CONFIGS[api]
    except KeyError as exc:
        raise ValueError(f"unsupported api: {api}") from exc


def resolve_plugin_root(repo_root: pathlib.Path, api: str = "anthropic") -> pathlib.Path:
    return pathlib.Path(repo_root) / api_config(api).plugin_path


def resolve_skill_path(repo_root: pathlib.Path, api: str = "anthropic") -> pathlib.Path:
    return resolve_plugin_root(repo_root, api) / "skills" / "venue-matcher" / "SKILL.md"


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


def _valid_extra_skill_paths(paths) -> list[pathlib.Path]:
    valid: list[pathlib.Path] = []
    for raw in paths or []:
        src = pathlib.Path(raw)
        if not (src / "SKILL.md").exists():
            print(f"warn: extra skill path has no SKILL.md, skipping: {src}", flush=True)
            continue
        name = src.name
        if name == "venue-matcher":
            raise SystemExit("FATAL: extra skill 'venue-matcher' conflicts with the plugin skill")
        valid.append(src)
    return valid


def stage_extra_skills(paths, dest_dir: pathlib.Path) -> list[str]:
    """Copy each extra skill dir into dest_dir/<name> (outer agent only). Returns
    the staged skill names. Fatal on a name collision with venue-matcher."""
    dest_dir = pathlib.Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    staged: list[str] = []
    for src in _valid_extra_skill_paths(paths):
        name = src.name
        shutil.copytree(src, dest_dir / name, dirs_exist_ok=True)
        staged.append(name)
    return staged


def build_openai_outer_instructions(repo_root: pathlib.Path, extra_skill_paths=None) -> str:
    skill_path = resolve_skill_path(repo_root, "openai")
    skill_text = skill_path.read_text(encoding="utf-8")
    parts = [
        "You are the dev outer agent. Follow the loaded venue-matcher skill exactly. "
        "Use run_shell as the Bash-equivalent tool, and use read_file, glob_files, "
        "and grep_files for workspace inspection.",
        f"Loaded plugin skill: {skill_path.as_posix()}\n\n{skill_text}",
    ]
    for src in _valid_extra_skill_paths(extra_skill_paths):
        parts.append(
            f"Extra outer-agent skill: {src.name}\n\n"
            f"{(src / 'SKILL.md').read_text(encoding='utf-8')}"
        )
    return "\n\n---\n\n".join(parts)


def _safe_path(root: pathlib.Path, raw_path: str) -> pathlib.Path:
    target = (root / raw_path).resolve()
    if not target.is_relative_to(root):
        raise ValueError("path must stay inside the repository root")
    return target


def _truncate(text: str, limit: int = _TOOL_OUTPUT_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"


def build_openai_tools(cwd: pathlib.Path):
    from agents import function_tool

    root = pathlib.Path(cwd).resolve()
    tool_env = os.environ.copy()

    @function_tool
    def run_shell(command: str, timeout_seconds: int = 60) -> str:
        """Run a shell command from the repository root and return stdout/stderr."""
        stripped = command.strip()
        if stripped.startswith("export ") and "\n" not in stripped:
            exported: list[str] = []
            for assignment in stripped.removeprefix("export ").split():
                if "=" not in assignment:
                    return "export requires NAME=value assignments"
                name, value = assignment.split("=", 1)
                tool_env[name] = value.strip("'\"")
                exported.append(name)
            return "exported " + ", ".join(exported)

        timeout = max(1, min(int(timeout_seconds or 60), 600))
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=root,
                env=tool_env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") + (exc.stderr or "")
            return _truncate(f"timed out after {timeout}s\n{output}")

        chunks = [f"exit_code={proc.returncode}"]
        if proc.stdout:
            chunks.append("stdout:\n" + proc.stdout)
        if proc.stderr:
            chunks.append("stderr:\n" + proc.stderr)
        return _truncate("\n".join(chunks))

    @function_tool
    def read_file(path: str) -> str:
        """Read a UTF-8 text file inside the repository root."""
        text = _safe_path(root, path).read_text(encoding="utf-8")
        return _truncate(text, _FILE_READ_LIMIT)

    @function_tool
    def glob_files(pattern: str) -> str:
        """List files matching a repository-relative glob pattern."""
        matches = []
        try:
            paths = root.glob(pattern)
        except ValueError as exc:
            return f"invalid glob pattern: {exc}"
        for match in paths:
            try:
                rel = match.resolve().relative_to(root).as_posix()
            except ValueError:
                continue
            matches.append(rel)
        return "\n".join(sorted(matches)[:500])

    @function_tool
    def grep_files(pattern: str, path_glob: str = "**/*") -> str:
        """Search text files matched by path_glob for a regular expression."""
        try:
            regex = re.compile(pattern)
            paths = root.glob(path_glob)
        except (re.error, ValueError) as exc:
            return f"invalid grep input: {exc}"
        lines: list[str] = []
        for path in paths:
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
                rel = path.resolve().relative_to(root).as_posix()
            except (OSError, UnicodeDecodeError, ValueError):
                continue
            for number, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    lines.append(f"{rel}:{number}:{line[:300]}")
                    if len(lines) >= 200:
                        return "\n".join(lines)
        return "\n".join(lines)

    return [run_shell, read_file, glob_files, grep_files]


async def _run_anthropic(prompt: str, repo_root: pathlib.Path, extra_skill_paths,
                         model: str) -> int:
    from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

    stage_extra_skills(extra_skill_paths, repo_root / ".claude" / "skills")
    plugin_root = resolve_plugin_root(repo_root, "anthropic")

    options = ClaudeAgentOptions(
        cwd=str(repo_root),
        plugins=[{"type": "local", "path": str(plugin_root)}],
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


async def _run_openai(prompt: str, repo_root: pathlib.Path, extra_skill_paths,
                      model: str) -> int:
    from agents import Agent, Runner

    agent = Agent(
        name="venue-matcher-outer",
        instructions=build_openai_outer_instructions(repo_root, extra_skill_paths),
        model=model,
        tools=build_openai_tools(repo_root),
    )
    result = await Runner.run(agent, prompt, max_turns=600)
    print(str(result.final_output or ""), flush=True)
    return 0


async def run(prompt: str, repo_root: pathlib.Path, extra_skill_paths=None,
              model: str | None = None,
              api: str = "anthropic") -> int:
    repo_root = pathlib.Path(repo_root)
    config = api_config(api)
    selected_model = model or config.default_model
    if api == "anthropic":
        return await _run_anthropic(prompt, repo_root, extra_skill_paths, selected_model)
    if api == "openai":
        return await _run_openai(prompt, repo_root, extra_skill_paths, selected_model)
    raise ValueError(f"unsupported api: {api}")
