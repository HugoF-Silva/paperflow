# paper-formatter

Converts a `.docx` manuscript into a LaTeX file that conforms to a target journal's template requirements.

## Status

🚧 Not yet implemented — see root `README.md` for product overview.

## Planned inputs / outputs

| | Detail |
|---|---|
| **Input** | `.docx` manuscript + target journal identifier |
| **Output** | `.tex` file + assets (figures, `.bib`, style files) ready to compile |

## Key design considerations

- Must preserve all semantic content (abstract, sections, figures, tables, citations, footnotes)
- Journal templates vary significantly: column layout, citation styles (APA, IEEE, ACS…), figure placement rules, required sections
- Output should be compilable with minimal manual intervention
- Edge cases: papers with non-standard section structures, custom figures, multi-language content
