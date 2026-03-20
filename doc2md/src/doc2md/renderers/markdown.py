"""GFM Markdown renderer — walks Document IR and emits Markdown text."""
from __future__ import annotations
import os
from doc2md.ir.nodes import (
    Document, Heading, Paragraph, Span,
    Table, Cell, Image, Formula, CodeBlock,
    List, ListItem, FidelityWarning, Node,
)


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
                return f"> **Warning:** {node.reason}"
            case _:
                return ""

    def _heading(self, node: Heading) -> str:
        return f"{'#' * node.level} {node.text}"

    def _spans(self, spans: list[Span]) -> str:
        out = []
        for s in spans:
            text = s.text
            if s.code:
                text = f"`{text}`"
            if s.bold:
                text = f"**{text}**"
            if s.italic:
                text = f"_{text}_"
            if s.link_href:
                text = f"[{text}]({s.link_href})"
            out.append(text)
        return "".join(out)

    def _paragraph(self, node: Paragraph) -> str:
        return self._spans(node.spans)

    def _table(self, node: Table) -> str:
        lines: list[str] = []

        if node.merged_cells:
            lines.append("> _Note: this table has merged cells; structure is approximated._")

        if node.caption:
            lines.append(f"**{node.caption}**")

        # Use first header row, fall back to column indices
        if node.headers:
            header_row = node.headers[0]
            col_count = len(header_row)
            lines.append("| " + " | ".join(c.text for c in header_row) + " |")
        elif node.rows:
            col_count = len(node.rows[0])
            lines.append("| " + " | ".join(str(i) for i in range(col_count)) + " |")
        else:
            return ""

        lines.append("| " + " | ".join("---" for _ in range(col_count)) + " |")

        for row in node.rows:
            lines.append("| " + " | ".join(c.text for c in row) + " |")

        return "\n".join(lines)

    def _image(self, node: Image) -> str:
        self._image_counter += 1
        label = node.caption or node.alt or f"image-{self._image_counter}"
        path = os.path.join(self._image_dir, f"{self._image_counter:03d}.png")
        return f"![{label}]({path})"

    def _formula(self, node: Formula) -> str:
        if node.inline:
            return f"${node.latex}$"
        return f"$$\n{node.latex}\n$$"

    def _code_block(self, node: CodeBlock) -> str:
        return f"```{node.language}\n{node.text}\n```"

    def _list(self, node: List, indent: int) -> str:
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
