# venue-matcher — design

**Date:** 2026-05-26
**Owner:** Hugo Fernandes (hugo.fernandes@discente.ufg.br)
**Status:** Draft for review (rev 2 — incorporates containerization, flat layout, composition root, simpler CLI, symlink-based skill discovery, "no false promise" pressure)

## 1. Purpose

For a given academic paper (`.docx`), produce a ranked list of publication
venues the paper truly belongs to, split into:

- **open_now** — accepting submissions today
- **opening_soon** — registration opens within `now + soon_days` (default 31)

Two artifacts, separate concerns:

1. **A shareable skill** (`skills/venue-matcher/`) that drives matching for a
   single paper. Plugin-shape on disk so it can be packaged and distributed later.
2. **A local-only, containerized batch app** (`batch_venue_matcher/`) that
   processes many papers in parallel by spawning per-paper Agent SDK agents
   that invoke the skill.

The skill is the brain. The app is industrial scale on top of it.

## 2. Non-goals

- **No plugin distribution in this scope.** Repo laid out plugin-ready, but
  `.claude-plugin/plugin.json` is intentionally not in git yet.
- **No template adaptation.** A future repo handles formatting to a venue's
  template.
- **No web UI.** App is CLI-only, run inside Docker.
- **No within-iteration quality polishing.** The agent's neuroticism *inside*
  a single iteration is the quality bar; outer iterations exist only to
  recover from deterministic failures (see §9).

## 3. Inputs and parameters

| Parameter | Default | Notes |
|---|---|---|
| `--input-dir` | required | Directory of `.docx` papers |
| `--output-dir` | required | Where rankings get written |
| `--soon-days` | `31` | "Opening soon" upper bound |
| `--countries` | `BR` | Comma-separated ISO-3166 codes |
| `--max-parallel` | `auto` | Upper bound on workers; `auto` = derive from available CPU/RAM |
| `--max-iterations` | `8` | Hard safety net for the outer ralph-style loop |
| `--extra-skills-dir` | `[]` | Path(s) holding additional skills, outside the repo; repeatable |
| `--extra-skill-name` | `[]` | Name(s) of specific skills to take from `--extra-skills-dir`; repeatable |

Intentionally removed:
- ~~`--per-worker-mb`~~ — humility over hubris. We probe what's available and
  trust it. No knob for the user to misconfigure.

## 4. Repository layout (flat, no `__init__.py`, no `src/<package>/` nesting)

```
paperflow/
├── skills/                          # canonical skill location (in git)
│   └── venue-matcher/
│       ├── SKILL.md                 # 1500–2000 words, neurotic-curator guidance
│       └── references/
│           ├── search-paranoia.md
│           ├── venue-anatomy.md
│           └── brazilian-ecosystems.md
├── batch_venue_matcher/             # local Agent SDK app (containerized)
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── cli.py                       # argparse entry; thin
│   ├── compose.py                   # composition root: assembles object graph
│   ├── orchestrator.py              # Orchestrator class (pool + dispatch)
│   └── worker.py                    # Worker class (per-paper SDK call + outer loop + docx parsing)
├── docs/
│   └── superpowers/specs/
├── input_examples/
├── .paperflow.local.toml.example    # template for local extras config (gitignored real file)
├── .gitignore                       # ignores .paperflow.local.toml, results/, .runtime/
├── CLAUDE.md
└── README.md
```

**Notes:**
- No `__init__.py` anywhere. Python 3.12 namespace packages handle imports.
- Skill files live exactly once in git: `skills/venue-matcher/`. There is no
  duplicate at `.claude/skills/`. See §6 for how the SDK discovers them.
- Four `.py` files in the app (`cli`, `compose`, `orchestrator`, `worker`).
  `docx` parsing is inlined in `worker.py` since it's small and only used there.

## 5. The skill: `skills/venue-matcher/SKILL.md`

### 5.1 Frontmatter

