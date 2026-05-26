---
name: venue-matcher
description: This skill should be used when the user explicitly invokes /venue-matcher to find the publication venue(s) where a given academic paper truly belongs. Reads the paper, runs deep judgmental web search, fetches and reads each candidate venue's CFP, and returns a fit-ranked output split into "open now" and "opening soon" buckets. Triggers ONLY on the explicit /venue-matcher slash command — never on related-sounding requests like "find a venue" or "publication search".
disable-model-invocation: true
user-invocable: true
---

# venue-matcher

Find the publication venue(s) where a given academic paper truly belongs.
Read the paper. Read each candidate venue's actual call-for-papers page.
Recognize the venue the paper genuinely fits, however many or few venues
that takes to find. Then — and only then — emit the completion promise.

## Mindset

The user prompt has been written in a way that pressures the agent toward
a paranoid-curator stance. Internalize it.

- The search is **oriented from query one toward recognizing fit**. It is
  not a counter ticking up toward a quota.
- Search snippets are **never** sufficient. A candidate is only a candidate
  after its CFP/about page has been WebFetched and read carefully.
- Recognition lands when reading a venue's stated topics, audience, and
  recent editions feels viscerally aligned with the paper's specific
  contribution. The moment "this is it" arrives is the moment to stop.
- If after honest, thorough search nothing strongly clicks, name the
  closest survivors and explain why none strongly fit. Never come back
  empty-handed. Never embellish a weak fit.

A lazy search that returns plausible-looking results is a failure. An
obsessive search that returns one venue with a precise rationale is a
success. See `references/search-paranoia.md` for concrete examples of the
difference.

## Constraint vocabulary

The user prompt supplies search constraints. Treat them as hard rules, not
suggestions.

- **`soon_days`** — Reject any venue whose registration opens AFTER
  `today + soon_days`. Venues whose registration opens before that bound
  but is in the future go in `opening_soon`. Venues already open go in
  `open_now`. This bound is the user's tolerance for waiting.
- **`countries`** — A list of ISO-3166 alpha-2 country codes (default
  `BR`). Strongly prefer venues with primary affiliation in these
  countries. Venues outside the list are not banned, but they need
  markedly stronger thematic fit to outrank a same-country venue, AND
  they only stay if they accept the paper's language (PT-BR or EN).
- **`output_path`** — Absolute directory path where `ranking.json` and
  `ranking.md` must be written. Do not write final outputs anywhere else.

## Stage A — Read the paper

Read the paper from the path provided. Extract:

