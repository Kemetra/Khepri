"""`W1-04` -- the workspace services (`RCA-005` `FR-110`, `FR-111`, `FR-114`, `FR-125`).

**Driven through the real admission.** The `G3-04` plan names this slice's one risk: a second
admission path. "If this slice can create a dataset version without calling `RRA-003`, `FR-110` is
violated however the code reads." So every version here is created from a session whose upload was
admitted by the real `ProfilingService` over real bytes, and every run is completed from a package
the real `FactPackageService` derived (`tests/w104_support.py`). The only fakes are at the report
boundary -- the delivery record and the stored artifacts -- because the pipeline that produces them
needs Chromium and a worker, and `RRA-006`'s own tests prove it. The service *reads* those products;
it makes none.

**Why the services live in `khepri.runtime`.** They call `khepri.rra` for admission and the pipeline
and `khepri.rca` for the workspace records, and `R7-01` §3 forbids either package importing the
other. `runtime/bridge.py` records why the composition layer is the one place that may know both.

**One audit event per action, by count.** `FR-125` says every workspace action emits one
content-free event. Each test here counts the events in the scope after the call -- one more than
before, whether the action completed or was refused -- rather than asserting that some event exists.
The event *record* itself is `test_w104_audit_events.py`'s subject.
"""

from __future__ import annotations

import pytest

from khepri.rca.errors import ScopeAccessDenied
from khepri.rca.workspace.audit import (
    ACTION_PROFILE_REMEMBERED,
    ACTION_PROFILE_REUSED,
    ACTION_RUN_COMPLETED,
    ACTION_RUN_FAILED,
    ACTION_RUN_STARTED,
    ACTION_VERSION_CREATED,
    OBJECT_PROFILE,
    OBJECT_RUN,
    OBJECT_VERSION,
    OUTCOME_ALREADY_RECORDED,
    OUTCOME_COMPLETED,
    OUTCOME_REFUSED,
)
from khepri.rca.workspace.contracts import RUN_COMPLETED, RUN_FAILED, RUN_STARTED, SourceProfile
from khepri.rra.datasets import document_digest, stored_manifest
from khepri.rra.pipeline import DeliveryRecord
from khepri.rra.report_artifacts import REQUIRED_ARTIFACT_KINDS
from khepri.runtime.workspace import ADMISSION_ADMITTED, ReportLocator, WorkspaceRefused
from tests.w104_support import (
    GOLDEN_CSV,
    JOB,
    LATER,
    NO_MEASURE_CSV,
    NOW,
    OTHER_CSV,
    Member,
    World,
    admitted_session,
    derived,
    events,
    member,
    session_with_upload,
    world,
)

# --- FR-110: a version records the admission the session holds, and nothing admits twice ---------


def test_creating_a_version_records_the_real_admission() -> None:
    w = world()
    who = member(w)
    session_id = admitted_session(w, who.owner_id)
    upload = w.uploads.get_upload_for_session(session_id)
    profile = w.profiling.get_session_profile(session_id=session_id, now=NOW)
    assert upload is not None and profile is not None and profile.admissible

    version = w.services.create_dataset_version(who.caller, session_id=session_id, now=LATER)

    assert version.owner_id == who.owner_id
    assert version.upload_plaintext_digest == upload.sha256_hex
    assert version.upload_ciphertext_digest == upload.ciphertext_sha256_hex
    assert version.upload_size_bytes == upload.size_bytes == len(GOLDEN_CSV)
    assert version.upload_media_type == upload.media_type
    manifest = stored_manifest(profile)
    assert manifest is not None
    assert version.manifest_digest == document_digest(manifest.as_document())
    assert version.mapping_version == profile.mapping_version
    assert version.admission_outcome == ADMISSION_ADMITTED
    assert version.created_at == LATER
    assert version.sealed_at is None, "sealing is the derivation's event, not the admission's"
    assert w.store.dataset_versions_for_scope(who.owner_id) == (version,)
    (recorded,) = events(w, who)
    assert (recorded.action, recorded.outcome) == (ACTION_VERSION_CREATED, OUTCOME_COMPLETED)
    assert (recorded.object_kind, recorded.object_id) == (OBJECT_VERSION, version.version_id)
    assert (recorded.owner_id, recorded.actor_account_id) == (who.owner_id, who.account_id)


