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
- **Input files:** Only `.docx` files are supported. If uploads include other
  formats, tell the user this skill only accepts `.docx`, then use the directory
  containing those `.docx` files. The matcher ignores other file types.

## Procedure
1. **Preflight before any install or run.** Verify all three items:
   - Paper: search directories the agent can access and confirm at least one
     `.docx` paper exists.
   - Opening tolerance: confirm how many days the user tolerates until a venue
     opens; this is the `--soon-days` value.
   - API key: confirm a provided API key value exists in the task prompt or
     from the user. The original key name does not matter.

   If any item is missing, ask exactly one question for each missing item with
   Claude's `AskUserQuestion` tool: one AskUserQuestion tool call per missing item. Do not use Codex's `request_user_input` tool name in this Claude skill.
   If no `AskUserQuestion` tool is available, stop and report the missing item
   instead of running the script.
2. **Find the input directory.** If you were given one, use it. Otherwise search
   the sandbox for the uploaded `.docx` paper(s) and use the directory containing those `.docx` files. Do not invent a default path.
3. **Set the API environment variable.** Set `ANTHROPIC_API_KEY` to the provided
   API key value before running the script. Do not pass the API key value as a venue-matcher command flag, and do not print it. For Bash:
   `export ANTHROPIC_API_KEY='<provided-api-key-value>'`
   If your shell tool does not preserve exported variables across calls, include
   the export in the same shell call that starts the matcher.
4. **Install deps once** (idempotent; safe to repeat):
   `pip install -q -r ${CLAUDE_PLUGIN_ROOT}/skills/venue-matcher/scripts/requirements.txt`
5. **Run it in the background and poll.** You may set only `--input-dir` and
   `--soon-days`:
   `python ${CLAUDE_PLUGIN_ROOT}/skills/venue-matcher/scripts/venue_matcher/cli.py --input-dir <dir> --soon-days <N> > /tmp/vm.out 2>&1 &`
   The program writes to `results` (its configured output directory) and
   prints that directory on its final stdout line, so you can confirm it there.
   Then poll `results/_progress.log` until it shows `BATCH COMPLETE`,
   reporting the running `done/total`. Do not give up early.
6. **If it ends with no result** (e.g. the sandbox killed it at ~5 min), say so
   plainly and suggest cloning the repo to run locally as a developer (more work,
   but reliable for many papers).
7. **Always report outcomes:** the created files `results/<stem>/ranking.json`
   and `results/<stem>/ranking.md`, plus a human-friendly summary of the ranking.
