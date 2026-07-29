from __future__ import annotations

import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parents[1]
REFERENCE_COMMIT = "f206b7f2c021c7d4e25ba131776ca4b22db6d876"


def write_yaml(path: Path, content: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")


def read_yaml(path: Path) -> dict[str, object]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def write_document(root: Path, relative_path: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {path.stem}\n", encoding="utf-8")


def valid_repository(root: Path) -> None:
    documents = [
        "governance/authorities/ahmed-shaaban.md",
        "governance/decisions/KHEPRI-DEC-001.md",
        "governance/families/FND.md",
        "governance/specifications/FND-001.md",
    ]
    for document in documents:
        write_document(root, document)

    registry = root / "governance" / "registries"
    write_yaml(
        registry / "authorities.yaml",
        {
            "schema_version": 1,
            "authorities": [
                {
                    "id": "AHMED-SHAABAN",
                    "name": "Ahmed Shaaban",
                    "roles": ["product_owner"],
                    "active": True,
                    "document": documents[0],
                }
            ],
        },
    )
    write_yaml(
        registry / "decisions.yaml",
        {
            "schema_version": 1,
            "decisions": [
                {
                    "id": "KHEPRI-DEC-001",
                    "title": "Successor policy",
                    "state": "accepted",
                    "owner": "AHMED-SHAABAN",
                    "document": documents[1],
                    "approved_by": "AHMED-SHAABAN",
                    "approved_at": "2026-07-29",
                    "approval_ref": "https://github.com/Kemetra/Khepri/pull/1",
                }
            ],
        },
    )
    write_yaml(
        registry / "families.yaml",
        {
            "schema_version": 1,
            "families": [
                {
                    "id": "FND",
                    "name": "Platform Foundation",
                    "state": "active",
                    "owner": "AHMED-SHAABAN",
                    "document": documents[2],
                    "depends_on": [],
                    "approved_by": "AHMED-SHAABAN",
                    "approved_at": "2026-07-29",
                    "approval_ref": "https://github.com/Kemetra/Khepri/pull/1",
                }
            ],
        },
    )
    write_yaml(
        registry / "specifications.yaml",
        {
            "schema_version": 1,
            "specifications": [
                {
                    "id": "FND-001",
                    "title": "Governance Kernel and Repository Controls",
                    "state": "approved",
                    "family": "FND",
                    "owner": "AHMED-SHAABAN",
                    "document": documents[3],
                    "depends_on": [],
                    "approved_by": "AHMED-SHAABAN",
                    "approved_at": "2026-07-29",
                    "approval_ref": "https://github.com/Kemetra/Khepri/pull/1",
                }
            ],
        },
    )
    write_yaml(
        registry / "reference-assessments.yaml",
        {
            "schema_version": 1,
            "source_repository": "Kemetra/Seshat-Platform",
            "source_commit": REFERENCE_COMMIT,
            "assessments": [
                {
                    "source_id": f"SESHAT-SPEC-{index:03d}",
                    "sources": [
                        {
                            "path": f"specs/{index:03d}-capability/spec.md",
                            "blob_id": f"{index:040x}",
                        }
                    ],
                    "review_state": "pending",
                    "disposition": "candidate",
                    "rationale": "Awaiting bounded Khepri review.",
                    "target_artifact_ids": [],
                }
                for index in range(1, 43)
            ],
        },
    )


def run_cli(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    source_path = str(PROJECT_ROOT / "src")
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in [source_path, environment.get("PYTHONPATH", "")] if part
    )
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "khepri_gov.cli",
            "--root",
            str(root),
            *arguments,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def run_validator(root: Path) -> subprocess.CompletedProcess[str]:
    return run_cli(root, "validate")


def registry_path(root: Path, name: str) -> Path:
    return root / "governance" / "registries" / f"{name}.yaml"


def first_assessment(root: Path) -> tuple[Path, dict[str, object], dict[str, object]]:
    path = registry_path(root, "reference-assessments")
    data = read_yaml(path)
    assessments = data["assessments"]
    assert isinstance(assessments, list)
    assessment = assessments[0]
    assert isinstance(assessment, dict)
    return path, data, assessment


def assert_invalid(result: subprocess.CompletedProcess[str], message: str) -> None:
    assert result.returncode != 0
    assert message in result.stderr
    assert result.stdout == ""


def test_valid_governance_graph_exits_successfully(tmp_path: Path) -> None:
    valid_repository(tmp_path)

    result = run_validator(tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "Governance validation passed.\n"


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path = registry_path(tmp_path, "specifications")
    data = read_yaml(path)
    specifications = data["specifications"]
    assert isinstance(specifications, list)
    specifications.append(deepcopy(specifications[0]))
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, "specifications:FND-001: duplicate id")


def test_unknown_owners_are_rejected(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path = registry_path(tmp_path, "families")
    data = read_yaml(path)
    data["families"][0]["owner"] = "UNKNOWN"  # type: ignore[index]
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, "families:FND: unknown owner 'UNKNOWN'")


@pytest.mark.parametrize(
    ("registry", "collection", "state", "message"),
    [
        ("decisions", "decisions", "approved", "invalid state 'approved'"),
        ("families", "families", "paused", "invalid state 'paused'"),
        ("specifications", "specifications", "accepted", "invalid state 'accepted'"),
    ],
)
def test_lifecycle_states_are_closed(
    tmp_path: Path,
    registry: str,
    collection: str,
    state: str,
    message: str,
) -> None:
    valid_repository(tmp_path)
    path = registry_path(tmp_path, registry)
    data = read_yaml(path)
    data[collection][0]["state"] = state  # type: ignore[index]
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, message)


def test_missing_document_is_rejected(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    (tmp_path / "governance" / "specifications" / "FND-001.md").unlink()

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "specifications:FND-001: document does not exist: "
        "governance/specifications/FND-001.md",
    )


@pytest.mark.parametrize("field", ["approved_by", "approved_at", "approval_ref"])
def test_accepted_artifacts_require_complete_approval_evidence(
    tmp_path: Path,
    field: str,
) -> None:
    valid_repository(tmp_path)
    path = registry_path(tmp_path, "specifications")
    data = read_yaml(path)
    del data["specifications"][0][field]  # type: ignore[index]
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, f"specifications:FND-001: missing approval field '{field}'")


