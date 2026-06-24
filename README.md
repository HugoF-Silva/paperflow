# paperflow - academia-perks-claude and academia-perks-openai plugins

`academia-perks-claude` and `academia-perks-openai` are academic publishing
plugins with separate Claude and Codex/OpenAI payloads. Their first skill,
**venue-matcher**, finds the publication venues a paper belongs to (conferences,
journals, magazines, tracks, workshops), ranked by fit, split into "open now"
and "opening soon".

## Ways to use it

### Layperson (claude.ai)
Toggle the `academia-perks-claude` plugin, upload ONE paper, ask "use
venue-matcher to find a venue for my paper", and provide the API key value if
the skill asks for it.
A single paper targets the ~5-minute sandbox limit. More papers run sequentially
and may exceed it — **use one session per paper**. Results are written to
`results/<paper>/ranking.{json,md}`.

### Developer (local, Docker)
Docker Desktop must be open and the Docker engine must be running on your
machine before starting the outer-agent process.

```bash
cp ops/.env.example ops/.env    # put the key for the API you will use in it
cp ops/.paperflow.local.toml.example ops/.paperflow.local.toml
# put, copy, symlink, or mount .docx files under ./src/papers
make -C ops run-openai
```
The smallest developer command is `make -C ops run-openai` for
OpenAI/Codex, or `make -C ops run-anthropic` for Claude. The provider
must be explicit; there is no default. The Make shortcuts always use the host
`./src/papers` folder. If your papers live elsewhere, put them there by copy,
symlink, junction, or host mount. Runtime code and I/O live under `src/`; Docker
Compose mounts the whole `./src` tree at `/app/src` so the container tree mirrors
the host, and passes `/app/src/papers` as the input dir through
`ops/docker-compose.yml`. Operational files (`ops/docker-compose.yml`,
`ops/Makefile`, `ops/Dockerfile`, `ops/.env`,
`ops/.paperflow.local.toml`) live under `ops/` at the repo root. Compose injects
the local operational config into the container under `/app/ops/`, read-only; the
container — and the agent inside it — still only sees `src/` plus that named
operational config directory. There is no
`INPUT_DIR` make variable to set. The harness loads
`academia-perks-openai` with `OPENAI_API_KEY` or `academia-perks-claude` with
`ANTHROPIC_API_KEY`. It uses `OPENAI_MODEL` for `run-openai` or
`ANTHROPIC_MODEL` for `run-anthropic` when set; otherwise it falls back to
`gpt-5.4-mini` or `claude-sonnet-4-6`. `make -C ops down`
runs `docker compose down -v` and `make -C ops prune` runs
`docker system prune -f -a --volumes`.

That command starts `python -m harness.cli` inside the `matcher` container. The
harness builds the outer-agent prompt, loads the selected plugin, and starts the
outer agent; the outer agent follows the `venue-matcher` skill and runs the
bundled matcher program. The prompt includes the selected API key and model
values; the loaded skill decides whether to set `OPENAI_API_KEY` or
`ANTHROPIC_API_KEY`, and sets `VENUE_MATCHER_MODEL`, before running the matcher.
Each harness run resets `./src/results/_execution.log`
before the outer agent starts; that file mirrors the timestamped harness, tool,
CLI, inner-agent, and batch status stream, plus the final outer-agent response,
that also appears in container logs.
The matcher consumes only `.docx` files from the selected input directory and
ignores other file types.

This split is intentional: `harness/` is just one possible **outer agent** —
our own dev/Docker implementation of the generic contract described in the
plugin's `SKILL.md`. Any other outer agent (a different harness, a different
host, claude.ai itself) can load the same `academia-perks-*` plugin and must
work correctly without ever having seen our harness code. So the harness only
owns what's genuinely its own — `_execution.log`, the container-scoped record of
the outer-agent/tool/CLI status stream — and never reaches into files owned by
the plugin. `./src/results/_progress.log` is one such plugin-owned file: only the
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
Required harness env: the selected provider API key: `OPENAI_API_KEY` for
OpenAI/Codex, or `ANTHROPIC_API_KEY` for Claude. Optional model overrides are
`OPENAI_MODEL` and `ANTHROPIC_MODEL`; defaults live in the harness config. The
outer agent passes the resolved model to the inner matcher as
`VENUE_MATCHER_MODEL`. Tunables (dev-only, never visible to the agent):
`MAX_PARALLEL` (default 1, or `auto`), `MAX_RALPH` (default 8),
`INNER_MAX_TURNS` (default 50). Set them in `ops/.env` or the shell.

### Codex (local or repo marketplace)
This repo also contains a Codex/OpenAI plugin copy at
`src/plugins/academia-perks-openai/`. The repo marketplace
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
The Codex plugin copy sets the provided API key value as `OPENAI_API_KEY`, uses
`openai-agents`; the Claude plugin copy lives at
`src/plugins/academia-perks-claude/` and sets the provided API key value as
`ANTHROPIC_API_KEY`. In both copies, the outer agent sets `VENUE_MATCHER_MODEL`
for the inner matcher, using a model that matches the provider/runtime of the
agent reading the skill.

## How it works
An **outer agent** runs the bundled `venue_matcher` program; the program spawns
**one process per paper**; each process runs a **ralph loop** around a fresh
neurotic **inner agent** that web-searches and ranks venues, carrying a
compacted recap from each pass into the next as its own first "memory". The
Claude copy uses Claude tool names (`Read`, `Write`, `WebSearch`, `WebFetch`);
the Codex copy uses OpenAI Agents SDK web search plus local read/write/fetch
function tools. Targeting is country-only (from the paper; Brazil if unstated).
The inner agent uses the target country's mother language for web-search terms
so local venue pages surface, but language is not a venue filter or ranking
factor. The inner artifacts are written in Brazilian Portuguese (`ranking.json`
keeps English keys); the outer agent reports the full ranking.md content in the
user's preferred language, defaulting to the language the user is already using,
and provides the `ranking.md` file for download when its environment supports
file attachments or links.
See `docs/superpowers/specs/2026-06-20-venue-matcher-design.md`.