```yaml
---
name: venue-matcher
description: Find the publication venue(s) where a given academic paper truly belongs. Reads the paper, runs deep judgmental web search, fetches and reads each candidate venue's CFP, and returns a fit-ranked output split into "open now" and "opening soon" buckets. Use only when explicitly invoked via /venue-matcher.
disable-model-invocation: true     # never auto-triggers; user-only
user-invocable: true               # default; triggered via /venue-matcher
---
```

`disable-model-invocation: true` keeps the skill out of the model's
auto-invocation surface so it doesn't pollute attention for unrelated work.
Only `/venue-matcher` in the user prompt triggers it.

### 5.2 Body outline (imperative, neurotic-curator tone)

1. **Mindset** — paranoid curator. Search is oriented from query one toward
   *recognition of fit*. No counts, no quotas.
2. **Inputs** — natural-language user prompt provides:
   - paper file path
   - search constraints (soon-days, countries)
   - output path
   - the explicit instruction to use `/venue-matcher`
   The skill body **explains what each constraint means** (see §5.4) so the
   agent treats them as real web-search constraints, not opaque flags.
3. **Stage A — Read the paper.** Extract title, abstract, contribution,
   methods, and real-world application. Write a one-paragraph "what this paper
   IS / what it ISN'T" statement.
4. **Stage B — Discover candidate venues.** Spawn 2–4 parallel `Agent`
   subagents, each with a *narrow* angle (niche keyword + country, broader
   keyword + country, mother-language country search terms,
   conference/journal/magazine/track).
   Subagents return URL lists, never verdicts.
5. **Stage C — Read every candidate.** For each URL, `WebFetch` the CFP/about
   page. Extract: accepted topics, audience, constraints, registration
   deadline, country, indexing. Compare against the paper's
   IS/ISN'T statement. Decide real candidate, weak candidate, or ruled out.
   Write rationale. **Search snippets are never sufficient.**
6. **Stage D — Bucket and rank.** Split survivors into `open_now` and
   `opening_soon` (registration deadline within `now + soon_days`). Rank by
   fit DESC. Tie-breaks: country match → niche specificity → "vibes" (allowed,
   but must include a one-line reason). Never rank or filter by language.
7. **Stage E — Recognize the fit.** Keep weighing "is this where the paper
   belongs?" Stop on recognition, however early or late. If nothing strongly
   clicks after honest, thorough searching, name the closest survivors and
   say so plainly. Never come back empty-handed; never embellish a weak fit.
8. **Output contract** — write `ranking.json` and `ranking.md` to the path
   given in the user prompt, then emit `<promise>VENUE-MATCH-COMPLETE</promise>`
   as the final text of the final message. See §11 for the JSON shape.

### 5.3 References (progressive disclosure)

- **`references/search-paranoia.md`** — concrete examples of
  lazy-vs-obsessive search so the agent can self-detect laziness.
- **`references/venue-anatomy.md`** — exact fields to extract from a venue's
  CFP page; what to do when fields are ambiguous (especially deadlines).
- **`references/brazilian-ecosystems.md`** — starting map of major BR venues
  across CS/IT: SBC portfolio (SBES, SBBD, SBIE, SBSI, …), IEEE LATAM, RBIE,
  REIT, SBPO, Embrapii's publication channels, magazines like *Computação
  Brasil*, etc.

### 5.4 Constraint vocabulary (a section in `SKILL.md`)

A short, explicit explanation the agent reads when invoked:

> **`soon_days`** — Reject any venue whose registration opens AFTER
> `today + soon_days`. Treat venues whose registration opens before that bound
> as "opening_soon"; venues already open as "open_now". This bound is the
> user's tolerance for waiting.
>
> **`countries`** — Comma-separated ISO-3166 alpha-2 country codes (default
> `BR`). Strongly prefer venues with primary affiliation in these countries.
> Venues outside the list are not banned, but they need much stronger
> thematic fit to outrank a same-country venue. Use each target country's
> mother language for discovery searches, but do not use language as an
> eligibility rule or tie-breaker.
>
> **`output_path`** — Absolute path to the directory where
> `ranking.json` and `ranking.md` must be written. Do not write anywhere else.

