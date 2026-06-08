"""Data models used by the CPA auth cleaner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class InvalidAuthFile:
    path: Path
    relative_path: Path
    provider: Optional[str]
    email: Optional[str]
    project_id: Optional[str]
    error_message: str
    error_type: str
    error_code: str


@dataclass(frozen=True)
class SkippedFile:
    path: Path
    reason: str


@dataclass(frozen=True)
class ScanReport:
    auth_dir: Path
    scanned_json_files: int
    invalid_files: tuple[InvalidAuthFile, ...]
    skipped_files: tuple[SkippedFile, ...]


@dataclass(frozen=True)
class MoveRecord:
    source: Path
    destination: Path
    moved: bool

