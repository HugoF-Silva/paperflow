---
name: venue-matcher
description: >-
  This skill should be used when a user wants to find the publication venues
  (conferences, journals, magazines, tracks, workshops) a specific academic
  paper truly belongs to - "find a venue for my paper", "where can I submit this
  paper", "match venues", "/venue-matcher". Guides running the bundled
  venue-matcher program over a paper (or a directory of papers) and reporting a
  fit-ranked result. Input directory will be the session's current working directory
  if not provided a path; results directory will be always a subdir inside the reading 
  agent's current working directory no matter whether input directory path were 
  provided or not. Current 2026-07 Language Models based web products 
  (e.g. claude.ai, chatgpt.com) can't keep this skill execution alive until completion, 
  a user's machine (or at least run it with an LLM based app) is recommended.
---

# venue-matcher (orchestrator guide)

You are the **outer agent**. You do not rank venues yourself. You run a bundled
program that, for each paper, spawns a fresh neurotic agent which web-searches
and writes a fit-ranked result with each ranked venue's own LaTeX template URL 
when verified. And, unless the user asks otherwise, your job is to run that program 
well, report outcomes concisely and straightfoward, while avoiding jargons regarding 
command line programs or explicit technical details, but talking about the system as 
a box of agents which parallelize web search to rank venues which are good fit for 
the content discussed in the paper, aiming the making of one `ranking.md` per paper, 
and subsequentially launch a box of more agents as an attempt to convert the papers 
layouts to match each assigned top-1's venue's LaTeX template if any (or the chosen 
venue if there was 1 ranking worth working with in the results directory) — so start 
from the premise the user is not technical, nor programmer, and you must deliver an 
excellent, concise and straightfoward service above all.

## What the system is (explain this to the user when useful)
- **Inner agent:** one fresh agent per paper, runs a *ralph loop* (repeats until
  it is genuinely done, carrying a compacted recap of each pass into the next as
  its own first "memory"). It only sees ITS paper's text.
- **Parallelism by default:** `MAX_PARALLEL=auto` attempts to conservatively estimate
  how many parallel processes the host machine can take. 1 paper per process always,
  venue-matcher program executes an agent per paper, in case there are multiple papers
  it finishes and a new batch execution is executed only to convert each paper, again
  1 process per paper. `auto` is the default value, and you must keep this way unless 
  the user explicitly tells a different number of processes. Even though that's the 
  default, often there's a need to execute venue-matcher / converter for a single paper.
- **Targeting:** use exactly one geographic audience scope from the paper: its
  sole stated scope, or only the first when several are listed; if none is
  stated, use **International**. Only venues whose primary geographic audience
  scope fits that one target are rankable. The inner agent may phrase discovery
  searches in the selected scope's expected language, but language never expands
  or determines the target scope.
- **Input files:** If the user did not provide
  an specific input directory for you, you must assume your working directory (cwd)
  is the input directory. Even though more type of files may happen to be inside 
  the input directory, only `.docx` files will be read by the program. If the user
  provides input directory with paper files which are an type other than .docx, 
  tell the user the venue-matcher ignores other file types. The `.docx` files must 
  be located directly inside the input directory, not in a subdirectory within it. 
  If you didn't find any papers directly in the input directory, refuse to continue 
  and tell the user that until they provide an input directory or start a session 
  within a working directory (cwd) in which contains papers, **you will not proceed!**
- **Output files (results directory):** Warn the user: The results root folder 
  will be created as a directory directly inside your current working directory.
  This results root is also where each paper workspace is created using the paper 
  .docx's stem.
- **Logs:** You can know what is the inner agent is doing and saying by inspecting 
  `_execution.log` inside results folder. `_progress.log` shows only how many papers 
  were already processed so far.

## Procedure
1. **Preflight before any install or run.** Verify all three items:
   - Opening tolerance: confirm how many days the user tolerates until a venue
     opens; this is the `--soon-days` value.
   - API key: confirm a provided API key value exists in the task prompt or
     from the user. The original key name does not matter.
   - Model: choose a model through `VENUE_MATCHER_MODEL`; it must be the same
     provider/runtime family as you, the agent reading this skill.

   If any item is missing, ask exactly one question for each missing item with
   a tool you know you can use to ask user questions.
   Make one user-question tool call per missing item. 
   If no user-question mechanism is available for you, stop and report the 
   missing item instead of running the script.
2. **Assert you have acess to the input directory.** If you were given one, use it. 
   Otherwise assume your current working directory is the input directory, look for 
   `.docx` paper(s) inside it. No directory besides the one given or besides
   your own (in case no input directory were provided) should be set as input
   directory.