def test_a_version_needs_an_admission_the_session_actually_holds() -> None:
    """An upload alone is not an admission. The service asks `ProfilingService` for the profile
    and refuses when there is none -- it never profiles the bytes itself."""
    w = world()
    who = member(w)
    session_id = session_with_upload(w, who.owner_id, GOLDEN_CSV)

    with pytest.raises(WorkspaceRefused, match="No admission"):
        w.services.create_dataset_version(who.caller, session_id=session_id, now=LATER)

    assert w.store.dataset_versions_for_scope(who.owner_id) == ()
    (recorded,) = events(w, who)
    assert (recorded.action, recorded.outcome) == (ACTION_VERSION_CREATED, OUTCOME_REFUSED)
    assert recorded.object_id is None


def test_a_refused_admission_creates_no_version_and_no_run() -> None:
    """`FR-114`'s Run Again refusal, at the service: the new source fails `RRA-003` admission, so
    reuse is refused, nothing is copied from the prior run, and the history gains no run."""
    w = world()
    who = member(w)
    prior = w.services.create_dataset_version(
        who.caller, session_id=admitted_session(w, who.owner_id), now=NOW
    )
    w.services.start_analysis_run(who.caller, version_id=prior.version_id, now=NOW)
    runs_before = w.store.analysis_runs_for_scope(who.owner_id)
    # Attested, so the one thing wrong with this source is that `RRA-003` did not admit it. The
    # first draft left it unattested and the refusal came from the missing manifest instead --
    # the mutant that dropped the admissibility check survived. Assert the reason, not the type.
    again = admitted_session(w, who.owner_id, NO_MEASURE_CSV, attest=True)

    with pytest.raises(WorkspaceRefused, match="not admitted"):
        w.services.create_dataset_version(who.caller, session_id=again, now=LATER)

    assert w.store.dataset_versions_for_scope(who.owner_id) == (prior,)
    assert w.store.analysis_runs_for_scope(who.owner_id) == runs_before
    assert events(w, who)[-1].outcome == OUTCOME_REFUSED


def test_an_admission_without_a_coverage_attestation_creates_no_version() -> None:
    """`W1-01` made the manifest digest a required field of a version, and `KHEPRI-DEC-033` §2
    keeps the manifest with the version it describes. A profile with no attestation has none to
    keep, so the version is refused rather than written with a digest of nothing."""
    w = world()
    who = member(w)
    session_id = admitted_session(w, who.owner_id, attest=False)

    with pytest.raises(WorkspaceRefused, match="attestation"):
        w.services.create_dataset_version(who.caller, session_id=session_id, now=LATER)

    assert w.store.dataset_versions_for_scope(who.owner_id) == ()
    assert len(events(w, who)) == 1


def test_creating_a_version_twice_for_one_session_returns_the_first() -> None:
    """A retry is not a second version. The upload's ciphertext digest is unique per stored copy,
    so it identifies the session's upload without the workspace holding a session identifier."""
    w = world()
    who = member(w)
    session_id = admitted_session(w, who.owner_id)

    first = w.services.create_dataset_version(who.caller, session_id=session_id, now=NOW)
    second = w.services.create_dataset_version(who.caller, session_id=session_id, now=LATER)

    assert second == first
    assert w.store.dataset_versions_for_scope(who.owner_id) == (first,)
    assert [e.outcome for e in events(w, who)] == [OUTCOME_COMPLETED, OUTCOME_ALREADY_RECORDED]


def test_the_retry_lookup_never_crosses_scopes() -> None:
    """Two organizations admit the same bytes. In production `RRA-002`'s randomised encryption
    gives the two copies different ciphertext digests; the test object store does not, which is
    what makes this the case that can see a missing `WHERE` -- a retry lookup unscoped by owner
    would hand the second organization the first's version as `already_recorded`."""
    w = world()
    ours, theirs = member(w), member(w, "other@example.test", "Other")
    our_version = w.services.create_dataset_version(
        ours.caller, session_id=admitted_session(w, ours.owner_id), now=NOW
    )

    their_version = w.services.create_dataset_version(
        theirs.caller, session_id=admitted_session(w, theirs.owner_id), now=NOW
    )

    assert their_version.owner_id == theirs.owner_id
    assert their_version.version_id != our_version.version_id
    assert their_version.upload_ciphertext_digest == our_version.upload_ciphertext_digest
    assert w.store.dataset_versions_for_scope(theirs.owner_id) == (their_version,)
    assert w.store.dataset_versions_for_scope(ours.owner_id) == (our_version,)
    assert [e.outcome for e in events(w, theirs)] == [OUTCOME_COMPLETED]


