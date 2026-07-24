"""The dev outer agent for Paperflow's venue-matcher and converter skills."""
from __future__ import annotations

import builtins
import ctypes
from dataclasses import dataclass
from datetime import datetime, timezone
import os
import pathlib
import re
import shutil
import subprocess
import sys
import threading


@dataclass(frozen=True)
class ApiConfig:
    required_keys: tuple[str, ...]
    model_env: str
    default_model: str
    plugin_path: pathlib.Path


API_CONFIGS = {
    "anthropic": ApiConfig(
        required_keys=("ANTHROPIC_API_KEY",),
        model_env="ANTHROPIC_MODEL",
        default_model="claude-sonnet-4-6",
        plugin_path=pathlib.Path("plugins") / "academia-perks-claude",
    ),
    "openai": ApiConfig(
        required_keys=("OPENAI_API_KEY",),
        model_env="OPENAI_MODEL",
        default_model="gpt-5.4-mini",
        plugin_path=pathlib.Path("plugins") / "academia-perks-openai",
    ),
}
API_CHOICES = tuple(API_CONFIGS)
TODO_CHOICES = ("matcher-and-converter", "converter")
venue_matcher_model_env = "VENUE_MATCHER_MODEL"
converter_model_env = "CONVERTER_MODEL"
_CONVERTER_EXEC_RULE = (
    "- Launch the converter as `exec env OPENAI_API_KEY='<literal-api-key>' "
    f"{converter_model_env}='<resolved-model>' python ...` so `exec` replaces the "
    "credential-bearing shell; never export these values.\n"
)
_TOOL_OUTPUT_LIMIT = 20_000
_FILE_READ_LIMIT = 500_000
_LOG_POLL_RESULT_LIMIT = 4_000
_MAX_LOGGED_TOOL_LINE_CHARS = 1_000
_AGENT_LOG_REFERENCES = ("_execution.log", "_progress.log", "vm.out")
_AGENT_LOG_LINE_PREFIXES = ("[venue-matcher] ", "[paperflow] ")
_SECRET_ASSIGNMENT_RE = re.compile(
    r'''((?:OPENAI|ANTHROPIC)_API_KEY=)(?:"[^"]*"|'[^']*'|\S+)'''
)
_OPENAI_KEY_RE = re.compile(r"sk-[A-Za-z0-9_\-*]+")


def _set_process_nondumpable(*, platform=sys.platform, prctl=None) -> None:
    if platform != "linux":
        return
    try:
        operation = prctl if prctl is not None else ctypes.CDLL(None, use_errno=True).prctl
        result = operation(4, 0, 0, 0, 0)  # PR_SET_DUMPABLE
    except (AttributeError, OSError) as exc:
        raise RuntimeError("PR_SET_DUMPABLE boundary could not be established") from exc
    if result != 0:
        raise RuntimeError(
            f"PR_SET_DUMPABLE boundary could not be established (errno {ctypes.get_errno()})"
        )


def _format_api_key_value_lines(api_keys: dict[str, str]) -> str:
    values = tuple(value for value in api_keys.values() if value)
    return "\n".join(f"- API key value: {value}" for value in values)


def _outer_execution_guidance(_api_key_names=None) -> str:
    return (
        "Shell/API-key execution rules:\n"
        "- If the venue-matcher skill requires an API key, use the literal API "
        "key value from the task prompt and set the environment variable "
        "required by the loaded venue-matcher skill before running the script.\n"
        "- If the venue-matcher skill requires a model, use the literal model "
        f"value from the task prompt and set `{venue_matcher_model_env}` "
        "before running the script.\n"
        "- Do not pass the API key as a venue-matcher command flag, argument, "
        "or file path.\n"
        "- Do not pass the model as a venue-matcher command flag, argument, "
        "or file path.\n"
        "- Do not print the API key. Avoid echoing commands that contain it.\n"
        "- If a tool, command, authentication, dependency setup, or path step "
        "fails, inspect the returned output and logs, retry in a bounded way "
        "after changing something concrete, and try a practical workaround "
        "before failing with the last error."
    )


