"""Phase 1 RED: Markdown renderer output."""
import pytest
from doc2md.ir.nodes import (
    Document, Heading, Paragraph, Span,
    Table, Cell, Image, Formula, CodeBlock,
    List, ListItem,
)
from doc2md.renderers.markdown import MarkdownRenderer


@pytest.fixture
def render():
    r = MarkdownRenderer()
    def _render(nodes):
        doc = Document(nodes=nodes)
        return r.render(doc)
    return _render


def test_heading_levels(render):
    for level in range(1, 4):
        out = render([Heading(level=level, text="Hi")])
        assert out.strip().startswith("#" * level + " Hi")


def test_paragraph_plain(render):
    out = render([Paragraph(spans=[Span(text="Hello world")])])
    assert "Hello world" in out


def test_paragraph_bold(render):
    out = render([Paragraph(spans=[Span(text="bold", bold=True)])])
    assert "**bold**" in out


def test_paragraph_italic(render):
    out = render([Paragraph(spans=[Span(text="em", italic=True)])])
    assert "_em_" in out


def test_paragraph_inline_code(render):
    out = render([Paragraph(spans=[Span(text="x", code=True)])])
    assert "`x`" in out


def test_paragraph_link(render):
    out = render([Paragraph(spans=[Span(text="click", link_href="https://example.com")])])
    assert "[click](https://example.com)" in out


def test_table_basic(render):
    out = render([Table(
        headers=[[Cell(text="Name"), Cell(text="Age")]],
        rows=[[Cell(text="Alice"), Cell(text="30")]],
    )])
    assert "| Name | Age |" in out
    assert "| Alice | 30 |" in out
    assert "| --- |" in out


def test_table_merged_cell_warning(render):
    out = render([Table(
        headers=[[Cell(text="A"), Cell(text="B")]],
        rows=[],
        merged_cells=[(0, 0, 0, 1)],
    )])
    assert "merged" in out.lower()


def test_image(render):
    out = render([Image(data=b"", alt="chart", caption="Figure 1")])
    assert "![Figure 1]" in out or "![chart]" in out


def test_formula_inline(render):
    out = render([Paragraph(spans=[Span(text="")]),
                  Formula(latex=r"\pi", inline=True)])
    assert r"$\pi$" in out


def test_formula_block(render):
    out = render([Formula(latex=r"\frac{a}{b}", inline=False)])
    assert r"$$" in out


def test_code_block(render):
    out = render([CodeBlock(text="x = 1", language="python")])
    assert "```python" in out
    assert "x = 1" in out


def test_unordered_list(render):
    out = render([List(ordered=False, items=[
        ListItem(spans=[Span(text="apple")]),
        ListItem(spans=[Span(text="banana")]),
    ])])
    assert "- apple" in out
    assert "- banana" in out


def test_ordered_list(render):
    out = render([List(ordered=True, items=[
        ListItem(spans=[Span(text="first")]),
        ListItem(spans=[Span(text="second")]),
    ])])
    assert "1. first" in out
    assert "2. second" in out


def test_nested_list(render):
    child = ListItem(spans=[Span(text="child")])
    parent = ListItem(spans=[Span(text="parent")], children=[child])
    out = render([List(ordered=False, items=[parent])])
    assert "- parent" in out
    assert "  - child" in out


def test_multiple_nodes_separated(render):
    out = render([
        Heading(level=1, text="Title"),
        Paragraph(spans=[Span(text="Body")]),
    ])
    assert "# Title" in out
    assert "Body" in out
