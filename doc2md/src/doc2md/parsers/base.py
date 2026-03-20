"""Abstract base parser."""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from doc2md.ir.nodes import Document

# SEC-04: reject files larger than this to prevent memory exhaustion
MAX_FILE_BYTES = 100 * 1024 * 1024  # 100 MB


def check_file_size(path: Path) -> None:
    """Raise ValueError if the file exceeds MAX_FILE_BYTES."""
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ValueError(
            f"File too large ({size} bytes); maximum allowed is {MAX_FILE_BYTES} bytes."
        )


class BaseParser(ABC):
    @abstractmethod
    def parse(self, path: Path) -> Document: ...