1. Title
2. Abstract (or executive summary if not labeled)
3. Specific contribution (what is novel here; what's the delta)
4. Methods and tooling used (e.g., specific ML frameworks, LLMs, datasets)
5. Real-world application domain (industry, vertical, problem class)
6. Language(s) the paper is written in

From those, write **two short sentences** to working notes — one describing
what the paper *is*, one describing what it *isn't*. Be specific about the
contribution. "Applied AI for X" is too generic; "An applied study of
LLM-driven prospecting between SMEs and Embrapii R&D centers" is the level
of specificity to aim for.

Save these statements; they are the lens against which every candidate
venue gets evaluated.

## Stage B — Discover candidate venues

Use the `Agent` tool to spawn 2–4 **narrow-angle** subagent searches in
parallel. Each subagent should hunt one angle and return URLs of venues
worth reading, with brief notes on why each looks worth a careful read.
Subagents return URL lists — never verdicts. Verdicts are this agent's
job, after reading the actual pages.

Suggested angles (vary by paper):

1. **Niche keyword + country**: the paper's specific contribution + a
   country code. E.g. "LLM prospecting Embrapii" + Brazilian academic
   venues.
2. **Broader keyword + country**: applied AI / applied ML + same country.
3. **Language-targeted**: venues in the paper's language(s) that accept
   the topic.
4. **Format-targeted**: separate angles for conferences, journals,
   magazines, and tracks/workshops — these have very different audiences.

When seeding the subagents, give them the IS/ISN'T statements from Stage A
so they don't drift.

## Stage C — Read every candidate

For each URL returned by Stage B, use `WebFetch` to read the venue's
call-for-papers page (or, when CFP is not yet posted for the current
edition, the venue's about/topics page and the most recent edition's CFP).
Extract:

- Accepted topics (verbatim from the venue's wording)
- Audience description
- Constraints (page limits, anonymity rules, etc. — these are the venue's
  framing of who they're for, not its template requirements)
- Registration deadline (the date by which a submission must be made)
- Languages accepted
- Country / hosting body
- Indexing / where the proceedings end up

If the venue's deadline is past, it's out (unless it's a journal with
rolling submissions — note this explicitly). If the deadline is beyond
`today + soon_days`, it's out for this run.

For each surviving candidate, write a paragraph rationale that ties the
paper's IS/ISN'T statements to the venue's stated topics — using the
venue's own words where possible. No generic platitudes. No "this would
be a good fit" without specifics.

`references/venue-anatomy.md` lists the exact fields to extract and how
to handle ambiguous deadline language.

## Stage D — Bucket and rank

Split the survivors:

- **`open_now`** — registration is open today
- **`opening_soon`** — registration opens before `today + soon_days`

Within each bucket, rank by fit DESC. Tie-breaks, in order:

1. Language match (paper's language explicitly listed by the venue)
2. Country match (venue in the user's `countries` list)
3. Niche specificity (venue centered on this paper's exact contribution
   beats a general-purpose venue)
4. Vibes — allowed when 1–3 are exhausted, but the rationale field must
   include a one-line note on what the tie-break vibe is.

## Stage E — Recognize the fit

Keep weighing every survivor against the IS/ISN'T statements. The
search ends when recognition lands: the venue (or small set) where this
paper genuinely belongs becomes self-evident.

That moment is **not** "I've read N venues, time to stop". The number is
irrelevant. The signal is recognition.

If recognition never lands after thorough, honest searching, write a
short paragraph at the top of `ranking.md` explaining what was searched
and why none of the survivors strongly fit. Then still present the
closest survivors in `open_now` / `opening_soon`, ranked. Do not pad.
Do not return empty-handed.

## Output contract

Write the final ranking to the path passed in the user prompt:

- `<output_path>/ranking.json` — structured, machine-readable
- `<output_path>/ranking.md` — human-readable summary + rationale per venue

The JSON shape:

```json
{
  "paper": {
    "path": "...",
    "language": "pt-BR" or "en" or "pt-BR+en",
    "is_statement": "What this paper IS — its specific contribution.",
    "isnt_statement": "What this paper IS NOT — out-of-scope notes."
  },
  "params": {
    "soon_days": 31,
    "countries": ["BR"],
    "as_of": "2026-05-26T14:30:00-03:00"
  },
  "open_now": [
    {
      "rank": 1,
      "name": "<venue name + year>",
      "kind": "conference|journal|magazine|track|workshop",
      "url": "https://...",
      "country": "BR",
      "languages": ["pt-BR", "en"],
      "deadline": "YYYY-MM-DD",
      "topics_matched": ["...", "..."],
      "rationale": "A paragraph specifically tying the paper's contribution to this venue's stated topics — using the venue's own words where possible. No generic platitudes."
    }
  ],
  "opening_soon": [ /* same shape; deadline within now+soon_days */ ],
  "closest_misses": [ /* venues considered seriously but ruled out, with reason */ ],
  "agent_notes": "Free-form short summary. Mention any tie-break vibes here."
}
```

Update both files **as the search progresses**, so this agent's prior
iteration (if there is one) can see the work-in-progress. The final state
of these files IS the output. Do not create per-iteration archive
directories.

## Completion promise

When — and only when — the work above is genuinely done, emit exactly
this text on its own line as the LAST line of the final message:

```
<promise>VENUE-MATCH-COMPLETE</promise>
```

CRITICAL — do not lie to exit:

- The promise marks "I did the work and arrived at a real result".
- It does not mean "I'm tired" or "I think I should stop now".
- If after honest thorough search no strong fit exists, write the
  honest "nothing strongly clicks" paragraph in `ranking.md`, present
  the closest survivors, and *then* emit the promise. That is a real
  result.
- The orchestrator watching for this promise is designed to keep
  iterating until it is unambiguously TRUE. Trust the process.

## Tools available

- `Read` — to read the paper text and the work-in-progress ranking files.
- `Write` — to write `ranking.json` and `ranking.md`, and to keep notes
  inside `ranking.json` (in the `agent_notes` field).
- `WebSearch` — for initial keyword exploration.
- `WebFetch` — **mandatory** for every venue under consideration. No
  venue makes the ranking on snippets alone.
- `Agent` — to spawn the 2–4 narrow-angle subagent searches in Stage B.

## References

Load these on demand for deeper guidance:

- `references/search-paranoia.md` — lazy vs obsessive search, with
  concrete examples.
- `references/venue-anatomy.md` — the exact fields to extract from a
  venue's CFP page, and what to do with ambiguous deadline language.
- `references/brazilian-ecosystems.md` — a starting map of major BR
  venues across CS/IT (SBC portfolio, IEEE LATAM, RBIE, REIT, SBPO,
  Embrapii channels, magazines like *Computação Brasil*).
