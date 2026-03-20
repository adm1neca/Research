"""DOCX parser — style-aware conversion to Document IR."""
from __future__ import annotations
from pathlib import Path
from doc2md.parsers.base import BaseParser, check_file_size
from doc2md.ir.nodes import (
    Document, Heading, Paragraph, Span, Table, Cell, List, ListItem,
)

try:
    from docx import Document as DocxDocument  # type: ignore
    from docx.oxml.ns import qn  # type: ignore
except ImportError as e:
    raise ImportError("Install python-docx: uv add python-docx") from e

# Map Word built-in style names → heading level
_HEADING_STYLES: dict[str, int] = {
    f"heading {i}": i for i in range(1, 7)
}
_LIST_STYLES = {"list bullet", "list bullet 2", "list number", "list number 2"}


class DocxParser(BaseParser):
    def parse(self, path: Path) -> Document:
        # SEC-04: reject oversized files before loading into memory
        check_file_size(path)
        raw = DocxDocument(str(path))
        nodes = []

        for block in raw.element.body:
            tag = block.tag.split("}")[-1] if "}" in block.tag else block.tag

            if tag == "p":
                node = self._parse_paragraph(block, raw)
                if node is not None:
                    nodes.append(node)
            elif tag == "tbl":
                nodes.append(self._parse_table(block, raw))

        return Document(
            nodes=nodes,
            source_format="docx",
            source_path=path.name,  # SEC-09: filename only, no full path
        )

    def _parse_paragraph(self, elem, raw):
        from docx.text.paragraph import Paragraph as DocxPara  # type: ignore
        para = DocxPara(elem, raw)
        style_name = (para.style.name or "").lower()

        if style_name in _HEADING_STYLES:
            return Heading(level=_HEADING_STYLES[style_name], text=para.text.strip())

        if not para.text.strip():
            return None

        if style_name in _LIST_STYLES:
            ordered = "number" in style_name
            item = ListItem(spans=self._runs_to_spans(para.runs))
            return List(ordered=ordered, items=[item])

        return Paragraph(spans=self._runs_to_spans(para.runs))

    def _runs_to_spans(self, runs) -> list[Span]:
        spans = []
        for run in runs:
            if not run.text:
                continue
            href = None
            # Check for hyperlink parent
            parent = run._element.getparent()
            if parent is not None and parent.tag.endswith("}hyperlink"):
                rel_id = parent.get(qn("r:id"))
                try:
                    href = run.part.rels[rel_id].target_ref
                except Exception:
                    href = None
            spans.append(Span(
                text=run.text,
                bold=bool(run.bold),
                italic=bool(run.italic),
                code=run.style.name.lower() == "code" if run.style else False,
                link_href=href,
            ))
        return spans or [Span(text="")]

    def _parse_table(self, elem, raw) -> Table:
        from docx.table import Table as DocxTable  # type: ignore
        tbl = DocxTable(elem, raw)

        if not tbl.rows:
            return Table()

        first_row = [Cell(text=c.text.strip()) for c in tbl.rows[0].cells]
        data_rows = [
            [Cell(text=c.text.strip()) for c in row.cells]
            for row in tbl.rows[1:]
        ]
        return Table(headers=[first_row], rows=data_rows)
