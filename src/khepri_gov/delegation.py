from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

DELEGATION_DIR = "governance/delegations"
DELEGATION_ID_PATTERN = re.compile(r"^DEL-[0-9]{3}$")
DELEGATION_SCHEMA_VERSION = 1
SCOPE_ALL = "*"
STANDING_MAX_DAYS = 90

RESERVED_FILES = (
    "governance/CONSTITUTION.md",
    "governance/registries/authorities.yaml",
)
RECORD_REQUIRED_FIELDS = {
    "schema_version",
    "id",
    "delegate",
    "granted_by",
    "instruction",
    "granted_at",
    "session",
    "scope",
    "expires_at",
    "revoked",
}
SCOPE_REQUIRED_FIELDS = {"kind", "artifacts"}
SCOPE_KINDS = {"session", "standing"}
DELEGATED_APPROVAL_FIELDS = {
    "approved_by",
    "approved_at",
    "approved_manifest_digest",
    "delegation_ref",
    "session",
}
HUMAN_FIELDS = {
    "approved_by",
    "approved_at",
    "approved_manifest_digest",
    "evidence_ref",
}


@dataclass(frozen=True)
class DelegationRecord:
    ref: str
    data: Mapping[str, Any]

    @property
    def scope(self) -> Mapping[str, Any]:
        scope = self.data.get("scope")
        return scope if isinstance(scope, dict) else {}

    @property
    def is_session_scoped(self) -> bool:
        return self.scope.get("kind") == "session"

    @property
    def artifacts(self) -> list[Any]:
        artifacts = self.scope.get("artifacts")
        return artifacts if isinstance(artifacts, list) else []

    def covers(self, artifact_id: str) -> bool:
        if SCOPE_ALL in self.artifacts:
            return True
        return artifact_id in self.artifacts


def is_reserved_file(path: str) -> bool:
    normalised = path.replace("\\", "/")
    if normalised in RESERVED_FILES:
        return True
    return normalised.startswith(f"{DELEGATION_DIR}/")


def reserved_file_violations(changed_paths: Iterable[str]) -> list[str]:
    return [
        f"delegated commit must not change reserved file {path}"
        for path in changed_paths
        if is_reserved_file(path)
    ]


def delegated_commit_errors(
    root: Path,
    changed_paths: Iterable[str],
    delegates: Iterable[str],
) -> list[str]:
    changed = list(changed_paths)
    if not _carries_delegated_approval(root, changed, set(delegates)):
        return []
    return reserved_file_violations(changed)


def _carries_delegated_approval(
    root: Path,
    changed_paths: Iterable[str],
    delegates: set[str],
) -> bool:
    for path in changed_paths:
        if not path.replace("\\", "/").startswith("governance/approvals/"):
            continue
        if _approver_of(root / path) in delegates:
            return True
    return False


def _approver_of(path: Path) -> Any:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return None
    if not isinstance(loaded, dict):
        return None
    approval = loaded.get("approval")
    if not isinstance(approval, dict):
        return None
    return approval.get("approved_by")


def delegate_ids(authorities: Iterable[Mapping[str, Any]]) -> set[str]:
    return {
        str(record.get("id"))
        for record in authorities
        if record.get("human") is False
    }


def load_delegations(root: Path) -> tuple[dict[str, DelegationRecord], list[str]]:
    records: dict[str, DelegationRecord] = {}
    errors: list[str] = []
    directory = root / DELEGATION_DIR
    if not directory.is_dir():
        return records, errors
    for path in sorted(directory.glob("DEL-*.yaml")):
        ref = path.relative_to(root).as_posix()
        data, load_errors = _load_record(path, ref)
        errors.extend(load_errors)
        if data is not None:
            records[ref] = DelegationRecord(ref, data)
    return records, errors


def _load_record(path: Path, ref: str) -> tuple[Mapping[str, Any] | None, list[str]]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return None, [f"delegations:{path.name}: invalid YAML"]
    if not isinstance(loaded, dict):
        return None, [f"delegations:{path.name}: root must be a mapping"]
    return loaded, _record_errors(ref, loaded)


def _record_errors(ref: str, data: Mapping[str, Any]) -> list[str]:
    errors = [
        f"{ref}: missing required field {field!r}"
        for field in sorted(RECORD_REQUIRED_FIELDS - data.keys())
    ]
    errors.extend(_record_field_errors(ref, data))
    errors.extend(_scope_errors(ref, data.get("scope")))
    errors.extend(_record_date_errors(ref, data))
    return errors


