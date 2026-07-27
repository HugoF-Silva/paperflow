"""Dev harness entry. Parses dev flags, sets the env-only knobs (MAX_RALPH,
MAX_PARALLEL, INNER_MAX_TURNS) that the outer agent must NOT see, builds the
outer agent's prompt with the selected API key and provider model values, and
runs it."""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import os
import pathlib
import sys
import tomllib

from harness import outer_agent

DEFAULT_OUTPUT_DIR = pathlib.Path("/app/src/results")
TODO_CHOICES = outer_agent.TODO_CHOICES


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="academia-perks-harness")
    p.add_argument("--input-dir", "--input_dir", dest="input_dir", type=pathlib.Path)
    p.add_argument("--soon-days", type=int, default=31)
    p.add_argument("--max-ralph", type=int, default=int(os.environ.get("MAX_RALPH", "4")))
    p.add_argument("--max-parallel", default=os.environ.get("MAX_PARALLEL", "auto"))          # int-as-str or "auto"
    p.add_argument("--inner-max-turns", type=int, default=int(os.environ.get("INNER_MAX_TURNS", "50")))
    p.add_argument("--extra-skill-paths", action="append", default=[], type=pathlib.Path)
    p.add_argument("--api", choices=outer_agent.API_CHOICES, required=True)
    p.add_argument("--todo", choices=TODO_CHOICES,
                   default="matcher-and-converter")
    p.add_argument("--chosen-venue")
    p.add_argument("--template-path", type=pathlib.Path)
    p.add_argument("--local-config", type=pathlib.Path,
                   default=pathlib.Path("/app/ops/.paperflow.local.toml"))
    p.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path("/app/src"))
    return p.parse_args(argv)


def read_local_extras(path: pathlib.Path) -> list[pathlib.Path]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return [pathlib.Path(p) for p in data.get("extras", {}).get("paths", [])]


def apply_env(ns: argparse.Namespace, env=os.environ) -> None:
    env["MAX_RALPH"] = str(ns.max_ralph)
    env["MAX_PARALLEL"] = str(ns.max_parallel)
    env["INNER_MAX_TURNS"] = str(max(50, ns.inner_max_turns))


def load_dotenv(path: pathlib.Path, env=os.environ) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env.setdefault(key.strip(), value.strip().strip("'\""))


def required_keys_for_api(api: str) -> list[str]:
    return list(outer_agent.api_config(api).required_keys)


def required_env_for_api(api: str) -> list[str]:
    return outer_agent.required_env_for_api(api)


def _configured_output_dir(env=os.environ) -> pathlib.Path | None:
    raw = env.get("OUTPUT_DIR")
    if raw:
        return pathlib.Path(raw)
    return DEFAULT_OUTPUT_DIR if DEFAULT_OUTPUT_DIR.parent.exists() else None


def _execution_log_name(repo_root: pathlib.Path) -> str:
    skill_root = repo_root / "plugins" / "academia-perks" / "skills"
    for skill_name, script_dir in (("venue-matcher", "venue_matcher"), ("converter", "converter")):
        source = skill_root / skill_name / "scripts" / script_dir / "cli.py"
        if not source.is_file():
            continue
        spec = importlib.util.spec_from_file_location(f"paperflow_{script_dir}_cli", source)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(source.parent))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
        if name := getattr(module, "EXECUTION_LOG_NAME", None):
            return name
    raise RuntimeError("OpenAI plugin execution log filename is unavailable")


def initialize_harness_logs(ns: argparse.Namespace, env=os.environ) -> pathlib.Path | None:
    out_dir = _configured_output_dir(env)
    if out_dir is None:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    execution_log = (out_dir / _execution_log_name(ns.repo_root)).resolve()
    execution_log.write_text("", encoding="utf-8")
    env[outer_agent.EXECUTION_LOG_ENV] = str(execution_log)
    return execution_log


def main(argv=None) -> int:
    ns = parse_args(argv)
    if ns.todo == "converter":
        if ns.api != "openai":
            print("Converter mode is available only with OpenAI.", file=sys.stderr, flush=True)
            return 2
        if (ns.chosen_venue is None) == (ns.template_path is None):
            print(
                "Converter mode requires exactly one of --chosen-venue or --template-path.",
                file=sys.stderr,
                flush=True,
            )
            return 2
    load_dotenv(ns.local_config.with_name(".env"))
    execution_log = initialize_harness_logs(ns)
    outer_agent.log_status(
        f"harness_cli_start api={ns.api} input_dir={ns.input_dir} "
        f"soon_days={ns.soon_days} execution_log={execution_log}"
    )

    required_keys = required_keys_for_api(ns.api)
    missing = [k for k in required_env_for_api(ns.api) if not os.environ.get(k)]
    if missing:
        outer_agent.log_status(
            f"harness_cli_failed reason=missing_env keys={','.join(missing)}"
        )
        print(f"The following environment variables are not set: {', '.join(missing)}",
              file=sys.stderr, flush=True)
        return 2

    apply_env(ns)
    api_keys = {k: os.environ[k] for k in required_keys}
    model = outer_agent.resolve_model(ns.api)
    extras = list(ns.extra_skill_paths) + read_local_extras(ns.local_config)

    input_dir = str(ns.input_dir) if ns.input_dir is not None else None
    if ns.todo == "converter":
        prompt = outer_agent.build_converter_prompt(
            input_dir,
            api_keys,
            model,
            ns.repo_root,
            chosen_venue=ns.chosen_venue,
            template_path=ns.template_path,
        )
    else:
        prompt = outer_agent.build_outer_prompt(
            input_dir,
            ns.soon_days,
            api_keys,
            model,
            ns.repo_root,
        )
    rc = asyncio.run(
        outer_agent.run(
            prompt,
            ns.repo_root,
            extras,
            model=model,
            api=ns.api,
            todo=ns.todo,
        )
    )
    if rc:
        outer_agent.log_status(f"harness_cli_failed outer_agent_exit_code={rc}")
    else:
        outer_agent.log_status("harness_cli_finish exit_code=0")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
