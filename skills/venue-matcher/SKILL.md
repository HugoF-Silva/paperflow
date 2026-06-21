---
name: venue-matcher
description: This skill should be used when a user wants to find the publication venues (conferences, journals, magazines, tracks, workshops) a specific academic paper truly belongs to — "find a venue for my paper", "where can I submit this paper", "match venues", "/venue-matcher". Guides running the bundled venue-matcher program over a paper (or a directory of papers) and reporting a fit-ranked result.
---

# venue-matcher (orchestrator guide)

You are the **outer agent**. You do not rank venues yourself. You run a bundled
program that, for each paper, spawns a fresh neurotic agent which web-searches
and writes a fit-ranked result. Your job is to run that program well and explain
what is happening — excellent service.

## What the system is (explain this to the user when useful)
- **Inner agent:** one fresh agent per paper, runs a *ralph loop* (repeats until
  it is genuinely done, carrying a compacted recap of each pass into the next as
  its own first "memory"). It only sees ITS paper's text.
- **Why one process at a time by default:** `MAX_PARALLEL=1` so a shared sandbox
  is never overloaded. A developer can raise it locally.
- **claude.ai 5-minute reality:** one paper's full loop is built to finish under
  ~5 minutes. More papers run sequentially and may exceed the sandbox cap — use
  one session per paper there.
- **Targeting:** country-only (from the paper; Brazil if unstated). Language is
  never a filter.

## Procedure
1. **Ensure the API key.** The program needs `ANTHROPIC_API_KEY` in the
   environment. If a human is present and it is missing, ask for it with
   AskUserQuestion, then `export ANTHROPIC_API_KEY=…` via Bash.
2. **Gather missing inputs** (only if a human is present), with AskUserQuestion,
   one at a time: (a) the paper, if none is visible — ask them to upload it;
   (b) `soon-days` — how many days they tolerate until a venue opens. **Never**
   ask for `--input-dir` — locate uploads yourself.
3. **Find the input directory.** If you were given one, use it. Otherwise search
   the sandbox for the uploaded paper(s) and use that directory.
4. **Install deps once** (idempotent; safe to repeat):
   `pip install -q -r ${CLAUDE_PLUGIN_ROOT}/skills/venue-matcher/scripts/requirements.txt`
5. **Run it in the background and poll.** You may set only `--input-dir` and
   `--soon-days`:
   `python ${CLAUDE_PLUGIN_ROOT}/skills/venue-matcher/scripts/venue_matcher/cli.py --input-dir <dir> --soon-days <N> > /tmp/vm.out 2>&1 &`
   The program writes to `/work/results` (its configured output directory) and
   prints that directory on its final stdout line, so you can confirm it there.
   Then poll `/work/results/_progress.log` until it shows `BATCH COMPLETE`,
   reporting the running `done/total`. Do not give up early.
6. **If it ends with no result** (e.g. the sandbox killed it at ~5 min), say so
   plainly and suggest cloning the repo to run locally as a developer (more work,
   but reliable for many papers).
7. **Always report outcomes:** the created files `/work/results/<stem>/ranking.json`
   and `/work/results/<stem>/ranking.md`, plus a human-friendly summary of the ranking.