4. **Set the API and model environment variables.** Set `OPENAI_API_KEY` to the
   provided API key value before running the script.
   If you are an OpenAI language model, set `VENUE_MATCHER_MODEL` to the model 
   identity that matches you, the agent reading this skill. The goal is for the 
   inner venue-matching agent to run as the same kind of agent as the skill reader, 
   not for this skill to prescribe a fixed model — but if you are neither an OpenAI 
   language model nor a model supported by the inner agent SDK's language model 
   provider API, resort to set `'gpt-5.4-mini'` as the `VENUE_MATCHER_MODEL`.
   Do not pass the API key or model value as a venue-matcher command flag, and
   do not print them. For Bash:
   `export OPENAI_API_KEY='<provided-api-key-value>'`
   `export VENUE_MATCHER_MODEL='<reader-model>'`
   If your shell tool does not preserve exported variables across calls, include
   the exports in the same shell call that starts the matcher.
5. **Install deps once** Use the directory containing this `SKILL.md` as `<skill-dir>`:
   `pip install -q -r <skill-dir>/scripts/requirements.txt`
6. **Run it once and wait patiently.** You may set only `--input-dir` and
   `--soon-days`:
   `python <skill-dir>/scripts/venue_matcher/cli.py --input-dir <dir> --soon-days <N>`
   Before running, tell the user that the paper conversion is the next logical stage
   after finding matching venues for it.
   Run this as a background execution, it can take from 7 minutes (1 paper) to full 
   hours (a lot of papers) depending on the amount of papers in the input directory 
   and parallelism performance.
7. **Look for what was done**: If you can set a timer to now and then concisely report 
   the background process, set a frequency interval based on the amount of papers, the 
   higher the amount of papers the smaller the report frequency. In order to know what 
   the inner agent did already or what is it saying, refer to `results/_execution.log`. 
   In order to know how many papers were processed so far, refer to 
   `results/_progress.log`. **If you cannot set a timer for periodic inspection**, at 
   least look for `BATCH COMPLETE` or final results files existence as a signal that it 
   has finished.
8. **If it ends with no result**, say so
   plainly and suggest cloning the repo to run the controlled container environment
   as a developer i.e. trigger its command through Makefile (more work, but more 
   reliable for many papers).
9. **Use only the final completed-result summary for the handoff.** One
   completed per-paper matcher-agent result means one paper's Ralph workflow
   received a terminal inner-agent response and returned its per-paper result
   to the batch runner. Multiple Ralph passes for one paper still count once.
   Never infer this count from discovered papers, processes, workspaces, or
   `ranking.md` files.
   - **More than one completed result:** read the converter skill immediately
     and run it once with the matcher's results root as `--results-dir`, the
     only optional source. Do not gate this action on ranking files.
   - **Exactly one completed result:** locate that result's workspace using its
     reported paper stem. If there's a `ranking.md` inside the reported paper stem
     directory, read it and show the ranked venues in descending order. Explain 
     that the Converter program will attempt to convert the paper with the selected 
     venue's LaTeX template, then — preferably through your user-question 
     tool/mechanism, but regardless of whether you know of any tool like that — ask 
     which venue the user wants. After selection,
     read the converter skill and run it with `--chosen-venue` as a paragraph
     linking the selected venue to its template URL or evidence. If the
     completed result has no `ranking.md`, report the honest no-ranking outcome
     and do not launch conversion. Neither `ranking.md` outside the paper's stem 
     workspace should be read or considered nor `ranking.md` file names written
     differently than just `ranking.md` — the file must be strictly called `ranking.md`
     and located inside the paper's stem in order for you to consider. If the 
     `ranking.md` shows no open venues, do not launch conversion, and do not ask 
     the user which of this ranking.md venue they want since in that case there's no 
     de facto choice to ask the user even if stale or early created ranking files 
     shows venues to choose.
   - **Zero completed results:** report the honest no-result outcome and do not
     launch conversion, even if stale or early-created ranking files exist.
10. **By the end of conversion.** Report both matcher and converter outcomes in the 
   user's preferred language; if the user did not state one, use the language already 
   in use by them. When a `ranking.md` is reported, tell the user its path and 
   summarize it alongside its conversion result. If it ends up with more than one 
   completed/blocked converter-agent result, do not propagate inner agent's 
   requests/appeals to user — neither through the tool you have access to ask 
   user questions nor other mechanism — instead, simply report all completed outcomes.
