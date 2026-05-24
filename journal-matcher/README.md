# journal-matcher

Analyzes a paper and returns a ranked list of journals that are currently open (or soon opening) for submissions on that topic.

## Status

🚧 Not yet implemented — see root `README.md` for product overview.

## Planned inputs / outputs

| | Detail |
|---|---|
| **Input** | `.docx` manuscript |
| **Output** | JSON list of scored journals with deadlines, scope notes, and submission links |

## Key design considerations

- Journal index must be kept fresh (calls-for-papers have hard deadlines)
- Scoring should account for: topic similarity, journal scope, impact factor preferences, open-access requirements
- A paper may legitimately rank highly at multiple journals — the list view is intentional, not a fallback
