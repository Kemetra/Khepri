from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from khepri_gov.validator import validate_repository
from tests.governance_support import decision, valid_artifacts, write_raw_registry, write_registry


def test_repository_registry_is_valid() -> None:
    root = Path(__file__).parents[1]
    assert validate_repository(root) == []


def test_valid_registry_passes(tmp_path: Path) -> None:
    write_registry(tmp_path, valid_artifacts())
    assert validate_repository(tmp_path) == []


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("[not: valid", "registry: invalid YAML"),
        ("[]", "registry: root must be a mapping"),
        ("schema_version: 1\nartifacts: []\n", "registry: unsupported schema_version 1"),
        ("schema_version: 2\n", "registry: artifacts must be a non-empty list"),
        ("schema_version: 2\nartifacts: []\n", "registry: artifacts must be a non-empty list"),
    ],
)
def test_registry_shape_fails_closed(tmp_path: Path, content: str, expected: str) -> None:
    write_raw_registry(tmp_path, content)
    assert validate_repository(tmp_path) == [expected]


def test_registry_rejects_unknown_top_level_fields(tmp_path: Path) -> None:
    write_raw_registry(tmp_path, "schema_version: 2\nartifacts: [{}]\nextra: true\n")
    assert "registry: unknown fields: extra" in validate_repository(tmp_path)


def test_artifact_requires_exact_fields(tmp_path: Path) -> None:
    artifacts = valid_artifacts()
    del artifacts[0]["state"]
    artifacts[0]["owner"] = "AHMED-SHAABAN"
    write_registry(tmp_path, artifacts)
    errors = validate_repository(tmp_path)
    assert "registry: artifact[0]: missing fields: state" in errors
    assert "registry: artifact[0]: unknown fields: owner" in errors


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("type", "authority", "registry: FND: unsupported type 'authority'"),
        ("state", "proposed", "registry: FND: unsupported state 'proposed'"),
        ("id", "", "registry: artifact[0]: id must be a non-empty string"),
        ("depends_on", "FND-001", "registry: FND: depends_on must be a list of identifiers"),
    ],
)
def test_artifact_values_use_closed_shapes(
    tmp_path: Path,
    field: str,
    value: object,
    expected: str,
) -> None:
    artifacts = valid_artifacts()
    artifacts[0][field] = value
    write_registry(tmp_path, artifacts)
    assert expected in validate_repository(tmp_path)


def test_identifiers_and_documents_are_unique(tmp_path: Path) -> None:
    artifacts = valid_artifacts()
    duplicate = deepcopy(artifacts[0])
    duplicate["document"] = artifacts[1]["document"]
    artifacts.append(duplicate)
    write_registry(tmp_path, artifacts)
    errors = validate_repository(tmp_path)
    assert "registry: duplicate id 'FND'" in errors
    assert "registry: duplicate document 'governance/specifications/FND-001.md'" in errors


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        ("../FND.md", "registry: FND: document must be a repository-relative Markdown path"),
        ("governance/families/FND.txt", "registry: FND: document must be a Markdown file"),
        ("missing/FND.md", "registry: FND: document does not exist: missing/FND.md"),
    ],
)
def test_document_paths_are_safe_and_existing(
    tmp_path: Path,
    document: str,
    expected: str,
) -> None:
    artifacts = valid_artifacts()
    artifacts[0]["document"] = document
    write_registry(tmp_path, artifacts)
    if document == "missing/FND.md":
        (tmp_path / document).unlink()
    assert expected in validate_repository(tmp_path)


def test_dependencies_must_be_known_unique_and_not_self(tmp_path: Path) -> None:
    artifacts = valid_artifacts()
    artifacts[1]["depends_on"] = ["FND-001", "UNKNOWN", "UNKNOWN"]
    write_registry(tmp_path, artifacts)
    errors = validate_repository(tmp_path)
    assert "registry: FND-001: cannot depend on itself" in errors
    assert "registry: FND-001: unknown dependency 'UNKNOWN'" in errors
    assert "registry: FND-001: duplicate dependency 'UNKNOWN'" in errors


def test_dependency_cycles_are_rejected(tmp_path: Path) -> None:
    artifacts = valid_artifacts()
    artifacts[0]["depends_on"] = ["FND-001"]
    write_registry(tmp_path, artifacts)
    assert "registry: dependency cycle: FND -> FND-001 -> FND" in validate_repository(tmp_path)


def test_specification_requires_exactly_one_family_dependency(tmp_path: Path) -> None:
    artifacts = valid_artifacts()
    artifacts.append(
        {
            "type": "family",
            "id": "RRA",
            "state": "active",
            "document": "governance/families/RRA.md",
            "depends_on": [],
        }
    )
    artifacts[1]["depends_on"] = ["FND", "RRA"]
    write_registry(tmp_path, artifacts)
    assert (
        "registry: FND-001: specification must depend on exactly one family"
        in validate_repository(tmp_path)
    )


def test_active_artifact_cannot_depend_on_retired_artifact(tmp_path: Path) -> None:
    artifacts = valid_artifacts()
    artifacts[0]["state"] = "retired"
    write_registry(tmp_path, artifacts)
    assert (
        "registry: FND-001: active artifact depends on retired artifact 'FND'"
        in validate_repository(tmp_path)
    )


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (
            {"state": "active", "superseded_by": "KHEPRI-DEC-002"},
            "registry: KHEPRI-DEC-001: only retired artifacts may name superseded_by",
        ),
        (
            {"state": "retired", "superseded_by": "UNKNOWN"},
            "registry: KHEPRI-DEC-001: unknown successor 'UNKNOWN'",
        ),
        (
            {"state": "retired", "superseded_by": "KHEPRI-DEC-001"},
            "registry: KHEPRI-DEC-001: cannot supersede itself",
        ),
    ],
)
def test_supersession_requires_a_distinct_known_active_peer(
    tmp_path: Path,
    change: dict[str, str],
    expected: str,
) -> None:
    first = decision()
    first.update(change)
    artifacts = [first, decision("KHEPRI-DEC-002")]
    write_registry(tmp_path, artifacts)
    assert expected in validate_repository(tmp_path)


def test_successor_must_be_active_and_have_the_same_type(tmp_path: Path) -> None:
    first = decision(state="retired")
    first["superseded_by"] = "FND"
    artifacts = valid_artifacts() + [first]
    write_registry(tmp_path, artifacts)
    assert (
        "registry: KHEPRI-DEC-001: successor 'FND' must have type 'decision'"
        in validate_repository(tmp_path)
    )

    first["superseded_by"] = "KHEPRI-DEC-002"
    artifacts.append(decision("KHEPRI-DEC-002", state="retired"))
    write_registry(tmp_path, artifacts)
    assert (
        "registry: KHEPRI-DEC-001: successor 'KHEPRI-DEC-002' must be active"
        in validate_repository(tmp_path)
    )