def test_a_version_cannot_be_created_from_another_scopes_session() -> None:
    """The session identifier is an object identifier, never authority (`FR-023`): a member of
    one organization naming another organization's session is refused, indistinguishably from
    naming no session at all."""
    w = world()
    ours, theirs = member(w), member(w, "other@example.test", "Other")
    their_session = admitted_session(w, theirs.owner_id)

    with pytest.raises(WorkspaceRefused):
        w.services.create_dataset_version(ours.caller, session_id=their_session, now=LATER)

    assert w.store.dataset_versions_for_scope(ours.owner_id) == ()
    assert w.store.dataset_versions_for_scope(theirs.owner_id) == ()
    assert len(events(w, ours)) == 1 and events(w, theirs) == ()


def test_a_non_member_is_refused_before_any_event_is_written() -> None:
    """Authorization is `resolve_scope`'s, one door (`R6-01` §5), and it comes first: an actor
    with no standing in the organization gets the uniform refusal and the workspace records
    nothing about the attempt, because there is no scope to record it in."""
    w = world()
    who = member(w)
    outsider = member(w, "other@example.test", "Other")
    session_id = admitted_session(w, who.owner_id)
    impostor = Member(outsider.account_id, who.organization_id, outsider.owner_id)

    with pytest.raises(ScopeAccessDenied):
        w.services.create_dataset_version(impostor.caller, session_id=session_id, now=LATER)

    assert events(w, who) == () and events(w, outsider) == ()


def test_the_service_reaches_admission_only_through_the_profiling_service() -> None:
    """The plan's named risk, asserted on the source: no admission internal is imported. The one
    way to a profile is `ProfilingService`, which is the `RRA-003` entry point."""
    import inspect as py_inspect

    from khepri.runtime import workspace

    source = py_inspect.getsource(workspace)
    for forbidden in (
        "khepri.rra.admission",
        "khepri.rra.profiling",
        "khepri.rra.mapping",
        "khepri.rra.facts",
        "build_document",
        "build_profile",
        "build_mapping",
        "build_fact_package",
    ):
        assert forbidden not in source, forbidden
    assert "ProfilingService" in source
    assert "FactPackageService" in source


# --- FR-111: a run is produced by the pipeline, and bound to its artifacts by digest -------------


def _version_and_run(w: World, who: Member) -> tuple[str, str, str]:
    session_id = admitted_session(w, who.owner_id)
    version = w.services.create_dataset_version(who.caller, session_id=session_id, now=NOW)
    run = w.services.start_analysis_run(who.caller, version_id=version.version_id, now=NOW)
    return session_id, version.version_id, run.run_id


def test_starting_a_run_needs_a_live_version_in_scope() -> None:
    w = world()
    who = member(w)
    session_id, version_id, run_id = _version_and_run(w, who)
    run = w.store.get_analysis_run(run_id)
    assert run is not None and run.state == RUN_STARTED and run.version_id == version_id
    # Two events at one instant order arbitrarily; the assertion is which actions occurred.
    assert sorted(e.action for e in events(w, who)) == sorted(
        [ACTION_VERSION_CREATED, ACTION_RUN_STARTED]
    )

    w.store.tombstone_dataset_version(version_id, now=LATER)
    with pytest.raises(WorkspaceRefused):
        w.services.start_analysis_run(who.caller, version_id=version_id, now=LATER)
    assert events(w, who)[-1].outcome == OUTCOME_REFUSED
    assert len(events(w, who)) == 3


