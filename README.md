# Research

Research projects carried out entirely by LLMs (Claude Code). Every line of text and code is LLM-generated.

Inspired by <https://simonwillison.net/2025/Nov/6/async-code-research/>

## Projects

### [doc2md](doc2md/) — 2026-03-20

High-fidelity PDF/DOCX/XLSX to Markdown converter. Fills the gap between `markitdown` (MIT but low-fidelity) and `marker` (high-fidelity but GPL). Built around a typed Document IR layer that separates parsing from rendering. 66 tests across 5 TDD phases. Self-verifying demo via `uvx showboat verify doc2md/demo/demo.md`.

### [llm-order-deprioritization-benchmark](llm-order-deprioritization-benchmark/) — 2025

Benchmarking Claude Opus, Sonnet, and Haiku on structured order deprioritization decisions against a rules-based baseline.
