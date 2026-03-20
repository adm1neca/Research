"""Phase 4 RED: PDF parser produces correct IR nodes."""
import pytest
from pathlib import Path
from doc2md.parsers.pdf import PdfParser
from doc2md.ir.nodes import Document, Heading, Paragraph

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


@pytest.fixture
def doc() -> Document:
    return PdfParser().parse(FIXTURE)


def test_returns_document(doc):
    assert isinstance(doc, Document)


def test_source_format(doc):
    assert doc.source_format == "pdf"


def test_produces_nodes(doc):
    assert len(doc.nodes) > 0


def test_detects_title_as_heading(doc):
    headings = [n for n in doc.nodes if isinstance(n, Heading)]
    assert len(headings) >= 1
    texts = [h.text for h in headings]
    assert any("Research" in t for t in texts)


def test_detects_section_headings(doc):
    headings = [n for n in doc.nodes if isinstance(n, Heading)]
    texts = [h.text for h in headings]
    assert any("Introduction" in t or "Methods" in t for t in texts)


def test_heading_hierarchy(doc):
    headings = [n for n in doc.nodes if isinstance(n, Heading)]
    levels = [h.level for h in headings]
    # Title should be level 1, sections level 2
    assert 1 in levels


def test_body_text_as_paragraphs(doc):
    paragraphs = [n for n in doc.nodes if isinstance(n, Paragraph)]
    assert len(paragraphs) >= 1


def test_paragraph_text_content(doc):
    paragraphs = [n for n in doc.nodes if isinstance(n, Paragraph)]
    all_text = " ".join(s.text for p in paragraphs for s in p.spans)
    assert "findings" in all_text.lower() or "data" in all_text.lower()


def test_no_empty_paragraphs(doc):
    paragraphs = [n for n in doc.nodes if isinstance(n, Paragraph)]
    for p in paragraphs:
        combined = "".join(s.text for s in p.spans).strip()
        assert combined, "Found empty paragraph in output"
