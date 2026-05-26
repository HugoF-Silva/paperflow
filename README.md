# paperflow

Personal automation tools for academic publishing.

The first one shipped here is **venue-matcher** — find the publication
venue(s) where an academic paper truly belongs.

## What's in this repo

- **`skills/venue-matcher/`** — the skill that drives the matching for a
  single paper. Plugin-shape on disk (distributed later via a plugin).
- **`batch_venue_matcher/`** — a local Python app that processes many
  papers in parallel, one Agent SDK agent per paper, by invoking the
  `/venue-matcher` skill against each.

## Quick start

1. Have Docker (with Compose) installed.
2. Drop your `.docx` papers into `./papers/`.
3. Put your Anthropic API key in `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```
4. Run:
   ```
   make run
   ```

Per-paper rankings land in `./results/<paper-stem>/`:

- `ranking.json` — structured fit ranking, two buckets (`open_now`,
  `opening_soon`), with per-venue rationale
- `ranking.md` — human-readable summary
- `iteration.log` — one line per outer-loop iteration (success or
  failure reason)

Any failed paper appends to `./results/_failures.log` with the
last-iteration reason.

## CLI

```
batch-venue-matcher run \
  --input-dir /work/papers \
  --output-dir /work/results \
  --soon-days 31 \
  --countries BR \
  --max-parallel auto \
  --max-iterations 8 \
  --extra-skills-dir <path>  --extra-skill-name <name>
```

- `--soon-days N` — reject venues whose registration opens after
  `today + N`.
- `--countries CSV` — comma-separated ISO-3166 codes (default `BR`).
- `--max-parallel auto|N` — `auto` derives a safe pool size from free
  CPU and free RAM at startup.
- `--max-iterations N` — hard ceiling on per-paper outer-loop iterations
  (default 8). The loop re-iterates only on deterministic failure
  (missing completion promise, crash, missing/malformed outputs,
  `max_turns` hit). Quality is the agent's job inside one iteration, not
  the loop's.
- `--extra-skills-dir`, `--extra-skill-name` — repeatable; pull only the
  *named* skills from the *searched* dirs. Conflicts (same name in two
  dirs, or collision with `venue-matcher`) abort the run.

Standalone validation:

```
make validate
```

resolves `.paperflow.local.toml` + CLI extras, prints any warnings, and
exits without spawning any agent.

## Local extras (per-machine)

`.paperflow.local.toml` is gitignored; it holds extras to use on your
machine without sharing them in git:

```toml
[extras]
dirs  = ["/home/me/.claude/plugins/marketplaces/.../skills"]
names = ["customer-research"]
```

Both `dirs` and `names` are merged with the CLI flags. The orchestrator
warns on requested names that aren't found anywhere, and aborts on name
conflicts.

## Resource budget

At startup the orchestrator prints exactly how it sized the pool, e.g.:

```
host:    8 CPUs (12% in use), 6.4 GiB RAM free
budget:  80% of free CPU, 70% of free RAM, ≥1 CPU for the OS
result:  5 workers   (cpu=6, mem=5, papers=23, capped_by=mem)
```

If `--max-parallel N` is set, it's an *upper bound* — still clamped by
CPU and memory so the run doesn't tip an already-loaded machine.

## Layout

```
paperflow/
├── pyproject.toml         # python project (top-level)
├── Dockerfile             # batch app image
├── docker-compose.yml
├── Makefile
├── .env.example
├── .paperflow.local.toml.example
├── batch_venue_matcher/   # python package: cli/compose/orchestrator/worker
├── skills/
│   └── venue-matcher/     # the skill (SKILL.md + references/)
├── docs/superpowers/specs/
└── input_examples/        # sample paper for end-to-end testing
```
