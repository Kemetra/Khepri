from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from khepri_gov.lifecycle import (
    APPROVED_OR_LATER,
    AUTHORITY_ENDING_FIELDS,
    INITIAL_TRANSITIONS,
    LIFECYCLE_TRANSITIONS,
    RENEWABLE_STATES,
    Artifact,
    ArtifactRef,
    LifecycleGraph,
    ends_authority,
    normalize_iso_date,
)

ARTIFACT_APPROVAL_FIELDS = {"approved_by", "approved_at", "approval_ref"}
PACKAGE_APPROVAL_FIELDS = ("approved_by", "approved_at")


@dataclass(frozen=True)
class PackageContext:
    label: str
    state: str
    package_ref: str


@dataclass(frozen=True)
class TransitionItem:
    ref: ArtifactRef
    entry: Mapping[str, Any]
    artifact: Artifact


@dataclass(frozen=True)
class TransitionKind:
    is_initial: bool
    is_lifecycle: bool
    is_renewal: bool

    @property
    def is_supported(self) -> bool:
        return any((self.is_initial, self.is_lifecycle, self.is_renewal))


@dataclass(frozen=True)
class ApprovedPackageIndex:
    packages: Mapping[str, Mapping[str, Any]]

    def has_successor(self, package_ref: str, ref: ArtifactRef) -> bool:
        for package in self.packages.values():
            if package.get("state") != "approved":
                continue
            entries = package.get("artifacts")
            if not isinstance(entries, list):
                continue
            if self._matching_entry(entries, package_ref, ref):
                return True
        return False

    @staticmethod
    def _matching_entry(
        entries: list[object],
        package_ref: str,
        ref: ArtifactRef,
    ) -> bool:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if _supersedes(entry, package_ref, ref):
                return True
        return False


def _supersedes(
    entry: Mapping[str, Any],
    package_ref: str,
    ref: ArtifactRef,
) -> bool:
    if entry.get("id") != ref.artifact_id:
        return False
    return entry.get("supersedes_approval_ref") == package_ref


@dataclass
class TransitionValidator:
    graph: LifecycleGraph
    package: PackageContext
    approved_packages: ApprovedPackageIndex

    def validate(
        self,
        item: TransitionItem,
        approval: Mapping[str, Any] | None,
    ) -> list[str]:
        errors = self._contract_errors(item)
        errors.extend(self._state_errors(item))
        errors.extend(self._approval_errors(item, approval))
        errors.extend(self._dependency_errors(item))
        self.graph.advance(item.ref, str(item.entry["to_state"]))
        return errors

    def _contract_errors(self, item: TransitionItem) -> list[str]:
        kind = _classify_transition(item.ref, item.entry)
        errors = _transition_shape_errors(item, kind)
        errors.extend(self._authority_field_errors(item))
        errors.extend(self._premature_approval_errors(item, kind))
        return errors

    def _premature_approval_errors(
        self,
        item: TransitionItem,
        kind: TransitionKind,
    ) -> list[str]:
        if self.package.state != "proposed":
            return []
        if not kind.is_initial:
            return []
        if not ARTIFACT_APPROVAL_FIELDS.intersection(item.artifact):
            return []
        return [
            f"{item.ref.label}: {item.ref.artifact_id} must not contain approval "
            "fields before initial approval"
        ]

    def _authority_field_errors(self, item: TransitionItem) -> list[str]:
        ref = item.ref
        to_state = str(item.entry["to_state"])
        if ends_authority(ref.registry, to_state):
            return self.graph.authority_ending_errors(ref, item.entry)
        return [
            f"{ref.label}: {field} is only valid for an authority-ending transition"
            for field in AUTHORITY_ENDING_FIELDS
            if field in item.entry
        ]

    def _state_errors(self, item: TransitionItem) -> list[str]:
        if self._state_is_settled(item):
            return []
        ref = item.ref
        if self.package.state == "proposed":
            from_state = str(item.entry["from_state"])
            return [
                f"{ref.label}: {ref.artifact_id} must remain at "
                f"from_state {from_state!r}"
            ]
        to_state = str(item.entry["to_state"])
        return [
            f"{ref.label}: {ref.artifact_id} must be at to_state {to_state!r}"
        ]

    def _state_is_settled(self, item: TransitionItem) -> bool:
        if item.artifact.get("state") == self._expected_state(item):
            return True
        if self.package.state != "approved":
            return False
        return self.approved_packages.has_successor(
            self.package.package_ref,
            item.ref,
        )

    def _expected_state(self, item: TransitionItem) -> str:
        if self.package.state == "proposed":
            return str(item.entry["from_state"])
        return str(item.entry["to_state"])

    def _approval_errors(
        self,
        item: TransitionItem,
        approval: Mapping[str, Any] | None,
    ) -> list[str]:
        if approval is None:
            return []
        if self._approval_is_carried_over(item):
            return []
        errors = _approval_field_errors(item, approval)
        errors.extend(self._approval_ref_errors(item))
        return errors

    def _approval_is_carried_over(self, item: TransitionItem) -> bool:
        if self.package.state != "approved":
            return True
        if ends_authority(item.ref.registry, str(item.entry["to_state"])):
            return True
        return self._is_historical(item)

    def _is_historical(self, item: TransitionItem) -> bool:
        """True when the registry has moved on from this package.

        An approved package the registry no longer names is a record of what was
        true, not a claim about the present, so the registry is not compared to it.
        That the registry names *some* approved package containing the artifact is
        guaranteed elsewhere, by `_package_evidence_errors`.
        """
        if item.artifact.get("approval_ref") == self.package.package_ref:
            return False
        return self.approved_packages.has_successor(
            self.package.package_ref,
            item.ref,
        )

    def _approval_ref_errors(self, item: TransitionItem) -> list[str]:
        if item.artifact.get("approval_ref") == self.package.package_ref:
            return []
        return [
            f"{item.ref.label}: {item.ref.artifact_id} approval_ref must be "
            f"{self.package.package_ref}"
        ]

    def _dependency_errors(self, item: TransitionItem) -> list[str]:
        ref = item.ref
        to_state = str(item.entry["to_state"])
        if ref.registry == "families" and to_state == "active":
            return self._family_dependency_errors(item)
        if ref.registry == "specifications" and to_state == "approved":
            return self._specification_dependency_errors(item)
        return []

    def _family_dependency_errors(self, item: TransitionItem) -> list[str]:
        errors: list[str] = []
        for dependency in item.artifact.get("depends_on", []):
            if self.graph.states["families"].get(dependency) != "active":
                errors.append(
                    f"{item.ref.label}: dependency {dependency!r} is not active "
                    f"before {item.ref.artifact_id}"
                )
        return errors

    def _specification_dependency_errors(self, item: TransitionItem) -> list[str]:
        errors = self._specification_family_errors(item)
        for dependency in item.artifact.get("depends_on", []):
            state = self.graph.states["specifications"].get(dependency)
            if state not in APPROVED_OR_LATER["specifications"]:
                errors.append(
                    f"{item.ref.label}: dependency {dependency!r} is not approved "
                    f"before {item.ref.artifact_id}"
                )
        return errors

    def _specification_family_errors(self, item: TransitionItem) -> list[str]:
        family = item.artifact.get("family")
        if self.graph.states["families"].get(family) == "active":
            return []
        return [
            f"{item.ref.label}: family {family!r} is not active before "
            f"{item.ref.artifact_id}"
        ]