## 6. Skill discovery in the container (runtime copy into `.claude/skills/`)

The Agent SDK's skill discovery looks at `.claude/skills/` inside `cwd` and
its ancestors. The two skill sources are:

- The repo's `skills/` directory — contains exactly one skill, `venue-matcher`
- Zero or more user-provided `extra_skill_dirs` — searched by `extra_skill_names`

At **runtime** (container startup, before any worker fires), the entrypoint
populates `/app/.claude/skills/` by copying:

1. `skills/venue-matcher/` → `.claude/skills/venue-matcher/`
2. For each name in `extra_skill_names`: find it in `extra_skill_dirs`,
   copy the resolved directory into `.claude/skills/<name>/`

After staging, the container looks like:

```
/app/
├── skills/                       # source files (only venue-matcher; never mutated)
│   └── venue-matcher/
└── .claude/
    └── skills/                   # runtime staging area, rebuilt every run
        ├── venue-matcher/        # copy of /app/skills/venue-matcher/
        └── <selected_extra>/     # copy of <extra_dir>/<name>/
```

The SDK is launched with `cwd=/app`; it discovers every skill under
`/app/.claude/skills/`.

**Why copy and not symlink:**
- Cross-platform safety (Windows containers don't reliably follow symlinks).
- The image stays generic — no user-specific extras baked in.
- The entrypoint can resolve `(extra_skill_dirs, extra_skill_names)` per run
  and fail fast on conflicts.

**Source of truth:** `skills/` in git. `.claude/skills/` is ephemeral
runtime state, never committed, rebuilt fresh each container start.

## 7. Extra skills as runtime dependencies

Extras are user-provided dependencies, resolved at container startup, not
baked into the image. The image stays generic; users (or the orchestrator)
supply extras at run-time via CLI flags or a local config file.

### 7.1 The resolution algorithm

`extra_skill_dirs` is a **search path**. `extra_skill_names` is an explicit
**allowlist** — only the named skills are pulled. The user never says "grab
everything in this directory".

```
for name in extra_skill_names:
    matches = [d for d in extra_skill_dirs if (d/name/SKILL.md).exists()]
    if not matches:          warn  ("requested skill '<name>' not found in any extra dir")
    elif len(matches) > 1:   fatal ("'<name>' found in multiple extra dirs — conflict")
    elif name == "venue-matcher": fatal ("'<name>' conflicts with the main skill")
    else:                    copy matches[0] -> /app/.claude/skills/<name>/
```

The orchestrator runs this *before* dispatching any worker. Fatal errors
abort the whole run; warnings are logged and the run continues without the
missing extra.

### 7.2 Local config

`.paperflow.local.toml` (gitignored) holds the user's per-machine extras:

```toml
# .paperflow.local.toml — gitignored, per-machine
[extras]
dirs  = ["/home/risp3mg/.claude/plugins/marketplaces/knowledge-work-plugins/customer-support/skills"]
names = ["customer-research"]   # only the names listed are pulled
```

CLI flags `--extra-skills-dir` and `--extra-skill-name` override the config
file at run time.

### 7.3 Validation invocation

Validation is a CLI subcommand a user can run on demand to check their
config without launching the SDK:

```
python -m batch_venue_matcher.cli validate-skills
```

The container's normal `run` entrypoint invokes the same validation step
before staging, so an invalid config aborts before any agent spawns.

### 7.4 Selection on this machine

Survey of installed plugin skills (knowledge-work-plugins,
claude-plugins-official, superpowers-marketplace) at the time of writing:
**none align with academic venue matching**. The closest matches
(`enterprise-search:search`, `customer-research`, `account-research`,
`competitive-brief`) are for company-internal sources or commercial
intelligence, not for searching the open academic web for CFPs.

**Default**: zero extras configured. `.paperflow.local.toml.example` exists
as a template; the actual `.paperflow.local.toml` is gitignored and absent
by default.

## 8. Containerization

### 8.1 Docker image

`Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# install package metadata first for better layer caching
COPY batch_venue_matcher/pyproject.toml /app/batch_venue_matcher/
RUN pip install --no-cache-dir -e /app/batch_venue_matcher

# copy the app code and the skill source files
COPY batch_venue_matcher/ /app/batch_venue_matcher/
COPY skills/ /app/skills/

# .paperflow.local.toml (gitignored) is OPTIONALLY mounted at runtime,
# not baked into the image — keeps the image generic.

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-m", "batch_venue_matcher.cli", "run"]
```

The image has **no skill staging step at build time**. Skill staging happens
inside the entrypoint, at container startup, after the orchestrator has
read the local config and CLI flags. This keeps the image hermetic of user
choices.

### 8.2 docker-compose

`docker-compose.yml`:

```yaml
services:
  matcher:
    build: .
    volumes:
      - ./papers:/work/papers:ro
      - ./results:/work/results
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
    # default args; override at the CLI
    command: >
      --input-dir /work/papers
      --output-dir /work/results
      --soon-days 31
      --countries BR
```

### 8.3 Docker Compose (the user-facing surface)

Docker Desktop must be open and the Docker engine must be running before the
outer-agent process starts. The provider is explicit; there is no default.

```bash
docker compose run --build --rm matcher --api anthropic
docker compose run --build --rm matcher --api openai
```

The command builds the image if needed, starts `python -m harness.cli` inside
the `matcher` container, and passes the chosen provider to the harness. The
harness builds the outer-agent prompt, loads the selected plugin, and starts
the outer agent. Resource sizing happens automatically inside the container.

## 9. SDK call (per worker)

```python
options = ClaudeAgentOptions(
    cwd="/app",
    setting_sources=["project"],     # discovers /app/.claude/skills/
    skills=["venue-matcher", *extra_names],
    allowed_tools=[
        "Read", "Write",
        "WebSearch", "WebFetch",
        "Agent",                     # for narrow-angle subagents
    ],
    system_prompt=SYSTEM_PROMPT,     # see §9.2
    max_turns=80,
)
```

**No** `Grep`, `Glob`, `Bash`. The agent doesn't search a codebase, doesn't
need shell. It reads one paper, web-searches, web-fetches, writes notes
and the final ranking. `claude_code` preset is NOT used — it would bloat
context with code-editing instructions irrelevant here.

### 9.1 User prompt (natural language, constraints explained)

For each paper, the worker constructs:

```
/venue-matcher

Match publication venues for this paper: /work/papers/<basename>.docx

Search constraints:
- Today's date: 2026-05-26.
- Open now OR opening within 31 calendar days from today. Reject anything
  whose registration opens later than that.
- Country preference: BR (primary). Non-BR venues are allowed only when their
  thematic fit is markedly stronger than any BR alternative.
- Search wording: use Brazilian Portuguese query terms for Brazil, because it is
  the country's mother language. Do not infer countries from the paper's
  language, and do not filter or rank venues by accepted language.

Write your final ranking to:
- /work/results/<basename>/ranking.json
- /work/results/<basename>/ranking.md

When — and only when — you have recognized the venue(s) the paper truly
belongs to, emit exactly this text on its own line as the LAST line of your
final message:
<promise>VENUE-MATCH-COMPLETE</promise>

CRITICAL — do not emit a false promise:
- The promise marks "I did the work and arrived at a genuine result".
- It does NOT mean "I gave up" or "I'm tired" or "I think I should stop now".
- Even if you feel stuck, the search seems impossible, or you've been
  running for a while — you MUST NOT emit a false promise.
- If after honest, thorough search you cannot find a strong fit, name the
  closest survivors and explain why none strongly fit — THEN emit the promise.
  That is a genuine result.
- The loop watching this is designed to continue until the promise is
  unambiguously TRUE. Trust the process.
```

This is the agent's "do not lie to escape" pressure — borrowed directly from
ralph-loop's prompt philosophy (you pointed to its setup script). The shape
is the same: an explicit, repeated reminder that the promise is a TRUTH
contract, not an EXIT button.

### 9.2 System prompt (lean, behavioral)

```
You are a venue-matching agent. Your only job: find the publication venue(s)
where a given academic paper truly belongs.

The user will invoke /venue-matcher with a paper path and search constraints.
Follow the skill body with neurotic care: read the paper, read each candidate
venue's actual CFP, and orient the search around recognizing fit — never
toward filling a quota or counter. Search snippets are never sufficient
justification for including a venue; you must WebFetch the CFP.

Stopping condition: recognition that you've found the venue(s) the paper
genuinely belongs to. Then, and only then, emit
<promise>VENUE-MATCH-COMPLETE</promise> as the last line of your final message.

Do not emit a false promise. Trust the process.
```

## 10. Outer-loop iteration (failure recovery only)

The orchestrator re-invokes the SDK for the same paper only on clear,
deterministic failure:

1. The final assistant message does not contain
   `<promise>VENUE-MATCH-COMPLETE</promise>`.
2. SDK process exited with an error or crashed.
3. Expected output files (`ranking.json`, `ranking.md`) are missing or the
   JSON doesn't parse.
4. `max_turns` ran out before the promise was emitted.

On any of those, the orchestrator re-runs the **same** user prompt. The
agent's working files (the in-progress `ranking.json` / `ranking.md` from
the previous iteration) persist on disk and the next iteration's agent sees
them — feedstock when iteration actually happens.