def _converter_execution_guidance() -> str:
    return (
        "Shell/API-key execution rules:\n"
        "- Substitute the literal API key and the prompt's resolved model only "
        "in the final launch below.\n"
        f"{_CONVERTER_EXEC_RULE}"
        "- Do not otherwise pass or print the API key or model.\n"
        "- If execution fails, inspect the returned output and logs, then retry "
        "in a bounded way only after changing something concrete."
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


def _append_execution_text(text: str) -> None:
    path = os.environ.get(EXECUTION_LOG_ENV)
    if not path:
        return
    try:
        target = pathlib.Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(text)
            if not text.endswith("\n"):
                fh.write("\n")
    except OSError:
        return


def _emit_agent_output(output) -> None:
    text = str(output or "")
    print(text, flush=True)
    if text:
        _append_execution_text(text)


def _safe_log_text(text: str, limit: int | None = 300, secrets=()) -> str:
    cleaned = text.strip()
    for secret in secrets or ():
        if secret and len(secret) >= 4:
            cleaned = cleaned.replace(secret, "<redacted>")
    cleaned = _SECRET_ASSIGNMENT_RE.sub(r"\1<redacted>", cleaned)
    cleaned = _OPENAI_KEY_RE.sub("sk-<redacted>", cleaned)
    cleaned = " ; ".join(line.strip() for line in cleaned.splitlines() if line.strip())
    return _truncate(cleaned, limit) if limit is not None else cleaned


def _references_agent_log(text: str) -> bool:
    normalized = str(text or "").replace("\\", "/").lower()
    return any(name in normalized for name in _AGENT_LOG_REFERENCES)


def _is_agent_log_line(text: str) -> bool:
    return str(text or "").startswith(_AGENT_LOG_LINE_PREFIXES)


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


def required_env_for_api(api: str) -> list[str]:
    return list(api_config(api).required_keys)


def resolve_model(api: str, env=os.environ) -> str:
    config = api_config(api)
    return env.get(config.model_env) or config.default_model


def resolve_plugin_root(repo_root: pathlib.Path, api: str = "anthropic") -> pathlib.Path:
    return pathlib.Path(repo_root) / api_config(api).plugin_path


def resolve_skill_path(
    repo_root: pathlib.Path,
    api: str = "anthropic",
    skill_name: str = "venue-matcher",
) -> pathlib.Path:
    return resolve_plugin_root(repo_root, api) / "skills" / skill_name / "SKILL.md"


def build_outer_prompt(
    input_dir: str | None,
    soon_days: int,
    api_keys: dict[str, str],
    model: str,
    cwd: pathlib.Path,
) -> str:
    key_values = _format_api_key_value_lines(api_keys)
    input_section = (
        f"Input directory (papers are here): {input_dir}\n"
        if input_dir
        else ""
    )
    missing_papers_instruction = (
        "If the input directory has no papers, say so and stop. "
        if input_dir
        else ""
    )
    return (
        "Use the venue-matcher skill to find publication venues for the papers.\n\n"
        f"Shell/Bash current working directory: {cwd}\n"
        "When using shell, glob, grep, or file tools, paths which aren't relative might not work "
        "use the relative or not, find out what works.\n\n"
        f"{input_section}"
        f"soon-days to pass to the program: {soon_days}\n\n"
        "API configuration for this run:\n"
        f"{key_values}\n"
        f"- Model env var: {venue_matcher_model_env}\n"
        f"- Model value: {model}\n"
        "If the venue-matcher skill requires an API key, use this literal API "
        "key value and set the environment variable required by the loaded "
        "venue-matcher skill. Do not pass the API key as a venue-matcher "
        "command flag. Do not print it. If the venue-matcher skill requires a "
        f"model, set {venue_matcher_model_env} to the model value above; it is "
        "the same model selected for you, the outer agent reading the skill.\n\n"
        f"{_outer_execution_guidance(api_keys)}\n\n"
        "Then follow the skill's patient execution policy: install deps, run "
        "the bundled CLI with --input-dir and --soon-days, wait patiently, and "
        "do not add host-specific polling, tailing, redirection, or monitoring "
        "instructions beyond the skill. Report the ranking.md file, then the full "
        "ranking.md content in the user's preferred language; if the user did "
        "not explicitly state one, use the language the user is already using "
        "with you or asked you to use. If your environment lets you attach or "
        "link local files for download, also provide the ranking.md file for "
        f"download. {missing_papers_instruction}"
        "Pass ONLY --input-dir and --soon-days to the program; never set "
        "MAX_PARALLEL, INNER_MAX_TURNS, or any other environment-variable knob "
        "— those are fixed by the developer and are not yours to change."
    )


def build_converter_prompt(
    input_dir: str | None,
    api_keys: dict[str, str],
    model: str,
    repo_root: pathlib.Path,
    *,
    chosen_venue: str | None,
    template_path: pathlib.Path | None,
) -> str:
    """Build the converter-only user prompt with exactly one conversion source."""
    if (chosen_venue is None) == (template_path is None):
        raise ValueError("converter mode requires exactly one source")
    source = (
        f"chosen_venue: {chosen_venue}"
        if chosen_venue is not None
        else f"template_path: {template_path}"
    )
    return (
        "Use the converter skill to convert the supplied paper.\n\n"
        f"input_dir: {input_dir}\n"
        f"repo_root: {repo_root}\n"
        f"{source}\n\n"
        "API configuration for this run:\n"
        f"{_format_api_key_value_lines(api_keys)}\n"
        f"- converter_model_env: {converter_model_env}\n"
        f"- resolved model: {model}\n"
        "Supply the literal API key and resolved model only in the converter "
        "skill's `exec env ... python` launch. Do not print the API key or pass "
        "it as a command argument.\n\n"
        "Follow the converter skill exactly, including dependency preflight and "
        "patient CLI execution. Pass --input-dir and only the selected source "
        "above. Report the conversion result in the user's preferred language. "
        "Never set MAX_PARALLEL, MAX_RALPH, INNER_MAX_TURNS, or another "
        "developer-owned environment knob."
    )


def _valid_extra_skill_paths(paths) -> list[pathlib.Path]:
    valid: list[pathlib.Path] = []
    for raw in paths or []:
        src = pathlib.Path(raw)
        if not (src / "SKILL.md").exists():
            print(f"warn: extra skill path has no SKILL.md, skipping: {src}", flush=True)
            continue
        name = src.name
        if name in {"venue-matcher", "converter"}:
            raise SystemExit(f"FATAL: extra skill '{name}' conflicts with the plugin skill")
        valid.append(src)
    if valid:
        log_status("outer_agent extra_skills=" + ",".join(src.name for src in valid))
    return valid


def stage_extra_skills(paths, dest_dir: pathlib.Path) -> list[str]:
    """Copy each extra skill dir into dest_dir/<name> (outer agent only). Returns
    the staged skill names. Fatal on a name collision with either plugin skill."""
    dest_dir = pathlib.Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    staged: list[str] = []
    for src in _valid_extra_skill_paths(paths):
        name = src.name
        shutil.copytree(src, dest_dir / name, dirs_exist_ok=True)
        staged.append(name)
    return staged


def build_openai_outer_instructions(
    repo_root: pathlib.Path,
    extra_skill_paths=None,
    todo: str = "matcher-and-converter",
) -> str:
    if todo not in TODO_CHOICES:
        raise ValueError(f"unsupported todo: {todo}")
    preamble = (
        "You are the dev outer agent. Follow the venue-matcher skill and its "
        "converter handoff exactly."
        if todo == "matcher-and-converter"
        else "You are the dev outer agent. Follow only the converter skill; never run venue-matcher."
    )
    guidance = (
        _outer_execution_guidance(("OPENAI_API_KEY",))
        if todo == "matcher-and-converter"
        else _converter_execution_guidance()
    )
    parts = [
        f"{preamble} Use run_shell as the Bash-equivalent tool, and use read_file, "
        f"glob_files, and grep_files for workspace inspection.\n\n{guidance}"
    ]
    for skill_name in ("venue-matcher", "converter"):
        skill_path = resolve_skill_path(repo_root, "openai", skill_name)
        if todo == "converter" and skill_name == "venue-matcher":
            parts.append(
                "Loaded plugin skill: venue-matcher\n"
                f"Path: {skill_path.as_posix()}\n"
                "Status: inactive; operational body omitted"
            )
            continue
        parts.append(
            f"Loaded plugin skill: {skill_name}\n"
            f"Path: {skill_path.as_posix()}\n\n"
            f"{skill_path.read_text(encoding='utf-8')}"
        )
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


def _log_poll_limit(enabled: bool) -> int:
    return _LOG_POLL_RESULT_LIMIT if enabled else _TOOL_OUTPUT_LIMIT


def _request_user_input(question: str, input_fn=None) -> str:
    print(question, flush=True)
    try:
        return (builtins.input if input_fn is None else input_fn)("> ")
    except EOFError as exc:
        raise RuntimeError(
            "User input is unavailable in this non-interactive environment."
        ) from exc


def build_openai_tools(cwd: pathlib.Path, state: dict | None = None):
    from agents import function_tool

    root = pathlib.Path(cwd).resolve()
    tool_env = os.environ.copy()
    state = state if state is not None else {}

    @function_tool
    def run_shell(command: str, timeout_seconds: int = 60) -> str:
        """Run a shell command from the repository root and return stdout/stderr."""
        matcher_command = "venue_matcher/cli.py" in command
        converter_command = "converter/cli.py" in command
        timeout = (
            None
            if matcher_command or converter_command
            else max(1, min(int(timeout_seconds or 60), 600))
        )
        secrets = _api_secret_values(tool_env)
        log_poll = _references_agent_log(command)
        log_status(
            f"tool=run_shell start timeout={'none' if timeout is None else str(timeout) + 's'} "
            f"command={_safe_log_text(command, limit=None, secrets=secrets)}"
        )
        output_lines: list[str] = []
        omitted_logged_agent_lines = 0

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
            nonlocal omitted_logged_agent_lines
            assert proc.stdout is not None
            for line in proc.stdout:
                output_lines.append(line)
                if log_poll:
                    continue
                if _is_agent_log_line(line):
                    omitted_logged_agent_lines += 1
                    continue
                log_status(
                    "tool=run_shell output "
                    + _safe_log_text(
                        line, _MAX_LOGGED_TOOL_LINE_CHARS, _api_secret_values(tool_env)
                    )
                )

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        try:
            returncode = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            returncode = proc.wait()
            reader.join(timeout=5)
            output = "".join(output_lines)
            if log_poll and output:
                log_status(
                    f"tool=run_shell output log_poll_truncated=true stdout_chars={len(output)}"
                )
            if omitted_logged_agent_lines:
                log_status(
                    "tool=run_shell output "
                    f"omitted_logged_agent_lines={omitted_logged_agent_lines}"
                )
            log_status(f"tool=run_shell timeout timeout={timeout}s output_chars={len(output)}")
            return _truncate(
                f"timed out after {timeout}s\n{output}",
                _log_poll_limit(log_poll),
            )
        reader.join(timeout=5)

        output = "".join(output_lines)
        if log_poll and output:
            log_status(
                f"tool=run_shell output log_poll_truncated=true stdout_chars={len(output)}"
            )
        if omitted_logged_agent_lines:
            log_status(
                "tool=run_shell output "
                f"omitted_logged_agent_lines={omitted_logged_agent_lines}"
            )
        if matcher_command:
            state["matcher_exit_code"] = returncode
        if converter_command:
            state["converter_exit_code"] = returncode
        log_status(
            "tool=run_shell finish "
            f"exit_code={returncode} stdout_chars={len(output)} stderr_chars=0"
        )
        chunks = [f"exit_code={returncode}"]
        if output:
            chunks.append("stdout:\n" + output)
        return _truncate("\n".join(chunks), _log_poll_limit(log_poll))

    @function_tool
    def read_file(path: str) -> str:
        """Read a UTF-8 text file inside the repository root."""
        log_status(f"tool=read_file path={_safe_log_text(path, 200)}")
        text = _safe_path(root, path).read_text(encoding="utf-8")
        limit = _LOG_POLL_RESULT_LIMIT if _references_agent_log(path) else _FILE_READ_LIMIT
        return _truncate(text, limit)

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
        log_poll = _references_agent_log(path_glob)
        for path in paths:
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
                rel = path.resolve().relative_to(root).as_posix()
            except (OSError, UnicodeDecodeError, ValueError):
                continue
            log_poll = log_poll or _references_agent_log(rel)
            for number, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    lines.append(f"{rel}:{number}:{line[:300]}")
                    if len(lines) >= 200:
                        return _truncate("\n".join(lines), _log_poll_limit(log_poll))
        return _truncate("\n".join(lines), _log_poll_limit(log_poll))

    @function_tool
    def request_user_input(question: str) -> str:
        """Ask the user one question and return their answer."""
        return _request_user_input(question)

    return [run_shell, read_file, glob_files, grep_files, request_user_input]


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
            _emit_agent_output(message.result)
            rc = 0 if getattr(message, "subtype", "") == "success" else 1
    log_status(f"outer_agent provider=anthropic finish exit_code={rc}")
    return rc


async def _run_openai(prompt: str, repo_root: pathlib.Path, extra_skill_paths,
                      model: str, todo: str = "matcher-and-converter") -> int:
    from agents import Agent, ModelSettings, Runner
    from openai.types.shared import Reasoning

    skill_path = resolve_skill_path(repo_root, "openai")
    tool_state: dict = {}
    log_status(f"outer_agent provider=openai skill={skill_path} model={model}")
    agent = Agent(
        name="paperflow-outer",
        instructions=build_openai_outer_instructions(repo_root, extra_skill_paths, todo),
        model=model,
        model_settings=ModelSettings(reasoning=Reasoning(effort="medium")),
        tools=build_openai_tools(repo_root, tool_state),
    )
    log_status("outer_agent provider=openai start")
    result = await Runner.run(agent, prompt, max_turns=600)
    rc = 0
    for exit_key in ("matcher_exit_code", "converter_exit_code"):
        if stage_rc := int(tool_state.get(exit_key, 0) or 0):
            rc = stage_rc
            break
    log_status(f"outer_agent provider=openai finish exit_code={rc}")
    _emit_agent_output(result.final_output)
    return rc


async def run(prompt: str, repo_root: pathlib.Path, extra_skill_paths=None,
              model: str | None = None,
              api: str = "anthropic",
              todo: str = "matcher-and-converter") -> int:
    if todo not in TODO_CHOICES:
        raise ValueError(f"unsupported todo: {todo}")
    if todo == "converter" and api != "openai":
        raise ValueError("converter mode is available only with OpenAI")
    _set_process_nondumpable()
    repo_root = pathlib.Path(repo_root)
    config = api_config(api)
    selected_model = model or resolve_model(api)
    log_status(
        f"harness_start api={api} model={selected_model} "
        f"repo_root={repo_root} plugin={repo_root / config.plugin_path}"
    )
    if api == "anthropic":
        return await _run_anthropic(prompt, repo_root, extra_skill_paths, selected_model)
    if api == "openai":
        return await _run_openai(prompt, repo_root, extra_skill_paths, selected_model, todo)
    raise ValueError(f"unsupported api: {api}")
