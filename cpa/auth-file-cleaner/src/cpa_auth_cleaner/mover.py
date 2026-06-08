"""Move invalidated CPA auth files out of the active auth directory."""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Tuple

from .models import InvalidAuthFile, MoveRecord


def default_move_dir(auth_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return auth_dir.parent / f"{auth_dir.name}-invalidated" / timestamp


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
    validate_move_dir(auth_dir, move_dir)

    records = []
    for item in invalid_files:
        destination = unique_destination(move_dir / item.relative_path)
        records.append(MoveRecord(source=item.path, destination=destination, moved=not dry_run))
        if dry_run:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(item.path), str(destination))
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