We do **not** iterate to chase subjective ranking quality. Quality is the
responsibility of the agent's intra-iteration neuroticism. The outer loop
is purely a failure-recovery mechanism.

When `max_iterations` is exhausted, the orchestrator persists whatever
artifacts exist, appends `<paper-stem>` to `results/_failures.log` with a
reason, and moves to the next paper. One failed paper doesn't fail the run.

### Difference from canonical ralph-loop

Ralph-loop iterates to *build* something across iterations (code, tests).
Our task is web search; "building" happens within a single iteration through
careful reading. We adopt ralph-loop's three primitives — persistent scratch
on disk, completion promise, max-iterations safety — and reject its
"keep-iterating-for-quality" instinct. Loop is for failure recovery only.

## 11. Output contract

### 11.1 Per-paper directory (final state only — no per-iteration archives)

```
results/<paper-stem>/
├── ranking.json          # final, structured
├── ranking.md            # final, human-readable
└── iteration.log         # one line per outer-loop iteration with outcome
```

The agent updates `ranking.json` and `ranking.md` continuously during a single
iteration. Between iterations they are the agent's own feedstock (it reads
its prior self's work from these files). When the agent emits the promise,
the current state of the files IS the final output. **No `notes/iter-N/`
sub-directories are created.**

### 11.2 `ranking.json` shape

