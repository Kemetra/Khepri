from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path

import pytest

from khepri_gov.approval_packages import document_digest, manifest_digest
from tests.test_cli import (
    assert_invalid,
    read_yaml,
    run_cli,
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


def package_artifacts(package: dict[str, object]) -> list[dict[str, object]]:
    artifacts = package["artifacts"]
    assert isinstance(artifacts, list)
    assert all(isinstance(artifact, dict) for artifact in artifacts)
    return artifacts


def test_package_rejects_unsupported_decision_transition(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    package_artifacts(package)[0]["to_state"] = "superseded"
    rewrite_package(path, package)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: unsupported transition for "
        "KHEPRI-DEC-002: proposed -> superseded",
    )


def test_proposed_artifact_must_remain_at_from_state(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    decisions_path = root_path(tmp_path, "decisions")
    decisions = read_yaml(decisions_path)
    decisions["decisions"][1]["state"] = "rejected"  # type: ignore[index]
    write_yaml(decisions_path, decisions)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: KHEPRI-DEC-002 must remain at "
        "from_state 'proposed'",
    )


def test_initial_proposed_artifact_must_not_contain_approval_fields(
    tmp_path: Path,
) -> None:
    valid_repository(tmp_path)
    proposed_package(tmp_path)
    decisions_path = root_path(tmp_path, "decisions")
    decisions = read_yaml(decisions_path)
    decisions["decisions"][1].update(  # type: ignore[index]
        {
            "approved_by": "AHMED-SHAABAN",
            "approved_at": "2026-07-29",
            "approval_ref": "https://github.com/Kemetra/Khepri/pull/4",
        }
    )
    write_yaml(decisions_path, decisions)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: KHEPRI-DEC-002 must not contain approval "
        "fields before initial approval",
    )


def test_initial_approval_cannot_supersede_prior_evidence(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    package_artifacts(package)[0]["supersedes_approval_ref"] = (
        "governance/approvals/APP-001-bootstrap.md"
    )
    rewrite_package(path, package)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: initial approval must not supersede prior evidence",
    )


def root_path(root: Path, registry: str) -> Path:
    return root / "governance" / "registries" / f"{registry}.yaml"


def approve_package(
    root: Path,
    path: Path,
    package: dict[str, object],
    *,
    evidence_ref: str = (
        "https://github.com/Kemetra/Khepri/pull/4"
        "#issuecomment-0000000000"
    ),
) -> None:
    digest = manifest_digest(package)
    package["state"] = "approved"
    package["approval"] = {
        "approved_by": "AHMED-SHAABAN",
        "approved_at": "2026-07-29",
        "approved_manifest_digest": digest,
        "evidence_ref": evidence_ref,
    }
    decisions_path = root_path(root, "decisions")
    decisions = read_yaml(decisions_path)
    artifact = decisions["decisions"][1]  # type: ignore[index]
    artifact.update(
        {
            "state": "accepted",
            "approved_by": "AHMED-SHAABAN",
            "approved_at": "2026-07-29",
            "approval_ref": "governance/approvals/APP-002.yaml",
        }
    )
    write_yaml(decisions_path, decisions)
    write_yaml(path, package)


