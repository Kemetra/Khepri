from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

PACKAGE_SCHEMA_VERSION = 1
PACKAGE_STATES = {"proposed", "approved"}
DIGEST_PREFIX = "sha256:"
MANIFEST_FIELDS = (
    "schema_version",
    "id",
    "title",
    "owner",
    "scope",
    "exclusions",
    "artifacts",
)
PACKAGE_REQUIRED_FIELDS = {
    "schema_version",
    "id",
    "title",
    "state",
    "owner",
    "scope",
    "exclusions",
    "manifest_digest",
    "artifacts",
}
PACKAGE_OPTIONAL_FIELDS = {"approval"}
ARTIFACT_REQUIRED_FIELDS = {
    "id",
    "document",
    "document_sha256",
    "from_state",
    "to_state",
}
ARTIFACT_OPTIONAL_FIELDS = {"supersedes_approval_ref"}
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
PACKAGE_ID_PATTERN = re.compile(r"^APP-[0-9]{3}$")
INITIAL_TRANSITIONS = {
    "decisions": {("proposed", "accepted")},
    "families": {("proposed", "active")},
    "specifications": {("draft", "approved")},
}
APPROVED_OR_LATER = {
    "decisions": {"accepted"},
    "families": {"active", "retired"},
    "specifications": {"approved", "implemented", "verified", "retired"},
}
PACKAGE_APPROVAL_FIELDS = {
    "approved_by",
    "approved_at",
    "approved_manifest_digest",
    "evidence_ref",
}
ARTIFACT_APPROVAL_FIELDS = {"approved_by", "approved_at", "approval_ref"}

Artifact = dict[str, Any]
Registries = Mapping[str, list[Artifact]]


def _sha256(content: bytes) -> str:
    return f"{DIGEST_PREFIX}{hashlib.sha256(content).hexdigest()}"


def document_digest(path: Path) -> str:
    return _sha256(path.read_bytes())


def manifest_payload(package: Mapping[str, Any]) -> dict[str, Any]:
    return {field: package.get(field) for field in MANIFEST_FIELDS}


