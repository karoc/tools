#!/usr/bin/env python3
"""Standalone entry for the CPA auth file cleaner."""

from __future__ import annotations

import sys
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_ROOT / "src"))

from cpa_auth_cleaner.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())

