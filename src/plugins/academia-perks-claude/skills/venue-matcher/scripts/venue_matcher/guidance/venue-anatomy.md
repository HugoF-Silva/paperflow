# Venue anatomy — what to extract from a CFP

For every venue you consider, WebFetch its page and capture:
- **Name + edition/year** (e.g. "SBSI 2026")
- **Kind**: conference | journal | magazine | track | workshop
- **URL** read
- **Primary geographic audience scope / responsible organization** (e.g.
  "Brazil / SBC", "International / ACM"). The publication ecosystem it serves
  decides the audience scope, not merely the event location; read the
  organizers/committee page if unsure. It must fit the one target scope to be
  rankable.
- **Accepted topics** — quote the venue's own wording, do not paraphrase.
- **Registration deadline** — the date a submission must be uploaded by:
  - "submission deadline" / "paper submission" → this is it.
  - "camera-ready" → too late, ignore.
  - "registration/submission opens" in the future → `opening_soon` if within
    `today + soon_days`, else drop.
  - "rolling"/"year-round" (journals) → treat as `open_now`; say so.
  - "TBA" / past-and-not-updated → not open this run; do not invent a date.
  - multiple deadlines → use the full-paper deadline.
- **Indexing** — DOI / DBLP / Scopus / IEEE Xplore / SBC OpenLib when present.

Rules:
1. Never invent missing facts — write "not stated".
2. Quote topics; paraphrase erodes precision.
3. If the CFP and the recent published archive disagree, trust the archive.
4. Keep extraction notes compact: fact, source, decision. Do not turn fetched
   pages into summaries unless that prose is going into `ranking.md`.
