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
from .service import (
    DEFAULT_ENV_FILE,
    DEFAULT_INTERVAL,
    DEFAULT_SERVICE_NAME,
    default_service_python,
    handle_service_action,
    render_service_result,
    service_action_requested,
)


DEFAULT_AUTH_DIR = "~/.cli-proxy-api"
DEFAULT_MANAGEMENT_URL = "http://127.0.0.1:8317"
DEFAULT_MANAGEMENT_KEY_ENV = "CPA_SECRET_KEY"


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
        default=DEFAULT_MANAGEMENT_URL,
        help=f"CPA base URL for management scanning. Default: {DEFAULT_MANAGEMENT_URL}",
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
        default=DEFAULT_MANAGEMENT_KEY_ENV,
        help=(
            "Environment variable containing the management key. "
            f"Default: {DEFAULT_MANAGEMENT_KEY_ENV}."
        ),
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
    service = parser.add_argument_group("systemd service")
    service.add_argument(
        "--install-service",
        action="store_true",
        help="Install and enable a systemd timer for this tool.",
    )
    service.add_argument(
        "--uninstall-service",
        action="store_true",
        help="Disable and remove the systemd timer and service unit.",
    )
    service.add_argument(
        "--print-service-units",
        action="store_true",
        help="Print systemd service/timer unit content without writing files.",
    )
    service.add_argument(
        "--service-name",
        default=DEFAULT_SERVICE_NAME,
        help=f"systemd service base name. Default: {DEFAULT_SERVICE_NAME}",
    )
    service.add_argument(
        "--service-interval",
        default=DEFAULT_INTERVAL,
        help=f"Timer interval for OnBootSec and OnUnitActiveSec. Default: {DEFAULT_INTERVAL}",
    )
    service.add_argument(
        "--service-env-file",
        default=DEFAULT_ENV_FILE,
        help=f"Optional EnvironmentFile used by the service. Default: {DEFAULT_ENV_FILE}",
    )
    service.add_argument(
        "--service-user",
        default="",
        help="Run the system service as this user. Omit to use systemd default.",
    )
    service.add_argument(
        "--service-unit-dir",
        default="",
        help="Override systemd unit directory. Defaults to /etc/systemd/system.",
    )
    service.add_argument(
        "--service-working-dir",
        default="",
        help="Repository root used as WorkingDirectory. Defaults to detected repo root.",
    )
    service.add_argument(
        "--service-python",
        default=default_service_python(),
        help="Python executable used by ExecStart.",
    )
    service.add_argument(
        "--user-service",
        action="store_true",
        help="Install as a systemd user timer under ~/.config/systemd/user.",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if service_action_requested(args):
        return run_service_action(args)

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


def run_service_action(args):
    try:
        result = handle_service_action(args)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(render_service_result(result, as_json=args.json))
    return 0


def prepare_management_key(args):
    if args.source != "management":
        return ""
    if not args.management_url.strip():
        raise ValueError("--management-url must not be empty when --source=management")
    return management_key_from_args(args.management_key, args.management_key_env)


def scan_current(args, auth_dir, management_key):
    if args.source == "management":
        payload = fetch_management_auth_files(args.management_url, management_key)
        return scan_management_payload(payload, match_mode=args.match, auth_dir=auth_dir)
    return scan_auth_dir(auth_dir, recursive=not args.no_recursive)


if __name__ == "__main__":
    raise SystemExit(main())