def _classify_transition(ref: ArtifactRef, entry: Mapping[str, Any]) -> TransitionKind:
    transition = (str(entry["from_state"]), str(entry["to_state"]))
    return TransitionKind(
        is_initial=transition in INITIAL_TRANSITIONS[ref.registry],
        is_lifecycle=transition in LIFECYCLE_TRANSITIONS[ref.registry],
        is_renewal=_is_renewal(ref, transition, entry.get("supersedes_approval_ref")),
    )


def _is_renewal(
    ref: ArtifactRef,
    transition: tuple[str, str],
    supersedes_ref: object,
) -> bool:
    from_state, to_state = transition
    if from_state != to_state:
        return False
    if to_state not in RENEWABLE_STATES[ref.registry]:
        return False
    return isinstance(supersedes_ref, str) and bool(supersedes_ref)


def _transition_shape_errors(item: TransitionItem, kind: TransitionKind) -> list[str]:
    ref = item.ref
    entry = item.entry
    errors: list[str] = []
    if not kind.is_supported:
        from_state = str(entry["from_state"])
        to_state = str(entry["to_state"])
        errors.append(
            f"{ref.label}: unsupported transition for {ref.artifact_id}: "
            f"{from_state} -> {to_state}"
        )
    if kind.is_initial and "supersedes_approval_ref" in entry:
        errors.append(f"{ref.label}: initial approval must not supersede prior evidence")
    if _lacks_supersession(entry, kind):
        errors.append(
            f"{ref.label}: lifecycle transition for {ref.artifact_id} must "
            "supersede prior approval evidence"
        )
    return errors


def _lacks_supersession(entry: Mapping[str, Any], kind: TransitionKind) -> bool:
    if not kind.is_lifecycle:
        return False
    supersedes_ref = entry.get("supersedes_approval_ref")
    return not isinstance(supersedes_ref, str) or not supersedes_ref.strip()


def _approval_field_errors(
    item: TransitionItem,
    approval: Mapping[str, Any],
) -> list[str]:
    return [
        f"{item.ref.label}: {item.ref.artifact_id} {field} does not match package"
        for field in PACKAGE_APPROVAL_FIELDS
        if _field_mismatch(field, approval, item.artifact)
    ]


def _field_mismatch(
    field: str,
    approval: Mapping[str, Any],
    artifact: Artifact,
) -> bool:
    package_value = approval.get(field)
    artifact_value = artifact.get(field)
    if field == "approved_at":
        return normalize_iso_date(artifact_value) != normalize_iso_date(package_value)
    return artifact_value != package_value
