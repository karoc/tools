"""Scan CPA auth JSON files for invalidated authentication markers."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .constants import (
    INVALIDATED_ERROR_CODE,
    INVALIDATED_ERROR_MESSAGE,
    INVALIDATED_ERROR_TYPE,
)
from .models import InvalidAuthFile, ScanReport, SkippedFile


def scan_auth_dir(auth_dir: Path, recursive: bool = True) -> ScanReport:
    auth_dir = auth_dir.expanduser()
    if not auth_dir.exists():
        raise FileNotFoundError(f"auth directory does not exist: {auth_dir}")
    if not auth_dir.is_dir():
        raise NotADirectoryError(f"auth path is not a directory: {auth_dir}")

    invalid_files = []  # type: List[InvalidAuthFile]
    skipped_files = []  # type: List[SkippedFile]
    scanned_json_files = 0

    for path in iter_json_files(auth_dir, recursive=recursive):
        scanned_json_files += 1
        payload = read_json_object(path, skipped_files)
        if payload is None:
            continue
        if is_invalidated_auth_payload(payload):
            invalid_files.append(build_invalid_auth_file(auth_dir, path, payload))

    return ScanReport(
        auth_dir=auth_dir,
        scanned_json_files=scanned_json_files,
        invalid_files=tuple(invalid_files),
        skipped_files=tuple(skipped_files),
    )


def iter_json_files(auth_dir: Path, recursive: bool) -> Iterable[Path]:
    if recursive:
        for root, _dirs, files in os.walk(auth_dir):
            for file_name in sorted(files, key=str.lower):
                if file_name.lower().endswith(".json"):
                    yield Path(root) / file_name
        return

    for entry in sorted(auth_dir.iterdir(), key=lambda p: p.name.lower()):
        if entry.is_file() and entry.name.lower().endswith(".json"):
            yield entry


def read_json_object(path: Path, skipped_files: List[SkippedFile]) -> Optional[Dict[str, Any]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        skipped_files.append(SkippedFile(path=path, reason=f"read_error: {exc}"))
        return None

    if raw.strip() == "":
        skipped_files.append(SkippedFile(path=path, reason="empty_file"))
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        skipped_files.append(SkippedFile(path=path, reason=f"invalid_json: {exc.msg}"))
        return None

    if not isinstance(payload, dict):
        skipped_files.append(SkippedFile(path=path, reason="json_root_not_object"))
        return None
    return payload


def is_invalidated_auth_payload(payload: Dict[str, Any]) -> bool:
    error = payload.get("error")
    if not isinstance(error, dict):
        return False
    return (
        error.get("message") == INVALIDATED_ERROR_MESSAGE
        and error.get("type") == INVALIDATED_ERROR_TYPE
        and error.get("code") == INVALIDATED_ERROR_CODE
    )


def build_invalid_auth_file(
    auth_dir: Path, path: Path, payload: Dict[str, Any]
) -> InvalidAuthFile:
    error = payload["error"]
    return InvalidAuthFile(
        path=path,
        relative_path=safe_relative_path(auth_dir, path),
        provider=string_field(payload, "type"),
        email=string_field(payload, "email"),
        project_id=string_field(payload, "project_id"),
        error_message=error["message"],
        error_type=error["type"],
        error_code=error["code"],
    )


def string_field(payload: Dict[str, Any], key: str) -> Optional[str]:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return None


def safe_relative_path(base: Path, path: Path) -> Path:
    try:
        return path.relative_to(base)
    except ValueError:
        return Path(path.name)