def test_valid_approved_package_passes(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    approve_package(tmp_path, path, package)

    result = run_validator(tmp_path)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("approval_mutation", "message"),
    [
        (
            lambda approval: approval.pop("evidence_ref"),
            "approval-packages:APP-002: approval missing required field 'evidence_ref'",
        ),
        (
            lambda approval: approval.update(extra=True),
            "approval-packages:APP-002: approval has unknown field 'extra'",
        ),
        (
            lambda approval: approval.update(approved_by="UNKNOWN"),
            "approval-packages:APP-002: unknown or inactive approver 'UNKNOWN'",
        ),
        (
            lambda approval: approval.update(
                approved_manifest_digest="sha256:" + ("0" * 64)
            ),
            "approval-packages:APP-002: approved_manifest_digest must equal "
            "manifest_digest",
        ),
        (
            lambda approval: approval.update(
                evidence_ref="https://example.com/approval"
            ),
            "approval-packages:APP-002: evidence_ref must be a Khepri GitHub "
            "review or comment URL",
        ),
        (
            lambda approval: approval.update(
                evidence_ref=(
                    "https://github.com/Kemetra/Khepri/pull/not-a-pr"
                    "#issuecomment-123"
                )
            ),
            "approval-packages:APP-002: evidence_ref must be a Khepri GitHub "
            "review or comment URL",
        ),
        (
            lambda approval: approval.update(
                evidence_ref=(
                    "https://github.com/Kemetra/Khepri/issues/4"
                    "#pullrequestreview-not-a-review"
                )
            ),
            "approval-packages:APP-002: evidence_ref must be a Khepri GitHub "
            "review or comment URL",
        ),
    ],
)
def test_approved_package_rejects_invalid_approval(
    tmp_path: Path,
    approval_mutation: Callable[[dict[str, object]], object],
    message: str,
) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    approve_package(tmp_path, path, package)
    approval = package["approval"]
    assert isinstance(approval, dict)
    approval_mutation(approval)
    write_yaml(path, package)

    result = run_validator(tmp_path)

    assert_invalid(result, message)


def test_approved_package_requires_approval_mapping(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    approve_package(tmp_path, path, package)
    del package["approval"]
    write_yaml(path, package)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: approved package requires approval mapping",
    )


