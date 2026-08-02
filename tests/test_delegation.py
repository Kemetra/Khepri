from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from khepri_gov.delegation import (
    DelegationContext,
    DelegationRecord,
    approval_identity_errors,
    delegate_ids,
    is_delegate,
    is_reserved_file,
    load_delegations,
    package_delegation_errors,
    reserved_file_violations,
)

HUMAN = {"id": "AHMED-SHAABAN", "active": True, "human": True}
DELEGATE = {"id": "KHEPRI-AGENT", "active": True, "human": False}
AUTHORITIES = {"AHMED-SHAABAN": HUMAN, "KHEPRI-AGENT": DELEGATE}


def record_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema_version": 1,
        "id": "DEL-001",
        "delegate": "KHEPRI-AGENT",
        "granted_by": "AHMED-SHAABAN",
        "instruction": "handle all yourself i authorize you",
        "granted_at": "2026-08-02",
        "session": "session-abc",
        "scope": {"kind": "standing", "artifacts": ["*"]},
        "expires_at": "2026-09-01",
        "revoked": False,
    }
    data.update(overrides)
    return data


def write_record(root: Path, data: dict[str, Any], name: str = "DEL-001") -> str:
    directory = root / "governance" / "delegations"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return f"governance/delegations/{name}.yaml"


def delegated_package(ref: str, **overrides: Any) -> dict[str, Any]:
    approval: dict[str, Any] = {
        "approved_by": "KHEPRI-AGENT",
        "approved_at": "2026-08-02",
        "approved_manifest_digest": "sha256:" + "0" * 64,
        "delegation_ref": ref,
        "session": "session-abc",
    }
    approval.update(overrides.pop("approval", {}))
    package: dict[str, Any] = {
        "id": "APP-999",
        "owner": "AHMED-SHAABAN",
        "manifest_digest": "sha256:" + "0" * 64,
        "approval": approval,
        "artifacts": [
            {"id": "FND-003", "document": "governance/specifications/FND-003.md"}
        ],
    }
    package.update(overrides)
    return package


def context(root: Path, **artifacts: Any) -> DelegationContext:
    records, _ = load_delegations(root)
    known = {"FND-003": ("specifications", {"id": "FND-003"})}
    known.update(artifacts)
    return DelegationContext(records, known, AUTHORITIES)


def test_delegate_is_identified_by_explicit_humanity() -> None:
    assert is_delegate(DELEGATE) is True
    assert is_delegate(HUMAN) is False
    assert is_delegate(None) is False
    assert delegate_ids(AUTHORITIES.values()) == {"KHEPRI-AGENT"}


@pytest.mark.parametrize("field", sorted(record_data().keys()))
def test_delegation_record_requires_every_field(tmp_path: Path, field: str) -> None:
    data = record_data()
    del data[field]
    write_record(tmp_path, data)

    _, errors = load_delegations(tmp_path)

    assert any(f"missing required field {field!r}" in error for error in errors)


def test_valid_delegation_record_loads_without_error(tmp_path: Path) -> None:
    ref = write_record(tmp_path, record_data())

    records, errors = load_delegations(tmp_path)

    assert errors == []
    assert records[ref].covers("ANYTHING") is True


@pytest.mark.parametrize(
    "scope",
    [
        {"kind": "session", "artifacts": ["FND-003"]},
        {"kind": "standing", "artifacts": ["*"]},
    ],
)
def test_admitted_scope_forms(tmp_path: Path, scope: dict[str, Any]) -> None:
    write_record(tmp_path, record_data(scope=scope))

    _, errors = load_delegations(tmp_path)

    assert errors == []


@pytest.mark.parametrize(
    "scope",
    [
        {"kind": "everything", "artifacts": ["FND-003"]},
        {"kind": "standing", "artifacts": []},
        {"kind": "standing", "artifacts": "FND-*"},
        {"kind": "standing", "artifacts": ["*", "FND-003"]},
        {"artifacts": ["FND-003"]},
    ],
)
def test_rejected_scope_forms(tmp_path: Path, scope: dict[str, Any]) -> None:
    write_record(tmp_path, record_data(scope=scope))

    _, errors = load_delegations(tmp_path)

    assert errors != []


def test_standing_delegation_may_not_outlive_ninety_days(tmp_path: Path) -> None:
    write_record(tmp_path, record_data(expires_at="2026-12-31"))

    _, errors = load_delegations(tmp_path)

    assert any("90 days" in error for error in errors)


def test_expiry_may_not_precede_grant(tmp_path: Path) -> None:
    write_record(tmp_path, record_data(expires_at="2026-08-01"))

    _, errors = load_delegations(tmp_path)

    assert any("must not precede granted_at" in error for error in errors)


def test_delegated_approval_may_not_name_a_human_approver() -> None:
    approval = {
        "approved_by": "AHMED-SHAABAN",
        "approved_at": "2026-08-02",
        "approved_manifest_digest": "sha256:" + "0" * 64,
        "delegation_ref": "governance/delegations/DEL-001.yaml",
        "session": "session-abc",
    }
    package = {"owner": "AHMED-SHAABAN"}

    errors = approval_identity_errors("APP-999", package, approval, HUMAN)

    assert any("unknown field 'delegation_ref'" in error for error in errors)
    assert any("missing required field 'evidence_ref'" in error for error in errors)


