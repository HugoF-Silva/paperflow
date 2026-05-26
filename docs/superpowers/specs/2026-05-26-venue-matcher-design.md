# venue-matcher — design

**Date:** 2026-05-26
**Owner:** Hugo Fernandes (hugo.fernandes@discente.ufg.br)
**Status:** Draft for review

## 1. Purpose

For a given academic paper (`.docx`), produce a ranked list of publication venues
the paper truly belongs to, separated into two buckets:

- **Open now** — accepting submissions today
- **Opening soon** — registration opens within `now + soon_days` (default 31)

The system has two artifacts:

1. **A shareable skill** (`skills/venue-matcher/`) that drives the matching of a
   single paper. Plugin-shaped on disk so it can be packaged and distributed later.
2. **A local-only batch app** (`batch_venue_matcher/`) that processes many papers
   in parallel by spawning per-paper Agent SDK agents that invoke the same skill.

The skill is the "brain"; the batch app is "industrial scale" on top of it.

## 2. Non-goals

- **No plugin distribution in this scope.** The repo is laid out plugin-ready,
  but `.claude-plugin/plugin.json` is intentionally **not** added yet.
- **No template adaptation.** A separate (future) repo handles formatting the paper
  to a venue's template.
- **No web UI.** Batch app is CLI-only.
- **No within-iteration quality polishing across outer loops.** The agent's
  neuroticism *inside* a single iteration is the quality bar; outer iterations
  exist only to recover from clear failures (see §8).

## 3. Inputs and parameters

| Parameter | Default | Notes |
|---|---|---|
| paper input | required | `.docx` (PT-BR or EN content) |
| `soon_days` | `31` | Registration opens after `today + soon_days` is "too far" — ruled out |
| `countries` | `["BR"]` | Comma-separated ISO-3166 codes; English-accepting non-BR venues still bonus-scored |
| `extra_skills_dir` | `[]` | Additional skill directories staged into `.claude/skills/` (repeatable) |
| `max_parallel` | `auto` | Worker pool size; `auto` uses available-resource sizing (see §7) |
| `max_iterations` | `8` | Hard safety net for the outer ralph-loop |
| `per_worker_mb` | `800` | Conservative memory estimate per worker, for pool sizing |

## 4. Repository layout

```
paperflow/
├── skills/                            # canonical skill location (plugin-shape, in git)
│   └── venue-matcher/
│       ├── SKILL.md                   # 1500–2000 words, neurotic-curator guidance
│       └── references/
│           ├── search-paranoia.md     # what counts as obsessive vs. lazy search
│           ├── venue-anatomy.md       # what to extract from a venue's CFP page
│           └── brazilian-ecosystems.md# SBC, RBIE, SBPO, Embrapii, IEEE LATAM, etc.
├── batch_venue_matcher/               # local Agent SDK app
│   ├── pyproject.toml
│   ├── README.md
│   └── src/batch_venue_matcher/
│       ├── __init__.py
│       ├── cli.py                     # argparse / typer entrypoint
│       ├── orchestrator.py            # multiprocessing pool, sizing, failure log
│       ├── worker.py                  # per-paper SDK agent + ralph-style outer loop
│       ├── skill_staging.py           # idempotent copy of skills/ → .claude/skills/
│       ├── resources.py               # CPU/memory probing for pool sizing
│       └── docx.py                    # docx → plain text (python-docx)
├── .claude/                           # gitignored runtime staging area
│   └── skills/                        #   ← runtime copy of ../skills/
├── docs/
│   └── superpowers/specs/             # design specs
├── input_examples/                    # already exists
├── .gitignore                         # ignores .claude/, results/, .runtime/, build artifacts
├── CLAUDE.md
└── README.md
```

### Source-of-truth strategy

- **In git:** `skills/venue-matcher/` (plugin-shape; the artifact teammates will
  eventually install via plugin).
