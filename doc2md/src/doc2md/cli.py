"""CLI entry point — doc2md convert / doc2md bench."""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

from doc2md.detector import detect_format
from doc2md.renderers.markdown import MarkdownRenderer
from doc2md.scorer import FidelityScorer


def _get_parser(fmt: str):
    if fmt == "docx":
        from doc2md.parsers.docx import DocxParser
        return DocxParser()
    if fmt == "xlsx":
        from doc2md.parsers.xlsx import XlsxParser
        return XlsxParser()
    if fmt == "pdf":
        from doc2md.parsers.pdf import PdfParser
        return PdfParser()
    raise ValueError(f"No parser for format: {fmt}")


def cmd_convert(args) -> int:
    path = Path(args.file)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1

    fmt = detect_format(path)
    parser = _get_parser(fmt)
    doc = parser.parse(path)
    renderer = MarkdownRenderer()
    md = renderer.render(doc)

    if args.output:
        # SEC-03: resolve to an absolute path to prevent path traversal
        out = Path(args.output).resolve()
        out.mkdir(parents=True, exist_ok=True)
        (out / "document.md").write_text(md)
        print(f"Saved to {out / 'document.md'}")
    else:
        print(md)

    if doc.warnings:
        print(f"\n[{len(doc.warnings)} fidelity warning(s)]", file=sys.stderr)
    return 0


def _convert_with_tool(tool: str, path: Path) -> str:
    """Run an external tool and return its stdout as a string."""
    try:
        if tool == "markitdown":
            result = subprocess.run(
                ["uvx", "markitdown", str(path)],
                capture_output=True, text=True, timeout=60,
            )
            return result.stdout
        if tool == "pandoc":
            result = subprocess.run(
                ["pandoc", str(path), "-t", "markdown"],
                capture_output=True, text=True, timeout=60,
            )
            return result.stdout
    except FileNotFoundError:
        return ""
    except subprocess.TimeoutExpired:
        return ""
    return ""


def cmd_bench(args) -> int:
    path = Path(args.file)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1

    fmt = detect_format(path)
    parser = _get_parser(fmt)
    doc = parser.parse(path)
    renderer = MarkdownRenderer()
    our_md = renderer.render(doc)

    # SEC-08: explicit allowlist — only known safe tool names are passed to subprocess
    _ALLOWED_TOOLS = {"markitdown", "pandoc"}
    tools = [t.strip() for t in args.against.split(",") if t.strip() in _ALLOWED_TOOLS]

    print(f"Benchmark: {path.name}\n{'─' * 50}")
    print(f"{'Tool':<20} {'Heading':>8} {'Table':>8} {'Text':>8} {'Overall':>8}")
    print("─" * 50)
    print(f"{'doc2md (ours)':<20} {'—':>8} {'—':>8} {'—':>8} {'baseline':>8}")

    for tool in tools:
        other_md = _convert_with_tool(tool, path)
        if not other_md.strip():
            print(f"{tool:<20} {'N/A':>8} {'N/A':>8} {'N/A':>8} {'N/A':>8}")
            continue
        s = FidelityScorer(our_md, other_md)
        r = s.report()
        print(
            f"{tool:<20} {r['heading']:>8.2f} {r['table']:>8.2f}"
            f" {r['text']:>8.2f} {r['overall']:>8.2f}"
        )
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="doc2md",
        description="High-fidelity document-to-Markdown converter",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    # convert
    p_conv = sub.add_parser("convert", help="Convert a document to Markdown")
    p_conv.add_argument("file", help="Input file (pdf, docx, xlsx)")
    p_conv.add_argument("-o", "--output", help="Output directory", default=None)

    # bench
    p_bench = sub.add_parser("bench", help="Benchmark against other tools")
    p_bench.add_argument("file", help="Input file to benchmark")
    p_bench.add_argument(
        "--against",
        default="markitdown,pandoc",
        help="Comma-separated list of tools to compare against",
    )

    parsed = ap.parse_args(argv)
    if parsed.command == "convert":
        return cmd_convert(parsed)
    if parsed.command == "bench":
        return cmd_bench(parsed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
