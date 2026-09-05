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

from collections.abc import Callable
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
    Attempt,
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
    """Create versions and runs, complete runs, remember and offer source profiles.

    Every public method is the same two steps -- resolve the caller to a scope, then perform one
    `Attempt` in it -- so each is written as the one line that differs: which recording operation,
    over which arguments. `_perform` holds the two steps once.
    """

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
        """Record the session's `RRA-003` admission as a dataset version, once. Two callers racing
        for the same upload are arbitrated by the database, and the loser reads the winner."""
        recording = self._recording
        return self._perform(
            caller,
            lambda owner: Attempt(
                ACTION_VERSION_CREATED,
                lambda: recording.create_version(owner, session_id, now),
                already=lambda: recording.existing_version(owner, session_id, now),
            ),
            now=now,
        )

    # --- FR-111 ---------------------------------------------------------------------------------

    def start_analysis_run(self, caller: Caller, *, version_id: str, now: datetime) -> AnalysisRun:
        """Open a run over a live version. Incomplete by construction; the pipeline fills it."""
        act = self._recording.start_run
        return self._perform(
            caller, lambda o: Attempt(ACTION_RUN_STARTED, lambda: act(o, version_id, now)), now=now
        )

    def complete_analysis_run(
        self, caller: Caller, *, run_id: str, report: ReportLocator, now: datetime
    ) -> AnalysisRun:
        """Record what the pipeline produced for a run: its package and every artifact, by digest.
        `report` says where to look; it is checked, never trusted -- `complete_run`."""
        act = self._recording.complete_run
        return self._perform(
            caller,
            lambda o: Attempt(ACTION_RUN_COMPLETED, lambda: act(o, run_id, report, now)),
            now=now,
        )

    def fail_analysis_run(self, caller: Caller, *, run_id: str, now: datetime) -> AnalysisRun:
        """End a run the pipeline did not deliver, as `failed`: a real state, with no provenance."""
        act = self._recording.fail_run
        return self._perform(
            caller, lambda o: Attempt(ACTION_RUN_FAILED, lambda: act(o, run_id, now)), now=now
        )

    # --- FR-114 / FR-115 ------------------------------------------------------------------------

    def remember_source_profile(
        self, caller: Caller, *, version_id: str, session_id: str, now: datetime
    ) -> SourceProfile:
        """Keep the admitted mapping's shape beside its version, as metadata a form can read
        (`FR-115`: descriptive only -- see `WorkspaceRecording.remember_profile`)."""
        act = self._recording.remember_profile
        return self._perform(
            caller,
            lambda o: Attempt(
                ACTION_PROFILE_REMEMBERED, lambda: act(o, version_id, session_id, now)
            ),
            now=now,
        )

    def propose_reuse(self, caller: Caller, *, profile_id: str, now: datetime) -> SourceProfile:
        """Offer a remembered profile for the customer to see before confirming (`FR-114`).

        Audited although it writes nothing: `FR-125` names profile reuse, and the showing is the
        action. The proposal pre-fills a form; the admission that follows runs on what the customer
        submits, against the new source, and refuses on its own terms.
        """
        act = self._recording.propose_reuse
        return self._perform(
            caller, lambda o: Attempt(ACTION_PROFILE_REUSED, lambda: act(o, profile_id)), now=now
        )

    # --- authorization, then one attempt ---------------------------------------------------------

    def _perform[T](
        self, caller: Caller, attempt_in: Callable[[str], Attempt[T]], *, now: datetime
    ) -> T:
        """Resolve the scope -- the one authorization door -- then perform the attempt in it.

        `attempt_in` receives the resolved `owner_id`, the only identity that crosses, and
        returns the attempt to perform there.
        """
        actor = self._actor(caller)
        return self._recording.perform(actor, attempt_in(actor.owner_id), now=now)

    def _actor(self, caller: Caller) -> AuditActor:
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
