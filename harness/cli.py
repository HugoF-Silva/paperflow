"""Dev harness entry. Parses dev flags, sets the env-only knobs (MAX_RALPH,
MAX_PARALLEL, INNER_MAX_TURNS) that the outer agent must NOT see, builds the
outer agent's prompt (with the shared API key), and runs it."""
from __future__ import annotations

import argparse
import asyncio
import os
import pathlib
import sys
import tomllib

from harness import outer_agent


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="academia-perks-harness")
    p.add_argument("--input-dir", type=pathlib.Path, default=pathlib.Path("/work/papers"))
    p.add_argument("--soon-days", type=int, default=31)
    p.add_argument("--max-ralph", type=int, default=int(os.environ.get("MAX_RALPH", "8")))
    p.add_argument("--max-parallel", default=os.environ.get("MAX_PARALLEL", "1"))          # int-as-str or "auto"
    p.add_argument("--inner-max-turns", type=int, default=int(os.environ.get("INNER_MAX_TURNS", "50")))
    p.add_argument("--extra-skill-paths", action="append", default=[], type=pathlib.Path)
    p.add_argument("--api", choices=outer_agent.API_CHOICES, default="anthropic")
    p.add_argument("--local-config", type=pathlib.Path,
                   default=pathlib.Path("/app/.paperflow.local.toml"))
    p.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path("/app"))
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


def main(argv=None) -> int:
    ns = parse_args(argv)
    load_dotenv(ns.repo_root / ".env")

    required_keys = required_keys_for_api(ns.api)
    missing = [k for k in required_keys if not os.environ.get(k)]
    if missing:
        print(f"The following API keys are not set: {', '.join(missing)}",
              file=sys.stderr, flush=True)
        return 2

    apply_env(ns)
    api_keys = {k: os.environ[k] for k in required_keys}
    extras = list(ns.extra_skill_paths) + read_local_extras(ns.local_config)

    prompt = outer_agent.build_outer_prompt(str(ns.input_dir), ns.soon_days, api_keys)
    return asyncio.run(outer_agent.run(prompt, ns.repo_root, extras, api=ns.api))


if __name__ == "__main__":
    raise SystemExit(main())
