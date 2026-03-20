"""Phase 1 RED: IR node construction and basic properties."""
import pytest
from doc2md.ir.nodes import (
    Document, Heading, Paragraph, Span,
    Table, Cell, Image, Formula, CodeBlock,
    List, ListItem, FidelityWarning,
)


def test_heading_level_range():
    for level in range(1, 7):
        h = Heading(level=level, text="Title")
        assert h.level == level


def test_heading_invalid_level():
    with pytest.raises(ValueError):
        Heading(level=0, text="Bad")
    with pytest.raises(ValueError):
        Heading(level=7, text="Bad")


def test_paragraph_with_spans():
    spans = [Span(text="Hello ", bold=True), Span(text="world")]
    p = Paragraph(spans=spans)
    assert len(p.spans) == 2
    assert p.spans[0].bold is True
    assert p.spans[1].bold is False


def test_span_defaults():
    s = Span(text="plain")
    assert s.bold is False
    assert s.italic is False
    assert s.code is False
    assert s.link_href is None


def test_table_basic():
    headers = [[Cell(text="Name"), Cell(text="Age")]]
    rows = [[Cell(text="Alice"), Cell(text="30")]]
    t = Table(headers=headers, rows=rows)
    assert len(t.headers[0]) == 2
    assert t.rows[0][1].text == "30"
    assert t.merged_cells == []
    assert t.caption is None


def test_table_merged_cells():
    t = Table(
        headers=[[Cell(text="A"), Cell(text="B")]],
        rows=[],
        merged_cells=[(0, 0, 0, 1)],
    )
    assert t.merged_cells == [(0, 0, 0, 1)]


def test_image_defaults():
    img = Image(data=b"\x89PNG", alt="chart")
    assert img.caption is None
    assert img.position is None


def test_formula():
    f = Formula(latex=r"\frac{a}{b}", inline=True)
    assert f.inline is True


def test_code_block():
    cb = CodeBlock(text="print('hi')", language="python")
    assert cb.language == "python"


def test_list_nested():
    inner = ListItem(spans=[Span(text="child")])
    outer = ListItem(spans=[Span(text="parent")], children=[inner])
    lst = List(ordered=False, items=[outer])
    assert lst.items[0].children[0].spans[0].text == "child"


def test_document_collects_nodes():
    doc = Document(nodes=[
        Heading(level=1, text="Hello"),
        Paragraph(spans=[Span(text="World")]),
    ])
    assert len(doc.nodes) == 2


def test_fidelity_warning():
    w = FidelityWarning(node_type="Table", reason="merged cells lost")
    assert "Table" in w.node_type


def test_document_metadata():
    doc = Document(nodes=[], title="My Doc", author="Alice")
    assert doc.title == "My Doc"
    assert doc.author == "Alice"
    assert doc.warnings == []
