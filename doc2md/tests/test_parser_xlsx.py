"""Phase 3 RED: XLSX parser produces correct IR nodes."""
import pytest
from pathlib import Path
from doc2md.parsers.xlsx import XlsxParser
from doc2md.ir.nodes import Document, Table

FIXTURE = Path(__file__).parent / "fixtures" / "sample.xlsx"


@pytest.fixture
def doc() -> Document:
    return XlsxParser().parse(FIXTURE)


def test_returns_document(doc):
    assert isinstance(doc, Document)


def test_source_format(doc):
    assert doc.source_format == "xlsx"


def test_produces_table(doc):
    tables = [n for n in doc.nodes if isinstance(n, Table)]
    assert len(tables) >= 1


def test_header_row_detected(doc):
    tables = [n for n in doc.nodes if isinstance(n, Table)]
    t = tables[0]
    assert t.headers, "Expected at least one header row"
    header_texts = [c.text for c in t.headers[0]]
    assert "Region" in header_texts
    assert "Q1" in header_texts


def test_data_rows_present(doc):
    tables = [n for n in doc.nodes if isinstance(n, Table)]
    t = tables[0]
    assert len(t.rows) >= 1


def test_merged_cells_detected(doc):
    tables = [n for n in doc.nodes if isinstance(n, Table)]
    t = tables[0]
    assert len(t.merged_cells) >= 1, "Expected at least one merged cell range"


def test_merged_cell_tuple_format(doc):
    tables = [n for n in doc.nodes if isinstance(n, Table)]
    t = tables[0]
    for mc in t.merged_cells:
        assert len(mc) == 4, "Merged cell should be (r1, c1, r2, c2)"


def test_table_caption_is_sheet_name(doc):
    tables = [n for n in doc.nodes if isinstance(n, Table)]
    t = tables[0]
    assert t.caption == "Sales"


def test_numeric_values_as_strings(doc):
    tables = [n for n in doc.nodes if isinstance(n, Table)]
    t = tables[0]
    all_texts = [c.text for row in t.rows for c in row]
    assert any(v in all_texts for v in ["100", "200", "90"])
