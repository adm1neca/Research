"""FidelityScorer — quantitative metric for Markdown conversion quality."""
from __future__ import annotations
import re


def _headings(md: str) -> list[tuple[int, str]]:
    out = []
    for line in md.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            out.append((len(m.group(1)), m.group(2).strip()))
    return out


def _table_rows(md: str) -> list[str]:
    return [
        line for line in md.splitlines()
        if re.match(r"^\|", line) and "---" not in line
    ]


def _plain_words(md: str) -> set[str]:
    clean = re.sub(r"[#|`*_\[\]()>]", " ", md)
    return set(w.lower() for w in clean.split() if w.isalpha())


class FidelityScorer:
    def __init__(self, reference: str, converted: str) -> None:
        self._ref = reference
        self._conv = converted

    def heading_score(self) -> float:
        ref_h  = _headings(self._ref)
        conv_h = _headings(self._conv)
        if not ref_h:
            return 1.0
        if not conv_h:
            return 0.0
        matches = sum(1 for h in conv_h if h in ref_h)
        return min(matches / len(ref_h), 1.0)

    def table_score(self) -> float:
        ref_rows  = _table_rows(self._ref)
        conv_rows = _table_rows(self._conv)
        if not ref_rows:
            return 1.0
        if not conv_rows:
            return 0.0
        matches = sum(1 for r in conv_rows if r in ref_rows)
        return min(matches / len(ref_rows), 1.0)

    def text_score(self) -> float:
        ref_words  = _plain_words(self._ref)
        conv_words = _plain_words(self._conv)
        if not ref_words:
            return 1.0
        if not conv_words:
            return 0.0
        overlap = ref_words & conv_words
        return len(overlap) / len(ref_words)

    def score(self) -> float:
        if not self._conv.strip():
            return 0.0
        return (
            0.35 * self.heading_score()
            + 0.35 * self.table_score()
            + 0.30 * self.text_score()
        )

    def report(self) -> dict[str, float]:
        return {
            "overall": round(self.score(), 4),
            "heading": round(self.heading_score(), 4),
            "table":   round(self.table_score(), 4),
            "text":    round(self.text_score(), 4),
        }
