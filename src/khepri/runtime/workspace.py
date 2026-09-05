"""The workspace services' customer door (`W1-04`; `RCA-005` `FR-110`, `FR-111`, `FR-114`,
`FR-125`).

Six actions over the workspace records, each authorized through `IsolationService.resolve_scope`,
each performed against what the existing `RRA` pipeline already produced, each leaving exactly one
content-free audit event. What each action *does* once the scope is resolved lives in
`workspace_recording.py`, which the pipeline door (`pipeline_recording.py`, `W1-04b`) shares:
two doors, one recording, so `FR-110`'s "no second admission" is not undone by a second recording
of it. This module keeps the vocabulary its callers import -- `Caller`, the ports, the locator, the
refusal -- and the authorization step, and nothing else.

## Authorization, and the one identity that crosses

```
account_id + organization_id       <- RCA vocabulary, stops at resolve_scope
        |
     owner_id                      <- the only identity that crosses (FR-032, FR-033)
```

Every public method resolves the scope first -- a caller with no standing gets `ScopeAccessDenied`
and the workspace records nothing, because there is no scope to record it in -- then performs the
action inside `WorkspaceRecording.perform`, which writes exactly one event.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from khepri.rca.isolation import IsolationService
from khepri.rca.workspace.audit import (
    ACTION_PROFILE_REMEMBERED,
    ACTION_PROFILE_REUSED,
    ACTION_RUN_COMPLETED,
    ACTION_RUN_FAILED,
    ACTION_RUN_STARTED,
    ACTION_VERSION_CREATED,
    AuditActor,
)
from khepri.rca.workspace.contracts import AnalysisRun, DatasetVersion, SourceProfile
from khepri.runtime.workspace_recording import (
    ADMISSION_ADMITTED,
    ADMISSION_REFUSED_FAILURE,
    BUNDLE_INCOMPLETE_FAILURE,
    NO_ADMISSION_FAILURE,
    NO_ATTESTATION_FAILURE,
    NO_DELIVERY_FAILURE,
    NO_DERIVATION_FAILURE,
    NO_PROFILE_FAILURE,
    NO_RUN_FAILURE,
    NO_SESSION_FAILURE,
    NO_VERSION_FAILURE,
    PROFILE_MISMATCH_FAILURE,
    PROVENANCE_FAILURE,
    ArtifactReader,
    DeliveryReader,
    Performed,
    RecordStores,
    ReportLocator,
    StoredArtifactLike,
    WorkspacePorts,
    WorkspaceRecording,
    WorkspaceRefused,
)


@dataclass(frozen=True, slots=True)
class Caller:
    """Who is asking, and about which organization -- the `RCA` vocabulary that stops at
    `resolve_scope`. Paired at the type so a service call cannot name one account's identifier
    beside another organization's one argument at a time."""

    account_id: str
    organization_id: str


class WorkspaceActions:
    """Create versions and runs, complete runs, remember and offer source profiles."""

    def __init__(
        self, *, isolation: IsolationService, rra: WorkspacePorts, rca: RecordStores
    ) -> None:
        self._isolation = isolation
        self._rra = rra
        self._recording = WorkspaceRecording(rra=rra, rca=rca)

    # --- FR-110 ---------------------------------------------------------------------------------

    def create_dataset_version(
        self, caller: Caller, *, session_id: str, now: datetime
    ) -> DatasetVersion:
        """Record the session's `RRA-003` admission as a dataset version, once."""
        actor = self._actor(caller)
        return self._recording.perform(
            actor,
            ACTION_VERSION_CREATED,
            lambda: self._recording.create_version(actor.owner_id, session_id, now),
            now=now,
        )

    # --- FR-111 ---------------------------------------------------------------------------------

    def start_analysis_run(self, caller: Caller, *, version_id: str, now: datetime) -> AnalysisRun:
        """Open a run over a live version. Incomplete by construction; the pipeline fills it."""
        actor = self._actor(caller)
        return self._recording.perform(
            actor,
            ACTION_RUN_STARTED,
            lambda: self._recording.start_run(actor.owner_id, version_id, now),
            now=now,
        )

    def complete_analysis_run(
        self, caller: Caller, *, run_id: str, report: ReportLocator, now: datetime
    ) -> AnalysisRun:
        """Record what the pipeline produced for a run: its package and every artifact, by digest.

        `report` says where to look; it is checked, never trusted -- see
        `WorkspaceRecording.complete_run`.
        """
        actor = self._actor(caller)
        return self._recording.perform(
            actor,
            ACTION_RUN_COMPLETED,
            lambda: self._recording.complete_run(actor.owner_id, run_id, report, now),
            now=now,
        )

    def fail_analysis_run(self, caller: Caller, *, run_id: str, now: datetime) -> AnalysisRun:
        """End a run the pipeline did not deliver, as `failed`: a real state, with no provenance."""
        actor = self._actor(caller)
        return self._recording.perform(
            actor,
            ACTION_RUN_FAILED,
            lambda: self._recording.fail_run(actor.owner_id, run_id, now),
            now=now,
        )

    # --- FR-114 / FR-115 ------------------------------------------------------------------------

    def remember_source_profile(
        self, caller: Caller, *, version_id: str, session_id: str, now: datetime
    ) -> SourceProfile:
        """Keep the admitted mapping's shape beside its version, as metadata a form can read
        (`FR-115`: descriptive only -- see `WorkspaceRecording.remember_profile`)."""
        actor = self._actor(caller)
        return self._recording.perform(
            actor,
            ACTION_PROFILE_REMEMBERED,
            lambda: self._recording.remember_profile(actor.owner_id, version_id, session_id, now),
            now=now,
        )

    def propose_reuse(self, caller: Caller, *, profile_id: str, now: datetime) -> SourceProfile:
        """Offer a remembered profile for the customer to see before confirming (`FR-114`).

        Audited although it writes nothing: `FR-125` names profile reuse, and the showing is the
        action. The proposal pre-fills a form; the admission that follows runs on what the customer
        submits, against the new source, and refuses on its own terms.
        """
        actor = self._actor(caller)
        return self._recording.perform(
            actor,
            ACTION_PROFILE_REUSED,
            lambda: self._recording.propose_reuse(actor.owner_id, profile_id),
            now=now,
        )

    # --- authorization ----------------------------------------------------------------------------

    def _actor(self, caller: Caller) -> AuditActor:
        """Resolve the scope -- the one authorization door -- and name the actor within it."""
        owner_id = self._isolation.resolve_scope(caller.account_id, caller.organization_id)
        return AuditActor(owner_id=owner_id, actor_account_id=caller.account_id)


__all__ = [
    "ADMISSION_ADMITTED",
    "ADMISSION_REFUSED_FAILURE",
    "BUNDLE_INCOMPLETE_FAILURE",
    "NO_ADMISSION_FAILURE",
    "NO_ATTESTATION_FAILURE",
    "NO_DELIVERY_FAILURE",
    "NO_DERIVATION_FAILURE",
    "NO_PROFILE_FAILURE",
    "NO_RUN_FAILURE",
    "NO_SESSION_FAILURE",
    "NO_VERSION_FAILURE",
    "PROFILE_MISMATCH_FAILURE",
    "PROVENANCE_FAILURE",
    "ArtifactReader",
    "Caller",
    "DeliveryReader",
    "Performed",
    "RecordStores",
    "ReportLocator",
    "StoredArtifactLike",
    "WorkspaceActions",
    "WorkspacePorts",
    "WorkspaceRefused",
]
