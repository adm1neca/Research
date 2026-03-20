"""Phase 5 RED: FidelityScorer returns meaningful 0.0–1.0 scores."""
import pytest
from doc2md.scorer import FidelityScorer


PERFECT = "# Title\n\nBody text.\n\n| A | B |\n| --- | --- |\n| 1 | 2 |"
EMPTY   = ""
PARTIAL = "# Title\n\nBody text."
WRONG   = "Some random text with no structure"


def test_perfect_match():
    s = FidelityScorer(PERFECT, PERFECT)
    assert s.score() == pytest.approx(1.0)


def test_empty_converted_is_zero():
    s = FidelityScorer(PERFECT, EMPTY)
    assert s.score() == pytest.approx(0.0)


def test_partial_is_between():
    s = FidelityScorer(PERFECT, PARTIAL)
    score = s.score()
    assert 0.0 < score < 1.0


def test_score_in_range():
    for ref, conv in [(PERFECT, WRONG), (PERFECT, PARTIAL), (PARTIAL, PERFECT)]:
        score = FidelityScorer(ref, conv).score()
        assert 0.0 <= score <= 1.0


def test_heading_score_perfect():
    ref  = "# H1\n\n## H2\n\n### H3"
    conv = "# H1\n\n## H2\n\n### H3"
    s = FidelityScorer(ref, conv)
    assert s.heading_score() == pytest.approx(1.0)


def test_heading_score_zero():
    s = FidelityScorer("# H1\n\n## H2", "No headings here")
    assert s.heading_score() == pytest.approx(0.0)


def test_table_score_perfect():
    ref  = "| A | B |\n| --- | --- |\n| 1 | 2 |"
    conv = "| A | B |\n| --- | --- |\n| 1 | 2 |"
    s = FidelityScorer(ref, conv)
    assert s.table_score() == pytest.approx(1.0)


def test_table_score_missing():
    s = FidelityScorer("| A | B |\n| --- | --- |", "No table here")
    assert s.table_score() == pytest.approx(0.0)


def test_score_report_keys():
    s = FidelityScorer(PERFECT, PARTIAL)
    report = s.report()
    assert "overall" in report
    assert "heading" in report
    assert "table" in report
    assert "text" in report