def test_package_owner_and_approver_must_match(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    authorities_path = root_path(tmp_path, "authorities")
    authorities = read_yaml(authorities_path)
    authority_document = "governance/authorities/other.md"
    write_document(tmp_path, authority_document)
    authorities["authorities"].append(  # type: ignore[union-attr]
        {
            "id": "OTHER",
            "name": "Other",
            "roles": ["product_owner"],
            "active": True,
            "human": True,
            "document": authority_document,
        }
    )
    write_yaml(authorities_path, authorities)
    approve_package(tmp_path, path, package)
    approval = package["approval"]
    assert isinstance(approval, dict)
    approval["approved_by"] = "OTHER"
    write_yaml(path, package)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: package owner and approver must match",
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "state",
            "proposed",
            "approval-packages:APP-002: KHEPRI-DEC-002 must be at to_state 'accepted'",
        ),
        (
            "approved_by",
            "OTHER",
            "approval-packages:APP-002: KHEPRI-DEC-002 approved_by does not match package",
        ),
        (
            "approved_at",
            "2026-07-28",
            "approval-packages:APP-002: KHEPRI-DEC-002 approved_at does not match package",
        ),
        (
            "approval_ref",
            "https://github.com/Kemetra/Khepri/pull/4",
            "approval-packages:APP-002: KHEPRI-DEC-002 approval_ref must be "
            "governance/approvals/APP-002.yaml",
        ),
    ],
)
def test_approved_package_requires_exact_materialization(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    approve_package(tmp_path, path, package)
    decisions_path = root_path(tmp_path, "decisions")
    decisions = read_yaml(decisions_path)
    decisions["decisions"][1][field] = value  # type: ignore[index]
    write_yaml(decisions_path, decisions)

    result = run_validator(tmp_path)

    assert_invalid(result, message)


def add_rra_graph(root: Path) -> list[dict[str, object]]:
    family_document = "governance/families/RRA.md"
    first_document = "governance/specifications/RRA-001.md"
    second_document = "governance/specifications/RRA-002.md"
    for document in (family_document, first_document, second_document):
        write_document(root, document)

    families_path = root_path(root, "families")
    families = read_yaml(families_path)
    families["families"].append(  # type: ignore[union-attr]
        {
            "id": "RRA",
            "name": "Retail Reporting Automation",
            "state": "proposed",
            "owner": "AHMED-SHAABAN",
            "document": family_document,
            "depends_on": ["FND"],
        }
    )
    write_yaml(families_path, families)

    specifications_path = root_path(root, "specifications")
    specifications = read_yaml(specifications_path)
    specifications["specifications"].extend(  # type: ignore[union-attr]
        [
            {
                "id": "RRA-001",
                "title": "First",
                "state": "draft",
                "family": "RRA",
                "owner": "AHMED-SHAABAN",
                "document": first_document,
                "depends_on": [],
            },
            {
                "id": "RRA-002",
                "title": "Second",
                "state": "draft",
                "family": "RRA",
                "owner": "AHMED-SHAABAN",
                "document": second_document,
                "depends_on": ["RRA-001"],
            },
        ]
    )
    write_yaml(specifications_path, specifications)

    return [
        {
            "id": "RRA",
            "document": family_document,
            "document_sha256": document_digest(root / family_document),
            "from_state": "proposed",
            "to_state": "active",
        },
        {
            "id": "RRA-001",
            "document": first_document,
            "document_sha256": document_digest(root / first_document),
            "from_state": "draft",
            "to_state": "approved",
        },
        {
            "id": "RRA-002",
            "document": second_document,
            "document_sha256": document_digest(root / second_document),
            "from_state": "draft",
            "to_state": "approved",
        },
    ]


def write_rra_package(
    root: Path,
    artifacts: list[dict[str, object]],
) -> Path:
    package: dict[str, object] = {
        "schema_version": 1,
        "id": "APP-002",
        "title": "RRA package",
        "state": "proposed",
        "owner": "AHMED-SHAABAN",
        "scope": "Approve the ordered RRA graph.",
        "exclusions": ["Product application code"],
        "artifacts": artifacts,
    }
    package["manifest_digest"] = manifest_digest(package)
    path = root / "governance/approvals/APP-002.yaml"
    write_yaml(path, package)
    return path


def test_dependency_closed_package_passes(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    artifacts = add_rra_graph(tmp_path)
    write_rra_package(tmp_path, artifacts)

    result = run_validator(tmp_path)

    assert result.returncode == 0, result.stderr


def test_family_must_precede_its_specification(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    artifacts = add_rra_graph(tmp_path)
    artifacts[0], artifacts[1] = artifacts[1], artifacts[0]
    write_rra_package(tmp_path, artifacts)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: family 'RRA' is not active before RRA-001",
    )


def test_dependency_must_precede_dependent_specification(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    artifacts = add_rra_graph(tmp_path)
    artifacts[1], artifacts[2] = artifacts[2], artifacts[1]
    write_rra_package(tmp_path, artifacts)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: dependency 'RRA-001' is not approved before RRA-002",
    )


def materialize_rra_package(root: Path, path: Path) -> None:
    package = read_yaml(path)
    package["state"] = "approved"
    package["approval"] = {
        "approved_by": "AHMED-SHAABAN",
        "approved_at": "2026-07-29",
        "approved_manifest_digest": package["manifest_digest"],
        "evidence_ref": (
            "https://github.com/Kemetra/Khepri/pull/4"
            "#issuecomment-5121383450"
        ),
    }
    write_yaml(path, package)

    for registry, artifact_ids, target_state in (
        ("families", {"RRA"}, "active"),
        ("specifications", {"RRA-001", "RRA-002"}, "approved"),
    ):
        registry_path = root_path(root, registry)
        data = read_yaml(registry_path)
        artifacts = data[registry]
        assert isinstance(artifacts, list)
        for artifact in artifacts:
            if artifact["id"] in artifact_ids:
                artifact.update(
                    {
                        "state": target_state,
                        "approved_by": "AHMED-SHAABAN",
                        "approved_at": "2026-07-29",
                        "approval_ref": "governance/approvals/APP-002.yaml",
                    }
                )
        write_yaml(registry_path, data)


def test_approved_package_replays_dependencies_from_pre_transition_states(
    tmp_path: Path,
) -> None:
    valid_repository(tmp_path)
    artifacts = add_rra_graph(tmp_path)
    artifacts[0], artifacts[1] = artifacts[1], artifacts[0]
    path = write_rra_package(tmp_path, artifacts)
    materialize_rra_package(tmp_path, path)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: family 'RRA' is not active before RRA-001",
    )


def test_draft_dependency_cannot_be_omitted(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    artifacts = add_rra_graph(tmp_path)
    write_rra_package(tmp_path, [artifacts[0], artifacts[2]])

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: dependency 'RRA-001' is not approved before RRA-002",
    )


@pytest.mark.parametrize(
    ("artifact_index", "to_state", "message"),
    [
        (
            0,
            "retired",
            "approval-packages:APP-002: unsupported transition for "
            "RRA: proposed -> retired",
        ),
        (
            1,
            "implemented",
            "approval-packages:APP-002: unsupported transition for "
            "RRA-001: draft -> implemented",
        ),
    ],
)
def test_family_and_specification_transitions_are_closed(
    tmp_path: Path,
    artifact_index: int,
    to_state: str,
    message: str,
) -> None:
    valid_repository(tmp_path)
    artifacts = add_rra_graph(tmp_path)
    artifacts[artifact_index]["to_state"] = to_state
    write_rra_package(tmp_path, artifacts)

    result = run_validator(tmp_path)

    assert_invalid(result, message)


def proposed_renewal(
    root: Path,
    *,
    package_id: str = "APP-003",
    supersedes: str = "governance/approvals/APP-002.yaml",
) -> tuple[Path, dict[str, object]]:
    document = "governance/decisions/KHEPRI-DEC-002.md"
    (root / document).write_bytes(b"# revised decision\n")
    package: dict[str, object] = {
        "schema_version": 1,
        "id": package_id,
        "title": "Renew atomic package decision",
        "state": "proposed",
        "owner": "AHMED-SHAABAN",
        "scope": "Renew the exact listed decision.",
        "exclusions": ["Product application code"],
        "artifacts": [
            {
                "id": "KHEPRI-DEC-002",
                "document": document,
                "document_sha256": document_digest(root / document),
                "from_state": "accepted",
                "to_state": "accepted",
                "supersedes_approval_ref": supersedes,
            }
        ],
    }
    package["manifest_digest"] = manifest_digest(package)
    path = root / "governance/approvals" / f"{package_id}.yaml"
    write_yaml(path, package)
    return path, package


def approved_package_with_renewal(
    root: Path,
) -> tuple[Path, dict[str, object], Path, dict[str, object]]:
    first_path, first_package = proposed_package(root)
    approve_package(root, first_path, first_package)
    renewal_path, renewal_package = proposed_renewal(root)
    return first_path, first_package, renewal_path, renewal_package


def test_valid_proposed_renewal_chain_passes(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    approved_package_with_renewal(tmp_path)

    result = run_validator(tmp_path)

    assert result.returncode == 0, result.stderr


def test_changed_document_requires_proposed_renewal(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    approve_package(tmp_path, path, package)
    document = package_artifacts(package)[0]["document"]
    assert isinstance(document, str)
    (tmp_path / document).write_bytes(b"# changed without renewal\n")

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: governed document for "
        "KHEPRI-DEC-002 changed without renewal",
    )


def test_renewal_must_supersede_current_approval(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    first_path, first_package = proposed_package(tmp_path)
    approve_package(tmp_path, first_path, first_package)
    proposed_renewal(
        tmp_path,
        supersedes="governance/approvals/APP-999.yaml",
    )

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-003: KHEPRI-DEC-002 does not currently use "
        "the superseded approval",
    )


def test_artifact_cannot_appear_in_multiple_proposed_packages(
    tmp_path: Path,
) -> None:
    valid_repository(tmp_path)
    first_path, first_package = proposed_package(tmp_path)
    approve_package(tmp_path, first_path, first_package)
    proposed_renewal(tmp_path)
    proposed_renewal(tmp_path, package_id="APP-004")

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages: artifact KHEPRI-DEC-002 appears in multiple "
        "proposed packages",
    )


def test_renewal_must_preserve_current_state(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    first_path, first_package = proposed_package(tmp_path)
    approve_package(tmp_path, first_path, first_package)
    renewal_path, renewal = proposed_renewal(tmp_path)
    package_artifacts(renewal)[0]["to_state"] = "rejected"
    rewrite_package(renewal_path, renewal)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-003: renewal must preserve state 'accepted'",
    )


def approve_renewal_in_registry(root: Path, renewal_path: Path, renewal: dict) -> None:
    """Land the renewal as approved, with the registry pointing at it."""
    renewal["state"] = "approved"
    renewal["approval"] = {
        "approved_by": "AHMED-SHAABAN",
        "approved_at": "2026-07-30",
        "approved_manifest_digest": manifest_digest(renewal),
        "evidence_ref": (
            "https://github.com/Kemetra/Khepri/pull/5#pullrequestreview-0000000000"
        ),
    }
    write_yaml(renewal_path, renewal)
    decisions_path = root_path(root, "decisions")
    decisions = read_yaml(decisions_path)
    decisions["decisions"][1].update(  # type: ignore[index]
        {
            "approved_at": "2026-07-30",
            "approval_ref": "governance/approvals/APP-003.yaml",
        }
    )
    write_yaml(decisions_path, decisions)


# --- the supersession defect -------------------------------------------------
#
# The validator judges EVERY approved package as though it were the package currently
# governing its artifacts. Two approved packages naming one artifact therefore cannot
# both pass -- and supersession is exactly that situation. Four checks express the same
# assumption, and superseding a once-renewed decision trips all four at once:
#
#   APP-003: KHEPRI-DEC-002 approved_at does not match package
#   APP-003: KHEPRI-DEC-002 approval_ref must be governance/approvals/APP-003.yaml
#   APP-003: renewal must preserve state 'superseded'
#   APP-004: KHEPRI-DEC-002 does not currently use the superseded approval
#
# The last two cannot both be satisfied. APP-003 requires the registry to still point at
# APP-003; APP-004 requires it to point at APP-004. No arrangement of correct files
# satisfies both, which is what makes this structural rather than a matter of getting a
# package right.
#
# Not hypothetical: KHEPRI-DEC-005 was renewed by APP-013, so KHEPRI-DEC-008 cannot be
# accepted -- it supersedes DEC-005 and DEC-007, and superseding DEC-005 trips these
# checks. Superseding only DEC-007 does validate, because APP-005 carries no
# supersedes_approval_ref and is not a renewal, but shipping that half leaves two live
# architecture decisions with contradictory deployment sections, which Constitution I
# forbids. The one edit that clears it rewrites APP-013, and Constitution VI forbids
# that: supersession is explicit and never rewrites prior authority.
#
# An earlier project note recorded supersession as unsupported because approval_packages
# admitted no accepted -> superseded transition. That has since been fixed and
# superseded_by is accepted, so the transition looks available if you read only the
# lifecycle table. The conclusion held for a different reason, one layer down, and this
# test pins that reason so it is not re-diagnosed from scratch a third time.
#
# FIXED. The history above is kept because it explains why four checks were arranged
# this way; what follows is what now holds. An approved package is an immutable record,
# the registry is the present, and exactly one approved package GOVERNS each artifact --
# the one the registry names in approval_ref. Registry agreement is judged only for that
# package; a package the registry has moved past is checked for lifecycle legality
# instead. See docs/superpowers/plans/2026-08-06-supersession-governing-package.md.
#
# Two assumptions in that plan were wrong, and finding out cost less than assuming.
# It proposed a new per-artifact invariant as the backstop for these relaxations. Both
# halves already existed: _state_errors compares the governing package's to_state to the
# registry state, and _package_evidence_errors requires every approval_ref to resolve to
# an approved package containing the artifact -- including the APP-001-bootstrap.md case
# the plan expected to have to special-case. So no new check was written. The second was
# untested, which was the real gap, and
# test_artifact_approval_ref_must_resolve_to_an_approved_package now pins it.


def superseding_package(root: Path, successor: str) -> dict[str, object]:
    """An approved package moving the renewed decision on to `superseded`."""
    document = "governance/decisions/KHEPRI-DEC-002.md"
    package: dict[str, object] = {
        "schema_version": 1,
        "id": "APP-004",
        "title": "Supersede the renewed decision",
        "state": "approved",
        "owner": "AHMED-SHAABAN",
        "scope": "Supersede the exact listed decision.",
        "exclusions": ["Product application code"],
        "artifacts": [
            {
                "id": "KHEPRI-DEC-002",
                "document": document,
                "document_sha256": document_digest(root / document),
                "from_state": "accepted",
                "to_state": "superseded",
                "superseded_by": successor,
                "supersedes_approval_ref": "governance/approvals/APP-003.yaml",
            }
        ],
    }
    digest = manifest_digest(package)
    package["manifest_digest"] = digest
    package["approval"] = {
        "approved_by": "AHMED-SHAABAN",
        "approved_at": "2026-07-31",
        "approved_manifest_digest": digest,
        "evidence_ref": (
            "https://github.com/Kemetra/Khepri/pull/6#pullrequestreview-0000000001"
        ),
    }
    return package


def supersede_in_registry(root: Path, successor: str) -> None:
    """Record the onward move, so the transition is registered rather than implied."""
    decisions_path = root_path(root, "decisions")
    decisions = read_yaml(decisions_path)
    decisions["decisions"][1].update(  # type: ignore[index]
        {
            "state": "superseded",
            "approved_at": "2026-07-31",
            "approval_ref": "governance/approvals/APP-004.yaml",
            "superseded_by": successor,
        }
    )
    write_yaml(decisions_path, decisions)


def registry_successor(root: Path) -> str:
    decisions = read_yaml(root_path(root, "decisions"))
    return str(decisions["decisions"][0]["id"])  # type: ignore[index]


def test_approved_renewal_survives_a_later_supersession(tmp_path: Path) -> None:
    """An approved package records history, so a later recorded move must not break it.

    The onward move is registered here -- `APP-004` carries the
    `accepted -> superseded` entry -- so this asserts only that a *recorded* move does
    not retroactively invalidate the packages that preceded it.
    """
    valid_repository(tmp_path)
    _, _, renewal_path, renewal = approved_package_with_renewal(tmp_path)
    approve_renewal_in_registry(tmp_path, renewal_path, renewal)

    successor = registry_successor(tmp_path)
    write_yaml(
        tmp_path / "governance/approvals/APP-004.yaml",
        superseding_package(tmp_path, successor),
    )
    supersede_in_registry(tmp_path, successor)

    result = run_validator(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr


def test_approved_renewal_must_replace_registry_approval_ref(
    tmp_path: Path,
) -> None:
    valid_repository(tmp_path)
    _, _, renewal_path, renewal = approved_package_with_renewal(tmp_path)
    digest = manifest_digest(renewal)
    renewal["state"] = "approved"
    renewal["approval"] = {
        "approved_by": "AHMED-SHAABAN",
        "approved_at": "2026-07-30",
        "approved_manifest_digest": digest,
        "evidence_ref": (
            "https://github.com/Kemetra/Khepri/pull/5"
            "#pullrequestreview-0000000000"
        ),
    }
    write_yaml(renewal_path, renewal)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-003: KHEPRI-DEC-002 approval_ref must be "
        "governance/approvals/APP-003.yaml",
    )


def test_legacy_bootstrap_markdown_evidence_remains_valid(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    evidence = "governance/approvals/APP-001-bootstrap.md"
    write_document(tmp_path, evidence)
    decisions_path = root_path(tmp_path, "decisions")
    decisions = read_yaml(decisions_path)
    decisions["decisions"][0]["approval_ref"] = evidence  # type: ignore[index]
    write_yaml(decisions_path, decisions)

    result = run_validator(tmp_path)

    assert result.returncode == 0, result.stderr


def test_other_unstructured_approval_evidence_is_rejected(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    evidence = "governance/approvals/APP-999.md"
    write_document(tmp_path, evidence)
    decisions_path = root_path(tmp_path, "decisions")
    decisions = read_yaml(decisions_path)
    decisions["decisions"][0]["approval_ref"] = evidence  # type: ignore[index]
    write_yaml(decisions_path, decisions)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages: unstructured approval evidence is limited to "
        "APP-001-bootstrap.md",
    )


def test_document_digest_command(tmp_path: Path) -> None:
    document = tmp_path / "decision.md"
    document.write_bytes(b"# KHEPRI-DEC-002\n")

    result = run_cli(tmp_path, "document-digest", "decision.md")

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "sha256:9b08cd92ee3f228e9d7167a935ec8acf13567019c633471fa6dab2bc1f5790ef\n"
    )


def test_approval_digest_command(tmp_path: Path) -> None:
    path = tmp_path / "APP-002.yaml"
    write_yaml(path, example_package())

    result = run_cli(tmp_path, "approval-digest", "APP-002.yaml")

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "sha256:796d415bf26999eb891b4af35f1b4f49f814abb4ed83a1320e5f646fb0ac0f07\n"
    )