def _record_field_errors(ref: str, data: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != DELEGATION_SCHEMA_VERSION:
        errors.append(f"{ref}: schema_version must be {DELEGATION_SCHEMA_VERSION}")
    if not DELEGATION_ID_PATTERN.fullmatch(str(data.get("id"))):
        errors.append(f"{ref}: id must match DEL-NNN")
    if not _is_filled_text(data.get("instruction")):
        errors.append(f"{ref}: instruction must record the instruction verbatim")
    if not _is_filled_text(data.get("session")):
        errors.append(f"{ref}: session must be a non-empty string")
    if not isinstance(data.get("revoked"), bool):
        errors.append(f"{ref}: revoked must be a boolean")
    return errors


def _scope_errors(ref: str, scope: Any) -> list[str]:
    if not isinstance(scope, dict):
        return [f"{ref}: scope must be a mapping"]
    errors = [
        f"{ref}: scope missing required field {field!r}"
        for field in sorted(SCOPE_REQUIRED_FIELDS - scope.keys())
    ]
    if scope.get("kind") not in SCOPE_KINDS:
        errors.append(f"{ref}: scope kind must be one of {sorted(SCOPE_KINDS)}")
    errors.extend(_scope_artifact_errors(ref, scope.get("artifacts")))
    return errors


def _scope_artifact_errors(ref: str, artifacts: Any) -> list[str]:
    if not isinstance(artifacts, list):
        return [f"{ref}: scope artifacts must be a list"]
    if not artifacts:
        return [f"{ref}: scope artifacts must not be empty"]
    if SCOPE_ALL in artifacts:
        return _scope_all_errors(ref, artifacts)
    return [
        f"{ref}: scope artifact {entry!r} must be an artifact identifier"
        for entry in artifacts
        if not _is_identifier(entry)
    ]


def _scope_all_errors(ref: str, artifacts: list[Any]) -> list[str]:
    if len(artifacts) == 1:
        return []
    return [f"{ref}: scope artifacts may not mix {SCOPE_ALL!r} with identifiers"]


def _record_date_errors(ref: str, data: Mapping[str, Any]) -> list[str]:
    granted = _as_date(data.get("granted_at"))
    expires = _as_date(data.get("expires_at"))
    if granted is None:
        return [f"{ref}: granted_at must be an ISO date"]
    if expires is None:
        return [f"{ref}: expires_at must be an ISO date"]
    if expires < granted:
        return [f"{ref}: expires_at must not precede granted_at"]
    return _standing_window_errors(ref, data, granted, expires)


def _standing_window_errors(
    ref: str,
    data: Mapping[str, Any],
    granted: date,
    expires: date,
) -> list[str]:
    scope = data.get("scope")
    kind = scope.get("kind") if isinstance(scope, dict) else None
    if kind != "standing":
        return []
    if expires - granted > timedelta(days=STANDING_MAX_DAYS):
        return [
            f"{ref}: a standing delegation expires no later than "
            f"{STANDING_MAX_DAYS} days after it is recorded"
        ]
    return []


def is_delegate(authority: Mapping[str, Any] | None) -> bool:
    if authority is None:
        return False
    return authority.get("human") is False


def approval_identity_errors(
    label: str,
    package: Mapping[str, Any],
    approval: Mapping[str, Any],
    authority: Mapping[str, Any] | None,
) -> list[str]:
    expected = DELEGATED_APPROVAL_FIELDS if is_delegate(authority) else HUMAN_FIELDS
    errors = [
        f"{label}: approval missing required field {field!r}"
        for field in sorted(expected - approval.keys())
    ]
    errors.extend(
        f"{label}: approval has unknown field {field!r}"
        for field in sorted(approval.keys() - expected)
    )
    errors.extend(_owner_errors(label, package, approval, authority))
    return errors


def _owner_errors(
    label: str,
    package: Mapping[str, Any],
    approval: Mapping[str, Any],
    authority: Mapping[str, Any] | None,
) -> list[str]:
    if is_delegate(authority):
        return _delegated_owner_errors(label, package)
    if approval.get("approved_by") == package.get("owner"):
        return []
    return [f"{label}: package owner and approver must match"]


def _delegated_owner_errors(label: str, package: Mapping[str, Any]) -> list[str]:
    if isinstance(package.get("owner"), str):
        return []
    return [f"{label}: a delegated package must name its human owner"]


def delegated_approval_errors(
    label: str,
    approval: Mapping[str, Any],
    records: Mapping[str, DelegationRecord],
    artifact_ids: Iterable[str],
) -> list[str]:
    ref = approval.get("delegation_ref")
    record = records.get(ref) if isinstance(ref, str) else None
    if record is None:
        return [f"{label}: delegation_ref must name a delegation record"]
    errors = _delegation_state_errors(label, approval, record)
    errors.extend(_delegation_scope_errors(label, record, artifact_ids))
    return errors


def _delegation_state_errors(
    label: str,
    approval: Mapping[str, Any],
    record: DelegationRecord,
) -> list[str]:
    errors: list[str] = []
    if record.data.get("revoked") is True:
        errors.append(f"{label}: delegation {record.ref} is revoked")
    if record.data.get("delegate") != approval.get("approved_by"):
        errors.append(f"{label}: delegation {record.ref} grants to another delegate")
    errors.extend(_expiry_errors(label, approval, record))
    errors.extend(_session_errors(label, approval, record))
    return errors


def _expiry_errors(
    label: str,
    approval: Mapping[str, Any],
    record: DelegationRecord,
) -> list[str]:
    approved = _as_date(approval.get("approved_at"))
    expires = _as_date(record.data.get("expires_at"))
    if approved is None:
        return []
    if expires is None:
        return []
    if approved > expires:
        return [f"{label}: delegation {record.ref} expired on {expires.isoformat()}"]
    return []


def _session_errors(
    label: str,
    approval: Mapping[str, Any],
    record: DelegationRecord,
) -> list[str]:
    if not record.is_session_scoped:
        return []
    if approval.get("session") == record.data.get("session"):
        return []
    return [
        f"{label}: session-scoped delegation {record.ref} requires the "
        "approval to name the same session"
    ]


def _delegation_scope_errors(
    label: str,
    record: DelegationRecord,
    artifact_ids: Iterable[str],
) -> list[str]:
    return [
        f"{label}: delegation {record.ref} does not cover {artifact_id}"
        for artifact_id in artifact_ids
        if not record.covers(artifact_id)
    ]


@dataclass(frozen=True)
class DelegationContext:
    records: Mapping[str, DelegationRecord]
    known_artifacts: Mapping[str, tuple[str, Mapping[str, Any]]]
    known_authorities: Mapping[str, Mapping[str, Any]]


def package_delegation_errors(
    label: str,
    package: Mapping[str, Any],
    context: DelegationContext,
) -> list[str]:
    approval = package.get("approval")
    if not isinstance(approval, dict):
        return []
    authority = context.known_authorities.get(approval.get("approved_by"))
    if not is_delegate(authority):
        return []
    entries = _package_entries(package)
    errors = delegated_approval_errors(
        label,
        approval,
        context.records,
        [str(entry.get("id")) for entry in entries],
    )
    errors.extend(reserved_artifact_errors(label, entries, context.known_artifacts))
    return errors


def _package_entries(package: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    artifacts = package.get("artifacts")
    if not isinstance(artifacts, list):
        return []
    return [entry for entry in artifacts if isinstance(entry, dict)]


def reserved_artifact_errors(
    label: str,
    entries: Iterable[Mapping[str, Any]],
    known_artifacts: Mapping[str, tuple[str, Mapping[str, Any]]],
) -> list[str]:
    errors: list[str] = []
    for entry in entries:
        artifact_id = str(entry.get("id"))
        errors.extend(_reserved_document_errors(label, entry))
        errors.extend(_reserved_decision_errors(label, artifact_id, known_artifacts))
    return errors


def _reserved_document_errors(label: str, entry: Mapping[str, Any]) -> list[str]:
    document = entry.get("document")
    if not isinstance(document, str):
        return []
    if not is_reserved_file(document):
        return []
    return [f"{label}: a delegate may not approve a change to {document}"]


def _reserved_decision_errors(
    label: str,
    artifact_id: str,
    known_artifacts: Mapping[str, tuple[str, Mapping[str, Any]]],
) -> list[str]:
    known = known_artifacts.get(artifact_id)
    if known is None:
        return []
    if known[1].get("alters_reserved_set") is not True:
        return []
    return [
        f"{label}: a delegate may not approve {artifact_id}, which alters "
        "the reserved set"
    ]


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _is_filled_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return bool(value.strip())


def _is_identifier(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return bool(value.strip())
