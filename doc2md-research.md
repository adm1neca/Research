# doc2md: High-Fidelity Document-to-Markdown Converter

**Research Proposal & Architecture Plan**
Date: 2026-03-20

---

## 1. Problem Statement

Converting PDF, Word (DOCX), and Excel (XLSX) documents to Markdown is a solved
problem — but only for LLM consumption. No existing MIT-licensed tool produces
Markdown faithful enough for human reading and publishing workflows.

### The Gap

| Tool | License | PDF | DOCX | XLSX | Human-Fidelity |
|---|---|---|---|---|---|
| microsoft/markitdown | MIT | text-only, no headings | loses style hierarchy | flat text | low (LLM-focused) |
| datalab-to/marker | GPL + non-MIT weights | high | high | high | high |
| opendatalab/MinerU | AGPL | high | — | — | high |
| jgm/pandoc | GPL | poor | good | — | medium |

**The opportunity:** `marker` and `MinerU` have the fidelity we want but are not
MIT-licensed. `markitdown` is MIT but explicitly trades fidelity for LLM
readiness. No MIT-licensed tool occupies the high-fidelity, human-readable
quadrant.

### Confirmed Limitations of markitdown (from official docs)

- PDF: strips all headings, lists, and layout — plain text dump only
- PDF: cannot process scanned PDFs without pre-OCR
- DOCX: loses Word style hierarchy (`Heading1` → `Heading2` → body text)
- XLSX: loses merged cells, multi-row headers, data type context
- Design intent: *"meant to be consumed by text analysis tools — may not be the
  best option for high-fidelity document conversions for human consumption"*

---

## 2. Research Questions

1. Can a typed Document Intermediate Representation (IR) capture enough semantic
   structure from PDF/DOCX/XLSX to render faithful Markdown for human consumption?
2. What heuristics (font size, bounding box, spacing) best approximate heading
   hierarchy in PDFs that lack tagged structure?
3. How should merged cells and multi-row headers in spreadsheets be represented
   in GFM pipe tables, and what information is necessarily lost?
4. Can a single fidelity scoring metric meaningfully compare converter output
   quality across formats?
5. At what document complexity does OCR accuracy become the bottleneck vs.
   parsing accuracy?

---

## 3. Proposed Solution: Option B — Pipeline with Document IR

The core research contribution is an **Intermediate Representation (IR)** layer
between format-specific parsing and Markdown rendering. This is what no existing
MIT tool has.

### Why IR matters

- Existing tools go `format → Markdown` directly, losing structure in translation
- IR enables: format-agnostic rendering, isolated testability per layer,
  future renderers (HTML, JSON/RAG chunks) from the same parse
- IR is the unit of research — the type system defines what "fidelity" means

### Architecture

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                        doc2md — High-Fidelity Converter                        ║
╚══════════════════════════════════════════════════════════════════════════════════╝

  INPUT
  ─────
  file.pdf  file.docx  file.xlsx
       │         │         │
       ▼         ▼         ▼
