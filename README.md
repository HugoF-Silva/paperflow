# 📄 Paperflow

**Paperflow** is a monorepo housing two academic publishing tools that help researchers move their work from manuscript to published paper faster and with less friction.

---

## Products

### 1. `journal-matcher` — Smart Journal Discovery

> *"Which journals should I submit to?"*

Given a paper (`.docx`), **journal-matcher** analyzes its content and ranks journals by match quality — considering only journals that are **currently open for submissions** or **opening soon**. Because the same paper can be a good fit for multiple venues, the service returns a scored list, not a single answer.

**Core workflow:**
1. Parse and extract semantic content from the input paper
2. Fetch and maintain an up-to-date index of journal calls-for-papers (open & upcoming)
3. Score journals against the paper using topic, scope, and keyword similarity
4. Return a ranked, filterable list with submission deadlines and direct links

---

### 2. `paper-formatter` — Journal Template Adapter

> *"This journal requires a specific LaTeX template — adapt my paper."*

Given a paper (`.docx`) and a target journal, **paper-formatter** converts and reformats the manuscript to comply with that journal's exact LaTeX template requirements. The output is a ready-to-compile `.tex` file (and assets) shaped to the journal's structure, margins, citation style, and section conventions.

**Core workflow:**
1. Parse the `.docx` input (text, figures, tables, references, metadata)
2. Fetch the target journal's LaTeX template and style guidelines
3. Map paper content onto the template structure
4. Emit a fully formatted `.tex` file + companion assets

---

## Repository Layout

```
paperflow/
├── journal-matcher/        # Product 1 — journal discovery service
│   ├── src/
│   ├── tests/
│   └── README.md
├── paper-formatter/        # Product 2 — LaTeX template adapter
│   ├── src/
│   ├── tests/
│   └── README.md
├── shared/                 # Code shared between both products
│   ├── parsers/            #   .docx parsing, text extraction
│   └── models/             #   shared data models / schemas
├── docs/                   # Architecture decisions, API specs, research notes
└── .github/
    └── ISSUE_TEMPLATE/
```

---

## Development

> Implementation details, setup instructions, and contribution guidelines will be added as each product is built out. See the individual `README.md` inside each product directory.

---

## License

TBD
