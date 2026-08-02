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
class ApprovedPackageIndex:
    packages: Mapping[str, Mapping[str, Any]]

    def has_successor(
        self,
        package_ref: str,
        ref: ArtifactRef,
        replaces_approval: bool | None = None,
    ) -> bool:
        for package in self.packages.values():
            if package.get("state") != "approved":
                continue
            entries = package.get("artifacts")
            if not isinstance(entries, list):
                continue
            if self._matching_entry(entries, package_ref, ref, replaces_approval):
                return True
        return False

    @staticmethod
    def _matching_entry(
        entries: list[object],
        package_ref: str,
        ref: ArtifactRef,
        replaces_approval: bool | None,
    ) -> bool:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            matches = (
                entry.get("id") == ref.artifact_id
                and entry.get("supersedes_approval_ref") == package_ref
            )
            replaces = not ends_authority(ref.registry, str(entry.get("to_state")))
            if matches and (replaces_approval is None or replaces == replaces_approval):
                return True
        return False


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
        ref = item.ref
        entry = item.entry
        from_state = str(entry["from_state"])
        to_state = str(entry["to_state"])
        transition = (from_state, to_state)
        is_initial = transition in INITIAL_TRANSITIONS[ref.registry]
        is_lifecycle = transition in LIFECYCLE_TRANSITIONS[ref.registry]
        supersedes_ref = entry.get("supersedes_approval_ref")
        is_renewal = (
            from_state == to_state
            and to_state in RENEWABLE_STATES[ref.registry]
            and isinstance(supersedes_ref, str)
            and bool(supersedes_ref)
        )
        errors: list[str] = []
        if not is_initial and not is_lifecycle and not is_renewal:
            errors.append(
                f"{ref.label}: unsupported transition for {ref.artifact_id}: "
                f"{from_state} -> {to_state}"
            )
        if is_initial and "supersedes_approval_ref" in entry:
            errors.append(f"{ref.label}: initial approval must not supersede prior evidence")
        if is_lifecycle and (
            not isinstance(supersedes_ref, str) or not supersedes_ref.strip()
        ):
            errors.append(
                f"{ref.label}: lifecycle transition for {ref.artifact_id} must "
                "supersede prior approval evidence"
            )
        errors.extend(self._authority_field_errors(item))
        if self.package.state == "proposed" and is_initial:
            claimed = ARTIFACT_APPROVAL_FIELDS.intersection(item.artifact)
            if claimed:
                errors.append(
                    f"{ref.label}: {ref.artifact_id} must not contain approval "
                    "fields before initial approval"
                )
        return errors

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
        ref = item.ref
        from_state = str(item.entry["from_state"])
        to_state = str(item.entry["to_state"])
        expected = from_state if self.package.state == "proposed" else to_state
        actual = item.artifact.get("state")
        has_successor = self.approved_packages.has_successor(
            self.package.package_ref,
            ref,
        )
        if actual == expected or (self.package.state == "approved" and has_successor):
            return []
        if self.package.state == "proposed":
            return [
                f"{ref.label}: {ref.artifact_id} must remain at "
                f"from_state {from_state!r}"
            ]
        return [
            f"{ref.label}: {ref.artifact_id} must be at to_state {to_state!r}"
        ]

    def _approval_errors(
        self,
        item: TransitionItem,
        approval: Mapping[str, Any] | None,
    ) -> list[str]:
        if self.package.state != "approved" or approval is None:
            return []
        ref = item.ref
        to_state = str(item.entry["to_state"])
        replacement = self.approved_packages.has_successor(
            self.package.package_ref,
            ref,
            replaces_approval=True,
        )
        if replacement or ends_authority(ref.registry, to_state):
            return []
        errors: list[str] = []
        for field in ("approved_by", "approved_at"):
            package_value = approval.get(field)
            artifact_value = item.artifact.get(field)
            if field == "approved_at":
                package_value = normalize_iso_date(package_value)
                artifact_value = normalize_iso_date(artifact_value)
            if artifact_value != package_value:
                errors.append(
                    f"{ref.label}: {ref.artifact_id} {field} does not match package"
                )
        if item.artifact.get("approval_ref") != self.package.package_ref:
            errors.append(
                f"{ref.label}: {ref.artifact_id} approval_ref must be "
                f"{self.package.package_ref}"
            )
        return errors

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
        errors: list[str] = []
        family = item.artifact.get("family")
        if self.graph.states["families"].get(family) != "active":
            errors.append(
                f"{item.ref.label}: family {family!r} is not active before "
                f"{item.ref.artifact_id}"
            )
        for dependency in item.artifact.get("depends_on", []):
            state = self.graph.states["specifications"].get(dependency)
            if state not in APPROVED_OR_LATER["specifications"]:
                errors.append(
                    f"{item.ref.label}: dependency {dependency!r} is not approved "
                    f"before {item.ref.artifact_id}"
                )
        return errors
