# venue-matcher skill

Finds the publication venues an academic paper belongs to, ranked by fit, split
into "open now" and "opening soon".

**Prerequisite:** `ANTHROPIC_API_KEY` must be set in the environment before use.

This skill guides an agent to run the bundled program at
`scripts/venue_matcher/cli.py`. It is invoked by asking ("find a venue for my
paper") or via `/venue-matcher`. One paper at a time is the happy path on
claude.ai and codex (a single run targets the ~5-minute sandbox cap), and, 
if you did not cloned the repository and run it through the harness command program, 
more papers run sequentially instead of parallel. 
For batch (i.e. dev use, harness command program) see the repo root README.
