"""Abstract base parser."""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from doc2md.ir.nodes import Document


class BaseParser(ABC):
    @abstractmethod
    def parse(self, path: Path) -> Document: ...
