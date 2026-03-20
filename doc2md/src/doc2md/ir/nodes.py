"""Document Intermediate Representation — typed node tree."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Span:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    link_href: str | None = None


@dataclass
class Heading:
    level: int
    text: str
    anchor: str | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.level <= 6:
            raise ValueError(f"Heading level must be 1–6, got {self.level}")


@dataclass
class Paragraph:
    spans: list[Span] = field(default_factory=list)


@dataclass
class Cell:
    text: str
    colspan: int = 1
    rowspan: int = 1


@dataclass
class Table:
    headers: list[list[Cell]] = field(default_factory=list)
    rows: list[list[Cell]] = field(default_factory=list)
    merged_cells: list[tuple[int, int, int, int]] = field(default_factory=list)
    caption: str | None = None


@dataclass
class Image:
    data: bytes
    alt: str = ""
    caption: str | None = None
    position: Any = None


@dataclass
class Formula:
    latex: str
    inline: bool = False


@dataclass
class CodeBlock:
    text: str
    language: str = ""


@dataclass
class ListItem:
    spans: list[Span] = field(default_factory=list)
    children: list[ListItem] = field(default_factory=list)


@dataclass
class List:
    ordered: bool
    items: list[ListItem] = field(default_factory=list)


@dataclass
class FidelityWarning:
    node_type: str
    reason: str


# Union of all node types
Node = Heading | Paragraph | Table | Image | Formula | CodeBlock | List | FidelityWarning


@dataclass
class Document:
    nodes: list[Node] = field(default_factory=list)
    title: str | None = None
    author: str | None = None
    created_at: str | None = None
    source_format: str | None = None
    source_path: str | None = None
    warnings: list[FidelityWarning] = field(default_factory=list)
