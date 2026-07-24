# Venue anatomy — what to extract from a CFP

For every venue you consider, WebFetch its page and capture:
- **Name + edition/year** (e.g. "SBSI 2026")
- **Kind**: conference | journal | magazine | track | workshop
- **Venue URL page** that was fetched and read.
- **Primary geographic audience scope / responsible organization** (e.g.
  "Brazil / SBC", "International / ACM"). The venue's audience scope is decided
  by the publication ecosystem it serves, not merely by the event location;
  read the organizers/committee page if unsure. It must fit the one target scope
  to be rankable.
- **Accepted topics** — quote the venue's own wording, do not paraphrase.
- **Venue Template URL**: the venue's latex template URL.
- **Registration deadline** — the date a submission must be uploaded by:
  - "submission deadline" / "paper submission" → this is it.
  - "camera-ready" → too late, ignore.
  - "registration/submission opens" in the future → list under "Abrindo em
    breve" if within `today + soon_days`, else drop.
  - "rolling"/"year-round" (journals) → list under "Abertos agora"; say so.
  - "TBA" / past-and-not-updated → not open this run; do not invent a date.
  - multiple deadlines → use the full-paper deadline.
- **Indexing** — DOI / DBLP / Scopus / IEEE Xplore / SBC OpenLib when present.

Rules:
1. Never invent missing facts — write "not stated" instead.
2. Quote topics; paraphrase erodes precision.
3. If the CFP and the recent published archive disagree, trust the archive.
4. After looking for the latex template, if the venue's points out a template
   without explicitly telling which is its file format, assume it is latex.
5. Keep extraction notes compact: fact, source, decision. Do not turn fetched
   pages into summaries unless that prose is going into `ranking.md`.

FYI:
There are at least 3 "languages" which could be referred to as "the venue's language",
- **accepted submission language(s)**: the languages the venue explicitly accepts for submitted papers.
- **target scope's expected discovery language**: the language used to phrase
  discovery searches for venues that serve the one target geographic audience
  scope. It does not determine whether a venue's primary scope fits.
- **CFP/about-page language**: the language used by the fetched venue source itself, which the venue opted to write their natural language text.

So it is important to be explicit and discern them instead of superficially pointing a language as "venue's language":
