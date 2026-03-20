# doc2md — High-Fidelity Document-to-Markdown Converter

*2026-03-20T19:56:47Z by Showboat 0.6.1*
<!-- showboat-id: 6180416e-7c81-43b9-92ff-271fbc27f518 -->

## Overview

doc2md is a high-fidelity, MIT-licensed document-to-Markdown converter for PDF, DOCX, and XLSX files.
It uses a Document IR (Intermediate Representation) as a typed AST between parsing and rendering,
enabling isolated testability per layer and format-agnostic output.

Built with: Python 3.12, uv, pytest (TDD red/green), PyMuPDF, pdfplumber, python-docx, openpyxl.

## CLI usage

```bash
uv run doc2md --help
```

```output
usage: doc2md [-h] {convert,bench} ...

High-fidelity document-to-Markdown converter

positional arguments:
  {convert,bench}
    convert        Convert a document to Markdown
    bench          Benchmark against other tools

options:
  -h, --help       show this help message and exit
```

## Convert a Word document (DOCX)

```bash
uv run doc2md convert tests/fixtures/sample.docx
```

```output
# Research Overview

## Background

This is **bold text** and _italic text_.

## Data Table

| Name | Score | Grade |
| --- | --- | --- |
| Alice | 95 | A |
| Bob | 82 | B |

## Nested List

- Item one

- Item two

```

## Convert an Excel spreadsheet (XLSX)

```bash
uv run doc2md convert tests/fixtures/sample.xlsx
```

```output
> _Note: this table has merged cells; structure is approximated._
**Sales**
| Region | Q1 | Q2 | Q3 | Q4 |
| --- | --- | --- | --- | --- |
| North | 100 | 120 | 130 | 110 |
|  | 90 | 95 | 105 | 100 |
| South | 200 | 210 | 190 | 220 |

```

## Convert a text-based PDF

```bash
uv run doc2md convert tests/fixtures/sample.pdf
```

```output
# Research Findings

## Introduction

This document summarises the key findings of the study.

## Methods

Data was collected over six months.

```

## Full test suite — 66 tests, all green

```bash
uv run pytest --no-cov -q
```

```output
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.2, pluggy-1.6.0
rootdir: /home/user/Research/doc2md
configfile: pyproject.toml
testpaths: tests
plugins: cov-7.0.0
collected 66 items

tests/test_ir_nodes.py .............                                     [ 19%]
tests/test_parser_docx.py ..........                                     [ 34%]
tests/test_parser_pdf.py .........                                       [ 48%]
tests/test_parser_xlsx.py .........                                      [ 62%]
tests/test_renderer_markdown.py ................                         [ 86%]
tests/test_scorer.py .........                                           [100%]

============================== 66 passed in 0.60s ==============================
```

## Fidelity Scorer — compare against markitdown

```bash
uv run doc2md bench tests/fixtures/sample.docx --against markitdown
```

```output
Benchmark: sample.docx
──────────────────────────────────────────────────
Tool                  Heading    Table     Text  Overall
──────────────────────────────────────────────────
doc2md (ours)               —        —        — baseline
markitdown                N/A      N/A      N/A      N/A
```

markitdown is not installed in this environment (N/A). To compare locally:

```bash
uv tool install markitdown
uv run doc2md bench tests/fixtures/sample.docx --against markitdown
```

The scorer compares heading hierarchy preservation, table row accuracy, and word-level text overlap — producing a 0.0–1.0 fidelity score per dimension.
