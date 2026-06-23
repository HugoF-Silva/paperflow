# venue-matcher skill

Finds the publication venues an academic paper belongs to, ranked by fit, split
into "open now" and "opening soon".

**Prerequisite:** an API key value must be provided by the user or outer-agent
prompt. The skill sets that value as `OPENAI_API_KEY` before running the
matcher.

This skill guides an agent to run the bundled program at
`scripts/venue_matcher/cli.py`. It is invoked by asking ("find a venue for my
paper") or via `/venue-matcher`. One paper at a time is the happy path on Codex
(a single run targets the ~5-minute sandbox cap); more papers run sequentially.
Only `.docx` files are supported; other files in the selected input directory
are ignored.
For batch/dev use, see the repo root README.
