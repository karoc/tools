import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOL_ROOT.parents[1]
sys.path.insert(0, str(TOOL_ROOT / "src"))

from cpa_auth_cleaner.constants import (  # noqa: E402
    INVALIDATED_ERROR_CODE,
    INVALIDATED_ERROR_MESSAGE,
    INVALIDATED_ERROR_TYPE,
)
from cpa_auth_cleaner.mover import move_invalid_files, validate_move_dir  # noqa: E402
from cpa_auth_cleaner.scanner import scan_auth_dir  # noqa: E402


def invalid_payload():
    return {
        "type": "codex",
        "email": "invalid@example.com",
        "error": {
            "message": INVALIDATED_ERROR_MESSAGE,
            "type": INVALIDATED_ERROR_TYPE,
            "code": INVALIDATED_ERROR_CODE,
        },
    }


class CPAAuthCleanerTests(unittest.TestCase):
    def test_scan_matches_exact_invalidated_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            auth_dir = Path(temp)
            write_json(auth_dir / "invalid.json", invalid_payload())
            write_json(
                auth_dir / "wrong-code.json",
                {
                    "error": {
                        "message": INVALIDATED_ERROR_MESSAGE,
                        "type": INVALIDATED_ERROR_TYPE,
                        "code": "invalid_api_key",
                    }
                },
            )
            write_json(auth_dir / "valid.json", {"type": "codex", "email": "ok@example.com"})

            report = scan_auth_dir(auth_dir)

            self.assertEqual(report.scanned_json_files, 3)
            self.assertEqual(len(report.invalid_files), 1)
            self.assertEqual(report.invalid_files[0].relative_path, Path("invalid.json"))
            self.assertEqual(report.invalid_files[0].provider, "codex")
            self.assertEqual(report.invalid_files[0].email, "invalid@example.com")

    def test_scan_records_invalid_json_as_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            auth_dir = Path(temp)
            (auth_dir / "broken.json").write_text("{not-json", encoding="utf-8")

            report = scan_auth_dir(auth_dir)

            self.assertEqual(report.scanned_json_files, 1)
            self.assertEqual(len(report.invalid_files), 0)
            self.assertEqual(len(report.skipped_files), 1)
            self.assertIn("invalid_json", report.skipped_files[0].reason)

    def test_dry_run_does_not_move_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            auth_dir = Path(temp) / "auths"
            move_dir = Path(temp) / "moved"
            auth_dir.mkdir()
            write_json(auth_dir / "invalid.json", invalid_payload())

            report = scan_auth_dir(auth_dir)
            records = move_invalid_files(auth_dir, report.invalid_files, move_dir, dry_run=True)

            self.assertEqual(len(records), 1)
            self.assertFalse(records[0].moved)
            self.assertTrue((auth_dir / "invalid.json").exists())
            self.assertFalse(move_dir.exists())

    def test_execute_moves_files_preserving_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            auth_dir = Path(temp) / "auths"
            nested = auth_dir / "nested"
            move_dir = Path(temp) / "moved"
            nested.mkdir(parents=True)
            write_json(nested / "invalid.json", invalid_payload())
            write_json(auth_dir / "valid.json", {"type": "codex"})

            report = scan_auth_dir(auth_dir)
            records = move_invalid_files(auth_dir, report.invalid_files, move_dir, dry_run=False)

            self.assertEqual(len(records), 1)
            self.assertTrue(records[0].moved)
            self.assertFalse((nested / "invalid.json").exists())
            self.assertTrue((move_dir / "nested" / "invalid.json").exists())
            self.assertTrue((auth_dir / "valid.json").exists())

    def test_rejects_move_dir_inside_auth_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            auth_dir = Path(temp) / "auths"
            auth_dir.mkdir()

            with self.assertRaises(ValueError):
                validate_move_dir(auth_dir, auth_dir / "invalidated")

    def test_unified_entry_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            auth_dir = Path(temp) / "auths"
            auth_dir.mkdir()
            write_json(auth_dir / "invalid.json", invalid_payload())

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "tools.py"),
                    "cpa-auth-file-cleaner",
                    "--auth-dir",
                    str(auth_dir),
                    "--json",
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "dry-run")
            self.assertEqual(payload["invalidated_count"], 1)
            self.assertTrue((auth_dir / "invalid.json").exists())


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
