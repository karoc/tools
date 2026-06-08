"""Format scan and move results for CLI output."""

import json
from pathlib import Path
from typing import Tuple

from .models import MoveRecord, ScanReport


def render_text_report(report: ScanReport, records: Tuple[MoveRecord, ...], dry_run: bool) -> str:
    lines = [
        f"Source: {getattr(report, 'source', 'file-marker')}",
        f"Auth dir: {report.auth_dir}",
        f"Mode: {'dry-run' if dry_run else 'execute'}",
        f"Scanned JSON files: {report.scanned_json_files}",
        f"Invalidated auth files: {len(report.invalid_files)}",
        f"Skipped files: {len(report.skipped_files)}",
    ]

    if report.invalid_files:
        lines.append("")
        lines.append("Matches:")
        for item in report.invalid_files:
            detail = compact_detail(
                provider=item.provider,
                email=item.email,
                project_id=item.project_id,
            )
            lines.append(f"  - {item.relative_path}{detail}")

    if records:
        lines.append("")
        lines.append("Move plan:" if dry_run else "Moved:")
        for record in records:
            lines.append(f"  - {record.source} -> {record.destination}")

    if dry_run and report.invalid_files:
        lines.append("")
        lines.append("Dry-run only. Add --execute to move matched files.")

    if report.skipped_files:
        lines.append("")
        lines.append("Skipped:")
        for skipped in report.skipped_files:
            lines.append(f"  - {skipped.path}: {skipped.reason}")

    return "\n".join(lines)


def render_json_report(report: ScanReport, records: Tuple[MoveRecord, ...], dry_run: bool) -> str:
    payload = {
        "source": getattr(report, "source", "file-marker"),
        "auth_dir": str(report.auth_dir),
        "mode": "dry-run" if dry_run else "execute",
        "scanned_json_files": report.scanned_json_files,
        "invalidated_count": len(report.invalid_files),
        "skipped_count": len(report.skipped_files),
        "invalidated_files": [
            {
                "path": str(item.path),
                "relative_path": str(item.relative_path),
                "provider": item.provider,
                "email": item.email,
                "project_id": item.project_id,
                "error": {
                    "message": item.error_message,
                    "type": item.error_type,
                    "code": item.error_code,
                },
            }
            for item in report.invalid_files
        ],
        "moves": [
            {
                "source": str(record.source),
                "destination": str(record.destination),
                "moved": record.moved,
            }
            for record in records
        ],
        "skipped_files": [
            {"path": str(skipped.path), "reason": skipped.reason}
            for skipped in report.skipped_files
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def compact_detail(**values) -> str:
    parts = [f"{key}={value}" for key, value in values.items() if value]
    if not parts:
        return ""
    return f" ({', '.join(parts)})"


def display_path(path: Path) -> str:
    return str(path)
