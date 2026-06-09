"""Move invalidated CPA auth files out of the active auth directory."""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Tuple

from .models import InvalidAuthFile, MoveRecord


def default_move_dir(auth_dir: Path) -> Path:
    now = datetime.now()
    return (
        auth_dir.parent
        / f"{auth_dir.name}-invalidated"
        / now.strftime("%Y%m%d")
        / now.strftime("%H%M%S")
    )


def validate_move_dir(auth_dir: Path, move_dir: Path) -> None:
    resolved_auth_dir = normalized_path(auth_dir)
    resolved_move_dir = normalized_path(move_dir)
    if resolved_move_dir == resolved_auth_dir:
        raise ValueError("move directory must not be the auth directory")
    if is_relative_to(resolved_move_dir, resolved_auth_dir):
        raise ValueError("move directory must not be inside the auth directory")


def move_invalid_files(
    auth_dir: Path,
    invalid_files: Tuple[InvalidAuthFile, ...],
    move_dir: Path,
    dry_run: bool,
) -> Tuple[MoveRecord, ...]:
    auth_dir = auth_dir.expanduser()
    if not auth_dir.exists():
        raise FileNotFoundError(f"auth directory does not exist: {auth_dir}")
    if not auth_dir.is_dir():
        raise NotADirectoryError(f"auth path is not a directory: {auth_dir}")
    validate_move_dir(auth_dir, move_dir)

    records = []
    for item in invalid_files:
        relative_path = validate_relative_auth_path(item.relative_path)
        source = Path(item.path).expanduser()
        ensure_child_path(auth_dir, source, "source path")
        destination = unique_destination(move_dir / relative_path)
        ensure_child_path(move_dir, destination, "destination path")

        if not source.exists():
            records.append(
                MoveRecord(
                    source=source,
                    destination=destination,
                    moved=False,
                    skip_reason="source_missing",
                )
            )
            continue

        records.append(MoveRecord(source=source, destination=destination, moved=not dry_run))
        if dry_run:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
    return tuple(records)


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path

    parent = path.parent
    stem = path.stem
    suffix = path.suffix
    index = 1
    while True:
        candidate = parent / f"{stem}.{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def normalized_path(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def validate_relative_auth_path(path: Path) -> Path:
    relative = Path(path)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("invalid relative auth file path: %s" % path)
    return relative


def ensure_child_path(base: Path, path: Path, label: str) -> None:
    resolved_base = normalized_path(base)
    resolved_path = normalized_path(path)
    if not is_relative_to(resolved_path, resolved_base):
        raise ValueError("%s must stay inside base directory: %s" % (label, path))
