# paperflow — academia-perks plugin

`academia-perks` is a Claude plugin for academic publishing. Its first skill,
**venue-matcher**, finds the publication venues a paper belongs to (conferences,
journals, magazines, tracks, workshops), ranked by fit, split into "open now"
and "opening soon".

## Two ways to use it

### Layperson (claude.ai)
Toggle the `academia-perks` plugin, set `ANTHROPIC_API_KEY` in your environment,
upload ONE paper, and ask: "use venue-matcher to find a venue for my paper."
A single paper targets the ~5-minute sandbox limit. More papers run sequentially
and may exceed it — **use one session per paper**. Results are written to
`results/<paper>/ranking.{json,md}`.

### Developer (local, Docker)
```bash
cp .env.example .env            # put your ANTHROPIC_API_KEY in it
mkdir -p papers && cp /path/to/*.docx papers/
make run                        # builds + runs the outer agent over ./papers
```
Per-paper output lands in `./results/<stem>/`. Tunables (dev-only, never visible
to the agent): `MAX_PARALLEL` (default 1, or `auto`), `MAX_RALPH` (default 8),
`INNER_MAX_TURNS` (default 50). Set them in `.env` or the shell.

## How it works
An **outer agent** runs the bundled `venue_matcher` program; the program spawns
**one process per paper**; each process runs a **ralph loop** around a fresh
neurotic **inner agent** (tools: Read/Write/WebSearch/WebFetch) that web-searches
and ranks venues, carrying a compacted recap from each pass into the next as its
own first "memory". Targeting is country-only (from the paper; Brazil if
unstated). See `docs/superpowers/specs/2026-06-20-venue-matcher-design.md`.