def test_accepted_artifacts_reject_non_string_approvers(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path = registry_path(tmp_path, "specifications")
    data = read_yaml(path)
    data["specifications"][0]["approved_by"] = ["AHMED-SHAABAN"]  # type: ignore[index]
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "specifications:FND-001: approved_by must be a string authority id",
    )


def test_draft_specifications_do_not_claim_approval(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path = registry_path(tmp_path, "specifications")
    data = read_yaml(path)
    specification = data["specifications"][0]  # type: ignore[index]
    specification["state"] = "draft"
    for field in ("approved_by", "approved_at", "approval_ref"):
        del specification[field]
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert result.returncode == 0, result.stderr


def test_unknown_dependencies_are_rejected(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path = registry_path(tmp_path, "specifications")
    data = read_yaml(path)
    data["specifications"][0]["depends_on"] = ["FND-999"]  # type: ignore[index]
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, "specifications:FND-001: unknown dependency 'FND-999'")


def test_dependency_cycles_are_rejected(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path = registry_path(tmp_path, "specifications")
    data = read_yaml(path)
    specifications = data["specifications"]
    assert isinstance(specifications, list)
    specifications[0]["depends_on"] = ["FND-002"]
    second = deepcopy(specifications[0])
    second.update(
        {
            "id": "FND-002",
            "title": "Second specification",
            "depends_on": ["FND-001"],
        }
    )
    specifications.append(second)
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "specifications: dependency cycle: FND-001 -> FND-002 -> FND-001",
    )


@pytest.mark.parametrize(
    ("family", "family_state", "message"),
    [
        ("UNKNOWN", None, "specifications:FND-001: unknown family 'UNKNOWN'"),
        ("FND", "retired", "specifications:FND-001: family 'FND' is not active"),
    ],
)
def test_specifications_require_an_active_known_family(
    tmp_path: Path,
    family: str,
    family_state: str | None,
    message: str,
) -> None:
    valid_repository(tmp_path)
    specification_path = registry_path(tmp_path, "specifications")
    specifications = read_yaml(specification_path)
    specifications["specifications"][0]["family"] = family  # type: ignore[index]
    write_yaml(specification_path, specifications)
    if family_state is not None:
        family_path = registry_path(tmp_path, "families")
        families = read_yaml(family_path)
        families["families"][0]["state"] = family_state  # type: ignore[index]
        write_yaml(family_path, families)

    result = run_validator(tmp_path)

    assert_invalid(result, message)


def test_draft_specification_can_prepare_a_proposed_family(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    family_path = registry_path(tmp_path, "families")
    families = read_yaml(family_path)
    family = families["families"][0]  # type: ignore[index]
    family["state"] = "proposed"
    for field in ("approved_by", "approved_at", "approval_ref"):
        del family[field]
    write_yaml(family_path, families)
    specification_path = registry_path(tmp_path, "specifications")
    specifications = read_yaml(specification_path)
    specification = specifications["specifications"][0]  # type: ignore[index]
    specification["state"] = "draft"
    for field in ("approved_by", "approved_at", "approval_ref"):
        del specification[field]
    write_yaml(specification_path, specifications)

    result = run_validator(tmp_path)

    assert result.returncode == 0, result.stderr


def test_specifications_reject_non_string_family_ids(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path = registry_path(tmp_path, "specifications")
    data = read_yaml(path)
    data["specifications"][0]["family"] = None  # type: ignore[index]
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, "specifications:FND-001: family must be a string id")


def test_unhashable_states_fail_closed_without_a_traceback(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path = registry_path(tmp_path, "families")
    data = read_yaml(path)
    data["families"][0]["state"] = []  # type: ignore[index]
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, "families:FND: invalid state []")
    assert "Traceback" not in result.stderr


def test_unknown_schema_versions_fail_closed(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path = registry_path(tmp_path, "authorities")
    data = read_yaml(path)
    data["schema_version"] = 2
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, "authorities: unsupported schema_version 2; expected integer 1")


@pytest.mark.parametrize("version", [True, 1.0])
def test_schema_version_must_be_an_integer(tmp_path: Path, version: object) -> None:
    valid_repository(tmp_path)
    path = registry_path(tmp_path, "authorities")
    data = read_yaml(path)
    data["schema_version"] = version
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        f"authorities: unsupported schema_version {version!r}; expected integer 1",
    )


def test_missing_registry_fails_closed(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    registry_path(tmp_path, "decisions").unlink()

    result = run_validator(tmp_path)

    assert_invalid(result, "decisions: registry does not exist")


def test_invalid_yaml_fails_closed_without_a_traceback(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    registry_path(tmp_path, "families").write_text("families: [\n", encoding="utf-8")

    result = run_validator(tmp_path)

    assert_invalid(result, "families: invalid YAML")
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "source_repository",
            "Kemetra/Other",
            "source_repository must be 'Kemetra/Seshat-Platform'",
        ),
        (
            "source_commit",
            "0" * 40,
            f"source_commit must be '{REFERENCE_COMMIT}'",
        ),
    ],
)
def test_reference_registry_requires_exact_source_pin(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    valid_repository(tmp_path)
    path = registry_path(tmp_path, "reference-assessments")
    data = read_yaml(path)
    data[field] = value
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, message)


