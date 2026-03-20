"""PDF parser — font-size heuristic heading detection + pdfplumber tables."""
from __future__ import annotations
import logging
import statistics
from pathlib import Path
from doc2md.parsers.base import BaseParser, check_file_size
from doc2md.ir.nodes import (
    Document, Heading, Paragraph, Span, Table, Cell, Image, FidelityWarning,
)

try:
    import pymupdf  # type: ignore
except ImportError as e:
    raise ImportError("Install pymupdf: uv add pymupdf") from e

try:
    import pdfplumber  # type: ignore
except ImportError as e:
    raise ImportError("Install pdfplumber: uv add pdfplumber") from e

_log = logging.getLogger(__name__)


class PdfParser(BaseParser):
    def parse(self, path: Path) -> Document:
        # SEC-04: reject oversized files before loading into memory
        check_file_size(path)
        nodes = []
        warnings = []

        # Use pdfplumber for table detection (better bounding-box accuracy)
        plumber_tables: dict[int, list] = {}
        with pdfplumber.open(str(path)) as plumb:
            for pg_num, pg in enumerate(plumb.pages):
                tbls = pg.extract_tables()
                if tbls:
                    plumber_tables[pg_num] = tbls

        with pymupdf.open(str(path)) as pdf:
            body_size = self._estimate_body_size(pdf)

            for pg_num, page in enumerate(pdf):
                # Insert extracted tables first keyed to this page
                if pg_num in plumber_tables:
                    for raw_table in plumber_tables[pg_num]:
                        nodes.append(self._convert_table(raw_table))

                blocks = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)["blocks"]
                image_counter = 0

                for block in blocks:
                    if block["type"] == 1:  # image block
                        try:
                            xref = block.get("xref", 0)
                            if xref:
                                img_data = pdf.extract_image(xref)
                                nodes.append(Image(
                                    data=img_data["image"],
                                    alt=f"image-p{pg_num + 1}-{image_counter}",
                                ))
                                image_counter += 1
                        except Exception as exc:
                            # SEC-10: log instead of silently swallowing
                            _log.warning("PDF image extraction failed (xref=%s): %s", block.get("xref"), exc)
                        continue

                    if block["type"] != 0:
                        continue

                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span["text"].strip()
                            if not text:
                                continue
                            size = span.get("size", body_size)
                            node = self._classify_span(text, size, body_size)
                            nodes.append(node)

        return Document(
            nodes=nodes,
            source_format="pdf",
            source_path=path.name,  # SEC-09: filename only, no full path
            warnings=warnings,
        )

    def _estimate_body_size(self, pdf) -> float:
        sizes: list[float] = []
        for page in pdf:
            for block in page.get_text("dict")["blocks"]:
                if block["type"] != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span["text"].strip():
                            sizes.append(span["size"])
        if not sizes:
            return 11.0
        # Use the smallest common size: body text is always the smallest font
        return min(sizes)

    def _classify_span(self, text: str, size: float, body_size: float):
        ratio = size / body_size if body_size else 1.0
        if ratio >= 1.8:
            return Heading(level=1, text=text)
        if ratio >= 1.3:
            return Heading(level=2, text=text)
        if ratio >= 1.1:
            return Heading(level=3, text=text)
        return Paragraph(spans=[Span(text=text)])

    def _convert_table(self, raw_table: list[list]) -> Table:
        if not raw_table:
            return Table()

        def clean(v) -> str:
            return "" if v is None else str(v).strip()

        header = [[Cell(text=clean(v)) for v in raw_table[0]]]
        rows = [
            [Cell(text=clean(v)) for v in row]
            for row in raw_table[1:]
            if any(v for v in row)
        ]
        return Table(headers=header, rows=rows)