Keep the JSON keys in English. Write human-readable string values in Brazilian
Portuguese; keep official venue names and URLs as published.

```json
{
  "paper": {
    "path": "papers/Foo.docx",
    "is_statement": "O que o artigo É — sua contribuição, métodos e domínio aplicado.",
    "isnt_statement": "O que o artigo NÃO É — notas explícitas fora de escopo."
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
      "deadline": "2026-06-15",
      "topics_matched": ["SI na indústria", "IA aplicada"],
      "rationale": "Parágrafo específico ligando a contribuição do artigo aos tópicos declarados do venue. Sem generalidades."
    }
  ],
  "opening_soon": [ /* same shape; deadline within now+soon_days */ ],
  "closest_misses": [ /* venues considered seriously but ruled out, with reason */ ],
  "agent_notes": "Free-form short summary, including any tie-break 'vibes' rationale."
}
```

### 11.3 Failures aggregate

`results/_failures.log` — one line per failed paper:

```
2026-05-26T14:35:11  Foo.docx  iterations_exhausted  last_reason=no_promise_in_final_message
```

## 12. Resource-aware concurrency (no knob for the user to misconfigure)

Pool size at startup is determined from **actually-available** resources,
inside the container (Docker enforces cgroup limits visible to psutil):

```python
cpu_count   = os.cpu_count()
cpu_used    = psutil.cpu_percent(interval=1.0)        # measured
cpu_free    = max(0, cpu_count * (1 - cpu_used/100))
cpu_workers = max(1, int(cpu_free * 0.8) - 1)         # 80% of free, leave 1 CPU

mem_free    = psutil.virtual_memory().available       # bytes currently free
# heuristic worker memory: probed empirically the first time, otherwise
# fall back to a conservative built-in estimate of ~800 MiB. NOT user-tuned.
mem_workers = max(1, mem_free // ESTIMATED_BYTES_PER_WORKER)

pool_size = min(num_papers, cpu_workers, mem_workers, user_max_parallel_or_inf)
```

