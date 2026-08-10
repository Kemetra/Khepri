from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import yaml

from khepri_gov.approval_packages import (
    document_digest,
    load_package,
    manifest_digest,
)
from khepri_gov.delegation import delegate_ids, delegated_commit_errors
from khepri_gov.lifecycle_conditions import (
    lifecycle_condition_errors,
    scan_repository,
)
from khepri_gov.validator import validate_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="khepri-gov")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "command",
        choices=[
            "validate",
            "document-digest",
            "approval-digest",
            "delegation-guard",
            "lifecycle-guard",
        ],
    )
    parser.add_argument("path", type=Path, nargs="?")
    return parser


def _authority_records(root: Path) -> list[dict[str, object]]:
    path = root / "governance" / "registries" / "authorities.yaml"
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return []
    if not isinstance(loaded, dict):
        return []
    records = loaded.get("authorities")
    return records if isinstance(records, list) else []


def _run_delegation_guard(root: Path) -> int:
    changed = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]
    delegates = delegate_ids(_authority_records(root))
    violations = delegated_commit_errors(root, changed, delegates)
    if violations:
        for violation in violations:
            print(f"ERROR {violation}", file=sys.stderr)
        return 1
    print("Delegation guard passed.")
    return 0


def _run_lifecycle_guard(root: Path) -> int:
    findings = scan_repository(root.resolve())
    for finding in findings:
        if finding.is_suppressed:
            print(f"NOTE {finding.message()}")
    errors = lifecycle_condition_errors(findings)
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    print("Lifecycle guard passed.")
    return 0


def _run_validate(root: Path) -> int:
    errors = validate_repository(root)
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    print("Governance validation passed.")
    return 0


def _resolve_digest_path(root: Path, requested: Path | None) -> Path | None:
    if requested is None:
        print("ERROR digest command requires a path", file=sys.stderr)
        return None
    path = (root / requested).resolve()
    if not path.is_relative_to(root):
        print("ERROR path does not resolve to a repository file", file=sys.stderr)
        return None
    if not path.is_file():
        print("ERROR path does not resolve to a repository file", file=sys.stderr)
        return None
    return path


def _run_approval_digest(path: Path) -> int:
    package, errors = load_package(path)
    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    assert package is not None
    print(manifest_digest(package))
    return 0


def _run_digest(command: str, root: Path, requested: Path | None) -> int:
    path = _resolve_digest_path(root.resolve(), requested)
    if path is None:
        return 1
    if command == "document-digest":
        print(document_digest(path))
        return 0
    return _run_approval_digest(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    if arguments.command == "validate":
        if arguments.path is not None:
            parser.error("validate does not accept a path")
        return _run_validate(arguments.root)
    if arguments.command == "delegation-guard":
        return _run_delegation_guard(arguments.root)
    if arguments.command == "lifecycle-guard":
        if arguments.path is not None:
            parser.error("lifecycle-guard does not accept a path")
        return _run_lifecycle_guard(arguments.root)
    return _run_digest(arguments.command, arguments.root, arguments.path)


if __name__ == "__main__":
    raise SystemExit(main())