- **At runtime:** `batch_venue_matcher` copies `skills/*` → `.claude/skills/*`
  before launching workers. The copy is idempotent (replaces, doesn't append).
- `.claude/` is gitignored.

This dual location keeps a single source of truth in git while satisfying the
Agent SDK's hardcoded skill-discovery path (`.claude/skills/`). When we later
add `.claude-plugin/plugin.json` to distribute as a plugin, the canonical
`skills/` dir is already in the right place.

## 5. The skill: `skills/venue-matcher/SKILL.md`

### 5.1 Frontmatter

```yaml
---
name: venue-matcher
description: Find the publication venue(s) where a given academic paper truly belongs. Reads the paper, runs deep judgmental web search, fetches and reads each candidate venue's CFP, and returns a fit-ranked output split into "open now" and "opening soon" buckets. Use only when explicitly invoked via /venue-matcher <paper-path>.
disable-model-invocation: true     # never auto-triggers; user-only
user-invocable: true               # default; triggered via /venue-matcher
---
```

`disable-model-invocation: true` keeps this skill out of the model's
auto-invocation surface — it does not pollute attention for unrelated agent work.
The only way to trigger it is the explicit `/venue-matcher` slash command.

### 5.2 Body outline (imperative, neurotic-curator tone)

1. **Mindset** — the agent is a paranoid curator. The search is oriented from
   query one toward *recognition of fit*. No counts, no quotas.
2. **Inputs** — paper path, plus optional flags from `$ARGUMENTS`:
   `--soon-days`, `--countries`, `--out`.
3. **Stage A — Read the paper.** Extract title, abstract, contribution, methods,
   real-world application, language(s). Write a one-paragraph "what this paper
   IS, what it ISN'T" statement to working notes.
4. **Stage B — Discover candidate venues.** Spawn 2–4 parallel `Explore`
   subagents, each with a *narrow* angle (niche keyword + country, broader
   keyword + country, language-targeted, conference/journal/magazine/track).
   Subagents return URL lists, never verdicts.
5. **Stage C — Read every candidate.** For each URL, `WebFetch` the CFP/about
   page. Extract: accepted topics, audience, constraints, registration deadline,
   language(s), country, indexing. Compare against the paper's IS/ISN'T
   statement. Decide: real candidate, weak candidate, or ruled out. Write
   rationale. **Search snippets are never sufficient.**
6. **Stage D — Bucket and rank.** Split survivors into `open_now` and
   `opening_soon` (registration deadline within `now + soon_days`). Rank by fit
   DESC within each bucket. Tie-breaks: language match → country match → niche
   specificity → "vibes" (allowed, but must include a one-line reason).
7. **Stage E — Recognize the fit.** Keep weighing "is this where the paper
   belongs?" If recognition arrives early, stop. If after thorough searching
   nothing strongly clicks, return the closest survivors with an honest note;
   **never come back empty-handed**, but **never embellish a weak fit**.
8. **Output contract** — write `ranking.json` and `ranking.md` to the path
   given by `--out=`. Then emit exactly `<promise>VENUE-MATCH-COMPLETE</promise>`
   in the final assistant message.

### 5.3 References (progressive disclosure)

- **`references/search-paranoia.md`** — concrete examples of lazy-vs-obsessive
  search so the agent can self-detect laziness.
- **`references/venue-anatomy.md`** — the exact fields to extract from a venue's
  site, and what to do when fields are ambiguous (especially deadlines).
- **`references/brazilian-ecosystems.md`** — starting map of major BR venues
  across CS/IT: SBC portfolio (SBES, SBBD, SBIE, SBSI, …), IEEE LATAM, RBIE,
  REIT, SBPO, Embrapii's publication channels, magazines like *Computação
  Brasil*, etc.

## 6. The batch app: `batch_venue_matcher/`

### 6.1 CLI

```
batch-venue-matcher \
  --input-dir ./papers/ \
  --output-dir ./results/ \
  --soon-days 31 \
  --countries BR \
  --max-parallel auto \
  --max-iterations 8 \
  --per-worker-mb 800 \
  --extra-skills-dir /some/external/path     # repeatable
  --keep-runtime                              # debug: do not clean .runtime/
```

### 6.2 Startup flow

1. Validate inputs; discover papers in `--input-dir` (`.docx` only for now).
2. Probe machine resources (see §7), choose worker count, **print the math**.
3. **Stage skills.** Copy `skills/*` → `.claude/skills/*` (idempotent). For each
   `--extra-skills-dir`, copy its contents into `.claude/skills/` too. Conflicts
   on the same skill name: extra dirs win, then warn.
4. Initialize the multiprocessing pool.
5. For each paper, dispatch one worker job.

### 6.3 Per-worker pipeline (one paper)

1. Convert `.docx` to plain text via `docx.py` (python-docx). Write to
   `.runtime/<paper-stem>/paper.txt`.
2. Compose user prompt:
   ```
   /venue-matcher <abs-path-to-paper.txt> --soon-days=<N> --countries=<list> --out=<results/<paper-stem>/>
   ```
3. Invoke SDK with the lean system prompt (§6.4) and run a streaming `query()`.
4. After the stream ends, check for the completion promise and the expected
   output files. Outer-loop decision is in §8.
5. On success or exhausted iterations: write a one-line summary to
   `results/<paper-stem>/iteration.log`. Cleanup `.runtime/<paper-stem>/`
   unless `--keep-runtime` is set.

### 6.4 SDK call (per worker)

```python
options = ClaudeAgentOptions(
    cwd="<repo>",
    setting_sources=["project"],            # discovers .claude/skills/
    skills=["venue-matcher"],               # filter to just this one
    allowed_tools=[
        "Read","Write","Bash","Glob","Grep",
        "WebSearch","WebFetch","Agent",
    ],
    system_prompt=(
        "You are a venue-matching agent. Your only job is to find the "
        "publication venue(s) where a specific academic paper truly belongs.\n\n"
        "The user will invoke /venue-matcher with a paper path. Follow that "
        "skill with neurotic care: read the paper, read each candidate venue's "
        "actual CFP, and orient the entire search around recognizing fit — not "
        "toward filling a quota or counter.\n\n"
        "You stop when you recognize the venue(s) the paper genuinely belongs "
        "to, however few or many venues that took. When you have, emit exactly:\n"
        "<promise>VENUE-MATCH-COMPLETE</promise>\nin your final message.\n\n"
        "You may use subagents (Agent tool) to parallelize narrow-angle searches. "
        "WebFetch is required for any venue you intend to include — search "
        "snippets are never sufficient."
    ),
    max_turns=80,
)
```

Notes:
- **No `claude_code` preset.** That preset bloats context with code-editing
  guidance unrelated to our task.
- **`allowed-tools` in SKILL.md is ignored by the SDK** (per docs); tool access
  is controlled here, in `allowed_tools`.

## 7. Resource-aware concurrency

The pool size is determined at startup from **actually-available** resources
(not totals), with a conservative margin so the run doesn't tip an already-busy
machine into OOM or thrash.

```python
cpu_count   = os.cpu_count()
cpu_used    = psutil.cpu_percent(interval=1.0)             # measured, not assumed
cpu_free    = max(0, cpu_count * (1 - cpu_used/100))
cpu_workers = max(1, int(cpu_free * 0.8) - 1)              # 80% of free, leave 1 CPU

mem_free    = psutil.virtual_memory().available            # bytes currently free
mem_workers = max(1, int(mem_free * 0.7 // (per_worker_mb * 1024 * 1024)))

pool_size   = min(num_papers, cpu_workers, mem_workers, user_override_or_inf)
```

The CLI **prints the chosen size and the math**:

```
host:    8 CPUs (12% in use right now), 16.0 GiB RAM (6.4 GiB free)
budget:  80% of free CPU, 70% of free RAM, leave ≥1 CPU for the OS
result:  5 workers   (capped by: mem=5, cpu=6, papers=23)
queue:   23 papers → 5 in parallel, ~4 batches
```

If `--max-parallel N` is passed, it is treated as an **upper bound** and is
still clamped by `cpu_workers` and `mem_workers` — we never overcommit, even if
the user explicitly asks. A clamp emits a warning.

### Multiprocessing, not threading

Python's GIL prevents true CPU parallelism for the SDK call's
JSON-parsing/streaming work. We use `multiprocessing.Pool` (or
`concurrent.futures.ProcessPoolExecutor`) with a `spawn` start method for
portability and predictability.

## 8. Outer-loop iteration (failure recovery only)

The orchestrator re-invokes the SDK for the same paper **only on clear,
deterministic failure**:

1. The final assistant message does not contain
   `<promise>VENUE-MATCH-COMPLETE</promise>`.
2. The SDK process exited with an error or crashed.
3. Expected output files (`ranking.json`, `ranking.md`) are missing or the JSON
   doesn't parse.
4. `max_turns` ran out before the promise was emitted.

On any of those, the orchestrator re-runs the **same** user prompt. Between
iterations, the agent's prior scratch (notes, partial rankings, fetched
content) persists under `results/<paper-stem>/notes/iter-N/`, so the next
iteration's agent has its previous self's work as feedstock when it starts.
We do **not** iterate to chase subjective ranking improvements — quality is
the responsibility of the agent's intra-iteration neuroticism, not the outer
loop.

