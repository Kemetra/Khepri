from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from khepri_gov.validator import validate_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="khepri-gov")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("command", choices=["validate"])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    errors = validate_repository(arguments.root)
    for error in errors:
        print(f"ERROR {error}", file=sys.stderr)
    if errors:
        return 1
    print("Governance validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
