from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from khepri_gov.digests import document_digest
from khepri_gov.lifecycle import (
    LIFECYCLE_TRANSITIONS,
    Artifact,
)

BOOTSTRAP_EVIDENCE = "governance/approvals/APP-001-bootstrap.md"
WEB_SCHEMES = {"http", "https"}

ProposedClaims = dict[str, tuple[str, Mapping[str, Any]]]


@dataclass(frozen=True)
class RenewalScope:
    root: Path
    packages_by_path: Mapping[str, Mapping[str, Any]]
    known_artifacts: Mapping[str, tuple[str, Artifact]]


@dataclass(frozen=True)
class PackageUnderReview:
    ref: str
    package: Mapping[str, Any]

    @property
    def label(self) -> str:
        return f"approval-packages:{self.package.get('id', Path(self.ref).name)}"

    @property
    def is_proposed(self) -> bool:
        return self.package.get("state") == "proposed"


@dataclass(frozen=True)
class EntryUnderReview:
    review: PackageUnderReview
    entry: Mapping[str, Any]
    known: tuple[str, Artifact]

    @property
    def artifact_id(self) -> str:
        return str(self.entry.get("id"))

    @property
    def supersedes(self) -> object:
        return self.entry.get("supersedes_approval_ref")


@dataclass(frozen=True)
class EvidenceTarget:
    artifact_id: str
    artifact: Artifact
    approval_ref: str


@dataclass(frozen=True)
class RenewalPass:
    errors: list[str]
    claims: ProposedClaims