When `max_iterations` is exhausted, the orchestrator persists whatever artifacts
exist, appends `<paper-stem>` to `results/_failures.log` with a reason, and
moves on. The batch run continues; one failed paper doesn't fail the run.

### Why this differs from canonical ralph-loop

Ralph-loop's "iterate until promise" pattern shines when each iteration *builds
something* the next iteration can polish (code, tests). Our task is web search;
"building" only happens within a single iteration through careful reading. So
we adopt ralph-loop's three primitives — **persistent scratch on disk**,
**completion promise**, **max-iterations safety** — but reject its
"keep-iterating-for-quality" instinct. The loop is purely a failure-recovery
mechanism here.

## 9. Done criterion (judgment-based, no counts)

The skill body instructs the agent to stop on **recognition**, not on a
threshold. The completion promise marks recognition. There is no minimum or
maximum number of venues to consult.

In the skill body:

> Keep searching until you recognize — viscerally, the way a reviewer would —
> that you've found the venue this paper belongs to. That recognition might
> land after one venue or after fifty. Do not count. Do not stop because you've
> "seen enough." Stop because *this is it*. If after honest, thorough searching
> nothing strongly clicks, name the closest survivors and say so plainly; never
> return empty-handed, but never embellish a weak fit.

## 10. Output contract

