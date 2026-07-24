# venue-matcher skill

Finds the publication venues an academic paper belongs to, ranked by fit, split
into "open now" and "opening soon".

**Prerequisite:** an API key value and reader-matching model value must be
provided by the user or outer-agent prompt. The skill sets those values as
`ANTHROPIC_API_KEY` and `VENUE_MATCHER_MODEL` before running the matcher.

This skill guides an agent to run the bundled program at
`scripts/venue_matcher/cli.py`. It is invoked by asking ("find a venue for my
paper") or via `/venue-matcher`. One paper at a time is the happy path on
claude.ai and codex (a single run targets the ~5-minute sandbox cap), and, 
if you did not cloned the repository and run it through the harness command program, 
more papers run sequentially instead of parallel. 
Only `.docx` files are supported; other files in the selected input directory
are ignored.

The matcher uses exactly one target geographic audience scope: the paper's sole
stated scope, or only the first if several are listed; if none is stated, the
target is **International**. It ranks only venues whose primary geographic
audience scope fits that one target.
For batch (i.e. dev use, harness command program) see the repo root README.
