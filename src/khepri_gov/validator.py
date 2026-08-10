from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import yaml

from khepri_gov.approval_packages import validate_approval_packages
from khepri_gov.lifecycle import decision_supersession_errors
from khepri_gov.lifecycle_conditions import (
    lifecycle_condition_errors,
    scan_repository,
)

SCHEMA_VERSION = 1
REGISTRY_NAMES = ("authorities", "decisions", "families", "specifications")
REFERENCE_REGISTRY_NAME = "reference-assessments"
REFERENCE_REPOSITORY = "Kemetra/Seshat-Platform"
REFERENCE_COMMIT = "f206b7f2c021c7d4e25ba131776ca4b22db6d876"
REFERENCE_COUNT = 42
REFERENCE_REVIEW_STATES = {"pending", "reviewed"}
REFERENCE_DISPOSITIONS = {"candidate", "adapted", "deferred", "rejected"}
REVIEW_EVIDENCE_FIELDS = ("reviewed_by", "reviewed_at", "review_ref")
GIT_OBJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{40}$")
STATE_VOCABULARIES = {
    "decisions": {"proposed", "accepted", "rejected", "superseded"},
    "families": {"proposed", "active", "retired"},
    "specifications": {"draft", "approved", "implemented", "verified", "retired"},
}
APPROVED_STATES = {
    "decisions": {"accepted", "superseded"},
    "families": {"active", "retired"},
    "specifications": {"approved", "implemented", "verified", "retired"},
}
REQUIRED_FIELDS = {
    "authorities": {"id", "name", "roles", "active", "document", "human"},
    "decisions": {"id", "title", "state", "owner", "document"},
    "families": {"id", "name", "state", "owner", "document", "depends_on"},
    "specifications": {
        "id",
        "title",
        "state",
        "family",
        "owner",
        "document",
        "depends_on",
    },
}
APPROVAL_FIELDS = ("approved_by", "approved_at", "approval_ref")

Artifact = dict[str, Any]


def _load_registry(root: Path, name: str, errors: list[str]) -> list[Artifact] | None:
    path = root / "governance" / "registries" / f"{name}.yaml"
    if not path.is_file():
        errors.append(f"{name}: registry does not exist")
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        errors.append(f"{name}: invalid YAML")
        return None
    if not isinstance(data, dict):
        errors.append(f"{name}: registry root must be a mapping")
        return None
    version = data.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        errors.append(
            f"{name}: unsupported schema_version {version!r}; "
            f"expected integer {SCHEMA_VERSION}"
        )
    artifacts = data.get(name)
    if not isinstance(artifacts, list):
        errors.append(f"{name}: '{name}' must be a list")
        return None
    if not all(isinstance(artifact, dict) for artifact in artifacts):
        errors.append(f"{name}: every entry must be a mapping")
        return None
    return artifacts


def _artifact_label(registry: str, artifact: Artifact, index: int) -> str:
    artifact_id = artifact.get("id")
    if isinstance(artifact_id, str) and artifact_id:
        return f"{registry}:{artifact_id}"
    return f"{registry}:entry-{index + 1}"