def test_completing_a_run_binds_every_required_artifact_and_seals_the_version() -> None:
    """The run's provenance is the real package's -- digest and the two governed versions -- and
    one binding per required artifact kind carries that artifact's own digest. The first
    completion over a version seals it: `KHEPRI-DEC-033` starts the raw upload's purge clock at
    "facts derived and reconciled", which is this event."""
    w = world()
    who = member(w)
    session_id, version_id, run_id = _version_and_run(w, who)
    package = derived(w, session_id)

    completed = w.services.complete_analysis_run(
        who.caller, run_id=run_id, report=ReportLocator(session_id, JOB), now=LATER
    )

    assert completed.state == RUN_COMPLETED
    assert completed.package_digest == package.package_digest
    assert completed.package_version == package.package_version
    assert completed.formula_version == package.formula_version
    assert completed.completed_at == LATER
    assert w.store.get_analysis_run(run_id) == completed
    bindings = w.store.artifact_bindings_for_run(run_id)
    assert {(b.surface, b.artifact_digest) for b in bindings} == {
        (kind, w.artifacts.items[(session_id, JOB, kind)].sha256_hex)
        for kind in REQUIRED_ARTIFACT_KINDS
    }
    assert {b.published_at for b in bindings} == {LATER}
    version = w.store.get_dataset_version(version_id)
    assert version is not None and version.sealed_at == LATER
    recorded = events(w, who)[-1]
    assert (recorded.action, recorded.outcome) == (ACTION_RUN_COMPLETED, OUTCOME_COMPLETED)
    assert (recorded.object_kind, recorded.object_id) == (OBJECT_RUN, run_id)
    assert len(events(w, who)) == 3


@pytest.mark.parametrize("missing", REQUIRED_ARTIFACT_KINDS)
def test_a_run_missing_any_required_artifact_is_not_presented_as_completed(missing: str) -> None:
    """`FR-111`: fewer than every required surface is incomplete. Per kind, because a check that
    loops over some of them passes for the ones it names. The run stays `started`, gains no
    binding, and the version stays unsealed."""
    w = world()
    who = member(w)
    session_id, version_id, run_id = _version_and_run(w, who)
    derived(w, session_id)
    del w.artifacts.items[(session_id, JOB, missing)]

    with pytest.raises(WorkspaceRefused):
        w.services.complete_analysis_run(
            who.caller, run_id=run_id, report=ReportLocator(session_id, JOB), now=LATER
        )

    run = w.store.get_analysis_run(run_id)
    assert run is not None and run.state == RUN_STARTED and run.package_digest is None
    assert w.store.artifact_bindings_for_run(run_id) == ()
    version = w.store.get_dataset_version(version_id)
    assert version is not None and version.sealed_at is None
    assert events(w, who)[-1].outcome == OUTCOME_REFUSED


def test_a_run_cannot_be_completed_without_a_delivery_for_its_job() -> None:
    w = world()
    who = member(w)
    session_id, _version_id, run_id = _version_and_run(w, who)
    derived(w, session_id)
    del w.deliveries.records[JOB]

    with pytest.raises(WorkspaceRefused):
        w.services.complete_analysis_run(
            who.caller, run_id=run_id, report=ReportLocator(session_id, JOB), now=LATER
        )
    run = w.store.get_analysis_run(run_id)
    assert run is not None and run.state == RUN_STARTED


def test_a_package_derived_from_another_source_cannot_complete_a_run() -> None:
    """Provenance is checked, not assumed: the package's source digest and mapping version must
    be the run's version's. A run over version A completed from a session that admitted file B
    would bind A's history to B's figures."""
    w = world()
    who = member(w)
    _session_a, _version_a, run_id = _version_and_run(w, who)
    session_b = admitted_session(w, who.owner_id, OTHER_CSV)
    derived(w, session_b, job_id="job_b")

    with pytest.raises(WorkspaceRefused):
        w.services.complete_analysis_run(
            who.caller, run_id=run_id, report=ReportLocator(session_b, "job_b"), now=LATER
        )

    run = w.store.get_analysis_run(run_id)
    assert run is not None and run.state == RUN_STARTED
    assert w.store.artifact_bindings_for_run(run_id) == ()


def test_a_delivery_from_another_session_cannot_complete_a_run() -> None:
    """The delivery names its session; a job identifier alone is not enough. A delivery recorded
    under another session -- even another session of the same scope -- is refused."""
    w = world()
    who = member(w)
    session_id, _version_id, run_id = _version_and_run(w, who)
    derived(w, session_id)
    other = admitted_session(w, who.owner_id, OTHER_CSV)
    w.deliveries.records[JOB] = DeliveryRecord(
        job_id=JOB,
        session_id=other,
        bundle_id="bdl_other",
        package_version=w.deliveries.records[JOB].package_version,
        narrative_state="included",
        surfaces=("web", "pdf", "excel"),
    )

    with pytest.raises(WorkspaceRefused):
        w.services.complete_analysis_run(
            who.caller, run_id=run_id, report=ReportLocator(session_id, JOB), now=LATER
        )
    run = w.store.get_analysis_run(run_id)
    assert run is not None and run.state == RUN_STARTED


