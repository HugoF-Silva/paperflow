---
name: converter
description: >- 
 Use when converting a paper to LaTeX with a venue template, either 
 after venue matching or from an explicit venue or template conversion request.
 If not provided an input directory, it will be the session's current working 
 directory; results directory will be always a subdir inside the reading agent's 
 current working directory no matter whether input directory path were provided 
 or not. Current 2026-07 Language Models based web products (e.g. claude.ai, chatgpt.com) 
 can't keep this skill execution alive until completion, a user's machine (or at least 
 run it with an LLM based app) is recommended.
---

# Converter

Act as the outer agent. Run the bundled converter, which assigns one Ralph-loop
inner agent per paper and runs those agents sequentially or in parallel. Do not
perform the conversion yourself. Avoid programmer jargons regarding command line 
programs or explicit technical details, but talking about the system as program 
of agents which parallelize paper layout conversion to follow a venue's LaTeX template.

## Please be advised
- Parallelism by default: `MAX_PARALLEL=auto` attempts to conservatively estimate
  how many parallel processes the host machine can take. 1 paper : 1 process.
  The converter program executes an agent per paper. `auto` is the default value. 
  Keep this way unless the user explicitly tells a different pool size.
- Input files: Even though more file types may be inside the input directory, only 
  `.docx` will be read by the converter. If the input directory has papers which 
  aren't .docx, tell the user the venue-matcher ignores other file types. The `.docx` 
  files must be located directly inside the input directory, not in a nested dir 
  within it. If you didn't find any direct children papers inside the input 
  directory, refuse to continue and tell the user: until they provide an input 
  directory or start a session within a working directory (cwd) in which contains 
  papers, you will not proceed!
- Output files: Each converter agent's assigned paper conversion workspace is located 
  inside the results directory, which — when a value is not set for `--results-dir` — 
  by default is a `results` directly inside the current working directory; after a 
  venue-matcher batch execution be the immediate causal predecessor of the decision 
  to come read — and use — the converter, you set `--results-dir` as `{cwd}/results` 
  due to have no other choice after directory had been already automatically created 
  by the matcher; if there was no multiple results for venue-matcher but a single one, 
  there's no reason to set `--results-dir` since the program was not designed to run 
  with a value set for it when there's a single preferred venue to be used — whether 
  that preferred venue is the top-1 from the singlemost ranking.md which might had 
  been generated, or a pragraph emphasizing the chosen venue alongside its template URL, 
  or an specific user provided venue's template path.
- Logs: Whatever the inner agent is saying or doing is logged in `_execution.log` inside
  results directory. `_progress.log` shows only how many papers were already processed so far.

## Procedure

1. Assert you have acess to the input directory. If you were given one, use it. 
   Otherwise assume your current working directory is the input directory, look 
   for `.docx` paper(s) inside it. No directory besides the one given or — in 
   case no input directory were provided — besides your own should be set as input
   directory.

2. Select exactly one optional source flag. Use these value shapes:

   | Flag | Value |
   | --- | --- |
   | `--input-dir` | `<path>` |
   | `--results-dir` | `<path>` |
   | `--chosen-venue` | `<paragraph>` linking the venue to its template URL or evidence |
   | `--template-path` | `<path>` |

   **For a venue-matcher handoff,** count only **completed per-paper matcher-agent 
   results**: one terminal inner-agent response returned per paper to the batch
   runner. Multiple Ralph passes for one paper still count as one result. Never
   infer this count from papers, runs, workspaces, or ranking files.

   - More than one completed result: run once immediately with `--results-dir`
     as the only optional source. Do not gate this choice on ranking files.
   - Exactly one completed result: locate its workspace from the reported paper
     stem.If that exactly one completed result has no `ranking.md`, report that 
     outcome and do not launch conversion. But If its `ranking.md` exists, read it, 
     then — as you tell to the user the converter will attempt conversion with that 
     venue's LaTeX template — ask which venue the user wants out of the ranked 
     venues you explicit highlight in descending order — ideally do it through a 
     tool/mechanism you can use to ask user questions but regardless whether you 
     are aware of any. The handoff is incomplete until the user let you proceed 
     by selecting a venue. After selection, use `--chosen-venue` with a paragraph 
     linking the selected venue to its template URL or evidence.
   - Zero completed results: report the no-result outcome and do not launch
     conversion, even when stale or early-created ranking files exist.

   **For a standalone request (i.e. not from a venue-matcher handoff)**, 
   - use `--chosen-venue` for one explicit venue + template paragraph, or 
     `--template-path` for one supplied local template. If neither or both are 
     supplied, ask the user to choose exactly one source.

3. Before running the command, resolve `OPENAI_API_KEY` from the provided key and
   `CONVERTER_MODEL` from the same provider/runtime family and model identity as
   you, the agent reading this skill. But if you are neither an OpenAI 
   language model nor a model supported by the inner agent SDK's language model 
   provider API, resort to set `'gpt-5.4-mini'` as `CONVERTER_MODEL`. Resolve that 
   identity dynamically; never hardcode or print either value, and keep both 
   values unexported until the final launch.

4. Install dependencies idempotently with the directory containing this file
   as `<skill-dir>`:

   ```bash
   pip install -q -r <skill-dir>/scripts/requirements.txt
   ```

   Verify that `tectonic` is on `PATH`. If absent, install an official prebuilt
   binary and verify it before continuing; do not use an unverified fallback.

5. Run exactly one converter command and wait for it to finish. Use `exec env`
   in the same shell call so the credential-bearing shell is replaced before
   inner tools can run. Replace the parenthesized group with the one selected
   optional source:

   ```bash
   exec env \
     OPENAI_API_KEY='<provided-api-key-value>' \
     CONVERTER_MODEL='<current-reader-model-identity>' \
     python <skill-dir>/scripts/converter/cli.py \
     --input-dir <path> \
     (--results-dir <path> | --chosen-venue <paragraph> | --template-path <path>)
   ```

6. If you can set a timer for periodic results inspection, do so and concisely report 
   the background process now and then. The higher the amount of papers the smaller 
   should be the report frequency. If there's no timer mechanism available, skip to 
   the procedure's step 7 when it finishes. `_execution.log` may provide context to 
   inner agents's messages.

7. Report the outcome and relevant file paths. Use the user's preferred language. 
   If the user did not state one, use the language already used by them. If you 
   can provide the file itself besides the file path to the user, provide it. if 
   it ends up with more than one completed or blocked converter-agent result, the 
   do not act on behalf of any of the inner agents's by asking the user whatever 
   inner agents's may had asked to the user, neither propagate natural language 
   requests in third person — no matter if you intended to do it through the tool 
   you have access to ask user questions or through other mechanism — instead, 
   simply report all outcomes writing about all of them in third person.
 