def _validate_shape(
    root: Path,
    registry: str,
    artifacts: list[Artifact],
    errors: list[str],
) -> None:
    seen_ids: set[str] = set()
    for index, artifact in enumerate(artifacts):
        label = _artifact_label(registry, artifact, index)
        for field in sorted(REQUIRED_FIELDS[registry]):
            if field not in artifact:
                errors.append(f"{label}: missing required field '{field}'")

        artifact_id = artifact.get("id")
        if not isinstance(artifact_id, str) or not artifact_id.strip():
            errors.append(f"{label}: id must be a non-empty string")
        elif artifact_id in seen_ids:
            errors.append(f"{label}: duplicate id")
        else:
            seen_ids.add(artifact_id)

        if registry in STATE_VOCABULARIES:
            state = artifact.get("state")
            if not isinstance(state, str) or state not in STATE_VOCABULARIES[registry]:
                errors.append(f"{label}: invalid state {state!r}")

        _validate_document(root, label, artifact.get("document"), errors)

        if registry == "authorities":
            if not isinstance(artifact.get("active"), bool):
                errors.append(f"{label}: active must be a boolean")
            if not isinstance(artifact.get("human"), bool):
                errors.append(f"{label}: human must be a boolean")
            roles = artifact.get("roles")
            if not isinstance(roles, list) or not roles or not all(
                isinstance(role, str) and role for role in roles
            ):
                errors.append(f"{label}: roles must be a non-empty list of strings")
        elif not isinstance(artifact.get("owner"), str):
            errors.append(f"{label}: owner must be a string")

        if registry in {"families", "specifications"}:
            dependencies = artifact.get("depends_on")
            if not isinstance(dependencies, list) or not all(
                isinstance(dependency, str) and dependency for dependency in dependencies
            ):
                errors.append(f"{label}: depends_on must be a list of ids")


def _validate_document(
    root: Path,
    label: str,
    document: object,
    errors: list[str],
) -> None:
    if not isinstance(document, str) or not document:
        errors.append(f"{label}: document must be a non-empty relative path")
        return
    document_path = Path(document)
    if document_path.is_absolute():
        errors.append(f"{label}: document must be a relative path: {document}")
        return
    resolved_root = root.resolve()
    resolved_document = (root / document_path).resolve()
    if not resolved_document.is_relative_to(resolved_root):
        errors.append(f"{label}: document escapes repository root: {document}")
    elif not resolved_document.is_file():
        errors.append(f"{label}: document does not exist: {document}")


def _authority_ids(registries: dict[str, list[Artifact]]) -> tuple[set[str], set[str]]:
    known: set[str] = set()
    active: set[str] = set()
    for authority in registries.get("authorities", []):
        authority_id = authority.get("id")
        if isinstance(authority_id, str):
            known.add(authority_id)
            if authority.get("active") is True:
                active.add(authority_id)
    return known, active


def _validate_authorities(
    root: Path,
    registries: dict[str, list[Artifact]],
    errors: list[str],
) -> None:
    known, active = _authority_ids(registries)
    for registry in ("decisions", "families", "specifications"):
        for index, artifact in enumerate(registries.get(registry, [])):
            label = _artifact_label(registry, artifact, index)
            owner = artifact.get("owner")
            if isinstance(owner, str) and owner not in known:
                errors.append(f"{label}: unknown owner {owner!r}")
            elif isinstance(owner, str) and owner not in active:
                errors.append(f"{label}: owner {owner!r} is inactive")

            state = artifact.get("state")
            if not isinstance(state, str) or state not in APPROVED_STATES[registry]:
                continue
            for field in APPROVAL_FIELDS:
                if field not in artifact or artifact[field] in ("", None):
                    errors.append(f"{label}: missing approval field '{field}'")
            approved_by = artifact.get("approved_by")
            if approved_by not in ("", None) and not isinstance(approved_by, str):
                errors.append(f"{label}: approved_by must be a string authority id")
            elif isinstance(approved_by, str) and approved_by not in known:
                errors.append(f"{label}: unknown approver {approved_by!r}")
            elif isinstance(approved_by, str) and approved_by not in active:
                errors.append(f"{label}: approver {approved_by!r} is inactive")
            _validate_iso_date(
                label,
                "approved_at",
                artifact.get("approved_at"),
                errors,
            )
            _validate_approval_ref(
                root,
                label,
                artifact.get("approval_ref"),
                errors,
            )


def _validate_iso_date(
    label: str,
    field: str,
    value: object,
    errors: list[str],
) -> None:
    if value in (None, ""):
        return
    if isinstance(value, (date, datetime)):
        return
    if isinstance(value, str):
        try:
            date.fromisoformat(value)
        except ValueError:
            errors.append(f"{label}: {field} must be an ISO 8601 date")
        return
    errors.append(f"{label}: {field} must be an ISO 8601 date")


