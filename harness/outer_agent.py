"""The dev outer agent: an Agent SDK agent that loads the selected plugin, uses
the venue-matcher skill, and runs the bundled CLI via Bash. API keys are kept
in the inherited environment, not formatted into prompts or shell commands."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
import pathlib
import re
import shutil
import subprocess
import threading


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
_MAX_LOGGED_TOOL_LINES = 200
_MAX_LOGGED_TOOL_LINE_CHARS = 1_000
_SECRET_ASSIGNMENT_RE = re.compile(r"((?:OPENAI|ANTHROPIC)_API_KEY=)(\S+)")
_OPENAI_KEY_RE = re.compile(r"sk-[A-Za-z0-9_\-*]+")


def _outer_execution_guidance(api_key_names) -> str:
    key_names = tuple(api_key_names) or ("API_KEY",)
    malformed = " or ".join(f"`{name}=... cd ...`" for name in key_names)
    listed = ", ".join(key_names)
    return (
        "Shell/API-key execution rules:\n"
        f"- The selected provider key is already available in the inherited "
        f"environment as {listed}. Do not print, export, or reassign API keys; "
        "run commands directly.\n"
        f"- Do not prefix commands with one-command assignments like {malformed}; "
        "do not include API-key values in commands.\n"
        "- If a tool, command, authentication, dependency setup, or path step "
        "fails, inspect the returned output and logs, retry in a bounded way "
        "after changing something concrete, and try a practical workaround "
        "before failing with the last error."
    )


EXECUTION_LOG_ENV = "PAPERFLOW_EXECUTION_LOG"


def log_status(message: str) -> None:
    stamp = datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="seconds")
    line = f"[paperflow] {stamp} {message}"
    print(line, flush=True)
    _append_execution_log(line)


def _append_execution_log(line: str) -> None:
    path = os.environ.get(EXECUTION_LOG_ENV)
    if not path:
        return
    try:
        target = pathlib.Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        return


def _safe_log_text(text: str, limit: int = 300, secrets=()) -> str:
    cleaned = text.strip()
    for secret in secrets or ():
        if secret and len(secret) >= 4:
            cleaned = cleaned.replace(secret, "<redacted>")
    cleaned = _SECRET_ASSIGNMENT_RE.sub(r"\1<redacted>", cleaned)
    cleaned = _OPENAI_KEY_RE.sub("sk-<redacted>", cleaned)
    cleaned = " ; ".join(line.strip() for line in cleaned.splitlines() if line.strip())
    return _truncate(cleaned, limit)


def _api_secret_values(env: dict[str, str]) -> list[str]:
    return [
        value for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
        if (value := env.get(key))
    ]


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
    keys = "\n".join(f"- {k}" for k in api_keys)
    return (
        "Use the venue-matcher skill to find publication venues for the papers.\n\n"
        f"Input directory (papers are here): {input_dir}\n"
        f"soon-days to pass to the program: {soon_days}\n\n"
        "The selected provider API key is already available in the inherited "
        "environment:\n"
        f"{keys}\n\n"
        f"{_outer_execution_guidance(api_keys)}\n\n"
        "Then follow the skill: install deps, run the bundled CLI in the "
        "foreground with --input-dir and --soon-days and a long timeout so its "
        "stdout/stderr stream to container logs. Do not redirect matcher output "
        "away from stdout/stderr. Report the result files "
        "plus a human-friendly summary. If the input directory has no papers, say so and stop. "
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
    if valid:
        log_status("outer_agent extra_skills=" + ",".join(src.name for src in valid))
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
        "and grep_files for workspace inspection.\n\n"
        f"{_outer_execution_guidance(('OPENAI_API_KEY',))}",
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


def build_openai_tools(cwd: pathlib.Path, state: dict | None = None):
    from agents import function_tool

    root = pathlib.Path(cwd).resolve()
    tool_env = os.environ.copy()
    state = state if state is not None else {}

    @function_tool
    def run_shell(command: str, timeout_seconds: int = 60) -> str:
        """Run a shell command from the repository root and return stdout/stderr."""
        timeout = max(1, min(int(timeout_seconds or 60), 600))
        secrets = _api_secret_values(tool_env)
        log_status(
            f"tool=run_shell start timeout={timeout}s "
            f"command={_safe_log_text(command, secrets=secrets)}"
        )
        output_lines: list[str] = []
        logged_lines = 0

        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=root,
            env=tool_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        def read_output() -> None:
            nonlocal logged_lines
            assert proc.stdout is not None
            for line in proc.stdout:
                output_lines.append(line)
                if logged_lines < _MAX_LOGGED_TOOL_LINES:
                    log_status(
                        "tool=run_shell output "
                        + _safe_log_text(
                            line, _MAX_LOGGED_TOOL_LINE_CHARS, _api_secret_values(tool_env)
                        )
                    )
                elif logged_lines == _MAX_LOGGED_TOOL_LINES:
                    log_status("tool=run_shell output omitted_more_lines=true")
                logged_lines += 1

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        try:
            returncode = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            returncode = proc.wait()
            reader.join(timeout=5)
            output = "".join(output_lines)
            log_status(f"tool=run_shell timeout timeout={timeout}s output_chars={len(output)}")
            return _truncate(f"timed out after {timeout}s\n{output}")
        reader.join(timeout=5)

        output = "".join(output_lines)
        if "venue_matcher/cli.py" in command:
            state["matcher_exit_code"] = returncode
        log_status(
            "tool=run_shell finish "
            f"exit_code={returncode} stdout_chars={len(output)} stderr_chars=0"
        )
        chunks = [f"exit_code={returncode}"]
        if output:
            chunks.append("stdout:\n" + output)
        return _truncate("\n".join(chunks))

    @function_tool
    def read_file(path: str) -> str:
        """Read a UTF-8 text file inside the repository root."""
        log_status(f"tool=read_file path={_safe_log_text(path, 200)}")
        text = _safe_path(root, path).read_text(encoding="utf-8")
        return _truncate(text, _FILE_READ_LIMIT)

    @function_tool
    def glob_files(pattern: str) -> str:
        """List files matching a repository-relative glob pattern."""
        log_status(f"tool=glob_files pattern={_safe_log_text(pattern, 200)}")
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
        log_status(
            "tool=grep_files "
            f"pattern={_safe_log_text(pattern, 200)} path_glob={_safe_log_text(path_glob, 200)}"
        )
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
    log_status(f"outer_agent provider=anthropic plugin={plugin_root} model={model}")

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
    log_status("outer_agent provider=anthropic start")
    async for message in query(prompt=prompt, options=options):
        log_status(f"outer_agent provider=anthropic event={type(message).__name__}")
        if isinstance(message, ResultMessage):
            print(message.result or "", flush=True)
            rc = 0 if getattr(message, "subtype", "") == "success" else 1
    log_status(f"outer_agent provider=anthropic finish exit_code={rc}")
    return rc


async def _run_openai(prompt: str, repo_root: pathlib.Path, extra_skill_paths,
                      model: str) -> int:
    from agents import Agent, ModelSettings, Runner
    from openai.types.shared import Reasoning

    skill_path = resolve_skill_path(repo_root, "openai")
    tool_state: dict = {}
    log_status(f"outer_agent provider=openai skill={skill_path} model={model}")
    agent = Agent(
        name="venue-matcher-outer",
        instructions=build_openai_outer_instructions(repo_root, extra_skill_paths),
        model=model,
        model_settings=ModelSettings(reasoning=Reasoning(effort="high")),
        tools=build_openai_tools(repo_root, tool_state),
    )
    log_status("outer_agent provider=openai start")
    result = await Runner.run(agent, prompt, max_turns=600)
    rc = int(tool_state.get("matcher_exit_code", 0) or 0)
    log_status(f"outer_agent provider=openai finish exit_code={rc}")
    print(str(result.final_output or ""), flush=True)
    return rc


async def run(prompt: str, repo_root: pathlib.Path, extra_skill_paths=None,
              model: str | None = None,
              api: str = "anthropic") -> int:
    repo_root = pathlib.Path(repo_root)
    config = api_config(api)
    selected_model = model or config.default_model
    log_status(
        f"harness_start api={api} model={selected_model} "
        f"repo_root={repo_root} plugin={repo_root / config.plugin_path}"
    )
    if api == "anthropic":
        return await _run_anthropic(prompt, repo_root, extra_skill_paths, selected_model)
    if api == "openai":
        return await _run_openai(prompt, repo_root, extra_skill_paths, selected_model)
    raise ValueError(f"unsupported api: {api}")
