"""Phase 2 RED: DOCX parser produces correct IR nodes."""
import pytest
from pathlib import Path
from doc2md.parsers.docx import DocxParser
from doc2md.ir.nodes import Document, Heading, Paragraph, Table

FIXTURE = Path(__file__).parent / "fixtures" / "sample.docx"


@pytest.fixture
def doc() -> Document:
    return DocxParser().parse(FIXTURE)


def test_returns_document(doc):
    assert isinstance(doc, Document)


def test_source_format(doc):
    assert doc.source_format == "docx"


def test_detects_h1(doc):
    headings = [n for n in doc.nodes if isinstance(n, Heading) and n.level == 1]
    assert len(headings) >= 1
    assert headings[0].text == "Research Overview"


def test_detects_h2(doc):
    h2s = [n for n in doc.nodes if isinstance(n, Heading) and n.level == 2]
    assert len(h2s) >= 2


def test_detects_bold_span(doc):
    from doc2md.ir.nodes import Span
    paragraphs = [n for n in doc.nodes if isinstance(n, Paragraph)]
    all_spans = [s for p in paragraphs for s in p.spans]
    bold_spans = [s for s in all_spans if s.bold]
    assert any("bold" in s.text.lower() for s in bold_spans)


def test_detects_italic_span(doc):
    paragraphs = [n for n in doc.nodes if isinstance(n, Paragraph)]
    all_spans = [s for p in paragraphs for s in p.spans]
    italic_spans = [s for s in all_spans if s.italic]
    assert any("italic" in s.text.lower() for s in italic_spans)


def test_table_extracted(doc):
    tables = [n for n in doc.nodes if isinstance(n, Table)]
    assert len(tables) >= 1


def test_table_headers(doc):
    tables = [n for n in doc.nodes if isinstance(n, Table)]
    t = tables[0]
    header_texts = [c.text for c in t.headers[0]]
    assert "Name" in header_texts
    assert "Score" in header_texts


def test_table_rows(doc):
    tables = [n for n in doc.nodes if isinstance(n, Table)]
    t = tables[0]
    assert len(t.rows) == 2
    row_texts = [c.text for c in t.rows[0]]
    assert "Alice" in row_texts


def test_node_order(doc):
    # Heading before first paragraph
    types = [type(n).__name__ for n in doc.nodes]
    assert types[0] == "Heading"
