"""Command line interface for the CPA auth file cleaner."""

import argparse
import sys
from pathlib import Path

from .management import (
    fetch_management_auth_files,
    management_key_from_args,
    scan_management_payload,
)
from .execution import execution_verification, quarantine_summary
from .mover import default_move_dir, move_invalid_files, validate_move_dir
from .reporting import render_json_report, render_text_report
from .scanner import scan_auth_dir


DEFAULT_AUTH_DIR = "~/.cli-proxy-api"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cpa-auth-file-cleaner",
        description="Scan CPA auth JSON files for invalidated tokens and move matches away.",
    )
    parser.add_argument(
        "--source",
        choices=("file-marker", "management"),
        default="file-marker",
        help="Scan source. file-marker reads auth JSON files; management reads CPA runtime status.",
    )
    parser.add_argument(
        "--auth-dir",
        default=DEFAULT_AUTH_DIR,
        help=f"CPA auth directory. Default: {DEFAULT_AUTH_DIR}",
    )
    parser.add_argument(
        "--move-dir",
        default="",
        help="Destination directory for matched files. Defaults to a sibling timestamp directory.",
    )
    parser.add_argument(
        "--management-url",
        default="",
        help="CPA base URL for management scanning, for example http://127.0.0.1:8317.",
    )
    parser.add_argument(
        "--management-key",
        default="",
        help=(
            "Management key. Prefer --management-key-env to avoid exposing secrets "
            "in shell history."
        ),
    )
    parser.add_argument(
        "--management-key-env",
        default="CPA_MANAGEMENT_KEY",
        help="Environment variable containing the management key. Default: CPA_MANAGEMENT_KEY.",
    )
    parser.add_argument(
        "--match",
        choices=("invalidated", "problem", "warning"),
        default="invalidated",
        help="Management status match mode. problem matches CPAMC problem filter.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Move matched files. Without this flag the command only reports a dry-run plan.",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Only scan JSON files directly under auth-dir.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable JSON report.",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    auth_dir = Path(args.auth_dir).expanduser()
    move_dir = (
        Path(args.move_dir).expanduser()
        if args.move_dir.strip()
        else default_move_dir(auth_dir)
    )
    dry_run = not args.execute
    post_report = None
    post_scan_error = ""
    quarantine = None
    verification = None

    try:
        validate_move_dir(auth_dir, move_dir)
        key = prepare_management_key(args)
        report = scan_current(args, auth_dir, key)
        records = move_invalid_files(
            auth_dir=auth_dir,
            invalid_files=report.invalid_files,
            move_dir=move_dir,
            dry_run=dry_run,
        )
        if not dry_run:
            quarantine = quarantine_summary(move_dir, records)
            try:
                post_report = scan_current(args, auth_dir, key)
            except (OSError, ValueError, RuntimeError) as exc:
                post_scan_error = str(exc)
            verification = execution_verification(
                records=records,
                post_report=post_report,
                quarantine=quarantine,
                post_scan_error=post_scan_error,
            )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output = (
        render_json_report(
            report,
            records,
            dry_run=dry_run,
            move_dir=move_dir,
            post_report=post_report,
            post_scan_error=post_scan_error,
            quarantine=quarantine,
            verification=verification,
        )
        if args.json
        else render_text_report(
            report,
            records,
            dry_run=dry_run,
            move_dir=move_dir,
            post_report=post_report,
            post_scan_error=post_scan_error,
            quarantine=quarantine,
            verification=verification,
        )
    )
    print(output)
    return 0


def prepare_management_key(args):
    if args.source != "management":
        return ""
    if not args.management_url.strip():
        raise ValueError("--management-url is required when --source=management")
    return management_key_from_args(args.management_key, args.management_key_env)


def scan_current(args, auth_dir, management_key):
    if args.source == "management":
        payload = fetch_management_auth_files(args.management_url, management_key)
        return scan_management_payload(payload, match_mode=args.match, auth_dir=auth_dir)
    return scan_auth_dir(auth_dir, recursive=not args.no_recursive)


if __name__ == "__main__":
    raise SystemExit(main())