def test_reference_registry_requires_all_42_assessments(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path = registry_path(tmp_path, "reference-assessments")
    data = read_yaml(path)
    data["assessments"].pop()  # type: ignore[union-attr]
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, "reference-assessments: expected 42 assessments; found 41")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("review_state", "approved", "invalid review_state 'approved'"),
        ("disposition", "copied", "invalid disposition 'copied'"),
    ],
)
def test_reference_states_and_dispositions_are_closed(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    valid_repository(tmp_path)
    path, data, assessment = first_assessment(tmp_path)
    assessment[field] = value
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, message)


def test_duplicate_reference_ids_and_paths_are_rejected(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path = registry_path(tmp_path, "reference-assessments")
    data = read_yaml(path)
    assessments = data["assessments"]
    assessments[1]["source_id"] = assessments[0]["source_id"]  # type: ignore[index]
    assessments[1]["sources"] = deepcopy(assessments[0]["sources"])  # type: ignore[index]
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, "duplicate source_id")
    assert "duplicate source path" in result.stderr
    assert "duplicate source reference" in result.stderr


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("path", "../spec.md", "malformed source path '../spec.md'"),
        ("path", r"specs\001\spec.md", r"malformed source path 'specs\\001\\spec.md'"),
        ("path", "C:/spec.md", "malformed source path 'C:/spec.md'"),
        ("path", "specs//001/spec.md", "malformed source path 'specs//001/spec.md'"),
        ("blob_id", "not-a-blob", "malformed Git blob id 'not-a-blob'"),
    ],
)
def test_malformed_reference_sources_are_rejected(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    valid_repository(tmp_path)
    path, data, assessment = first_assessment(tmp_path)
    assessment["sources"][0][field] = value  # type: ignore[index]
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, message)


