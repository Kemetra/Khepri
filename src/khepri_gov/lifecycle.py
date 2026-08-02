from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

INITIAL_TRANSITIONS = {
    "decisions": {("proposed", "accepted"), ("proposed", "rejected")},
    "families": {("proposed", "active")},
    "specifications": {("draft", "approved")},
}
LIFECYCLE_TRANSITIONS = {
    "decisions": {("accepted", "superseded")},
    "families": {("active", "retired")},
    "specifications": {
        ("approved", "implemented"),
        ("implemented", "verified"),
        ("approved", "retired"),
        ("implemented", "retired"),
        ("verified", "retired"),
    },
}
APPROVED_OR_LATER = {
    "decisions": {"accepted"},
    "families": {"active", "retired"},
    "specifications": {"approved", "implemented", "verified", "retired"},
}
RENEWABLE_STATES = {
    "decisions": {"accepted"},
    "families": {"active"},
    "specifications": {"approved", "implemented", "verified"},
}
SUCCESSOR_STATES = {
    **APPROVED_OR_LATER,
    "decisions": {"accepted", "superseded"},
}
AUTHORITY_ENDING_FIELDS = ("superseded_by", "retirement_reason")
REGISTRY_NAMES = ("decisions", "families", "specifications")

Artifact = dict[str, Any]
Registries = Mapping[str, list[Artifact]]


def normalize_iso_date(value: Any) -> str | None:
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


def ends_authority(registry: str, to_state: str) -> bool:
    if registry == "decisions":
        return to_state == "superseded"
    return registry in {"families", "specifications"} and to_state == "retired"


@dataclass(frozen=True)
class ArtifactRef:
    label: str
    artifact_id: str
    registry: str


@dataclass
class LifecycleGraph:
    known_artifacts: Mapping[str, tuple[str, Artifact]]
    states: dict[str, dict[str, object]]

    @classmethod
    def from_registries(cls, registries: Registries) -> LifecycleGraph:
        known = {
            item["id"]: (registry, item)
            for registry in REGISTRY_NAMES
            for item in registries.get(registry, [])
            if isinstance(item.get("id"), str)
        }
        states = {
            registry: {
                item["id"]: item.get("state")
                for item in registries.get(registry, [])
                if isinstance(item.get("id"), str)
            }
            for registry in REGISTRY_NAMES
        }
        return cls(known, states)

    def reset_package_sources(self, entries: list[object]) -> None:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            artifact_id = entry.get("id")
            known = self.known_artifacts.get(artifact_id)
            from_state = entry.get("from_state")
            if known is not None and isinstance(from_state, str):
                self.states[known[0]][artifact_id] = from_state

    def advance(self, ref: ArtifactRef, to_state: str) -> None:
        self.states[ref.registry][ref.artifact_id] = to_state

    def successor_errors(self, ref: ArtifactRef, successor_id: object) -> list[str]:
        if not isinstance(successor_id, str) or not successor_id:
            return [f"{ref.label}: superseded_by must be a non-empty artifact id"]
        if successor_id == ref.artifact_id:
            return [f"{ref.label}: artifact cannot supersede itself"]
        successor = self.known_artifacts.get(successor_id)
        if successor is None:
            return [f"{ref.label}: unknown successor {successor_id!r}"]
        successor_registry, _ = successor
        if successor_registry != ref.registry:
            return [
                f"{ref.label}: successor {successor_id!r} belongs to "
                f"{successor_registry}, not {ref.registry}"
            ]
        successor_state = self.states[ref.registry].get(successor_id)
        if successor_state not in SUCCESSOR_STATES[ref.registry]:
            return [
                f"{ref.label}: successor {successor_id} is not approved before "
                f"{ref.artifact_id}"
            ]
        return []

    def authority_ending_errors(
        self,
        ref: ArtifactRef,
        entry: Mapping[str, Any],
    ) -> list[str]:
        errors: list[str] = []
        successor_supplied = "superseded_by" in entry
        reason_supplied = "retirement_reason" in entry
        if successor_supplied:
            errors.extend(self.successor_errors(ref, entry.get("superseded_by")))
        reason = entry.get("retirement_reason")
        if reason_supplied and (not isinstance(reason, str) or not reason.strip()):
            errors.append(f"{ref.label}: retirement_reason must be a non-empty string")
        if ref.registry == "decisions" and not successor_supplied:
            errors.append(f"{ref.label}: {ref.artifact_id} must name superseded_by")
        elif not successor_supplied and not reason_supplied:
            errors.append(
                f"{ref.label}: {ref.artifact_id} must name a successor or "
                "retirement_reason"
            )
        return errors


def decision_supersession_errors(registries: Registries) -> list[str]:
    graph = LifecycleGraph.from_registries(registries)
    errors: list[str] = []
    for index, decision in enumerate(registries.get("decisions", [])):
        artifact_id = decision.get("id")
        label = (
            f"decisions:{artifact_id}"
            if isinstance(artifact_id, str) and artifact_id
            else f"decisions:entry-{index + 1}"
        )
        errors.extend(_decision_linkage_errors(graph, label, decision))
    return errors


def _decision_linkage_errors(
    graph: LifecycleGraph,
    label: str,
    decision: Artifact,
) -> list[str]:
    state = decision.get("state")
    successor_id = decision.get("superseded_by")
    if state != "superseded":
        if "superseded_by" in decision:
            return [f"{label}: superseded_by is only valid for a superseded decision"]
        return []
    if not isinstance(successor_id, str) or not successor_id:
        return [f"{label}: superseded decision must name superseded_by"]
    artifact_id = decision.get("id")
    if not isinstance(artifact_id, str):
        return []
    ref = ArtifactRef(label, artifact_id, "decisions")
    errors = graph.successor_errors(ref, successor_id)
    unavailable = (
        f"{label}: successor {successor_id!r} must be accepted or superseded"
    )
    return [unavailable if "is not approved before" in error else error for error in errors]
