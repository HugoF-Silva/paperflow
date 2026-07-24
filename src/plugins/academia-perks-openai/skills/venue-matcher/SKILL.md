---
name: venue-matcher
description: >-
  This skill should be used when a user wants to find the publication venues
  (conferences, journals, magazines, tracks, workshops) a specific academic
  paper truly belongs to - "find a venue for my paper", "where can I submit this
  paper", "match venues", "/venue-matcher". Guides running the bundled
  venue-matcher program over a paper (or a directory of papers) and reporting a
  fit-ranked result.
---

# venue-matcher (orchestrator guide)

You are the **outer agent**. You do not rank venues yourself. You run a bundled
program that, for each paper, spawns a fresh neurotic agent which web-searches
and writes a fit-ranked result with each ranked venue's own LaTeX template URL
when verified. Your job is to run that program well and explain what is
happening - excellent service.

## What the system is (explain this to the user when useful)
- **Inner agent:** one fresh agent per paper, runs a *ralph loop* (repeats until
  it is genuinely done, carrying a compacted recap of each pass into the next as
  its own first "memory"). It only sees ITS paper's text.
- **Why one process at a time by default:** `MAX_PARALLEL=1` so a shared sandbox
  is never overloaded. A developer can raise it locally.
- **Codex 5-minute reality:** one paper's full loop is built to finish under
  ~5 minutes. More papers run sequentially and may exceed the sandbox cap - use
  one session per paper there.
- **Targeting:** use exactly one geographic audience scope from the paper: its
  sole stated scope, or only the first when several are listed; if none is
  stated, use **International**. Only venues whose primary geographic audience
  scope fits that one target are rankable. The inner agent may phrase discovery
  searches in the selected scope's expected language, but language never expands
  or determines the target scope.
- **Input files:** Only `.docx` files are supported. If uploads include other
  formats, tell the user this skill only accepts `.docx`, then use the directory
  containing those `.docx` files. The matcher ignores other file types.

## Procedure
1. **Preflight before any install or run.** Verify all four items:
   - Paper: search directories the agent can access and confirm at least one
     `.docx` paper exists.
   - Opening tolerance: confirm how many days the user tolerates until a venue
     opens; this is the `--soon-days` value.
   - API key: confirm a provided API key value exists in the task prompt or
     from the user. The original key name does not matter.
   - Model: choose a model through `VENUE_MATCHER_MODEL`; it must be the same
     provider/runtime family as you, the agent reading this skill.

   If any item is missing, ask exactly one question for each missing item with
   Codex's user-question tool, `request_user_input`: one user-question tool call per missing item.
   If no user-question tool is available, stop and report
   the missing item instead of running the script.
2. **Find the input directory.** If you were given one, use it. Otherwise search
   the sandbox for the uploaded `.docx` paper(s) and use the directory containing those `.docx` files. Do not invent a default path.
3. **Set the API and model environment variables.** Set `OPENAI_API_KEY` to the
   provided API key value before running the script.
   Set `VENUE_MATCHER_MODEL` to the model identity that matches you, the agent reading this skill. The goal is for the inner venue-matching agent to run as the same kind of agent as the skill reader, not for this skill to prescribe a fixed model.
   Do not pass the API key or model value as a venue-matcher command flag, and
   do not print them. For Bash:
   `export OPENAI_API_KEY='<provided-api-key-value>'`
   `export VENUE_MATCHER_MODEL='<reader-model>'`
   If your shell tool does not preserve exported variables across calls, include
   the exports in the same shell call that starts the matcher.
4. **Install deps once** (idempotent; safe to repeat). Use the directory
   containing this `SKILL.md` as `<skill-dir>`:
   `pip install -q -r <skill-dir>/scripts/requirements.txt`
5. **Run it once and wait patiently.** You may set only `--input-dir` and
   `--soon-days`:
   `python <skill-dir>/scripts/venue_matcher/cli.py --input-dir <dir> --soon-days <N>`
   Before running, tell the user that conversion is the next logical stage
   after venue matching.
   If your host forces background execution, be patient: Check only `results/_progress.log`
   for `BATCH COMPLETE` or final result file existence; do not read large/tailing
   logs unless the process exited or timed out.
6. **If it ends with no result** (e.g. the sandbox killed it at ~5 min), say so
   plainly and suggest cloning the repo to run locally as a developer (more work,
   but reliable for many papers).
7. **Use only the final completed-result summary for the handoff.** One
   completed per-paper matcher-agent result means one paper's Ralph workflow
   received a terminal inner-agent response and returned its per-paper result
   to the batch runner. Multiple Ralph passes for one paper still count once.
   Never infer this count from discovered papers, processes, workspaces, or
   `ranking.md` files.
   - **More than one completed result:** read the converter skill immediately
     and run it once with the matcher's results root as `--results-dir`, the
     only optional source. Do not gate this action on ranking files.
   - **Exactly one completed result:** locate that result's workspace using its
     reported paper stem. If its `ranking.md` exists, read it and show the
     ranked venues in descending order. Explain that Paperflow will attempt to
     convert the paper with the selected venue's LaTeX template, then call
     `request_user_input` to ask which venue the user wants. After selection,
     read the converter skill and run it with `--chosen-venue` as a paragraph
     linking the selected venue to its template URL or evidence. If the
     completed result has no `ranking.md`, report the honest no-ranking outcome
     and do not launch conversion.
   - **Zero completed results:** report the honest no-result outcome and do not
     launch conversion, even if stale or early-created ranking files exist.
   Report matcher and converter outcomes in the user's preferred language; if
   the user did not state one, use the language already used with them. When a
   `ranking.md` is reported, include its full content and provide the file for
   download when the environment supports it.
