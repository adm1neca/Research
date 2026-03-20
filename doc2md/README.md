# doc2md

> **Note: All code, tests, documentation, and architecture in this project were generated entirely by an LLM (Claude Sonnet 4.6 via Claude Code). No human wrote any line of source code or prose.**

High-fidelity, MIT-licensed converter from PDF, DOCX, and XLSX documents to Markdown — built as a research project to fill the gap left by existing tools.

## Why this exists

The best document-to-Markdown converters ([marker](https://github.com/datalab-to/marker), [MinerU](https://github.com/opendatalab/MinerU)) are GPL/AGPL-licensed. The best MIT-licensed tool ([markitdown](https://github.com/microsoft/markitdown)) explicitly trades fidelity for LLM readiness and strips heading structure, styles, and merged cells from output.

`doc2md` is the MIT-licensed, human-readable-output alternative.

## Key design: Document IR

Unlike tools that convert `format → Markdown` directly, doc2md parses into a typed **Intermediate Representation** first:

```
Input file → Parser → Document IR → Markdown Renderer → output.md
```

The IR captures headings (with levels), paragraphs (with inline spans), tables (with merged cells), images, formulas, and code blocks as a proper typed node tree — making each layer independently testable.

## Supported formats

| Format | Parser backend | Features |
|---|---|---|
| PDF | PyMuPDF + pdfplumber | Font-size heading heuristics, table extraction, image extraction |
| DOCX | python-docx | Style-aware heading mapping, bold/italic runs, tables |
| XLSX | openpyxl | Merged cell detection, bold header inference, multi-sheet |

## Quick start

```bash
# Install all format support
uv sync --extra all

# Convert a document
uv run doc2md convert myfile.docx
uv run doc2md convert report.pdf -o output/
uv run doc2md convert data.xlsx

# Benchmark fidelity against other tools
uv run doc2md bench myfile.docx --against markitdown,pandoc

# Run the test suite (66 tests)
uv run pytest

# Verify the self-documenting demo
uv run showboat verify demo/demo.md
```

## Installation

```bash
# Core only (no format support)
pip install doc2md

# With specific format support
pip install "doc2md[pdf]"
pip install "doc2md[docx]"
pip install "doc2md[xlsx]"
pip install "doc2md[all]"
```

Requires Python 3.12+. PDF OCR (scanned documents) additionally requires [Tesseract](https://github.com/tesseract-ocr/tesseract) installed as a system binary.

## Project structure

```
src/doc2md/
├── ir/nodes.py          ← Document IR — typed node tree
├── parsers/
│   ├── pdf.py           ← PyMuPDF + pdfplumber
│   ├── docx.py          ← python-docx (style-aware)
│   └── xlsx.py          ← openpyxl (merged cells)
├── renderers/
│   └── markdown.py      ← GFM Markdown output
├── scorer.py            ← FidelityScorer (0.0–1.0)
└── cli.py               ← doc2md convert / bench
```

## Fidelity scoring

The `FidelityScorer` compares converted output against a reference across three dimensions:

| Dimension | Weight | Measures |
|---|---|---|
| Heading | 35% | Heading level hierarchy preserved |
| Table | 35% | Table row/cell content accuracy |
| Text | 30% | Word-level content overlap |

## Development

Built with TDD (red → green per phase):

```bash
uv sync --extra all      # install everything including dev deps
uv run pytest -v         # run all 66 tests with coverage
```

## License

MIT
