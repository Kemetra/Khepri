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
AUTHORITY_END_STATES = {
    "decisions": "superseded",
    "families": "retired",
    "specifications": "retired",
}
AUTHORITY_ENDING_FIELDS = ("superseded_by", "retirement_reason")
REGISTRY_NAMES = ("decisions", "families", "specifications")

Artifact = dict[str, Any]
Registries = Mapping[str, list[Artifact]]


def normalize_iso_date(value: Any) -> str | None:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return _parse_iso_text(value)
    return None


def _parse_iso_text(text: str) -> str | None:
    parse = datetime.fromisoformat if "T" in text else date.fromisoformat
    try:
        return parse(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def ends_authority(registry: str, to_state: str) -> bool:
    return AUTHORITY_END_STATES.get(registry) == to_state


def _identified(registries: Registries, registry: str) -> list[Artifact]:
    return [
        item for item in registries.get(registry, []) if isinstance(item.get("id"), str)
    ]


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
            for item in _identified(registries, registry)
        }
        states = {
            registry: {
                item["id"]: item.get("state")
                for item in _identified(registries, registry)
            }
            for registry in REGISTRY_NAMES
        }
        return cls(known, states)

    def reset_package_sources(self, entries: list[object]) -> None:
        for entry in entries:
            if isinstance(entry, dict):
                self._reset_source(entry)

    def _reset_source(self, entry: Mapping[str, Any]) -> None:
        artifact_id = entry.get("id")
        known = self.known_artifacts.get(artifact_id)
        if known is None:
            return
        from_state = entry.get("from_state")
        if isinstance(from_state, str):
            self.states[known[0]][artifact_id] = from_state

    def advance(self, ref: ArtifactRef, to_state: str) -> None:
        self.states[ref.registry][ref.artifact_id] = to_state

    def successor_errors(self, ref: ArtifactRef, successor_id: object) -> list[str]:
        identity_error = _successor_identity_error(ref, successor_id)
        if identity_error is not None:
            return [identity_error]
        return self._successor_state_errors(ref, str(successor_id))

    def _successor_state_errors(self, ref: ArtifactRef, successor_id: str) -> list[str]:
        successor = self.known_artifacts.get(successor_id)
        if successor is None:
            return [f"{ref.label}: unknown successor {successor_id!r}"]
        successor_registry = successor[0]
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
        if "superseded_by" in entry:
            errors.extend(self.successor_errors(ref, entry.get("superseded_by")))
        errors.extend(_retirement_reason_errors(ref, entry))
        errors.extend(_missing_authority_errors(ref, entry))
        return errors


def _successor_identity_error(ref: ArtifactRef, successor_id: object) -> str | None:
    if not isinstance(successor_id, str) or not successor_id:
        return f"{ref.label}: superseded_by must be a non-empty artifact id"
    if successor_id == ref.artifact_id:
        return f"{ref.label}: artifact cannot supersede itself"
    return None


def _retirement_reason_errors(ref: ArtifactRef, entry: Mapping[str, Any]) -> list[str]:
    if "retirement_reason" not in entry:
        return []
    reason = entry.get("retirement_reason")
    if not isinstance(reason, str) or not reason.strip():
        return [f"{ref.label}: retirement_reason must be a non-empty string"]
    return []


def _missing_authority_errors(ref: ArtifactRef, entry: Mapping[str, Any]) -> list[str]:
    if "superseded_by" in entry:
        return []
    if ref.registry == "decisions":
        return [f"{ref.label}: {ref.artifact_id} must name superseded_by"]
    if "retirement_reason" in entry:
        return []
    return [
        f"{ref.label}: {ref.artifact_id} must name a successor or retirement_reason"
    ]


def decision_supersession_errors(registries: Registries) -> list[str]:
    graph = LifecycleGraph.from_registries(registries)
    errors: list[str] = []
    for index, decision in enumerate(registries.get("decisions", [])):
        label = _decision_label(index, decision)
        errors.extend(_decision_linkage_errors(graph, label, decision))
    return errors


def _decision_label(index: int, decision: Artifact) -> str:
    artifact_id = decision.get("id")
    if isinstance(artifact_id, str) and artifact_id:
        return f"decisions:{artifact_id}"
    return f"decisions:entry-{index + 1}"


def _decision_linkage_errors(
    graph: LifecycleGraph,
    label: str,
    decision: Artifact,
) -> list[str]:
    if decision.get("state") != "superseded":
        return _unsuperseded_decision_errors(label, decision)
    return _superseded_decision_errors(graph, label, decision)


def _unsuperseded_decision_errors(label: str, decision: Artifact) -> list[str]:
    if "superseded_by" in decision:
        return [f"{label}: superseded_by is only valid for a superseded decision"]
    return []


def _superseded_decision_errors(
    graph: LifecycleGraph,
    label: str,
    decision: Artifact,
) -> list[str]:
    successor_id = decision.get("superseded_by")
    if not isinstance(successor_id, str) or not successor_id:
        return [f"{label}: superseded decision must name superseded_by"]
    artifact_id = decision.get("id")
    if not isinstance(artifact_id, str):
        return []
    ref = ArtifactRef(label, artifact_id, "decisions")
    unavailable = f"{label}: successor {successor_id!r} must be accepted or superseded"
    return [
        unavailable if "is not approved before" in error else error
        for error in graph.successor_errors(ref, successor_id)
    ]
