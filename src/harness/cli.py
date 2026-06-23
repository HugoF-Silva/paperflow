"""Dev harness entry. Parses dev flags, sets the env-only knobs (MAX_RALPH,
MAX_PARALLEL, INNER_MAX_TURNS) that the outer agent must NOT see, builds the
outer agent's prompt with the selected API key and provider model values, and
runs it."""
from __future__ import annotations

import argparse
import asyncio
import os
import pathlib
import sys
import tomllib

from harness import outer_agent

DEFAULT_OUTPUT_DIR = pathlib.Path("/app/src/results")
EXECUTION_LOG_NAME = "_execution.log"


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="academia-perks-harness")
    p.add_argument("--input-dir", "--input_dir", dest="input_dir", type=pathlib.Path)
    p.add_argument("--soon-days", type=int, default=31)
    p.add_argument("--max-ralph", type=int, default=int(os.environ.get("MAX_RALPH", "8")))
    p.add_argument("--max-parallel", default=os.environ.get("MAX_PARALLEL", "1"))          # int-as-str or "auto"
    p.add_argument("--inner-max-turns", type=int, default=int(os.environ.get("INNER_MAX_TURNS", "50")))
    p.add_argument("--extra-skill-paths", action="append", default=[], type=pathlib.Path)
    p.add_argument("--api", choices=outer_agent.API_CHOICES, required=True)
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


def initialize_harness_logs(ns: argparse.Namespace, env=os.environ) -> pathlib.Path | None:
    out_dir = _configured_output_dir(env)
    if out_dir is None:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    execution_log = out_dir / EXECUTION_LOG_NAME
    execution_log.write_text("", encoding="utf-8")
    env[outer_agent.EXECUTION_LOG_ENV] = str(execution_log)
    return execution_log


def main(argv=None) -> int:
    ns = parse_args(argv)
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

    prompt = outer_agent.build_outer_prompt(
        str(ns.input_dir) if ns.input_dir is not None else None,
        ns.soon_days,
        api_keys,
        model,
        ns.repo_root,
    )
    rc = asyncio.run(outer_agent.run(prompt, ns.repo_root, extras, model=model, api=ns.api))
    if rc:
        outer_agent.log_status(f"harness_cli_failed outer_agent_exit_code={rc}")
    else:
        outer_agent.log_status("harness_cli_finish exit_code=0")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
