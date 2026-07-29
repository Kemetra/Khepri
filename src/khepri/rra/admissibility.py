from __future__ import annotations

from dataclasses import dataclass

from khepri.rra.mapping import (
    CORE_MEASURES,
    SEMANTIC_TRANSACTION_DATE,
    STATE_AMBIGUOUS,
    STATE_CONFLICTING,
    STATE_MAPPED,
    RetailMapping,
)
from khepri.rra.profiling import DatasetProfile

REASON_NO_DATA_ROWS = "no_data_rows"
REASON_NO_TIME_FIELD = "no_admissible_time_field"
REASON_NO_CORE_MEASURE = "no_answerable_core_measure"
REASON_IRRECONCILABLE_TYPES = "irreconcilable_types"
REASON_UNRESOLVED_AMBIGUITY = "unresolved_ambiguous_mapping"
REASON_MISSING_REQUESTED_SEMANTIC = "missing_requested_semantic"


@dataclass(frozen=True, slots=True)
class ReportRequest:
    requested_semantics: frozenset[str] = frozenset()

    def as_document(self) -> dict[str, object]:
        return {"requested_semantics": sorted(self.requested_semantics)}


DEFAULT_REPORT_REQUEST = ReportRequest()


@dataclass(frozen=True, slots=True)
class AdmissibilityDecision:
    admissible: bool
    reasons: tuple[str, ...]
    requested_semantics: tuple[str, ...]

    def as_document(self) -> dict[str, object]:
        return {
            "admissible": self.admissible,
            "reasons": list(self.reasons),
            "requested_semantics": list(self.requested_semantics),
        }


def assess_admissibility(
    profile: DatasetProfile,
    mapping: RetailMapping,
    *,
    request: ReportRequest = DEFAULT_REPORT_REQUEST,
) -> AdmissibilityDecision:
    needed = frozenset({SEMANTIC_TRANSACTION_DATE}) | request.requested_semantics
    reasons: list[str] = []

    if profile.row_count == 0:
        reasons.append(REASON_NO_DATA_ROWS)

    if mapping.state_of(SEMANTIC_TRANSACTION_DATE) != STATE_MAPPED:
        reasons.append(REASON_NO_TIME_FIELD)

    core_states = {measure: mapping.state_of(measure) for measure in CORE_MEASURES}
    if STATE_MAPPED not in core_states.values():
        reasons.append(REASON_NO_CORE_MEASURE)
        if STATE_AMBIGUOUS in core_states.values():
            reasons.append(REASON_UNRESOLVED_AMBIGUITY)
        if STATE_CONFLICTING in core_states.values():
            reasons.append(REASON_IRRECONCILABLE_TYPES)

    for semantic in sorted(needed):
        state = mapping.state_of(semantic)
        if state == STATE_MAPPED:
            continue
        if state == STATE_AMBIGUOUS:
            reasons.append(REASON_UNRESOLVED_AMBIGUITY)
        elif state == STATE_CONFLICTING:
            reasons.append(REASON_IRRECONCILABLE_TYPES)
        elif semantic != SEMANTIC_TRANSACTION_DATE:
            reasons.append(REASON_MISSING_REQUESTED_SEMANTIC)

    ordered = tuple(dict.fromkeys(reasons))
    return AdmissibilityDecision(
        admissible=not ordered,
        reasons=ordered,
        requested_semantics=tuple(sorted(request.requested_semantics)),
    )