def test_human_approval_may_not_carry_a_delegation_reference() -> None:
    approval = {
        "approved_by": "KHEPRI-AGENT",
        "approved_at": "2026-08-02",
        "approved_manifest_digest": "sha256:" + "0" * 64,
        "evidence_ref": "https://github.com/Kemetra/Khepri/pull/1#issuecomment-1",
    }
    package = {"owner": "AHMED-SHAABAN"}

    errors = approval_identity_errors("APP-999", package, approval, DELEGATE)

    assert any("unknown field 'evidence_ref'" in error for error in errors)
    assert any("missing required field 'delegation_ref'" in error for error in errors)


def test_absent_delegation_record_is_rejected(tmp_path: Path) -> None:
    package = delegated_package("governance/delegations/DEL-404.yaml")

    errors = package_delegation_errors("APP-999", package, context(tmp_path))

    assert any("must name a delegation record" in error for error in errors)


def test_revoked_delegation_is_rejected(tmp_path: Path) -> None:
    ref = write_record(tmp_path, record_data(revoked=True))
    package = delegated_package(ref)

    errors = package_delegation_errors("APP-999", package, context(tmp_path))

    assert any("is revoked" in error for error in errors)


def test_expired_delegation_is_rejected(tmp_path: Path) -> None:
    ref = write_record(
        tmp_path,
        record_data(granted_at="2026-06-01", expires_at="2026-07-01"),
    )
    package = delegated_package(ref)

    errors = package_delegation_errors("APP-999", package, context(tmp_path))

    assert any("expired on 2026-07-01" in error for error in errors)


def test_session_scoped_delegation_requires_the_same_session(tmp_path: Path) -> None:
    ref = write_record(
        tmp_path,
        record_data(scope={"kind": "session", "artifacts": ["*"]}),
    )
    package = delegated_package(ref, approval={"session": "another-session"})

    errors = package_delegation_errors("APP-999", package, context(tmp_path))

    assert any("same session" in error for error in errors)


def test_delegation_granting_to_another_delegate_is_rejected(tmp_path: Path) -> None:
    ref = write_record(tmp_path, record_data(delegate="OTHER-AGENT"))
    package = delegated_package(ref)

    errors = package_delegation_errors("APP-999", package, context(tmp_path))

    assert any("grants to another delegate" in error for error in errors)


def test_artifact_outside_enumerated_scope_is_rejected(tmp_path: Path) -> None:
    ref = write_record(
        tmp_path,
        record_data(scope={"kind": "standing", "artifacts": ["RRA-001"]}),
    )
    package = delegated_package(ref)

    errors = package_delegation_errors("APP-999", package, context(tmp_path))

    assert any("does not cover FND-003" in error for error in errors)


@pytest.mark.parametrize(
    "document",
    [
        "governance/CONSTITUTION.md",
        "governance/registries/authorities.yaml",
        "governance/delegations/DEL-001.yaml",
    ],
)
def test_delegate_may_not_approve_a_reserved_document(
    tmp_path: Path,
    document: str,
) -> None:
    ref = write_record(tmp_path, record_data())
    package = delegated_package(ref)
    package["artifacts"] = [{"id": "FND-003", "document": document}]

    errors = package_delegation_errors("APP-999", package, context(tmp_path))

    assert any("may not approve a change to" in error for error in errors)


def test_delegate_may_not_accept_a_reserved_set_decision(tmp_path: Path) -> None:
    ref = write_record(tmp_path, record_data())
    package = delegated_package(ref)
    package["artifacts"] = [
        {"id": "KHEPRI-DEC-099", "document": "governance/decisions/x.md"}
    ]
    known = {
        "KHEPRI-DEC-099": (
            "decisions",
            {"id": "KHEPRI-DEC-099", "alters_reserved_set": True},
        )
    }

    errors = package_delegation_errors(
        "APP-999",
        package,
        context(tmp_path, **known),
    )

    assert any("alters" in error for error in errors)


def test_human_approved_package_is_not_subject_to_delegation_rules(
    tmp_path: Path,
) -> None:
    package = delegated_package("governance/delegations/DEL-404.yaml")
    package["approval"]["approved_by"] = "AHMED-SHAABAN"

    errors = package_delegation_errors("APP-999", package, context(tmp_path))

    assert errors == []


@pytest.mark.parametrize(
    ("path", "reserved"),
    [
        ("governance/CONSTITUTION.md", True),
        ("governance/registries/authorities.yaml", True),
        ("governance/delegations/DEL-001.yaml", True),
        ("governance\\delegations\\DEL-001.yaml", True),
        ("governance/registries/decisions.yaml", False),
        ("src/khepri_gov/delegation.py", False),
    ],
)
def test_reserved_file_detection(path: str, reserved: bool) -> None:
    assert is_reserved_file(path) is reserved


def test_reserved_file_violations_reports_every_reserved_change() -> None:
    changed = [
        "governance/CONSTITUTION.md",
        "src/khepri_gov/delegation.py",
        "governance/delegations/DEL-002.yaml",
    ]

    violations = reserved_file_violations(changed)

    assert len(violations) == 2


def test_record_covers_named_artifact_only() -> None:
    record = DelegationRecord(
        "governance/delegations/DEL-001.yaml",
        record_data(scope={"kind": "standing", "artifacts": ["FND-003"]}),
    )

    assert record.covers("FND-003") is True
    assert record.covers("RRA-001") is False