def package_entries(package: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if package is None:
        return []
    artifacts = package.get("artifacts")
    if not isinstance(artifacts, list):
        return []
    return [entry for entry in artifacts if isinstance(entry, dict)]


def package_artifact(
    package: Mapping[str, Any] | None,
    artifact_id: str,
) -> Mapping[str, Any] | None:
    for entry in package_entries(package):
        if entry.get("id") == artifact_id:
            return entry
    return None


def renewal_and_legacy_evidence_errors(scope: RenewalScope) -> list[str]:
    renewals = _renewal_pass(scope)
    errors = renewals.errors
    errors.extend(_legacy_evidence_errors(scope, renewals.claims))
    return errors


def _renewal_pass(scope: RenewalScope) -> RenewalPass:
    result = RenewalPass([], {})
    for ref, package in scope.packages_by_path.items():
        review = PackageUnderReview(ref, package)
        for item in _reviewable_entries(scope, review):
            _record_claim(item, result)
            result.errors.extend(_supersession_errors(scope, item))
    return result


def _reviewable_entries(
    scope: RenewalScope,
    review: PackageUnderReview,
) -> list[EntryUnderReview]:
    items: list[EntryUnderReview] = []
    for entry in package_entries(review.package):
        artifact_id = entry.get("id")
        known = scope.known_artifacts.get(artifact_id)
        if isinstance(artifact_id, str) and known is not None:
            items.append(EntryUnderReview(review, entry, known))
    return items


def _record_claim(item: EntryUnderReview, result: RenewalPass) -> None:
    if not item.review.is_proposed:
        return
    if item.artifact_id in result.claims:
        result.errors.append(
            f"approval-packages: artifact {item.artifact_id} appears in "
            "multiple proposed packages"
        )
        return
    result.claims[item.artifact_id] = (item.review.ref, item.entry)


def _supersession_errors(scope: RenewalScope, item: EntryUnderReview) -> list[str]:
    if item.supersedes is None:
        return []
    errors = _renewal_state_errors(item)
    errors.extend(_prior_package_errors(scope, item))
    errors.extend(_current_evidence_errors(item))
    return errors


def _renewal_state_errors(item: EntryUnderReview) -> list[str]:
    if _preserves_state(item):
        return []
    current_state = item.known[1].get("state")
    return [f"{item.review.label}: renewal must preserve state {current_state!r}"]


def _preserves_state(item: EntryUnderReview) -> bool:
    registry, artifact = item.known
    from_state = item.entry.get("from_state")
    to_state = item.entry.get("to_state")
    if from_state != to_state:
        return (from_state, to_state) in LIFECYCLE_TRANSITIONS[registry]
    if artifact.get("approval_ref") == item.review.ref:
        return from_state == artifact.get("state")
    return _is_known_state(registry, from_state)


def _is_known_state(registry: str, state: object) -> bool:
    """A renewal the registry has moved past is checked for legality, not agreement.

    Comparing it to the current state would re-judge a historical record against a
    present it never claimed. What must still hold is that the state it names is one
    the registry's lifecycle admits.
    """
    return any(state in edge for edge in LIFECYCLE_TRANSITIONS[registry])


def _prior_package_errors(scope: RenewalScope, item: EntryUnderReview) -> list[str]:
    if _has_approved_prior(scope, item):
        return []
    return [
        f"{item.review.label}: superseded approval must be an approved YAML "
        f"package containing {item.artifact_id}"
    ]


def _has_approved_prior(scope: RenewalScope, item: EntryUnderReview) -> bool:
    supersedes = item.supersedes
    if not isinstance(supersedes, str):
        return False
    prior = scope.packages_by_path.get(supersedes)
    if prior is None:
        return False
    if prior.get("state") != "approved":
        return False
    return package_artifact(prior, item.artifact_id) is not None


def _current_evidence_errors(item: EntryUnderReview) -> list[str]:
    if not _requires_prior_ref(item):
        return []
    if item.known[1].get("approval_ref") == item.supersedes:
        return []
    return [
        f"{item.review.label}: {item.artifact_id} does not currently use the "
        "superseded approval"
    ]


def _requires_prior_ref(item: EntryUnderReview) -> bool:
    """Only an unrecorded package can be checked against the registry it will change.

    Once the transition is recorded the registry names this package, not the one it
    supersedes, so requiring the older reference contradicts the check that the
    registry agrees with its governing package. That `supersedes_approval_ref` names
    an approved package containing the artifact is still required, by
    `_prior_package_errors`, which reads packages rather than the registry.
    """
    return item.review.is_proposed


def _legacy_evidence_errors(scope: RenewalScope, claims: ProposedClaims) -> list[str]:
    errors: list[str] = []
    for target in _evidence_targets(scope):
        errors.extend(_target_evidence_errors(scope, target, claims))
    return errors


def _evidence_targets(scope: RenewalScope) -> list[EvidenceTarget]:
    targets: list[EvidenceTarget] = []
    for artifact_id, (_, artifact) in scope.known_artifacts.items():
        approval_ref = artifact.get("approval_ref")
        if isinstance(approval_ref, str):
            targets.append(EvidenceTarget(artifact_id, artifact, approval_ref))
    return targets


def _target_evidence_errors(
    scope: RenewalScope,
    target: EvidenceTarget,
    claims: ProposedClaims,
) -> list[str]:
    approval_ref = target.approval_ref
    if urlparse(approval_ref).scheme in WEB_SCHEMES:
        return []
    if approval_ref.endswith(".md"):
        return _unstructured_evidence_errors(approval_ref)
    if not approval_ref.endswith(".yaml"):
        return []
    return _package_evidence_errors(scope, target, claims)


def _unstructured_evidence_errors(approval_ref: str) -> list[str]:
    if approval_ref == BOOTSTRAP_EVIDENCE:
        return []
    return [
        "approval-packages: unstructured approval evidence is "
        "limited to APP-001-bootstrap.md"
    ]


def _package_evidence_errors(
    scope: RenewalScope,
    target: EvidenceTarget,
    claims: ProposedClaims,
) -> list[str]:
    package = scope.packages_by_path.get(target.approval_ref)
    entry = package_artifact(package, target.artifact_id)
    if not _is_approved_evidence(package, entry):
        return [
            f"approval-packages: {target.artifact_id} approval_ref must identify "
            "an approved package containing the artifact"
        ]
    if target.artifact_id in claims:
        return []
    return _stale_document_errors(scope, target, entry)


def _is_approved_evidence(
    package: Mapping[str, Any] | None,
    entry: Mapping[str, Any] | None,
) -> bool:
    if package is None:
        return False
    if entry is None:
        return False
    return package.get("state") == "approved"


def _stale_document_errors(
    scope: RenewalScope,
    target: EvidenceTarget,
    entry: Mapping[str, Any] | None,
) -> list[str]:
    if not _document_changed(scope.root, target.artifact, entry):
        return []
    package = scope.packages_by_path.get(target.approval_ref, {})
    package_id = package.get("id", Path(target.approval_ref).stem)
    return [
        f"approval-packages:{package_id}: governed document for "
        f"{target.artifact_id} changed without renewal"
    ]


def _document_changed(
    root: Path,
    artifact: Artifact,
    entry: Mapping[str, Any] | None,
) -> bool:
    document = artifact.get("document")
    if not isinstance(document, str):
        return False
    path = root / document
    if not path.is_file():
        return False
    return entry is not None and entry.get("document_sha256") != document_digest(path)