def _validate_approval_ref(
    root: Path,
    label: str,
    approval_ref: object,
    errors: list[str],
) -> None:
    if approval_ref in (None, ""):
        return
    if not isinstance(approval_ref, str):
        errors.append(f"{label}: approval_ref must be a URL or repository-relative path")
        return
    parsed = urlparse(approval_ref)
    if parsed.scheme in {"https", "http"} and parsed.netloc:
        return
    reference_path = Path(approval_ref)
    if (
        reference_path.is_absolute()
        or not (root / reference_path).resolve().is_relative_to(root.resolve())
        or not (root / reference_path).is_file()
    ):
        errors.append(f"{label}: approval_ref does not resolve to evidence: {approval_ref}")


def _validate_global_ids(
    registries: dict[str, list[Artifact]],
    errors: list[str],
) -> None:
    seen: dict[str, str] = {}
    for registry in REGISTRY_NAMES:
        for index, artifact in enumerate(registries.get(registry, [])):
            artifact_id = artifact.get("id")
            if not isinstance(artifact_id, str) or not artifact_id:
                continue
            previous = seen.get(artifact_id)
            if previous is not None and previous != registry:
                label = _artifact_label(registry, artifact, index)
                errors.append(f"{label}: id collides with {previous}")
            else:
                seen[artifact_id] = registry


def _validate_family_relationships(
    registries: dict[str, list[Artifact]],
    errors: list[str],
) -> None:
    families = {
        family["id"]: family
        for family in registries.get("families", [])
        if isinstance(family.get("id"), str)
    }
    for index, specification in enumerate(registries.get("specifications", [])):
        label = _artifact_label("specifications", specification, index)
        family_id = specification.get("family")
        if not isinstance(family_id, str):
            errors.append(f"{label}: family must be a string id")
            continue
        if family_id not in families:
            errors.append(f"{label}: unknown family {family_id!r}")
            continue
        specification_state = specification.get("state")
        family_state = families[family_id].get("state")
        if specification_state in APPROVED_STATES["specifications"] and family_state != "active":
            errors.append(f"{label}: family {family_id!r} is not active")
        elif specification_state == "draft" and family_state not in {"proposed", "active"}:
            errors.append(
                f"{label}: draft family {family_id!r} must be proposed or active"
            )
        specification_id = specification.get("id")
        if isinstance(specification_id, str) and not specification_id.startswith(
            f"{family_id}-"
        ):
            errors.append(f"{label}: id must use family prefix '{family_id}-'")


def _validate_dependencies(
    registry: str,
    artifacts: list[Artifact],
    errors: list[str],
) -> None:
    known = {
        artifact["id"]
        for artifact in artifacts
        if isinstance(artifact.get("id"), str)
    }
    graph: dict[str, list[str]] = {}
    for index, artifact in enumerate(artifacts):
        artifact_id = artifact.get("id")
        dependencies = artifact.get("depends_on")
        if not isinstance(artifact_id, str) or not isinstance(dependencies, list):
            continue
        valid_dependencies: list[str] = []
        for dependency in dependencies:
            if not isinstance(dependency, str):
                continue
            if dependency not in known:
                label = _artifact_label(registry, artifact, index)
                errors.append(f"{label}: unknown dependency {dependency!r}")
            else:
                valid_dependencies.append(dependency)
        graph[artifact_id] = valid_dependencies
    cycle = _find_cycle(graph)
    if cycle:
        errors.append(f"{registry}: dependency cycle: {' -> '.join(cycle)}")


def _find_cycle(graph: dict[str, list[str]]) -> list[str]:
    visited: set[str] = set()
    active: list[str] = []
    active_set: set[str] = set()

    def visit(node: str) -> list[str]:
        if node in active_set:
            start = active.index(node)
            return [*active[start:], node]
        if node in visited:
            return []
        active.append(node)
        active_set.add(node)
        for dependency in graph.get(node, []):
            cycle = visit(dependency)
            if cycle:
                return cycle
        active.pop()
        active_set.remove(node)
        visited.add(node)
        return []

    for node in graph:
        cycle = visit(node)
        if cycle:
            return cycle
    return []