### 10.1 Per-paper directory

```
results/<paper-stem>/
├── ranking.json          # structured, machine-readable
├── ranking.md            # human-readable summary + per-venue rationale
├── iteration.log         # one line per outer-loop iteration with outcome
└── notes/
    └── iter-1/           # agent scratchpad from iteration 1
        ├── paper-statement.md
        ├── candidates.jsonl
        └── fetched/      # cached WebFetch content (optional)
```

### 10.2 `ranking.json` shape

```json
{
  "paper": {
    "path": "input_examples/Foo.docx",
    "language": "pt-BR",
    "is_statement": "…",
    "isnt_statement": "…"
  },
  "params": {
    "soon_days": 31,
    "countries": ["BR"],
    "as_of": "2026-05-26T14:30:00-03:00"
  },
  "open_now": [
    {
      "rank": 1,
      "name": "SBSI 2026",
      "kind": "conference|journal|magazine|track|workshop",
      "url": "https://…",
      "country": "BR",
      "languages": ["pt-BR","en"],
      "deadline": "2026-06-15",
      "topics_matched": ["IS in industry","applied AI"],
      "rationale": "Paragraph explaining why this is the fit and what about the paper specifically lands here."
    }
  ],
  "opening_soon": [ /* same shape; deadline > today+soon_days excluded */ ],
  "closest_misses": [
    /* venues considered seriously but ruled out, with reason */
  ],
  "agent_notes": "free-form short summary from the agent, including any tie-break vibes-rationale"
}
```

### 10.3 Failures aggregate

`results/_failures.log` — one line per failed paper:
```
2026-05-26T14:35:11  Foo.docx  iterations_exhausted  last_reason=no_promise_in_final_message
```

## 11. Distribution plan

### Today (in scope)
- `skills/venue-matcher/` exists in this repo.
- `batch_venue_matcher/` consumes it locally via runtime staging.
- Nothing is published. No `.claude-plugin/plugin.json`.

### Later (out of scope here, but path is preserved)
- Add `.claude-plugin/plugin.json` to publish as a plugin.
- Teammates run `/plugin install paperflow@<source>`; the skill becomes
  available as `/paperflow:venue-matcher` in their Claude Code.
- The repo will also document the local batch app for power users who clone.

## 12. Open questions

None that block writing the implementation plan. The two questions deferred to
implementation:

- Whether `docx.py` should pre-translate non-EN papers or just pass-through
  (currently pass-through; the agent reads PT-BR fine and the venue-matching is
  about content, not surface form).
- Exact subagent count in Stage B (2–4 currently); we'll tune during the first
  real runs against `input_examples/`.

## 13. Verification

Before declaring the skill+app working:

1. Run `batch_venue_matcher` on `input_examples/CONSULTOR VIRTUAL PARA
   PROSPECÇÃO DE P&D EMBRAPII_MatchIT.docx` end-to-end.
2. Inspect `ranking.json` and `ranking.md` for the example paper; the top venue
   in `open_now` must have a rationale specifically tying the paper's
   contribution to the venue's stated topics.
3. Confirm pool sizing log line on at least two machines with different
   load profiles.
4. Confirm failure recovery by injecting a forced failure (e.g. unplug network
   mid-run, or set `max_turns=2` so the agent can't finish) and observing the
   outer loop re-iterate up to `max_iterations` then log to `_failures.log`.
