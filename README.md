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
```bash
cp .env.example .env            # put the key for the API you will use in it
mkdir -p papers && cp /path/to/*.docx papers/
make run                        # defaults to --api anthropic
docker compose run --rm matcher --input-dir /work/papers --soon-days 31 --api openai
```
The dev harness accepts `--api anthropic` or `--api openai`, loading
`academia-perks-claude` with `ANTHROPIC_API_KEY` or `academia-perks-openai`
with `OPENAI_API_KEY`. Each matcher run resets `./results/_progress.log` and
replaces output for the paper stems in that run under `./results/<stem>/`.
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
