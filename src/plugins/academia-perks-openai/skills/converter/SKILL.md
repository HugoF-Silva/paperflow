---
name: converter
description: Use when converting a paper to LaTeX with a venue template, either after venue matching or from an explicit venue or template conversion request.
---

# Converter

Act as the outer agent. Run the bundled converter, which assigns one Ralph-loop
inner agent per paper and runs those agents sequentially or in parallel. Do not
perform the conversion yourself.

## Procedure

1. Find the input directory. Use a provided directory when available; otherwise
   search accessible directories for the uploaded `.docx` paper or papers and
   use their containing directory. Confirm the files exist. Do not invent a
   default path.

2. Select exactly one optional source flag. Use these value shapes:

   | Flag | Value |
   | --- | --- |
   | `--input-dir` | `<path>` |
   | `--results-dir` | `<path>` |
   | `--chosen-venue` | `<paragraph>` linking the venue to its template URL or evidence |
   | `--template-path` | `<path>` |

   For a matcher handoff, count only **completed per-paper matcher-agent
   results**: one terminal inner-agent response returned per paper to the batch
   runner. Multiple Ralph passes for one paper still count as one result. Never
   infer this count from papers, runs, workspaces, or ranking files.

   - More than one completed result: run once immediately with `--results-dir`
     as the only optional source. Do not gate this choice on ranking files.
   - Exactly one completed result: locate its workspace from the reported paper
     stem. If its `ranking.md` exists, read it, show its venues in descending
     order, and explain that Paperflow will attempt conversion with that venue's
     LaTeX template. Then call `request_user_input` to ask which venue the user
     wants.
     The handoff is incomplete until that tool is called; a plain-text question
     is not a substitute.
     After selection, use `--chosen-venue` with a paragraph linking
     the selected venue to its template URL or evidence. If exactly one result
     has no `ranking.md`, report that outcome and do not launch conversion.
   - Zero completed results: report the no-result outcome and do not launch
     conversion, even when stale or early-created ranking files exist.
   - For a standalone request, use `--chosen-venue` for one explicit venue and
     template paragraph, or `--template-path` for one supplied local template.
     If neither or both are supplied, ask the user to choose exactly one source.

3. Before running the command, resolve `OPENAI_API_KEY` from the provided key and
   `CONVERTER_MODEL` from the same provider/runtime family and model identity as
   you, the agent reading this skill. Resolve that identity dynamically; never
   hardcode or print either value, and keep both values unexported until the
   final launch.

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

6. Report the outcome and relevant file paths in the user's preferred language.
   If the user did not state one, use the language already used with them.
