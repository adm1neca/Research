# Research

Research projects carried out by AI tools. Each directory in this repo is a separate research project carried out by an LLM tool - usually Claude Code. Every single line of text and code was written by an LLM.

I try to include prompts and links to transcripts in the PRs that added each report, or in the commits.

Inspired by <https://simonwillison.net/2025/Nov/6/async-code-research/>

## Research Projects

- [llm-order-deprioritization-benchmark](llm-order-deprioritization-benchmark/) - Benchmarking Claude Opus, Sonnet, and Haiku on structured order deprioritization decisions against a rules-based baseline
- [doc2md](doc2md/) - High-fidelity, MIT-licensed PDF/DOCX/XLSX to Markdown converter built as a research project

---

## doc2md — Research Notes

### Problem

Converting documents (PDF, Word, Excel) to Markdown is a solved problem — but only for LLM consumption. No MIT-licensed tool produces Markdown faithful enough for human reading and publishing workflows.

The gap in the ecosystem:

| Tool | License | Human-Fidelity | Notes |
|---|---|---|---|
| [markitdown](https://github.com/microsoft/markitdown) | MIT | Low | Explicitly LLM-focused; strips headings, styles, merged cells |
| [marker](https://github.com/datalab-to/marker) | GPL + non-MIT weights | High | Cannot be used in MIT projects |
| [MinerU](https://github.com/opendatalab/MinerU) | AGPL | High | PDF only |
| [pandoc](https://pandoc.org/) | GPL | Medium | Weak PDF support |

### Key Finding: markitdown's confirmed limitations

- PDF: plain text dump only — all heading/list structure stripped
- PDF: cannot process scanned documents without pre-OCR
- DOCX: Word style hierarchy (`Heading1` → `Heading2`) lost
- XLSX: merged cells, multi-row headers, data types all lost
- By design: *"meant to be consumed by text analysis tools — may not be the best option for high-fidelity document conversions for human consumption"*

### Architecture: Document IR Pipeline

The core research contribution is an **Intermediate Representation (IR)** layer between format-specific parsing and Markdown rendering. No existing MIT tool has this.

```
Input → Format Detector → Parser Layer → Document IR → Renderer → Markdown
                              │                │
                         PDF: PyMuPDF      Heading(level)
                              pdfplumber   Paragraph(spans)
                         DOCX: python-docx Table(merged_cells)
                         XLSX: openpyxl    Image(data)
                                           Formula(latex)
```

**Why IR matters:** existing tools go `format → Markdown` directly, losing structure in translation. The IR is a typed AST that captures what "fidelity" means and makes each layer independently testable.

### Research Contributions

1. **Document IR** — typed node tree as format-agnostic intermediate representation; enables isolated testing per layer and future renderers (HTML, JSON/RAG) from the same parse
2. **FidelityScorer** — quantitative metric (heading/table/text sub-scores → 0.0–1.0 overall) for comparing converter output quality; no standard benchmark metric existed
3. **Heading heuristics for untagged PDFs** — `min(font_sizes)` as body baseline outperforms median (median is skewed by heading spans); ratio thresholds 1.8/1.3/1.1 map to H1/H2/H3
4. **Merged cell representation** — openpyxl `merged_cells.ranges` API captures `(r1,c1,r2,c2)` tuples; GFM pipe tables cannot represent merges so a blockquote warning convention is used
5. **MIT-licensed full-stack converter** — fills the license gap left by marker (GPL) and MinerU (AGPL)

### Implementation

Built in Python 3.12 with `uv`, strict TDD (red → green per phase):

| Phase | Scope | Tests |
|---|---|---|
| 1 | IR nodes + GFM renderer | 29 |
| 2 | DOCX parser | 10 |
| 3 | XLSX parser | 9 |
| 4 | PDF parser (font-size heuristics) | 9 |
| 5 | FidelityScorer + CLI | 9 |
| **Total** | | **66** |

The project ships `demo/demo.md` — a [showboat](https://github.com/simonw/showboat) self-verifying executable document. Reproducibility check: `uv run showboat verify doc2md/demo/demo.md`.

### Tooling notes

- **`uv`** — zero-activation virtual environments, per-format optional deps (`uv sync --extra pdf`), reproducible lockfile
- **`showboat`** — builds a Markdown document interleaved with captured shell output; `showboat verify` re-runs all code blocks and diffs outputs; installable with `uvx showboat`
- **`uvx`** — runs any PyPI tool ephemerally without installing: `uvx showboat verify demo/demo.md`