def test_a_second_completion_is_refused_and_binds_nothing_twice() -> None:
    w = world()
    who = member(w)
    session_id, _version_id, run_id = _version_and_run(w, who)
    derived(w, session_id)
    report = ReportLocator(session_id, JOB)
    w.services.complete_analysis_run(who.caller, run_id=run_id, report=report, now=LATER)

    with pytest.raises(WorkspaceRefused):
        w.services.complete_analysis_run(who.caller, run_id=run_id, report=report, now=LATER)

    assert len(w.store.artifact_bindings_for_run(run_id)) == len(REQUIRED_ARTIFACT_KINDS)
    completions = [e for e in events(w, who) if e.action == ACTION_RUN_COMPLETED]
    assert sorted(e.outcome for e in completions) == sorted([OUTCOME_COMPLETED, OUTCOME_REFUSED])


def test_completion_locks_the_version_before_the_run() -> None:
    """`set_retention_state` locks the version and then, in the cascade, its runs. A completion
    taking the same two rows in the other order could hold one each with a concurrent deletion and
    wait forever; the first draft did, and said the opposite in its docstring. Review on `#372`
    found it. Asserted on the source, because SQLite serializes writers and cannot show a deadlock;
    the run is re-checked *after* both locks, under its own."""
    import inspect as py_inspect

    from khepri.rca.workspace.persistence import SqlWorkspaceRecordStore

    body = py_inspect.getsource(SqlWorkspaceRecordStore.record_completion).split('"""')[-1]

    assert body.index("version_for_update(") < body.index("run_for_update(")
    assert body.index("run_for_update(") < body.index("row.state = outcome.state")
    assert "_live_in(row, owner_id)" in body, "a run the cascade tombstoned is refused"


def test_a_state_write_is_not_kept_without_its_audit_event() -> None:
    """`FR-125`: one action, one event -- and not one action, then hopefully one event. The
    action's write and the event share a unit of work, so an audit store that fails leaves no
    version behind for a retry to record as `already_recorded`. Review on `#372` found the two
    transactions the first draft used."""
    from khepri.rca.workspace.audit import WorkspaceAuditEvent
    from khepri.runtime.workspace import RecordStores, WorkspaceActions

    class _Exploding:
        def record(self, event: WorkspaceAuditEvent) -> WorkspaceAuditEvent:
            raise RuntimeError("the audit store is unavailable")

        def events_for_scope(self, owner_id: str) -> tuple[WorkspaceAuditEvent, ...]:
            return ()

    w = world()
    who = member(w)
    session_id = admitted_session(w, who.owner_id)
    unaudited = WorkspaceActions(
        isolation=w.services._isolation,
        rra=w.services._rra,
        rca=RecordStores(
            workspace=w.store, profiles=w.profiles, audit=_Exploding(), factory=w.factory
        ),
    )

    with pytest.raises(RuntimeError, match="audit store"):
        unaudited.create_dataset_version(who.caller, session_id=session_id, now=LATER)

    assert w.store.dataset_versions_for_scope(who.owner_id) == ()
    assert events(w, who) == ()


def test_failing_a_run_records_the_real_state_and_no_provenance() -> None:
    """A pipeline that did not deliver ends the run as `failed`: a real runtime state the history
    spine can show, never a run that looks unfinished forever or a completion with nothing behind
    it."""
    w = world()
    who = member(w)
    _session_id, version_id, run_id = _version_and_run(w, who)

    failed = w.services.fail_analysis_run(who.caller, run_id=run_id, now=LATER)

    assert failed.state == RUN_FAILED
    assert failed.package_digest is None and failed.completed_at == LATER
    assert w.store.get_analysis_run(run_id) == failed
    version = w.store.get_dataset_version(version_id)
    assert version is not None and version.sealed_at is None, "nothing was derived"
    recorded = events(w, who)[-1]
    assert (recorded.action, recorded.outcome) == (ACTION_RUN_FAILED, OUTCOME_COMPLETED)


# --- FR-114 / FR-115: the source profile is remembered as metadata and offered as a proposal ------


def _remembered(w: World, who: Member) -> tuple[str, SourceProfile]:
    session_id = admitted_session(w, who.owner_id)
    version = w.services.create_dataset_version(who.caller, session_id=session_id, now=NOW)
    profile = w.services.remember_source_profile(
        who.caller, version_id=version.version_id, session_id=session_id, now=LATER
    )
    return session_id, profile