┌─────────────────────────────────┐
│         FORMAT DETECTOR         │  ← magic bytes + extension
│   (routes to correct parser)    │
└────────────┬────────────────────┘
             │
  ┌──────────────────────────────────────────────────────────────┐
  │                       PARSER LAYER                           │
  │                                                              │
  │  ┌─────────────────┐  ┌──────────────────┐  ┌────────────┐  │
  │  │   PDF PARSER    │  │   DOCX PARSER    │  │ XLSX PARSER│  │
  │  │                 │  │                  │  │            │  │
  │  │ PyMuPDF         │  │ python-docx      │  │ openpyxl   │  │
  │  │  ├─ text blocks │  │  ├─ style map    │  │  ├─ sheets │  │
  │  │  ├─ bounding box│  │  ├─ heading lvls │  │  ├─ merged │  │
  │  │  ├─ font sizes  │  │  ├─ runs + bold  │  │  │  cells  │  │
  │  │  └─ image bytes │  │  ├─ tables       │  │  ├─ headers│  │
  │  │                 │  │  └─ images       │  │  └─ types  │  │
  │  │ pdfplumber      │  └──────────────────┘  └────────────┘  │
  │  │  └─ table cells │                                         │
  │  │                 │                                         │
  │  │ [if scanned]    │                                         │
  │  │ Tesseract OCR   │                                         │
  │  └─────────────────┘                                         │
  └──────────────────────────────┬───────────────────────────────┘
                                 │  raw extracted data
                                 ▼
  ┌──────────────────────────────────────────────────────────────┐
  │                    DOCUMENT IR LAYER                         │
  │              (the research contribution)                     │
  │                                                              │
  │   Document                                                   │
  │     ├── Heading(level=1..6, text, anchor)                    │
  │     ├── Paragraph(spans=[                                    │
  │     │     Span(text, bold, italic, code, link_href)          │
  │     │   ])                                                   │
  │     ├── Table(                                               │
  │     │     headers=[ [Cell, Cell, ...] ],                     │
  │     │     rows=   [ [Cell, Cell, ...] ],                     │
  │     │     merged_cells=[(r1,c1,r2,c2), ...],                 │
  │     │     caption                                            │
  │     │   )                                                    │
  │     ├── Image(data=bytes, alt, caption, position)            │
  │     ├── Formula(latex, inline=True|False)                    │
  │     ├── CodeBlock(text, language)                            │
  │     ├── List(ordered=True|False, items=[                     │
  │     │     ListItem(spans, children=[...])   ← nested         │
  │     │   ])                                                   │
  │     └── PageBreak / HorizontalRule                           │
  │                                                              │
  │   Metadata                                                   │
  │     ├── title, author, created_at                            │
  │     ├── source_format, source_path                           │
  │     └── warnings=[ FidelityWarning(node, reason) ]           │
  └──────────────────────────────┬───────────────────────────────┘
                                 │  typed node tree
                                 ▼
  ┌──────────────────────────────────────────────────────────────┐
  │                    RENDERER LAYER                            │
  │                                                              │
  │   MarkdownRenderer                                           │
  │     ├── heading   → # / ## / ###                             │
  │     ├── paragraph → inline spans with **bold** / _italic_    │
  │     ├── table     → GFM pipe table  |col|col|                │
  │     │               + footnote for merged cells              │
  │     ├── image     → ![caption](./img/001.png)                │
  │     ├── formula   → $inline$  or  $$block$$                  │
  │     ├── code      → ```lang ... ```                          │
  │     └── list      → - item\n  - item\n    - nested           │
  │                                                              │
  │   [future renderers via same IR]                             │
  │     ├── HTMLRenderer                                         │
  │     ├── JSONRenderer  (RAG chunks)                           │
  │     └── ASTDumper     (debug / testing)                      │
  └──────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
  ┌──────────────────────────────────────────────────────────────┐
  │                     OUTPUT LAYER                             │
  │                                                              │
  │   output.md          ← single file                           │
  │   output/                                                    │
  │     ├── document.md  ← main markdown                         │
  │     ├── img/         ← extracted images                      │
  │     │    ├── 001.png                                         │
  │     │    └── 002.png                                         │
  │     └── meta.json    ← metadata + fidelity warnings          │
  └──────────────────────────────────────────────────────────────┘

  INTERFACES
  ──────────
  CLI   →  doc2md convert file.pdf -o output/
  API   →  converter.convert("file.pdf") → Document → str
  Bench →  doc2md benchmark --against markitdown,pandoc

  FIDELITY SCORING  (research contribution #2)
  ─────────────────
  ground_truth.md  ─┐
                    ├──▶  FidelityScorer  ──▶  score: 0.0–1.0
  converted.md     ─┘     ├─ heading hierarchy preserved?
                           ├─ table structure intact?
                           ├─ inline formatting correct?
                           └─ images extracted?
```

---

## 4. Technology Stack

**Language:** Python 3.12+

Python is the unambiguous choice: the entire document-processing ecosystem
(PyMuPDF, pdfplumber, python-docx, openpyxl, pytesseract) exists only in Python,
as do all ML/OCR hooks needed for scanned PDFs.

**Package management:** `uv` — fast, reproducible, supports optional dependency
groups per format, lockfile-based, no venv activation required.

### Dependencies by format

| Format | Libraries | Notes |
|---|---|---|
| PDF (text) | `pymupdf`, `pdfplumber` | PyMuPDF for speed/images; pdfplumber for table geometry |
| PDF (scanned) | `pytesseract` | Tesseract OCR via system binary |
| DOCX | `python-docx` | Style-aware: maps Word styles to heading levels |
| XLSX | `openpyxl` | Merged cell API, data type detection |
| Dev/test | `pytest`, `pytest-cov`, `showboat` | TDD + demo |

### `pyproject.toml` structure

```toml
[project]
name = "doc2md"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []            # zero hard runtime deps

[project.optional-dependencies]
pdf  = ["pymupdf", "pdfplumber", "pytesseract"]
docx = ["python-docx"]
xlsx = ["openpyxl"]
all  = ["doc2md[pdf,docx,xlsx]"]

[project.scripts]
doc2md = "doc2md.cli:main"

[dependency-groups]
dev = ["pytest", "pytest-cov", "showboat"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Install for development:**

```bash
uv sync --extra all          # install all format deps + dev deps
uv run pytest                # run full test suite
uv run doc2md --help         # run CLI
uvx showboat verify demo/demo.md  # verify demo doc
```

---

## 5. Project Layout

```
doc2md/
├── pyproject.toml
├── uv.lock
├── .python-version          ← 3.12
│
├── src/
│   └── doc2md/
│       ├── __init__.py
│       ├── detector.py      ← format detection (magic bytes + extension)
│       │
│       ├── parsers/
│       │   ├── base.py      ← abstract Parser → Document
│       │   ├── pdf.py       ← PyMuPDF + pdfplumber + tesseract
│       │   ├── docx.py      ← python-docx (style-aware)
│       │   └── xlsx.py      ← openpyxl (merged cells, headers)
│       │
│       ├── ir/
│       │   └── nodes.py     ← Document, Heading, Table, Image, ...
│       │
│       ├── renderers/
│       │   ├── base.py      ← abstract Renderer(Document) → str
│       │   └── markdown.py  ← GFM output
│       │
│       ├── scorer.py        ← FidelityScorer
│       └── cli.py           ← CLI entry point
│
├── tests/
│   ├── fixtures/
│   │   ├── sample.pdf
│   │   ├── sample.docx
│   │   └── sample.xlsx
│   ├── test_detector.py
│   ├── test_ir_nodes.py
│   ├── test_parser_pdf.py
│   ├── test_parser_docx.py
│   ├── test_parser_xlsx.py
│   ├── test_renderer_markdown.py
│   └── test_scorer.py
│
└── demo/
    └── demo.md              ← showboat self-verifying demo document
```

---

## 6. TDD Red → Green Development Plan

Each phase follows strict red/green: write the failing test first, then write
only enough code to make it pass.

### Phase 1 — IR Nodes (pure Python, zero deps)

```
RED   uv run pytest tests/test_ir_nodes.py
      # AssertionError: cannot import Document, Heading, Table...

GREEN write src/doc2md/ir/nodes.py
      # dataclasses: Document, Heading, Paragraph, Span,
      #              Table, Cell, Image, Formula, CodeBlock,
      #              List, ListItem, FidelityWarning

RED   uv run pytest tests/test_renderer_markdown.py
      # Heading(level=1, text="Hello") should render "# Hello\n"

GREEN write src/doc2md/renderers/markdown.py
```

### Phase 2 — DOCX Parser (most deterministic, start here)

```
RED   uv run pytest tests/test_parser_docx.py
      # assert parser.parse("sample.docx").nodes[0] == Heading(level=1, ...)

GREEN uv add python-docx
      write src/doc2md/parsers/docx.py
        ├─ map Word styles → Heading levels
        ├─ extract runs: bold, italic, hyperlink
        └─ extract tables: rows, cols, basic merge detection
```

### Phase 3 — XLSX Parser

```
RED   uv run pytest tests/test_parser_xlsx.py
      # assert merged cell (A1:B1) captured as MergedCell in IR
      # assert header row detected and separated from data rows

GREEN uv add openpyxl
      write src/doc2md/parsers/xlsx.py
        ├─ iterate sheets → Table nodes
        ├─ resolve merged_cells from openpyxl API
        └─ infer header rows (bold formatting heuristic)
```

### Phase 4 — PDF Parser (two sub-phases)

```
RED   uv run pytest tests/test_parser_pdf.py -k "not ocr"
      # text-based PDF: assert Heading detected from font-size heuristic

GREEN uv add pymupdf pdfplumber
      write src/doc2md/parsers/pdf.py
        ├─ extract blocks with font metadata (PyMuPDF)
        ├─ heading heuristic: font_size > body_median * 1.2 → Heading
        ├─ table extraction: pdfplumber bounding boxes → Table IR
        └─ image extraction: PyMuPDF pixmap → Image(data=bytes)

RED   uv run pytest tests/test_parser_pdf.py -k "ocr"
      # scanned PDF: assert text extracted via OCR

GREEN uv add pytesseract
      extend pdf.py
        └─ detect scanned page (char count < threshold)
           → rasterize with PyMuPDF → Tesseract → Paragraph nodes
```

### Phase 5 — Scorer + CLI

```
RED   uv run pytest tests/test_scorer.py
      # FidelityScorer(ground_truth_md, converted_md).score() → float

GREEN write src/doc2md/scorer.py
        ├─ heading_score: compare heading hierarchy structure
        ├─ table_score: compare row/col counts and cell content
        ├─ formatting_score: bold/italic preservation rate
        └─ image_score: extracted image count ratio

      write src/doc2md/cli.py
        ├─ doc2md convert <file> [-o output/]
        └─ doc2md bench [--against markitdown,pandoc]
```

---

## 7. Showboat Demo Plan

The project ships a `demo/demo.md` built with
[showboat](https://github.com/simonw/showboat) — a self-verifying executable
document. Anyone can re-run it to confirm outputs are real.

```bash
# Run the demo tool without installing it
uvx showboat --help

# How the demo/demo.md was built (for reproducibility):
showboat init demo/demo.md "doc2md — High-Fidelity Converter Demo"

showboat note demo/demo.md "Install doc2md with all format support:"
showboat exec demo/demo.md bash "uv run doc2md --help"

showboat note demo/demo.md "Convert a Word document with headings and a table:"
showboat exec demo/demo.md bash "uv run doc2md convert tests/fixtures/sample.docx"

showboat note demo/demo.md "Convert a multi-sheet Excel file with merged cells:"
showboat exec demo/demo.md bash "uv run doc2md convert tests/fixtures/sample.xlsx"

showboat note demo/demo.md "Convert a text-based PDF:"
showboat exec demo/demo.md bash "uv run doc2md convert tests/fixtures/sample.pdf"

showboat note demo/demo.md "Convert a scanned PDF via OCR:"
showboat exec demo/demo.md bash \
  "uv run doc2md convert tests/fixtures/sample_scanned.pdf"

showboat note demo/demo.md "Fidelity benchmark vs markitdown and pandoc:"
showboat exec demo/demo.md bash \
  "uv run doc2md bench --against markitdown,pandoc"

# Verify all outputs are still reproducible
showboat verify demo/demo.md
```

---

## 8. Research Contributions Summary

| # | Contribution | Why Novel |
|---|---|---|
| 1 | **Document IR** — typed node tree as format-agnostic intermediate representation | No MIT tool has this layer; enables isolated testing and future renderers |
| 2 | **FidelityScorer** — quantitative metric for Markdown conversion quality | No standard benchmark metric exists for this problem |
| 3 | **Heading heuristics for untagged PDFs** — font-size + spacing inference | Systematic study of which heuristics generalize across document types |
| 4 | **Merged cell representation** in GFM tables | Documents the information loss boundary and proposes footnote convention |
| 5 | **MIT-licensed full-stack converter** — PDF + DOCX + XLSX in one tool | Fills the license gap left by marker (GPL) and MinerU (AGPL) |

---

## 9. References

- [microsoft/markitdown](https://github.com/microsoft/markitdown) — MIT, LLM-focused baseline
- [datalab-to/marker](https://github.com/datalab-to/marker) — GPL, high-fidelity reference
- [opendatalab/MinerU](https://github.com/opendatalab/MinerU) — AGPL, PDF-specialist reference
- [markitdown architecture — DeepWiki](https://deepwiki.com/microsoft/markitdown/1.1-architecture)
- [PyMuPDF](https://github.com/pymupdf/PyMuPDF)
- [simonw/showboat](https://github.com/simonw/showboat) — self-verifying demo documents
- [uv documentation](https://docs.astral.sh/uv/)
- [Python Document Processing State 2025](https://substack.com/home/post/p-162342870)
- [PDF Extractors Benchmark 2025](https://dev.to/onlyoneaman/i-tested-7-python-pdf-extractors-so-you-dont-have-to-2025-edition-akm)
