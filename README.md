# paperflow - academia-perks-claude and academia-perks-openai plugins

`academia-perks-claude` and `academia-perks-openai` are academic publishing
plugins with separate Claude and Codex/OpenAI payloads. Their first skill,
**venue-matcher**, finds the publication venues a paper belongs to (conferences,
journals, magazines, tracks, workshops), ranked by fit, split into "open now"
and "opening soon".

## Ways to use it

### Layperson (claude.ai)
Toggle the `academia-perks-claude` plugin, set `ANTHROPIC_API_KEY` in your
environment, upload ONE paper, and ask: "use venue-matcher to find a venue for
my paper."
A single paper targets the ~5-minute sandbox limit. More papers run sequentially
and may exceed it — **use one session per paper**. Results are written to
`results/<paper>/ranking.{json,md}`.

### Developer (local, Docker)
Docker Desktop must be open and the Docker engine must be running on your
machine before starting the outer-agent process.

```bash
cp .env.example .env            # put the key for the API you will use in it
cp .paperflow.local.toml.example .paperflow.local.toml
mkdir -p papers && cp /path/to/*.docx papers/
docker compose run --build --rm matcher --api openai
```
The smallest successful command is
`docker compose run --build --rm matcher --api openai` for OpenAI/Codex, or
`docker compose run --build --rm matcher --api anthropic` for Claude. The
provider must be explicit; there is no default. The harness loads
`academia-perks-openai` with `OPENAI_API_KEY` or `academia-perks-claude` with
`ANTHROPIC_API_KEY`. `make run-openai` / `make run-anthropic` are shortcuts for
the same two commands; `make down` runs `docker compose down -v` and
`make prune` runs `docker system prune -f -a --volumes`.

That command starts `python -m harness.cli` inside the `matcher` container. The
harness builds the outer-agent prompt, loads the selected plugin, and starts the
outer agent; the outer agent follows the `venue-matcher` skill and runs the
bundled matcher program. Each harness run resets `./results/_execution.log`
before the outer agent starts; that file mirrors the timestamped harness, tool,
CLI, inner-agent, and batch status stream that also appears in container logs.

This split is intentional: `harness/` is just one possible **outer agent** —
our own dev/Docker implementation of the generic contract described in the
plugin's `SKILL.md`. Any other outer agent (a different harness, a different
host, claude.ai itself) can load the same `academia-perks-*` plugin and must
work correctly without ever having seen our harness code. So the harness only
owns what's genuinely its own — `_execution.log`, the container-scoped record of
the outer-agent/tool/CLI status stream — and never reaches into files owned by
the plugin. `./results/_progress.log` is one such plugin-owned file: only the
matcher (`runner.py`) resets and appends it, on every host, regardless of which
outer agent is driving it. The fact that the matcher writes batch progress there
and signals completion with `BATCH COMPLETE` lives once, in `SKILL.md`, so every
outer agent gets it for free; the harness does not repeat it. Where the harness
does add its own instructions to the outer-agent prompt, it states goals (e.g.
"keep matcher output visible in container logs") rather than host-specific
mechanics, since the agent — not the harness — is responsible for working out
how to satisfy a goal on whatever host it is actually running on.
For Docker Desktop log inspection, omit `--rm` and pass `--name <container-name>`;
the harness and matcher emit timestamped `[paperflow]` / `[venue-matcher]`
status lines to stdout/stderr.
Tunables (dev-only, never visible to the agent): `MAX_PARALLEL` (default 1, or
`auto`), `MAX_RALPH` (default 8), `INNER_MAX_TURNS` (default 50). Set them in
`.env` or the shell.

### Codex (local or repo marketplace)
This repo also contains a Codex/OpenAI plugin copy at
`plugins/academia-perks-openai/`. The repo marketplace
`.agents/plugins/marketplace.json` points at that plugin-only folder, so Codex
installs the plugin payload without the dev harness, tests, Docker files, or
input examples.

For a local checkout, add the repo marketplace and then install the plugin:

```bash
codex plugin marketplace add /path/to/paperflow
codex plugin add academia-perks-openai@paperflow
```

For a published Git repo, use the GitHub shorthand or Git URL instead of the
local path. This makes the plugin available to users who add that marketplace;
it does not publish the plugin to Codex's public OpenAI-curated directory.
The Codex plugin copy uses `OPENAI_API_KEY`, `openai-agents`, and defaults to
`gpt-5.4-mini`; the Claude plugin copy lives at
`plugins/academia-perks-claude/` and uses `ANTHROPIC_API_KEY`.

## How it works
An **outer agent** runs the bundled `venue_matcher` program; the program spawns
**one process per paper**; each process runs a **ralph loop** around a fresh
neurotic **inner agent** that web-searches and ranks venues, carrying a
compacted recap from each pass into the next as its own first "memory". The
Claude copy uses Claude tool names (`Read`, `Write`, `WebSearch`, `WebFetch`);
the Codex copy uses OpenAI Agents SDK web search plus local read/write/fetch
function tools. Targeting is country-only (from the paper; Brazil if unstated).
See `docs/superpowers/specs/2026-06-20-venue-matcher-design.md`.
