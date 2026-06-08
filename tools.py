#!/usr/bin/env python3
"""Unified command entry for repository tools."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent

TOOLS = {
    "cpa-auth-file-cleaner": {
        "description": "Scan CPA auth files for invalidated tokens and move matches away.",
        "src": ROOT / "cpa" / "auth-file-cleaner" / "src",
        "module": "cpa_auth_cleaner.cli",
    },
}


def print_help() -> None:
    print("Usage:")
    print("  python3 tools.py list")
    print("  python3 tools.py <tool-name> [tool arguments]")
    print("")
    print("Tools:")
    for name, meta in sorted(TOOLS.items()):
        print(f"  {name:<24} {meta['description']}")


def list_tools() -> None:
    for name, meta in sorted(TOOLS.items()):
        print(f"{name}\t{meta['description']}")


def run_tool(name: str, args: list[str]) -> int:
    meta = TOOLS[name]
    sys.path.insert(0, str(meta["src"]))
    module_name = str(meta["module"])
    module = __import__(module_name, fromlist=["main"])
    return int(module.main(args))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print_help()
        return 0

    command = argv[0]
    if command == "list":
        list_tools()
        return 0

    if command not in TOOLS:
        print(f"Unknown tool: {command}", file=sys.stderr)
        print_help()
        return 2

    return run_tool(command, argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
