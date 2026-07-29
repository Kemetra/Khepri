from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from khepri_gov.approval_packages import (
    document_digest,
    load_package,
    manifest_digest,
)
from khepri_gov.validator import validate_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="khepri-gov")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "command",
        choices=["validate", "document-digest", "approval-digest"],
    )
    parser.add_argument("path", type=Path, nargs="?")
    return parser


def _run_validate(root: Path) -> int:
    errors = validate_repository(root)
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    print("Governance validation passed.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    if arguments.command == "validate":
        if arguments.path is not None:
            parser.error("validate does not accept a path")
        return _run_validate(arguments.root)

    if arguments.path is None:
        print("ERROR digest command requires a path", file=sys.stderr)
        return 1
    root = arguments.root.resolve()
    path = (root / arguments.path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        print("ERROR path does not resolve to a repository file", file=sys.stderr)
        return 1
    if arguments.command == "document-digest":
        print(document_digest(path))
        return 0

    package, errors = load_package(path)
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    assert package is not None
    print(manifest_digest(package))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
