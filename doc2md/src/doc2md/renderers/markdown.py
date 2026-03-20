"""GFM Markdown renderer — walks Document IR and emits Markdown text."""
from __future__ import annotations
import os
import re
from urllib.parse import urlparse
from doc2md.ir.nodes import (
    Document, Heading, Paragraph, Span,
    Table, Cell, Image, Formula, CodeBlock,
    List, ListItem, FidelityWarning, Node,
)

# SEC-07: maximum nesting depth for list rendering
_MAX_LIST_DEPTH = 20

# SEC-02: escape Markdown-special characters in raw document content
_MD_SPECIAL = str.maketrans({
    '\\': '\\\\',
    '`':  '\\`',
    '*':  '\\*',
    '_':  '\\_',
    '{':  '\\{',
    '}':  '\\}',
    '[':  '\\[',
    ']':  '\\]',
    '(':  '\\(',
    ')':  '\\)',
    '#':  '\\#',
    '+':  '\\+',
    '-':  '\\-',
    '.':  '\\.',
    '!':  '\\!',
})


def _escape_md(text: str) -> str:
    """Escape Markdown-special characters in document-sourced text."""
    return text.translate(_MD_SPECIAL)


def _escape_cell(text: str) -> str:
    """Escape pipe characters and newlines in GFM table cell content."""
    return text.replace('|', '\\|').replace('\n', ' ')


# SEC-01: safe URL schemes for links
_SAFE_SCHEMES = {"http", "https", "mailto"}


def _safe_href(url: str | None) -> str | None:
    """Return url only if it uses a safe scheme; otherwise None."""
    if url is None:
        return None
    try:
        scheme = urlparse(url).scheme.lower()
    except Exception:
        return None
    return url if scheme in _SAFE_SCHEMES else None


# SEC-06: LaTeX commands that can embed URLs or trigger shell execution
_DANGEROUS_LATEX = re.compile(
    r'\\(href|url|hyperref|write18|input|include|immediate|openout|closeout|read)\b',
    re.IGNORECASE,
)


def _sanitize_latex(latex: str) -> str:
    """Strip LaTeX that could inject URLs or trigger shell escapes."""
    if _DANGEROUS_LATEX.search(latex):
        return r'\text{[formula removed: unsafe content]}'
    return latex


class MarkdownRenderer:
    def __init__(self, image_dir: str = "img") -> None:
        self._image_dir = image_dir
        self._image_counter = 0

    def render(self, doc: Document) -> str:
        parts: list[str] = []
        for node in doc.nodes:
            parts.append(self._render_node(node))
        return "\n\n".join(p for p in parts if p) + "\n"

    def _render_node(self, node: Node) -> str:
        match node:
            case Heading():
                return self._heading(node)
            case Paragraph():
                return self._paragraph(node)
            case Table():
                return self._table(node)
            case Image():
                return self._image(node)
            case Formula():
                return self._formula(node)
            case CodeBlock():
                return self._code_block(node)
            case List():
                return self._list(node, indent=0)
            case FidelityWarning():
                return f"> **Warning:** {_escape_md(node.reason)}"
            case _:
                return ""

    def _heading(self, node: Heading) -> str:
        # SEC-02: escape heading text from document content
        return f"{'#' * node.level} {_escape_md(node.text)}"

    def _spans(self, spans: list[Span]) -> str:
        out = []
        for s in spans:
            # SEC-02: escape raw text before applying Markdown formatting
            text = _escape_md(s.text)
            if s.code:
                text = f"`{text}`"
            if s.bold:
                text = f"**{text}**"
            if s.italic:
                text = f"_{text}_"
            # SEC-01: only embed safe URLs
            href = _safe_href(s.link_href)
            if href:
                text = f"[{text}]({href})"
            out.append(text)
        return "".join(out)

    def _paragraph(self, node: Paragraph) -> str:
        return self._spans(node.spans)

    def _table(self, node: Table) -> str:
        lines: list[str] = []

        if node.merged_cells:
            lines.append("> _Note: this table has merged cells; structure is approximated._")

        if node.caption:
            # SEC-02: escape caption text
            lines.append(f"**{_escape_md(node.caption)}**")

        # Use first header row, fall back to column indices
        if node.headers:
            header_row = node.headers[0]
            col_count = len(header_row)
            # SEC-02: escape pipe chars inside cell text
            lines.append("| " + " | ".join(_escape_cell(c.text) for c in header_row) + " |")
        elif node.rows:
            col_count = len(node.rows[0])
            lines.append("| " + " | ".join(str(i) for i in range(col_count)) + " |")
        else:
            return ""

        lines.append("| " + " | ".join("---" for _ in range(col_count)) + " |")

        for row in node.rows:
            lines.append("| " + " | ".join(_escape_cell(c.text) for c in row) + " |")

        return "\n".join(lines)

    def _image(self, node: Image) -> str:
        self._image_counter += 1
        label = _escape_md(node.caption or node.alt or f"image-{self._image_counter}")
        path = os.path.join(self._image_dir, f"{self._image_counter:03d}.png")
        return f"![{label}]({path})"

    def _formula(self, node: Formula) -> str:
        # SEC-06: sanitize before embedding
        latex = _sanitize_latex(node.latex)
        if node.inline:
            return f"${latex}$"
        return f"$$\n{latex}\n$$"

    def _code_block(self, node: CodeBlock) -> str:
        return f"```{node.language}\n{node.text}\n```"

    def _list(self, node: List, indent: int) -> str:
        # SEC-07: guard against stack overflow from deeply nested lists
        if indent > _MAX_LIST_DEPTH:
            return ""
        lines: list[str] = []
        prefix = "  " * indent
        for i, item in enumerate(node.items):
            bullet = f"{i + 1}." if node.ordered else "-"
            text = self._spans(item.spans)
            lines.append(f"{prefix}{bullet} {text}")
            for child in item.children:
                child_list = List(ordered=node.ordered, items=[child])
                lines.append(self._list(child_list, indent + 1))
        return "\n".join(lines)