def _load_reference_assessments(root: Path, errors: list[str]) -> list[Artifact] | None:
    path = root / "governance" / "registries" / "reference-assessments.yaml"
    if not path.is_file():
        errors.append(f"{REFERENCE_REGISTRY_NAME}: registry does not exist")
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        errors.append(f"{REFERENCE_REGISTRY_NAME}: invalid YAML")
        return None
    if not isinstance(data, dict):
        errors.append(f"{REFERENCE_REGISTRY_NAME}: registry root must be a mapping")
        return None
    version = data.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        errors.append(
            f"{REFERENCE_REGISTRY_NAME}: unsupported schema_version {version!r}; "
            f"expected integer {SCHEMA_VERSION}"
        )
    repository = data.get("source_repository")
    if repository != REFERENCE_REPOSITORY:
        errors.append(
            f"{REFERENCE_REGISTRY_NAME}: source_repository must be "
            f"{REFERENCE_REPOSITORY!r}"
        )
    commit = data.get("source_commit")
    if commit != REFERENCE_COMMIT:
        errors.append(
            f"{REFERENCE_REGISTRY_NAME}: source_commit must be {REFERENCE_COMMIT!r}"
        )
    assessments = data.get("assessments")
    if not isinstance(assessments, list):
        errors.append(f"{REFERENCE_REGISTRY_NAME}: 'assessments' must be a list")
        return None
    if not all(isinstance(assessment, dict) for assessment in assessments):
        errors.append(f"{REFERENCE_REGISTRY_NAME}: every entry must be a mapping")
        return None
    if len(assessments) != REFERENCE_COUNT:
        errors.append(
            f"{REFERENCE_REGISTRY_NAME}: expected {REFERENCE_COUNT} assessments; "
            f"found {len(assessments)}"
        )
    return assessments