def test_remembering_a_source_profile_stores_descriptive_metadata_only() -> None:
    """The column labels are the profile's *safe* labels and the proposal is the admitted
    mapping's (semantic, safe label) pairs -- what pre-fills a form. No outcome, no check result:
    `SourceProfile`'s field set is `W1-01`'s equality, and this fills only those fields."""
    w = world()
    who = member(w)
    session_id, profile = _remembered(w, who)
    admitted = w.profiling.get_session_profile(session_id=session_id, now=NOW)
    assert admitted is not None
    safe_labels = tuple(column["safe_label"] for column in admitted.document["profile"]["columns"])
    mapped = tuple(
        (mapping["semantic"], mapping["candidates"][0]["safe_label"])
        for mapping in admitted.document["mapping"]["mappings"]
        if mapping["state"] == "mapped"
    )

    assert profile.owner_id == who.owner_id
    assert profile.column_labels == safe_labels
    assert profile.proposed_mapping == mapped
    assert mapped, "the golden extract maps at least one semantic"
    assert profile.created_at == LATER
    assert w.profiles.get(profile.profile_id, who.owner_id) == profile
    assert w.profiles.for_scope(who.owner_id) == (profile,)
    recorded = events(w, who)[-1]
    assert (recorded.action, recorded.outcome) == (ACTION_PROFILE_REMEMBERED, OUTCOME_COMPLETED)
    assert (recorded.object_kind, recorded.object_id) == (OBJECT_PROFILE, profile.profile_id)


def test_a_profile_must_describe_the_version_it_is_remembered_for() -> None:
    """A session that admitted a different file cannot be remembered as this version's profile:
    the source digest and mapping version are compared, so the labels offered for reuse are the
    ones the version was actually admitted under."""
    w = world()
    who = member(w)
    version = w.services.create_dataset_version(
        who.caller, session_id=admitted_session(w, who.owner_id), now=NOW
    )
    other = admitted_session(w, who.owner_id, OTHER_CSV)

    with pytest.raises(WorkspaceRefused):
        w.services.remember_source_profile(
            who.caller, version_id=version.version_id, session_id=other, now=LATER
        )

    assert w.profiles.for_scope(who.owner_id) == ()
    assert events(w, who)[-1].outcome == OUTCOME_REFUSED


def test_proposing_reuse_returns_the_profile_and_emits_one_event() -> None:
    """`FR-125` names profile reuse as an audited action even though it writes nothing: the
    proposal is what the customer sees before confirming (`FR-114`), and that showing is the
    action."""
    w = world()
    who = member(w)
    _session_id, profile = _remembered(w, who)
    before = len(events(w, who))

    proposed = w.services.propose_reuse(who.caller, profile_id=profile.profile_id, now=LATER)

    assert proposed == profile
    (recorded,) = [e for e in events(w, who) if e.action == ACTION_PROFILE_REUSED]
    assert recorded.outcome == OUTCOME_COMPLETED
    assert (recorded.object_kind, recorded.object_id) == (OBJECT_PROFILE, profile.profile_id)
    assert len(events(w, who)) == before + 1


def test_a_profile_of_a_deleted_version_is_not_offered() -> None:
    """`KHEPRI-DEC-033` §1: derived content never outlives its input's right to exist. The
    profile describes a version the customer withdrew, so it is not proposed."""
    w = world()
    who = member(w)
    _session_id, profile = _remembered(w, who)
    w.store.tombstone_dataset_version(profile.source_version_id, now=LATER)

    assert w.profiles.get(profile.profile_id, who.owner_id) is None
    assert w.profiles.for_scope(who.owner_id) == ()
    with pytest.raises(WorkspaceRefused):
        w.services.propose_reuse(who.caller, profile_id=profile.profile_id, now=LATER)
    (recorded,) = [e for e in events(w, who) if e.action == ACTION_PROFILE_REUSED]
    assert (recorded.outcome, recorded.object_id) == (OUTCOME_REFUSED, None)


def test_a_profile_is_read_by_scope() -> None:
    w = world()
    ours, theirs = member(w), member(w, "other@example.test", "Other")
    _session_id, profile = _remembered(w, ours)

    assert w.profiles.get(profile.profile_id, theirs.owner_id) is None
    assert w.profiles.for_scope(theirs.owner_id) == ()
    with pytest.raises(WorkspaceRefused):
        w.services.propose_reuse(theirs.caller, profile_id=profile.profile_id, now=LATER)