The CLI prints the chosen size and the math:

```
host:    8 CPUs (12% in use right now), 16.0 GiB RAM (6.4 GiB free)
budget:  80% of free CPU, leave ≥1 CPU for the OS
result:  5 workers   (capped by: mem=5, cpu=6, papers=23)
queue:   23 papers → 5 in parallel, ~4 batches expected
```

`--max-parallel N` is an upper bound, still clamped by `cpu_workers` /
`mem_workers`. We never overcommit, even if asked.

### Multiprocessing, not threading

`multiprocessing.Pool` (or `ProcessPoolExecutor`) with `spawn` start method.
GIL-irrelevant; each worker is a separate process.

## 13. Composition root

`compose.py` is the DDD composition root. It assembles the object graph in
plain Python and exposes a single function:

```python
# compose.py
def build_orchestrator(args) -> Orchestrator:
    skill_root        = ensure_skills_resolved(args)             # validates extras
    resource_probe    = ResourceProbe()
    worker_factory    = WorkerFactory(
        cwd="/app",
        skill_names=["venue-matcher", *args.extra_skill_names],
        system_prompt=SYSTEM_PROMPT,
        max_turns=80,
        max_iterations=args.max_iterations,
    )
    return Orchestrator(
        worker_factory=worker_factory,
        resource_probe=resource_probe,
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        user_max_parallel=args.max_parallel,
        soon_days=args.soon_days,
        countries=args.countries,
    )
```

Entry points (`cli.py`, future tests, future alternative drivers) import
from `compose.py` to get a wired-up `Orchestrator` they can `.run()`.

## 14. Distribution plan

### Today (in scope)
- `skills/venue-matcher/` in git.
- `batch_venue_matcher/` consumes it locally via a build-time symlink inside
  the Docker image.
- Nothing published. No `.claude-plugin/plugin.json`.

### Later (out of scope here)
- Add `.claude-plugin/plugin.json`, publish.
- Teammates run `/plugin install paperflow@<source>`; the skill becomes
  available as `/paperflow:venue-matcher` in their Claude Code.
- Document the local batch app for power users who clone.

## 15. Verification

Before declaring skill+app working:

1. Run the app on `input_examples/CONSULTOR VIRTUAL PARA PROSPECÇÃO DE P&D
   EMBRAPII_MatchIT.docx` end-to-end.
2. Inspect `results/<stem>/ranking.json` and `ranking.md`. The top venue in
   `open_now` must have a rationale specifically tying the paper's
   contribution to the venue's stated topics.
3. Confirm pool sizing log line on at least two machines / load profiles.
4. Inject a forced failure (e.g. set `max_turns=2`) and confirm the outer
   loop iterates up to `max_iterations` and then logs to `_failures.log`.
5. Confirm `docker compose run --build --rm matcher` without `--api` exits
   with argparse code 2 instead of choosing a provider.

## 16. Open questions (deferred to implementation)

- Whether to pre-translate non-EN papers (currently: pass-through; the agent
  reads PT-BR fine and the matching is about content, not surface form).
- Exact subagent count in Stage B (2–4 currently); tune during the first
  real runs against `input_examples/`.
