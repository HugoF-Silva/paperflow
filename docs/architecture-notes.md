# Architecture Notes

A living document for design decisions, open questions, and research references.

---

## Open questions

### journal-matcher
- Which data sources will feed the journal index? (Elsevier, Springer, IEEE Xplore, DOAJ, Scholastica, journal websites themselves…)
- How often should the index be refreshed? (daily crawl vs. webhook-based updates)
- What embedding/similarity model to use for paper ↔ journal scope matching?
- Should match scores factor in the user's past publication history or institution?

### paper-formatter
- How to handle journals that only distribute templates as Word (`.dotx`) rather than LaTeX?
- Citation style conversion: parse from `.docx` reference list vs. require a `.bib` file as a second input?
- How to handle figures that are embedded in the `.docx` vs. linked externally?

### shared
- Single monorepo with shared library, or separate packages published to a registry?
- What is the primary implementation language? (Python is idiomatic for NLP/ML pipelines and LaTeX tooling; TypeScript if a web-first API is the priority)

---

## References

- DOAJ (Directory of Open Access Journals): https://doaj.org
- Sherpa Romeo (journal open-access & embargo policies): https://v2.sherpa.ac.uk/romeo/
- Elsevier Journal Finder: https://journalfinder.elsevier.com (prior art / inspiration)
- Springer Journal Suggester: https://journalsuggester.springer.com
- `python-docx` library for `.docx` parsing
- `pandoc` as a potential `.docx` → `.tex` conversion backbone
