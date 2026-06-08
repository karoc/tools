"""Build execution summaries and verification checks."""

from collections import Counter
from pathlib import Path


def scan_summary(report):
    return {
        "source": getattr(report, "source", "file-marker"),
        "auth_dir": str(report.auth_dir),
        "scanned_json_files": report.scanned_json_files,
        "invalidated_count": len(report.invalid_files),
        "skipped_count": len(report.skipped_files),
        "provider_counts": count_values(item.provider for item in report.invalid_files),
        "error_type_counts": count_values(item.error_type for item in report.invalid_files),
        "error_code_counts": count_values(item.error_code for item in report.invalid_files),
        "message_counts": count_values(item.error_message for item in report.invalid_files),
    }


def move_summary(records):
    moved_count = sum(1 for record in records if record.moved)
    planned_count = len(records)
    return {
        "planned_count": planned_count,
        "moved_count": moved_count,
        "not_moved_count": planned_count - moved_count,
    }


def quarantine_summary(move_dir, records):
    moved_destinations = [Path(record.destination) for record in records if record.moved]
    missing_destinations = [
        str(destination)
        for destination in moved_destinations
        if not destination.exists()
    ]
    return {
        "directory": str(move_dir),
        "exists": Path(move_dir).exists(),
        "file_count": count_regular_files(move_dir),
        "json_file_count": count_json_files(move_dir),
        "confirmed_destination_count": len(moved_destinations) - len(missing_destinations),
        "missing_destinations": missing_destinations,
    }


def execution_verification(records, post_report, quarantine, post_scan_error=""):
    moves = move_summary(records)
    confirmed_count = 0
    missing_destinations = []
    if quarantine:
        confirmed_count = quarantine.get("confirmed_destination_count", 0)
        missing_destinations = quarantine.get("missing_destinations", [])

    checks = [
        verification_check(
            name="all_planned_moves_completed",
            ok=moves["moved_count"] == moves["planned_count"],
            expected=moves["planned_count"],
            actual=moves["moved_count"],
        ),
        verification_check(
            name="moved_destinations_exist",
            ok=confirmed_count == moves["moved_count"] and not missing_destinations,
            expected=moves["moved_count"],
            actual=confirmed_count,
        ),
    ]

    if post_scan_error:
        checks.append(
            verification_check(
                name="post_scan_completed",
                ok=False,
                expected="success",
                actual=post_scan_error,
            )
        )
    else:
        checks.append(
            verification_check(
                name="post_scan_completed",
                ok=post_report is not None,
                expected="success",
                actual="success" if post_report is not None else "not_run",
            )
        )

    remaining_count = len(post_report.invalid_files) if post_report is not None else None
    checks.append(
        verification_check(
            name="post_scan_has_no_matches",
            ok=remaining_count == 0,
            expected=0,
            actual=remaining_count,
        )
    )

    return {
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
    }


def dry_run_verification():
    return {
        "ok": None,
        "reason": "dry_run_not_executed",
        "checks": [],
    }


def verification_check(name, ok, expected, actual):
    return {
        "name": name,
        "ok": bool(ok),
        "expected": expected,
        "actual": actual,
    }


def count_values(values):
    counter = Counter()
    for value in values:
        if value:
            counter[value] += 1
    return dict(counter)


def count_regular_files(root):
    root = Path(root)
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file())


def count_json_files(root):
    root = Path(root)
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file() and path.suffix == ".json")
