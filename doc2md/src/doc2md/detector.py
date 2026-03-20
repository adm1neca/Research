"""Format detection by magic bytes and file extension."""
from __future__ import annotations
from pathlib import Path

_MAGIC: list[tuple[bytes, str]] = [
    (b"%PDF",         "pdf"),
    (b"PK\x03\x04",  "zip"),  # DOCX/XLSX are ZIP-based
]

_EXT_MAP: dict[str, str] = {
    ".pdf":  "pdf",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".xls":  "xlsx",
    ".doc":  "docx",
}


def detect_format(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _EXT_MAP:
        return _EXT_MAP[ext]

    with open(path, "rb") as f:
        header = f.read(8)
    for magic, fmt in _MAGIC:
        if header.startswith(magic):
            return fmt

    raise ValueError(f"Unsupported or undetected format for: {path}")