def test_digest_command_rejects_missing_path_without_traceback(
    tmp_path: Path,
) -> None:
    result = run_cli(tmp_path, "document-digest", "missing.md")

    assert result.returncode == 1
    assert result.stderr == "ERROR path does not resolve to a repository file\n"
    assert "Traceback" not in result.stderr


def test_approval_digest_rejects_malformed_package_without_traceback(
    tmp_path: Path,
) -> None:
    path = tmp_path / "APP-002.yaml"
    path.write_bytes(b"[invalid")

    result = run_cli(tmp_path, "approval-digest", "APP-002.yaml")

    assert result.returncode == 1
    assert result.stderr == "ERROR approval-packages:APP-002.yaml: invalid YAML\n"
    assert "Traceback" not in result.stderr


# The governing-package backstop, pinned before it is relied on.
#
# Supersession requires relaxing the checks that judge every approved package against
# the current registry. What makes that safe is a guard that already exists and was
# untested: _package_evidence_errors requires every artifact's approval_ref to resolve
# to an approved package containing that artifact. Together with the to_state check
# pinned above, it is the whole per-artifact invariant, so the relaxations below need
# no replacement check -- only this test, so a later edit cannot remove the backstop
# silently. See docs/superpowers/plans/2026-08-06-supersession-governing-package.md.


