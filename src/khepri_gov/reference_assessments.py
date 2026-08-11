"""Validation of the reference-assessment registry.

This module implements the reference-assessment portion of FND-001's governance
kernel. It is a behaviour-preserving extraction from `khepri_gov.validator`: the
error strings and the order in which they are appended are part of the governed
refusal surface, so each rule below appends exactly what the original did.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

SCHEMA_VERSION = 1
REFERENCE_REGISTRY_NAME = "reference-assessments"
REFERENCE_REPOSITORY = "Kemetra/Seshat-Platform"
REFERENCE_COMMIT = "f206b7f2c021c7d4e25ba131776ca4b22db6d876"
REFERENCE_COUNT = 42
REFERENCE_REVIEW_STATES = {"pending", "reviewed"}
REFERENCE_DISPOSITIONS = {"candidate", "adapted", "deferred", "rejected"}
REVIEW_EVIDENCE_FIELDS = ("reviewed_by", "reviewed_at", "review_ref")
GIT_OBJECT_ID_PATTERN = re.compile(r"^[0-9a-f]{40}$")
TARGET_REGISTRIES = ("decisions", "families", "specifications")
REQUIRED_ASSESSMENT_FIELDS = (
    "source_id",
    "sources",
    "review_state",
    "disposition",
    "rationale",
    "target_artifact_ids",
)
DISPOSITIONS_WITHOUT_TARGETS = {"candidate", "deferred", "rejected"}

Artifact = dict[str, Any]


def _is_nonempty_text(value: object) -> bool:
    """Report whether the value is a string carrying non-whitespace content."""
    return isinstance(value, str) and bool(value.strip())


def _read_registry_document(path: Path, errors: list[str]) -> dict[str, Any] | None:
    """Read the registry file, or record why it cannot be read."""
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
    return data


def _validate_provenance(data: dict[str, Any], errors: list[str]) -> None:
    """Check the schema version and the pinned upstream source coordinates."""
    version = data.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        errors.append(
            f"{REFERENCE_REGISTRY_NAME}: unsupported schema_version {version!r}; "
            f"expected integer {SCHEMA_VERSION}"
        )
    if data.get("source_repository") != REFERENCE_REPOSITORY:
        errors.append(
            f"{REFERENCE_REGISTRY_NAME}: source_repository must be "
            f"{REFERENCE_REPOSITORY!r}"
        )
    if data.get("source_commit") != REFERENCE_COMMIT:
        errors.append(
            f"{REFERENCE_REGISTRY_NAME}: source_commit must be {REFERENCE_COMMIT!r}"
        )


def _extract_assessments(
    data: dict[str, Any],
    errors: list[str],
) -> list[Artifact] | None:
    """Return the assessment list when it is well formed and correctly sized."""
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


def load_reference_assessments(root: Path, errors: list[str]) -> list[Artifact] | None:
    """Load the reference-assessment registry, recording any structural refusal."""
    path = root / "governance" / "registries" / f"{REFERENCE_REGISTRY_NAME}.yaml"
    data = _read_registry_document(path, errors)
    if data is None:
        return None
    _validate_provenance(data, errors)
    return _extract_assessments(data, errors)


def _is_malformed_path(value: str) -> bool:
    """Report whether the string is unsafe as a repository-relative source path."""
    path = PurePosixPath(value)
    return (
        "\\" in value
        or value != value.strip()
        or path.as_posix() != value
        or path.is_absolute()
        or (path.parts and ":" in path.parts[0])
        or any(part in {"", ".", ".."} for part in path.parts)
    )


def validate_reference_path(label: str, value: object, errors: list[str]) -> str | None:
    """Return the source path when it is a safe repository-relative path."""
    if not isinstance(value, str) or not value:
        errors.append(f"{label}: source path must be a non-empty string")
        return None
    if _is_malformed_path(value):
        errors.append(f"{label}: malformed source path {value!r}")
        return None
    return value


class _SourceLedger:
    """Tracks source paths and (path, blob) pairs already seen across assessments."""

    def __init__(self) -> None:
        self.paths: set[str] = set()
        self.references: set[tuple[str, str]] = set()

    def record(self, label: str, path: str, blob_id: str, errors: list[str]) -> None:
        """Record one source, reporting a duplicate path or duplicate reference."""
        if path in self.paths:
            errors.append(f"{label}: duplicate source path {path!r}")
        else:
            self.paths.add(path)
        reference = (path, blob_id)
        if reference in self.references:
            errors.append(f"{label}: duplicate source reference")
        else:
            self.references.add(reference)


def _validate_source(
    label: str,
    source: object,
    ledger: _SourceLedger,
    errors: list[str],
) -> None:
    """Validate one source entry and record it against the ledger."""
    if not isinstance(source, dict):
        errors.append(f"{label}: source must be a mapping")
        return
    source_path = validate_reference_path(label, source.get("path"), errors)
    blob_id = source.get("blob_id")
    if not isinstance(blob_id, str) or not GIT_OBJECT_ID_PATTERN.fullmatch(blob_id):
        errors.append(f"{label}: malformed Git blob id {blob_id!r}")
    if source_path is None or not isinstance(blob_id, str):
        return
    ledger.record(label, source_path, blob_id, errors)


def _validate_sources(
    label: str,
    sources: object,
    ledger: _SourceLedger,
    errors: list[str],
) -> None:
    """Validate the source list of a single assessment."""
    if not isinstance(sources, list) or not sources:
        errors.append(f"{label}: sources must be a non-empty list")
        return
    for index, source in enumerate(sources):
        _validate_source(f"{label}:source-{index + 1}", source, ledger, errors)


def _validate_source_id(
    label: str,
    source_id: object,
    seen_ids: set[str],
    errors: list[str],
) -> None:
    """Check that the source id is present, well formed, and not a duplicate."""
    if not _is_nonempty_text(source_id):
        errors.append(f"{label}: source_id must be a non-empty string")
    elif source_id in seen_ids:
        errors.append(f"{label}: duplicate source_id")
    else:
        seen_ids.add(source_id)


def _in_vocabulary(value: object, vocabulary: set[str]) -> bool:
    """Report whether the value is a string drawn from the given vocabulary."""
    return isinstance(value, str) and value in vocabulary


def _validate_vocabularies(label: str, assessment: Artifact, errors: list[str]) -> None:
    """Check review_state, disposition, and rationale against their vocabularies."""
    review_state = assessment.get("review_state")
    if not _in_vocabulary(review_state, REFERENCE_REVIEW_STATES):
        errors.append(f"{label}: invalid review_state {review_state!r}")
    disposition = assessment.get("disposition")
    if not _in_vocabulary(disposition, REFERENCE_DISPOSITIONS):
        errors.append(f"{label}: invalid disposition {disposition!r}")
    rationale = assessment.get("rationale")
    if not _is_nonempty_text(rationale):
        errors.append(f"{label}: rationale must be a non-empty string")


def _is_id_list(value: object) -> bool:
    """Report whether the value is a list of non-empty string ids."""
    if not isinstance(value, list):
        return False
    return all(isinstance(item, str) and item for item in value)


def _validate_targets(
    label: str,
    targets: object,
    artifact_ids: set[str],
    errors: list[str],
) -> list[str]:
    """Return the valid target ids, reporting duplicates and unknown artifacts."""
    if not _is_id_list(targets):
        errors.append(f"{label}: target_artifact_ids must be a list of ids")
        return []
    if len(targets) != len(set(targets)):
        errors.append(f"{label}: duplicate target artifact id")
    for target in targets:
        if target not in artifact_ids:
            errors.append(f"{label}: unknown target artifact {target!r}")
    return targets


def _validate_pending(label: str, assessment: Artifact, errors: list[str]) -> None:
    """A pending assessment stays a candidate and claims no review evidence."""
    if assessment.get("disposition") != "candidate":
        errors.append(f"{label}: pending assessment must be a candidate")
    for field in REVIEW_EVIDENCE_FIELDS:
        if assessment.get(field) not in (None, ""):
            errors.append(f"{label}: pending assessment must not claim '{field}'")


def _validate_disposition_targets(
    label: str,
    disposition: object,
    valid_targets: list[str],
    errors: list[str],
) -> None:
    """Only an adapted assessment names Khepri targets, and it must name one."""
    if disposition == "adapted" and not valid_targets:
        errors.append(f"{label}: adapted assessment requires an existing Khepri target")
    elif disposition in DISPOSITIONS_WITHOUT_TARGETS and valid_targets:
        errors.append(f"{label}: {disposition} assessment must not name targets")


def _assessment_label(source_id: object, index: int) -> str:
    """Name the assessment by source id, falling back to its position."""
    if isinstance(source_id, str) and source_id:
        return f"{REFERENCE_REGISTRY_NAME}:{source_id}"
    return f"{REFERENCE_REGISTRY_NAME}:entry-{index + 1}"


def _collect_artifact_ids(registries: dict[str, list[Artifact]]) -> set[str]:
    """Gather every governed artifact id an assessment may legitimately target."""
    return {
        artifact_id
        for registry in TARGET_REGISTRIES
        for artifact in registries.get(registry, [])
        if isinstance((artifact_id := artifact.get("id")), str)
    }


class ReferenceAssessmentValidator:
    """Validates reference assessments against the governed registries.

    `review_evidence` is the callable that validates the reviewer, review date,
    and review reference of a reviewed assessment. It is injected so this module
    does not depend on the shared approval-reference helpers in `validator`.
    """

    def __init__(self, artifact_ids: set[str], review_evidence: Any) -> None:
        self._artifact_ids = artifact_ids
        self._review_evidence = review_evidence
        self._seen_ids: set[str] = set()
        self._ledger = _SourceLedger()

    def _validate_lifecycle(
        self,
        label: str,
        assessment: Artifact,
        errors: list[str],
    ) -> None:
        """Apply the rules that depend on the assessment's review state."""
        review_state = assessment.get("review_state")
        if review_state == "pending":
            _validate_pending(label, assessment, errors)
        elif review_state == "reviewed":
            if assessment.get("disposition") == "candidate":
                errors.append(f"{label}: reviewed assessment needs a final disposition")
            self._review_evidence(label, assessment, errors)

    def validate_one(self, index: int, assessment: Artifact, errors: list[str]) -> None:
        """Validate a single assessment, appending refusals in governed order."""
        source_id = assessment.get("source_id")
        label = _assessment_label(source_id, index)
        for field in REQUIRED_ASSESSMENT_FIELDS:
            if field not in assessment:
                errors.append(f"{label}: missing required field '{field}'")
        _validate_source_id(label, source_id, self._seen_ids, errors)
        _validate_sources(label, assessment.get("sources"), self._ledger, errors)
        _validate_vocabularies(label, assessment, errors)
        valid_targets = _validate_targets(
            label, assessment.get("target_artifact_ids"), self._artifact_ids, errors
        )
        self._validate_lifecycle(label, assessment, errors)
        _validate_disposition_targets(
            label, assessment.get("disposition"), valid_targets, errors
        )

    def validate_all(self, assessments: list[Artifact], errors: list[str]) -> None:
        """Validate every assessment in registry order."""
        for index, assessment in enumerate(assessments):
            self.validate_one(index, assessment, errors)


def validate_reference_assessments(
    assessments: list[Artifact],
    registries: dict[str, list[Artifact]],
    review_evidence: Any,
    errors: list[str],
) -> None:
    """Validate the reference-assessment registry against the governed registries."""
    validator = ReferenceAssessmentValidator(
        _collect_artifact_ids(registries), review_evidence
    )
    validator.validate_all(assessments, errors)
