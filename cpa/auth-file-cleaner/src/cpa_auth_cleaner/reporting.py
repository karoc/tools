"""Format scan and move results for CLI output."""

import json
from pathlib import Path
from typing import Tuple

from .execution import dry_run_verification, move_summary, post_scan_file_state, scan_summary
from .models import MoveRecord, ScanReport


def render_text_report(
    report: ScanReport,
    records: Tuple[MoveRecord, ...],
    dry_run: bool,
    move_dir=None,
    post_report=None,
    post_scan_error="",
    quarantine=None,
    verification=None,
) -> str:
    pre_summary = scan_summary(report)
    moves = move_summary(records)
    lines = [
        f"Source: {getattr(report, 'source', 'file-marker')}",
        f"Auth dir: {report.auth_dir}",
        f"Mode: {'dry-run' if dry_run else 'execute'}",
        f"Move dir: {move_dir or ''}",
        f"Scanned JSON files: {report.scanned_json_files}",
        f"Invalidated auth files: {len(report.invalid_files)}",
        f"Skipped files: {len(report.skipped_files)}",
    ]

    lines.append("")
    lines.append("Summary:")
    lines.append(f"  Planned moves: {moves['planned_count']}")
    lines.append(f"  Moved files: {moves['moved_count']}")
    lines.append(f"  Not moved: {moves['not_moved_count']}")
    lines.append(f"  Providers: {format_counts(pre_summary['provider_counts'])}")
    lines.append(f"  Error codes: {format_counts(pre_summary['error_code_counts'])}")

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

    if not dry_run:
        lines.append("")
        lines.append("Post-move verification:")
        if post_report is not None:
            lines.append(f"  Post-scan invalidated auth files: {len(post_report.invalid_files)}")
            file_state = post_scan_file_state(post_report)
            lines.append(f"  Post-scan active files still present: {file_state['active_file_count']}")
            lines.append(
                f"  Post-scan management-only stale entries: {file_state['management_only_count']}"
            )
        if post_scan_error:
            lines.append(f"  Post-scan error: {post_scan_error}")
        if quarantine:
            lines.append(f"  Quarantine dir: {quarantine['directory']}")
            lines.append(f"  Quarantine files: {quarantine['file_count']}")
            lines.append(f"  Quarantine JSON files: {quarantine['json_file_count']}")
            lines.append(
                f"  Confirmed moved destinations: {quarantine['confirmed_destination_count']}"
            )
        if verification:
            lines.append(f"  Verification: {verification.get('status', 'failed')}")

    if report.skipped_files:
        lines.append("")
        lines.append("Skipped:")
        for skipped in report.skipped_files:
            lines.append(f"  - {skipped.path}: {skipped.reason}")

    return "\n".join(lines)


def render_json_report(
    report: ScanReport,
    records: Tuple[MoveRecord, ...],
    dry_run: bool,
    move_dir=None,
    post_report=None,
    post_scan_error="",
    quarantine=None,
    verification=None,
) -> str:
    pre_summary = scan_summary(report)
    payload = {
        "source": getattr(report, "source", "file-marker"),
        "auth_dir": str(report.auth_dir),
        "mode": "dry-run" if dry_run else "execute",
        "move_dir": str(move_dir) if move_dir else "",
        "scanned_json_files": report.scanned_json_files,
        "invalidated_count": len(report.invalid_files),
        "skipped_count": len(report.skipped_files),
        "pre_scan": pre_summary,
        "move_summary": move_summary(records),
        "post_scan": scan_summary(post_report) if post_report is not None else None,
        "post_scan_file_state": post_scan_file_state(post_report),
        "post_scan_error": post_scan_error or None,
        "quarantine_summary": quarantine,
        "verification": verification if verification is not None else dry_run_verification(),
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


def format_counts(counts) -> str:
    if not counts:
        return "-"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def display_path(path: Path) -> str:
    return str(path)