def _validate_reference_path(label: str, value: object, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label}: source path must be a non-empty string")
        return None
    path = PurePosixPath(value)
    if (
        "\\" in value
        or value != value.strip()
        or path.as_posix() != value
        or path.is_absolute()
        or (path.parts and ":" in path.parts[0])
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        errors.append(f"{label}: malformed source path {value!r}")
        return None
    return value


def _validate_review_evidence(
    root: Path,
    label: str,
    assessment: Artifact,
    errors: list[str],
) -> None:
    for field in REVIEW_EVIDENCE_FIELDS:
        if field not in assessment or assessment[field] in ("", None):
            errors.append(f"{label}: missing review evidence field '{field}'")
    reviewer = assessment.get("reviewed_by")
    if reviewer not in ("", None) and (
        not isinstance(reviewer, str) or not reviewer.strip()
    ):
        errors.append(f"{label}: reviewed_by must be a non-empty string")
    _validate_iso_date(
        label,
        "reviewed_at",
        assessment.get("reviewed_at"),
        errors,
    )
    _validate_approval_ref(root, label, assessment.get("review_ref"), errors)


def _validate_reference_assessments(
    root: Path,
    assessments: list[Artifact],
    registries: dict[str, list[Artifact]],
    errors: list[str],
) -> None:
    artifact_ids = {
        artifact_id
        for registry in ("decisions", "families", "specifications")
        for artifact in registries.get(registry, [])
        if isinstance((artifact_id := artifact.get("id")), str)
    }
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    seen_references: set[tuple[str, str]] = set()
    for index, assessment in enumerate(assessments):
        source_id = assessment.get("source_id")
        label = (
            f"{REFERENCE_REGISTRY_NAME}:{source_id}"
            if isinstance(source_id, str) and source_id
            else f"{REFERENCE_REGISTRY_NAME}:entry-{index + 1}"
        )
        for field in (
            "source_id",
            "sources",
            "review_state",
            "disposition",
            "rationale",
            "target_artifact_ids",
        ):
            if field not in assessment:
                errors.append(f"{label}: missing required field '{field}'")

        if not isinstance(source_id, str) or not source_id.strip():
            errors.append(f"{label}: source_id must be a non-empty string")
        elif source_id in seen_ids:
            errors.append(f"{label}: duplicate source_id")
        else:
            seen_ids.add(source_id)

        sources = assessment.get("sources")
        if not isinstance(sources, list) or not sources:
            errors.append(f"{label}: sources must be a non-empty list")
        else:
            for source_index, source in enumerate(sources):
                source_label = f"{label}:source-{source_index + 1}"
                if not isinstance(source, dict):
                    errors.append(f"{source_label}: source must be a mapping")
                    continue
                source_path = _validate_reference_path(
                    source_label, source.get("path"), errors
                )
                blob_id = source.get("blob_id")
                if not isinstance(blob_id, str) or not GIT_OBJECT_ID_PATTERN.fullmatch(
                    blob_id
                ):
                    errors.append(f"{source_label}: malformed Git blob id {blob_id!r}")
                if source_path is None or not isinstance(blob_id, str):
                    continue
                reference = (source_path, blob_id)
                if source_path in seen_paths:
                    errors.append(f"{source_label}: duplicate source path {source_path!r}")
                else:
                    seen_paths.add(source_path)
                if reference in seen_references:
                    errors.append(f"{source_label}: duplicate source reference")
                else:
                    seen_references.add(reference)

        review_state = assessment.get("review_state")
        if not isinstance(review_state, str) or review_state not in REFERENCE_REVIEW_STATES:
            errors.append(f"{label}: invalid review_state {review_state!r}")
        disposition = assessment.get("disposition")
        if not isinstance(disposition, str) or disposition not in REFERENCE_DISPOSITIONS:
            errors.append(f"{label}: invalid disposition {disposition!r}")
        rationale = assessment.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            errors.append(f"{label}: rationale must be a non-empty string")

        targets = assessment.get("target_artifact_ids")
        valid_targets: list[str] = []
        if not isinstance(targets, list) or not all(
            isinstance(target, str) and target for target in targets
        ):
            errors.append(f"{label}: target_artifact_ids must be a list of ids")
        else:
            valid_targets = targets
            if len(targets) != len(set(targets)):
                errors.append(f"{label}: duplicate target artifact id")
            for target in targets:
                if target not in artifact_ids:
                    errors.append(f"{label}: unknown target artifact {target!r}")

        if review_state == "pending":
            if disposition != "candidate":
                errors.append(f"{label}: pending assessment must be a candidate")
            for field in REVIEW_EVIDENCE_FIELDS:
                if assessment.get(field) not in (None, ""):
                    errors.append(f"{label}: pending assessment must not claim '{field}'")
        elif review_state == "reviewed":
            if disposition == "candidate":
                errors.append(f"{label}: reviewed assessment needs a final disposition")
            _validate_review_evidence(root, label, assessment, errors)

        if disposition == "adapted" and not valid_targets:
            errors.append(f"{label}: adapted assessment requires an existing Khepri target")
        elif disposition in {"candidate", "deferred", "rejected"} and valid_targets:
            errors.append(f"{label}: {disposition} assessment must not name targets")


def validate_repository(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    registries: dict[str, list[Artifact]] = {}
    for name in REGISTRY_NAMES:
        artifacts = _load_registry(root, name, errors)
        if artifacts is None:
            continue
        registries[name] = artifacts
        _validate_shape(root, name, artifacts, errors)

    _validate_global_ids(registries, errors)
    errors.extend(decision_supersession_errors(registries))
    _validate_authorities(root, registries, errors)
    _validate_family_relationships(registries, errors)
    for registry in ("families", "specifications"):
        _validate_dependencies(registry, registries.get(registry, []), errors)
    assessments = _load_reference_assessments(root, errors)
    if assessments is not None:
        _validate_reference_assessments(root, assessments, registries, errors)
    errors.extend(validate_approval_packages(root, registries))
    errors.extend(lifecycle_condition_errors(scan_repository(root)))
    return errors
