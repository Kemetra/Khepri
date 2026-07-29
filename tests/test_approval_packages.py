from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path

import pytest

from khepri_gov.approval_packages import document_digest, manifest_digest
from tests.test_cli import (
    assert_invalid,
    read_yaml,
    run_validator,
    valid_repository,
    write_document,
    write_yaml,
)


def example_package() -> dict[str, object]:
    return {
        "schema_version": 1,
        "id": "APP-002",
        "title": "Example",
        "state": "proposed",
        "owner": "AHMED-SHAABAN",
        "scope": "Approve exact artifacts.",
        "exclusions": ["Product code"],
        "manifest_digest": "sha256:" + ("0" * 64),
        "artifacts": [
            {
                "id": "KHEPRI-DEC-002",
                "document": "governance/decisions/KHEPRI-DEC-002.md",
                "document_sha256": "sha256:" + ("a" * 64),
                "from_state": "proposed",
                "to_state": "accepted",
            }
        ],
    }


def test_manifest_digest_is_canonical_and_excludes_approval_state() -> None:
    package = example_package()

    assert manifest_digest(package) == (
        "sha256:796d415bf26999eb891b4af35f1b4f49f814abb4ed83a1320e5f646fb0ac0f07"
    )

    approved = deepcopy(package)
    approved["state"] = "approved"
    approved["approval"] = {
        "approved_by": "AHMED-SHAABAN",
        "approved_at": "2026-07-29",
        "approved_manifest_digest": manifest_digest(package),
        "evidence_ref": (
            "https://github.com/Kemetra/Khepri/pull/4"
            "#issuecomment-0000000000"
        ),
    }
    assert manifest_digest(approved) == manifest_digest(package)


def test_document_digest_hashes_exact_utf8_bytes(tmp_path: Path) -> None:
    document = tmp_path / "decision.md"
    document.write_bytes(b"# KHEPRI-DEC-002\n")

    assert document_digest(document) == (
        "sha256:9b08cd92ee3f228e9d7167a935ec8acf13567019c633471fa6dab2bc1f5790ef"
    )


def add_proposed_decision(root: Path) -> str:
    document = "governance/decisions/KHEPRI-DEC-002.md"
    write_document(root, document)
    path = root / "governance/registries/decisions.yaml"
    data = read_yaml(path)
    decisions = data["decisions"]
    assert isinstance(decisions, list)
    decisions.append(
        {
            "id": "KHEPRI-DEC-002",
            "title": "Atomic packages",
            "state": "proposed",
            "owner": "AHMED-SHAABAN",
            "document": document,
        }
    )
    write_yaml(path, data)
    return document


def proposed_package(root: Path) -> tuple[Path, dict[str, object]]:
    document = add_proposed_decision(root)
    package: dict[str, object] = {
        "schema_version": 1,
        "id": "APP-002",
        "title": "Atomic package",
        "state": "proposed",
        "owner": "AHMED-SHAABAN",
        "scope": "Approve the exact listed decision.",
        "exclusions": ["Product application code"],
        "artifacts": [
            {
                "id": "KHEPRI-DEC-002",
                "document": document,
                "document_sha256": document_digest(root / document),
                "from_state": "proposed",
                "to_state": "accepted",
            }
        ],
    }
    package["manifest_digest"] = manifest_digest(package)
    path = root / "governance/approvals/APP-002.yaml"
    write_yaml(path, package)
    return path, package


def rewrite_package(path: Path, package: dict[str, object]) -> None:
    package["manifest_digest"] = manifest_digest(package)
    write_yaml(path, package)


def test_valid_proposed_package_passes(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    proposed_package(tmp_path)

    result = run_validator(tmp_path)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda package: package.update(schema_version=2),
            "approval-packages:APP-002: unsupported schema_version 2",
        ),
        (
            lambda package: package.update(state="executed"),
            "approval-packages:APP-002: invalid state 'executed'",
        ),
        (
            lambda package: package.update(owner="UNKNOWN"),
            "approval-packages:APP-002: unknown owner 'UNKNOWN'",
        ),
    ],
)
def test_package_shape_fails_closed(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
    message: str,
) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    mutation(package)
    rewrite_package(path, package)

    result = run_validator(tmp_path)

    assert_invalid(result, message)


def test_package_rejects_incorrect_manifest_digest(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    package["manifest_digest"] = "sha256:" + ("0" * 64)
    write_yaml(path, package)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: manifest_digest does not match canonical payload",
    )


def test_package_filename_must_match_id(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    other_path = path.with_name("APP-003.yaml")
    write_yaml(other_path, package)
    path.unlink()

    result = run_validator(tmp_path)

    assert_invalid(result, "approval-packages:APP-002: filename must match package id")


def test_package_rejects_missing_and_unknown_fields(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    del package["scope"]
    package["extra"] = True
    rewrite_package(path, package)

    result = run_validator(tmp_path)

    assert_invalid(result, "approval-packages:APP-002: missing required field 'scope'")
    assert "approval-packages:APP-002: unknown field 'extra'" in result.stderr


def test_package_rejects_invalid_exclusions(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    package["exclusions"] = ["Product code", ""]
    rewrite_package(path, package)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: exclusions must be a list of non-empty strings",
    )


def test_package_requires_artifacts(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    package["artifacts"] = []
    rewrite_package(path, package)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: artifacts must be a non-empty list",
    )


def test_package_rejects_duplicate_artifacts(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    artifacts = package["artifacts"]
    assert isinstance(artifacts, list)
    artifacts.append(deepcopy(artifacts[0]))
    rewrite_package(path, package)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: duplicate artifact id 'KHEPRI-DEC-002'",
    )


def test_package_rejects_unknown_artifact(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    artifacts = package["artifacts"]
    assert isinstance(artifacts, list)
    artifacts[0]["id"] = "UNKNOWN"
    rewrite_package(path, package)

    result = run_validator(tmp_path)

    assert_invalid(result, "approval-packages:APP-002: unknown artifact 'UNKNOWN'")


def test_package_document_must_match_registry(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    artifacts = package["artifacts"]
    assert isinstance(artifacts, list)
    artifacts[0]["document"] = "governance/decisions/OTHER.md"
    rewrite_package(path, package)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: artifact document does not match registry",
    )


def test_package_document_digest_must_match_file(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    artifacts = package["artifacts"]
    assert isinstance(artifacts, list)
    artifacts[0]["document_sha256"] = "sha256:" + ("0" * 64)
    rewrite_package(path, package)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: document_sha256 does not match governed document",
    )


def test_proposed_package_must_not_claim_approval(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    package["approval"] = {
        "approved_by": "AHMED-SHAABAN",
        "approved_at": "2026-07-29",
        "approved_manifest_digest": package["manifest_digest"],
        "evidence_ref": "https://github.com/Kemetra/Khepri/pull/4",
    }
    rewrite_package(path, package)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: proposed package must not contain approval",
    )