@pytest.mark.parametrize("field", ["reviewed_by", "reviewed_at", "review_ref"])
def test_reviewed_references_require_complete_evidence(
    tmp_path: Path,
    field: str,
) -> None:
    valid_repository(tmp_path)
    path, data, assessment = first_assessment(tmp_path)
    assessment.update(
        {
            "review_state": "reviewed",
            "disposition": "deferred",
            "reviewed_by": "AUTOMATION-CODEX",
            "reviewed_at": "2026-07-29",
            "review_ref": "https://github.com/Kemetra/Khepri/pull/2",
        }
    )
    del assessment[field]
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, f"missing review evidence field '{field}'")


def test_pending_references_cannot_claim_review_evidence(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, data, assessment = first_assessment(tmp_path)
    assessment["reviewed_by"] = "AHMED-SHAABAN"
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, "pending assessment must not claim 'reviewed_by'")


def test_reviewed_at_requires_an_iso_date(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, data, assessment = first_assessment(tmp_path)
    assessment.update(
        {
            "review_state": "reviewed",
            "disposition": "deferred",
            "reviewed_by": "AUTOMATION-CODEX",
            "reviewed_at": "29 July",
            "review_ref": "https://github.com/Kemetra/Khepri/pull/2",
        }
    )
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, "reviewed_at must be an ISO 8601 date")


def test_adapted_reference_requires_existing_unique_targets(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, data, assessment = first_assessment(tmp_path)
    assessment.update(
        {
            "review_state": "reviewed",
            "disposition": "adapted",
            "target_artifact_ids": ["FND-001", "FND-001", "UNKNOWN"],
            "reviewed_by": "AUTOMATION-CODEX",
            "reviewed_at": "2026-07-29",
            "review_ref": "https://github.com/Kemetra/Khepri/pull/2",
        }
    )
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, "duplicate target artifact id")
    assert "unknown target artifact 'UNKNOWN'" in result.stderr


def test_adapted_reference_cannot_target_an_authority(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, data, assessment = first_assessment(tmp_path)
    assessment.update(
        {
            "review_state": "reviewed",
            "disposition": "adapted",
            "target_artifact_ids": ["AHMED-SHAABAN"],
            "reviewed_by": "AUTOMATION-CODEX",
            "reviewed_at": "2026-07-29",
            "review_ref": "https://github.com/Kemetra/Khepri/pull/2",
        }
    )
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, "unknown target artifact 'AHMED-SHAABAN'")


def test_adapted_reference_rejects_an_empty_target_list(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, data, assessment = first_assessment(tmp_path)
    assessment.update(
        {
            "review_state": "reviewed",
            "disposition": "adapted",
            "reviewed_by": "AUTOMATION-CODEX",
            "reviewed_at": "2026-07-29",
            "review_ref": "https://github.com/Kemetra/Khepri/pull/2",
        }
    )
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, "adapted assessment requires an existing Khepri target")


def test_non_adapted_reference_cannot_name_targets(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, data, assessment = first_assessment(tmp_path)
    assessment["target_artifact_ids"] = ["FND-001"]
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, "candidate assessment must not name targets")


def test_missing_reference_registry_fails_closed(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    registry_path(tmp_path, "reference-assessments").unlink()

    result = run_validator(tmp_path)

    assert_invalid(result, "reference-assessments: registry does not exist")