def manifest_digest(package: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        manifest_payload(package),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return _sha256(encoded)


def load_package(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return None, [f"approval-packages:{path.name}: invalid YAML"]
    if not isinstance(loaded, dict):
        return None, [f"approval-packages:{path.name}: root must be a mapping"]
    return loaded, []


def _package_label(path: Path, package: Mapping[str, Any]) -> str:
    package_id = package.get("id")
    if isinstance(package_id, str) and package_id:
        return f"approval-packages:{package_id}"
    return f"approval-packages:{path.name}"


def _validate_required_and_unknown_fields(
    label: str,
    item: Mapping[str, Any],
    required: set[str],
    optional: set[str],
    errors: list[str],
) -> None:
    for field in sorted(required - item.keys()):
        errors.append(f"{label}: missing required field {field!r}")
    for field in sorted(item.keys() - required - optional):
        errors.append(f"{label}: unknown field {field!r}")


def _validate_package_artifacts(
    root: Path,
    label: str,
    package: Mapping[str, Any],
    known_artifacts: Mapping[str, tuple[str, Artifact]],
    errors: list[str],
) -> None:
    artifacts = package.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append(f"{label}: artifacts must be a non-empty list")
        return

    seen_ids: set[str] = set()
    for index, entry in enumerate(artifacts):
        entry_label = f"{label}:artifact-{index + 1}"
        if not isinstance(entry, dict):
            errors.append(f"{entry_label}: artifact must be a mapping")
            continue
        _validate_required_and_unknown_fields(
            entry_label,
            entry,
            ARTIFACT_REQUIRED_FIELDS,
            ARTIFACT_OPTIONAL_FIELDS,
            errors,
        )
        artifact_id = entry.get("id")
        if not isinstance(artifact_id, str) or not artifact_id:
            errors.append(f"{entry_label}: id must be a non-empty string")
            continue
        if artifact_id in seen_ids:
            errors.append(f"{label}: duplicate artifact id {artifact_id!r}")
        else:
            seen_ids.add(artifact_id)
        known = known_artifacts.get(artifact_id)
        if known is None:
            errors.append(f"{label}: unknown artifact {artifact_id!r}")
            continue

        _, registry_artifact = known
        document = entry.get("document")
        registry_document = registry_artifact.get("document")
        if document != registry_document:
            errors.append(f"{label}: artifact document does not match registry")
        digest = entry.get("document_sha256")
        if not isinstance(digest, str) or not DIGEST_PATTERN.fullmatch(digest):
            errors.append(f"{entry_label}: document_sha256 must be a lowercase SHA-256 digest")
            continue
        if package.get("state") == "proposed" and isinstance(registry_document, str):
            document_path = (root / registry_document).resolve()
            if document_path.is_file() and digest != document_digest(document_path):
                errors.append(
                    f"{label}: document_sha256 does not match governed document"
                )


def _validate_package_shape(
    root: Path,
    path: Path,
    package: Mapping[str, Any],
    known_authorities: Mapping[str, Artifact],
    known_artifacts: Mapping[str, tuple[str, Artifact]],
    errors: list[str],
) -> None:
    label = _package_label(path, package)
    _validate_required_and_unknown_fields(
        label,
        package,
        PACKAGE_REQUIRED_FIELDS,
        PACKAGE_OPTIONAL_FIELDS,
        errors,
    )

    version = package.get("schema_version")
    if type(version) is not int or version != PACKAGE_SCHEMA_VERSION:
        errors.append(f"{label}: unsupported schema_version {version!r}")

    package_id = package.get("id")
    if not isinstance(package_id, str) or not PACKAGE_ID_PATTERN.fullmatch(package_id):
        errors.append(f"{label}: id must match 'APP-NNN'")
    elif path.name != f"{package_id}.yaml":
        errors.append(f"{label}: filename must match package id")

    for field in ("title", "owner", "scope"):
        value = package.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label}: {field} must be a non-empty string")

    state = package.get("state")
    if not isinstance(state, str) or state not in PACKAGE_STATES:
        errors.append(f"{label}: invalid state {state!r}")

    owner = package.get("owner")
    if isinstance(owner, str):
        authority = known_authorities.get(owner)
        if authority is None:
            errors.append(f"{label}: unknown owner {owner!r}")
        elif authority.get("active") is not True:
            errors.append(f"{label}: owner {owner!r} is inactive")

    exclusions = package.get("exclusions")
    if not isinstance(exclusions, list) or not all(
        isinstance(exclusion, str) and exclusion.strip() for exclusion in exclusions
    ):
        errors.append(f"{label}: exclusions must be a list of non-empty strings")

    _validate_package_artifacts(root, label, package, known_artifacts, errors)

    if state == "proposed" and "approval" in package:
        errors.append(f"{label}: proposed package must not contain approval")

    declared_digest = package.get("manifest_digest")
    if not isinstance(declared_digest, str) or not DIGEST_PATTERN.fullmatch(
        declared_digest
    ):
        errors.append(f"{label}: manifest_digest must be a lowercase SHA-256 digest")
    else:
        try:
            expected_digest = manifest_digest(package)
        except (TypeError, ValueError):
            errors.append(f"{label}: manifest payload must be canonical JSON data")
        else:
            if declared_digest != expected_digest:
                errors.append(
                    f"{label}: manifest_digest does not match canonical payload"
                )


def _normalize_iso_date(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str) or not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _valid_evidence_ref(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    path_match = re.fullmatch(
        r"/Kemetra/Khepri/(?P<kind>pull|issues)/[0-9]+",
        parsed.path,
    )
    fragment_match = re.fullmatch(
        r"(?P<kind>issuecomment|pullrequestreview)-[0-9]+",
        parsed.fragment,
    )
    review_matches_pull = (
        fragment_match is not None
        and (
            fragment_match.group("kind") == "issuecomment"
            or (
                path_match is not None
                and path_match.group("kind") == "pull"
            )
        )
    )
    return (
        parsed.scheme == "https"
        and parsed.netloc == "github.com"
        and path_match is not None
        and fragment_match is not None
        and review_matches_pull
    )


def _validate_approval(
    label: str,
    package: Mapping[str, Any],
    known_authorities: Mapping[str, Artifact],
    errors: list[str],
) -> Mapping[str, Any] | None:
    approval = package.get("approval")
    if not isinstance(approval, dict):
        errors.append(f"{label}: approved package requires approval mapping")
        return None

    for field in sorted(PACKAGE_APPROVAL_FIELDS - approval.keys()):
        errors.append(f"{label}: approval missing required field {field!r}")
    for field in sorted(approval.keys() - PACKAGE_APPROVAL_FIELDS):
        errors.append(f"{label}: approval has unknown field {field!r}")

    approver = approval.get("approved_by")
    authority = known_authorities.get(approver) if isinstance(approver, str) else None
    if authority is None or authority.get("active") is not True:
        errors.append(f"{label}: unknown or inactive approver {approver!r}")
    if approver != package.get("owner"):
        errors.append(f"{label}: package owner and approver must match")

    if _normalize_iso_date(approval.get("approved_at")) is None:
        errors.append(f"{label}: approved_at must be an ISO date or datetime")

    if approval.get("approved_manifest_digest") != package.get("manifest_digest"):
        errors.append(f"{label}: approved_manifest_digest must equal manifest_digest")

    if not _valid_evidence_ref(approval.get("evidence_ref")):
        errors.append(
            f"{label}: evidence_ref must be a Khepri GitHub review or comment URL"
        )

    return approval


def _validate_transitions_and_materialization(
    root: Path,
    path: Path,
    package: Mapping[str, Any],
    known_authorities: Mapping[str, Artifact],
    known_artifacts: Mapping[str, tuple[str, Artifact]],
    registries: Registries,
    packages_by_path: Mapping[str, Mapping[str, Any]],
    errors: list[str],
) -> None:
    label = _package_label(path, package)
    package_state = package.get("state")
    artifacts = package.get("artifacts")
    if package_state not in PACKAGE_STATES or not isinstance(artifacts, list):
        return

    approval: Mapping[str, Any] | None = None
    if package_state == "approved":
        approval = _validate_approval(label, package, known_authorities, errors)

    simulated_states = {
        registry: {
            item.get("id"): item.get("state")
            for item in registries.get(registry, [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        for registry in ("families", "specifications")
    }
    for entry in artifacts:
        if not isinstance(entry, dict):
            continue
        artifact_id = entry.get("id")
        known = known_artifacts.get(artifact_id) if isinstance(artifact_id, str) else None
        from_state = entry.get("from_state")
        if (
            known is not None
            and known[0] in simulated_states
            and isinstance(from_state, str)
        ):
            simulated_states[known[0]][artifact_id] = from_state
    package_ref = path.relative_to(root.resolve()).as_posix()

    for entry in artifacts:
        if not isinstance(entry, dict):
            continue
        artifact_id = entry.get("id")
        if not isinstance(artifact_id, str):
            continue
        known = known_artifacts.get(artifact_id)
        if known is None:
            continue
        registry, registry_artifact = known
        from_state = entry.get("from_state")
        to_state = entry.get("to_state")
        if not isinstance(from_state, str) or not isinstance(to_state, str):
            errors.append(
                f"{label}: unsupported transition for {artifact_id}: "
                f"{from_state} -> {to_state}"
            )
            continue

        transition = (from_state, to_state)
        is_initial = transition in INITIAL_TRANSITIONS[registry]
        is_renewal = (
            from_state == to_state
            and to_state in APPROVED_OR_LATER[registry]
            and isinstance(entry.get("supersedes_approval_ref"), str)
            and bool(entry.get("supersedes_approval_ref"))
        )
        if not is_initial and not is_renewal:
            errors.append(
                f"{label}: unsupported transition for {artifact_id}: "
                f"{from_state} -> {to_state}"
            )
        if is_initial and "supersedes_approval_ref" in entry:
            errors.append(
                f"{label}: initial approval must not supersede prior evidence"
            )
        if (
            package_state == "proposed"
            and is_initial
            and ARTIFACT_APPROVAL_FIELDS.intersection(registry_artifact)
        ):
            errors.append(
                f"{label}: {artifact_id} must not contain approval fields "
                "before initial approval"
            )

        expected_state = from_state if package_state == "proposed" else to_state
        actual_state = registry_artifact.get("state")
        if actual_state != expected_state:
            if package_state == "proposed":
                errors.append(
                    f"{label}: {artifact_id} must remain at "
                    f"from_state {from_state!r}"
                )
            else:
                errors.append(
                    f"{label}: {artifact_id} must be at to_state {to_state!r}"
                )

        has_approved_successor = any(
            successor.get("state") == "approved"
            and any(
                isinstance(successor_entry, dict)
                and successor_entry.get("id") == artifact_id
                and successor_entry.get("supersedes_approval_ref") == package_ref
                for successor_entry in successor.get("artifacts", [])
            )
            for successor in packages_by_path.values()
            if isinstance(successor.get("artifacts"), list)
        )
        if (
            package_state == "approved"
            and approval is not None
            and not has_approved_successor
        ):
            for field in ("approved_by", "approved_at"):
                package_value = approval.get(field)
                artifact_value = registry_artifact.get(field)
                if field == "approved_at":
                    package_value = _normalize_iso_date(package_value)
                    artifact_value = _normalize_iso_date(artifact_value)
                if artifact_value != package_value:
                    errors.append(
                        f"{label}: {artifact_id} {field} does not match package"
                    )
            if registry_artifact.get("approval_ref") != package_ref:
                errors.append(
                    f"{label}: {artifact_id} approval_ref must be {package_ref}"
                )

        if registry == "families" and to_state == "active":
            for dependency in registry_artifact.get("depends_on", []):
                if simulated_states["families"].get(dependency) != "active":
                    errors.append(
                        f"{label}: dependency {dependency!r} is not active "
                        f"before {artifact_id}"
                    )
        elif registry == "specifications" and to_state == "approved":
            family = registry_artifact.get("family")
            if simulated_states["families"].get(family) != "active":
                errors.append(
                    f"{label}: family {family!r} is not active before {artifact_id}"
                )
            for dependency in registry_artifact.get("depends_on", []):
                dependency_state = simulated_states["specifications"].get(dependency)
                if dependency_state not in APPROVED_OR_LATER["specifications"]:
                    errors.append(
                        f"{label}: dependency {dependency!r} is not approved "
                        f"before {artifact_id}"
                    )

        if registry in simulated_states:
            simulated_states[registry][artifact_id] = to_state


def _package_artifact(
    package: Mapping[str, Any],
    artifact_id: str,
) -> Mapping[str, Any] | None:
    artifacts = package.get("artifacts")
    if not isinstance(artifacts, list):
        return None
    return next(
        (
            entry
            for entry in artifacts
            if isinstance(entry, dict) and entry.get("id") == artifact_id
        ),
        None,
    )


def _validate_renewals_and_legacy_evidence(
    root: Path,
    packages_by_path: Mapping[str, Mapping[str, Any]],
    known_artifacts: Mapping[str, tuple[str, Artifact]],
    errors: list[str],
) -> None:
    proposed_claims: dict[str, tuple[str, Mapping[str, Any]]] = {}

    for package_ref, package in packages_by_path.items():
        label = f"approval-packages:{package.get('id', Path(package_ref).name)}"
        artifacts = package.get("artifacts")
        if not isinstance(artifacts, list):
            continue
        for entry in artifacts:
            if not isinstance(entry, dict):
                continue
            artifact_id = entry.get("id")
            if not isinstance(artifact_id, str):
                continue
            known = known_artifacts.get(artifact_id)
            if known is None:
                continue
            _, registry_artifact = known

            if package.get("state") == "proposed":
                if artifact_id in proposed_claims:
                    errors.append(
                        f"approval-packages: artifact {artifact_id} appears in "
                        "multiple proposed packages"
                    )
                else:
                    proposed_claims[artifact_id] = (package_ref, entry)

            supersedes = entry.get("supersedes_approval_ref")
            if supersedes is None:
                continue
            current_state = registry_artifact.get("state")
            if (
                entry.get("from_state") != current_state
                or entry.get("to_state") != current_state
            ):
                errors.append(
                    f"{label}: renewal must preserve state {current_state!r}"
                )

            prior = packages_by_path.get(supersedes) if isinstance(supersedes, str) else None
            if (
                prior is None
                or prior.get("state") != "approved"
                or _package_artifact(prior, artifact_id) is None
            ):
                errors.append(
                    f"{label}: superseded approval must be an approved YAML "
                    f"package containing {artifact_id}"
                )

            if (
                package.get("state") == "proposed"
                and registry_artifact.get("approval_ref") != supersedes
            ):
                errors.append(
                    f"{label}: {artifact_id} does not currently use the "
                    "superseded approval"
                )

    for artifact_id, (_, registry_artifact) in known_artifacts.items():
        approval_ref = registry_artifact.get("approval_ref")
        if not isinstance(approval_ref, str):
            continue
        parsed = urlparse(approval_ref)
        if parsed.scheme in {"http", "https"}:
            continue
        if approval_ref.endswith(".md"):
            if approval_ref != "governance/approvals/APP-001-bootstrap.md":
                errors.append(
                    "approval-packages: unstructured approval evidence is "
                    "limited to APP-001-bootstrap.md"
                )
            continue
        if not approval_ref.endswith(".yaml"):
            continue

        current_package = packages_by_path.get(approval_ref)
        current_entry = (
            _package_artifact(current_package, artifact_id)
            if current_package is not None
            else None
        )
        if (
            current_package is None
            or current_package.get("state") != "approved"
            or current_entry is None
        ):
            errors.append(
                f"approval-packages: {artifact_id} approval_ref must identify "
                "an approved package containing the artifact"
            )
            continue

        if artifact_id in proposed_claims:
            continue
        document = registry_artifact.get("document")
        expected_digest = current_entry.get("document_sha256")
        if (
            isinstance(document, str)
            and (root / document).is_file()
            and expected_digest != document_digest(root / document)
        ):
            package_id = current_package.get("id", Path(approval_ref).stem)
            errors.append(
                f"approval-packages:{package_id}: governed document for "
                f"{artifact_id} changed without renewal"
            )


def validate_approval_packages(root: Path, registries: Registries) -> list[str]:
    errors: list[str] = []
    packages: list[tuple[Path, dict[str, Any]]] = []
    approval_dir = root / "governance" / "approvals"
    for path in sorted(approval_dir.glob("APP-*.yaml")):
        resolved_path = path.resolve()
        if not resolved_path.is_relative_to(root) or not resolved_path.is_file():
            errors.append(
                f"approval-packages:{path.name}: package path must stay within repository"
            )
            continue
        package, load_errors = load_package(resolved_path)
        errors.extend(load_errors)
        if package is not None:
            packages.append((resolved_path, package))

    known_authorities = {
        item["id"]: item
        for item in registries.get("authorities", [])
        if isinstance(item.get("id"), str)
    }
    known_artifacts = {
        item["id"]: (registry, item)
        for registry in ("decisions", "families", "specifications")
        for item in registries.get(registry, [])
        if isinstance(item.get("id"), str)
    }
    packages_by_path = {
        path.relative_to(root.resolve()).as_posix(): package
        for path, package in packages
    }
    for path, package in packages:
        _validate_package_shape(
            root,
            path,
            package,
            known_authorities,
            known_artifacts,
            errors,
        )
        _validate_transitions_and_materialization(
            root,
            path,
            package,
            known_authorities,
            known_artifacts,
            registries,
            packages_by_path,
            errors,
        )
    _validate_renewals_and_legacy_evidence(
        root,
        packages_by_path,
        known_artifacts,
        errors,
    )
    return errors