def test_artifact_approval_ref_must_resolve_to_an_approved_package(
    tmp_path: Path,
) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    approve_package(tmp_path, path, package)
    decisions_path = root_path(tmp_path, "decisions")
    decisions = read_yaml(decisions_path)
    decisions["decisions"][1]["approval_ref"] = "governance/approvals/APP-404.yaml"  # type: ignore[index]
    write_yaml(decisions_path, decisions)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages: KHEPRI-DEC-002 approval_ref must identify "
        "an approved package containing the artifact",
    )


def test_superseded_package_is_not_rejudged_against_a_moved_registry(
    tmp_path: Path,
) -> None:
    """A historical package records what was true, not a claim about the present."""
    valid_repository(tmp_path)
    _, _, renewal_path, renewal = approved_package_with_renewal(tmp_path)
    approve_renewal_in_registry(tmp_path, renewal_path, renewal)
    successor = registry_successor(tmp_path)
    write_yaml(
        tmp_path / "governance/approvals/APP-004.yaml",
        superseding_package(tmp_path, successor),
    )
    supersede_in_registry(tmp_path, successor)

    result = run_validator(tmp_path)

    assert "approved_at does not match package" not in result.stderr
    assert "approval_ref must be governance/approvals/APP-003.yaml" not in result.stderr
