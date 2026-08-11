from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from khepri_gov.approval_packages import validate_approval_packages
from khepri_gov.delegation import CONSEQUENCE_VALUES
from khepri_gov.lifecycle import decision_supersession_errors
from khepri_gov.lifecycle_conditions import (
    lifecycle_condition_errors,
    scan_repository,
)
from khepri_gov.reference_assessments import (
    REVIEW_EVIDENCE_FIELDS,
    load_reference_assessments,
    validate_reference_assessments,
)

SCHEMA_VERSION = 1
REGISTRY_NAMES = ("authorities", "decisions", "families", "specifications")
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
    assessments = load_reference_assessments(root, errors)
    if assessments is not None:

        def review_evidence(label: str, assessment: Artifact, errs: list[str]) -> None:
            _validate_review_evidence(root, label, assessment, errs)

        validate_reference_assessments(
            assessments, registries, review_evidence, errors
        )
    errors.extend(validate_approval_packages(root, registries))
    errors.extend(lifecycle_condition_errors(scan_repository(root)))
    _validate_consequences(registries, errors)
    return errors


def _validate_consequences(
    registries: dict[str, list[Artifact]],
    errors: list[str],
) -> None:
    """Article VIII: every decision and specification records a consequence.

    Fail closed on a missing or unrecognised value, per Article V — an
    unclassified artifact is an unknown state, and unknown states block progress.
    """
    for name in ("decisions", "specifications"):
        for artifact in registries.get(name, []):
            value = artifact.get("consequence")
            if value in CONSEQUENCE_VALUES:
                continue
            errors.append(
                f"{name}:{artifact.get('id')}: consequence must be one of "
                f"{sorted(CONSEQUENCE_VALUES)}; an artifact recording none is reserved"
            )
