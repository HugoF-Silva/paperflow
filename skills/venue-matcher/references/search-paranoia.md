# Search paranoia

Concrete examples of lazy vs obsessive search. Read when in doubt about
whether the current iteration of work is good enough to stop.

## The core distinction

**Lazy search** finds *plausible-looking* results: a list of venues whose
names overlap with the paper's topic, presented with confident-sounding
rationales that could apply to many papers.

**Obsessive search** finds *the* venues for *this* paper: each rationale
ties the paper's specific contribution to the venue's specific stated
topics, with the venue's own wording quoted where helpful. The rationale
could not be cut-and-pasted to a different paper without becoming wrong.

## Symptoms of laziness

Catch any of these in your own work and start over for that candidate:

- Rationales written without WebFetching the venue's actual page.
- Rationales that use only the paper's own keywords (e.g. "applied AI in
  industry") instead of the venue's stated topics.
- Topic matches taken from a search snippet rather than the CFP page.
- "This looks like a fit" without explaining *why* this paper (not a
  generic paper) fits *this* venue (not a generic venue).
- Including venues whose deadline is past, ambiguous, or beyond
  `today + soon_days`, because skimming would have caught those.
- Treating a venue's name keywords as evidence of fit (e.g. "Applied AI"
  in the venue title doesn't mean the venue accepts applied AI papers —
  read what they actually publish).
- Settling on the first venues found, instead of letting recognition
  emerge from comparing several.

## Symptoms of healthy obsession

These look like progress, not paranoia:

- Reading 3–10 candidate CFPs before deciding any of them fit.
- Going back to the paper twice to re-check what its specific
  contribution actually is, before deciding whether a venue accepts it.
- Quoting the venue's own wording in the rationale — "the venue calls
  for 'applied case studies of LLMs in industry partnerships'".
- Ruling out a name-recognizable venue because their CFP shows they
  prioritize a different methodology, even though the topic seems to
  match at first glance.
- Including a niche venue with low name recognition because its CFP
  matches the paper precisely.

## When recognition lands

You don't have to be 100% certain. You have to be specifically certain.
The signal is when you can write the rationale — with the venue's words
woven into the paper's contribution — without having to hedge or
generalize. If the rationale would still be true if you replaced "this
paper" with "any paper about [broad topic]", you're not done yet.

## When recognition doesn't land

Sometimes the paper is a strange shape and no venue is a clear fit.
That's allowed. Don't fake recognition by writing a confident-sounding
rationale for a weak match. Write an honest "nothing strongly clicks"
note at the top of `ranking.md`, present the closest survivors with
honest rationales that include the caveats, and emit the completion
promise. That is a real result.

## Calibration questions

Before emitting the completion promise, ask:

1. Could I copy this rationale into a venue match for a different paper
   on the same general topic, with only minor edits? — If yes, you're
   not done. Rewrite the rationale with paper-specific anchors.
2. Did I read each venue's CFP page, not just the search snippet? — If
   any venue's rationale was written without WebFetch, go fetch it.
3. Am I including a venue because it's famous, or because it fits? — If
   famous, demote or drop unless fit is independently real.
4. Did I check the deadline against `today + soon_days`? — If not, do
   it now.
