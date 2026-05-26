# Venue anatomy

What to read on a venue's page, what to extract, and what to do when
fields are ambiguous.

## Pages worth reading, in order

1. **Current edition's call-for-papers (CFP)** — the authoritative source
   for this year's topics, deadlines, and rules.
2. **Topics / scope page** — when CFP is not yet posted for the current
   edition, this page describes the venue's enduring focus.
3. **About / scope** page — for journals especially, this is the
   editorial scope.
4. **Most recent edition's CFP** — when the venue's pattern is annual and
   the current edition isn't out yet, the previous edition is a strong
   proxy.
5. **Recent published papers list** — when in doubt about what the venue
   actually accepts, read 2–3 recent paper titles from the proceedings.

## Fields to extract

For every venue under consideration, capture:

- **Name + year/edition** — e.g. "SBSI 2026"
- **Kind** — `conference` | `journal` | `magazine` | `track` | `workshop`
- **URL** — the page that was read
- **Country / hosting body** — e.g. "BR / SBC", "International / IEEE"
- **Languages accepted** — explicit list from the CFP. If the CFP doesn't
  say, infer cautiously from the published archive.
- **Accepted topics** — verbatim phrases from the CFP, not paraphrased.
- **Registration deadline** — see "Deadline parsing" below.
- **Indexing / where proceedings end up** — DOI? DBLP? Scopus? IEEE
  Xplore? SBC's open library? Mention when present.

## Deadline parsing

Venue CFPs use inconsistent language. Standardize:

- "Submission deadline" or "paper submission" — this is the date the
  paper must be uploaded by. THIS is the registration deadline for our
  purposes.
- "Camera-ready deadline" — too late, the venue has already decided.
  Not what we want.
- "Registration opens" / "Submission opens" — start of the window. If
  this date is in the future and within `today + soon_days`, the venue
  belongs in `opening_soon`. If past, the venue is `open_now` (assuming
  the close deadline is still in the future).
- "Rolling deadline" or "year-round submissions" — journals only. Treat
  as `open_now`; note in the rationale.
- "TBA" / "to be announced" — the venue's edition is not yet active. If
  the venue runs annually and last year's edition is recent, you can
  flag it as "expected open soon" but you must say so honestly in the
  rationale. Do not fabricate dates.

When a CFP lists multiple deadlines (e.g. "abstract due X, full paper
due Y"), use the full-paper deadline.

When a deadline is past but the venue page hasn't been updated yet,
look for a "next edition" link. If absent, treat the venue as not open
this run.

## Country / hosting body

The hosting body matters more than where the venue physically takes
place. SBC (Sociedade Brasileira de Computação) venues are Brazilian
even when hosted in São Paulo for one year and Rio for another. IEEE
LATAM regional venues count as Brazilian when based in Brazil, even
though IEEE is international.

When unsure: read the venue's "organizers" or "committee" page. If most
chairs are at Brazilian institutions, the venue is functionally
Brazilian.

## Ambiguity handling

Three rules:

1. **Never invent**. If the CFP doesn't say something, write "not
   stated" in your notes; don't fill the gap with a plausible guess.
2. **Quote, don't paraphrase**. When extracting topics, copy the
   venue's wording. Paraphrasing erodes precision.
3. **Cross-check the recent archive**. If the CFP says one thing and
   the last edition's accepted papers consistently say another, the
   archive is the more reliable signal.
