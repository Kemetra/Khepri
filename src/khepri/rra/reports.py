"""What the HTTP surface is allowed to say about a requested report.

**Why this is a module and not part of `api.py`.** A caller asking for a report
reaches three separate questions -- was one already asked for, what happened to
it, and may the result be served -- and each has a governed answer that is not a
transport concern. The vocabularies, the fail-closed guards, and the
collaborator contracts live here; `api.py` maps them onto status codes.

**Nothing here reads or writes anything.** The two Protocols are the seam a
separate persistence slice fills. This module owns no store, no queue, and no
renderer, so the whole surface is exercisable against hand-written fakes.

**The state vocabulary is imported, never restated.** `jobs.JOB_STATES` is the
one authority on which states exist, and the report jobs table constrains its
`state` column to exactly that set. A second list here would be a second thing
to forget: when `failed` became `dead_lettered`, a local copy would have gone on
accepting a state no writer produces and rejecting the one they do.

**Two reason vocabularies, deliberately not merged.** `dead_letter_reason` says
why the queue stopped retrying a job and is a closed two-value enum written only
by the job store, so an unrecognized value there means the store is broken and
fails closed. The stage reason says what the last attempt failed on, reaches this
module from provider and renderer paths, and is therefore collapsed to
`stage_failed` when ungoverned rather than refused. Different provenance, so
different treatment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from khepri.rra.artifact_publication import ArtifactDocument
from khepri.rra.bundle import GOVERNED_REASONS as BUNDLE_REASONS
from khepri.rra.bundle import (
    REASON_BUNDLE_MISMATCH,
    REASON_DUPLICATE_SURFACE,
    REASON_MISSING_SURFACE,
    REASON_SURFACE_FAILED,
    REASON_UNKNOWN_SURFACE,
    REQUIRED_SURFACES,
)
from khepri.rra.jobs import (
    DEAD_LETTER_REASONS,
    JOB_DEAD_LETTERED,
    JOB_STATES,
    JOB_SUCCEEDED,
    ReportJob,
    UnknownJobState,
)
from khepri.rra.package_source import SessionPackageReader
from khepri.rra.pipeline import (
    GOVERNED_REASONS,
    REASON_STAGE_FAILED,
    DeliveryRecord,
)


class ReportPackageMissing(LookupError):
    """No fact package was published for this session, so nothing can be built."""


@dataclass(frozen=True, slots=True)
class ReportJobView:
    """One job as a caller may see it, and nothing more.

    The reason and the delivery record are carried beside the job rather than on
    it: `ReportJob` is the lease and retry record that RRA-007 governs, and a
    field for "why did this fail" on it would be a field a worker has to
    remember to fill. Both are optional because most states have neither.
    """

    job: ReportJob
    reason: str | None = None
    delivery: DeliveryRecord | None = None


class JobEvidenceContradicted(RuntimeError):
    """A stored job claims one thing and the evidence beside it says another.

    Not a caller's mistake and not a refusal, so it carries no reason a caller
    could act on: which invariant a store broke is an operator's question.
    """


@dataclass(frozen=True, slots=True)
class JobOutcome:
    """Everything one job's state entitles a caller to be told.

    Assembled once, so every way a job can say too much -- a bundle named before
    one was delivered, a verdict given before the report finished, a dead-letter
    reason on a job still running -- is decided in one place rather than at each
    field.
    """

    state: str
    bundle_id: str | None
    reason: str | None
    dead_letter_reason: str | None


def job_outcome(view: ReportJobView) -> JobOutcome:
    """What may be reported for this job, or nothing at all.

    Fails closed rather than reporting a partial answer: a job this release
    cannot govern, or whose evidence contradicts its state, has no outcome to
    describe, and describing it anyway is how an abandoned or unfinished run
    comes to look like a delivered report.
    """
    _require_governed_state(view)
    return JobOutcome(
        state=view.job.state,
        bundle_id=_delivered_bundle_id(view),
        reason=_failure_reason(view),
        dead_letter_reason=_dead_letter_reason(view),
    )


def _require_governed_state(view: ReportJobView) -> None:
    """A state this release does not govern is not a state to report.

    `jobs.JOB_STATES` is the authority, and `UnknownJobState` is the exception
    `jobs` already raises for exactly this question -- inventing a second one
    here would mean two names for one refusal.
    """
    if view.job.state not in JOB_STATES:
        raise UnknownJobState("Report job state is unrecognized.")


def _dead_letter_reason(view: ReportJobView) -> str | None:
    """Why the queue gave up on this job, if it did.

    The report jobs table constrains a dead-letter reason to be present exactly
    when the state is `dead_lettered`, and to be one of the governed reasons.
    Both halves are checked again here rather than assumed, because the store is
    a Protocol: an abandoned job that cannot say why it was abandoned, and a live
    job carrying an abandonment reason, are each a contradiction rather than an
    outcome to describe.
    """
    reason = view.job.dead_letter_reason
    if view.job.state != JOB_DEAD_LETTERED:
        if reason is not None:
            raise JobEvidenceContradicted("A live report job was given up on.")
        return None
    if reason not in DEAD_LETTER_REASONS:
        # Closed enum, written only by the job store, so an unrecognized value
        # is a broken writer rather than text that needs collapsing.
        raise JobEvidenceContradicted("Report job dead-letter reason is not governed.")
    return reason


def _delivered_bundle_id(view: ReportJobView) -> str | None:
    """The bundle this job delivered, or nothing it is entitled to name.

    A succeeded job is a delivered report, so one with no delivery record, or
    with a record naming another job, is a contradiction rather than a report.
    An unfinished job names nothing: it has no outcome yet, and a bundle
    identifier on a running job would announce one.
    """
    if view.job.state != JOB_SUCCEEDED:
        return None
    delivered = view.delivery
    if delivered is None or delivered.job_id != view.job.job_id:
        raise JobEvidenceContradicted("Report job delivery is not its own.")
    return delivered.bundle_id


def _failure_reason(view: ReportJobView) -> str | None:
    """What the last attempt failed on, in governed words or none at all.

    Collapsed rather than passed through, exactly as `ReportPipelineFailed`
    collapses an ungoverned reason: this value reaches a response documented as
    content-free, and no store is trusted to have kept a provider's sentence or
    a customer's label out of the reason it recorded.

    Only a dead-lettered job carries one. A retrying job has failed an attempt
    and not the report, and a reason on it would read as a verdict already
    reached while the queue is still going to try again.
    """
    if view.reason is None or view.job.state != JOB_DEAD_LETTERED:
        return None
    if view.reason in GOVERNED_REASONS:
        return view.reason
    return REASON_STAGE_FAILED


class DeliveryWithheld(ValueError):
    """A stored delivery cannot be served as one whole report.

    Carries a governed reason code rather than store text, the same gate
    `BundleRefused` applies for the same purpose: the reason travels into
    operational evidence that claims to hold no customer content.
    """

    def __init__(self, reason: str) -> None:
        governed = reason if reason in BUNDLE_REASONS else REASON_SURFACE_FAILED
        super().__init__(governed)
        self.reason = governed


@dataclass(frozen=True, slots=True)
class DeliveredSurface:
    """One published surface, named and bound to the bundle it was built for.

    A name and a content address, and nothing a reader would recognize: no
    filename, no location, no size, no bytes. `bundle_id` is the whole binding
    RRA-006 needs, because it is a digest over `BundleIdentity` -- so a surface
    agreeing on it agrees on the fact-package version, the mapping, the source
    digest, and the narrative behind it at once.
    """

    surface: str
    bundle_id: str


@dataclass(frozen=True, slots=True)
class DeliveredBundle:
    """What a store holds for one job: the evidence, and the surfaces beside it.

    Permissive on purpose. A partially committed delivery is a state that
    happens, and a type that refused to describe one would turn an unservable
    report into a crash without a governed reason. What is stored and what is
    servable are separate questions -- `reconcile_delivery` answers the second,
    following `SurfaceContent` being untrusted until reconciled.
    """

    record: DeliveryRecord
    surfaces: tuple[DeliveredSurface, ...]


def reconcile_delivery(bundle: DeliveredBundle, *, job_id: str) -> None:
    """Refuse a delivery that is not one whole report for this one job.

    RRA-006 calls a partial export an incomplete bundle and forbids serving a
    mixture of versions, so every required surface must be present exactly once
    and every one of them must name the bundle the record names. Nothing here is
    repaired or partially served: a delivery either reconciles whole or is
    withheld whole.
    """
    if bundle.record.job_id != job_id:
        raise DeliveryWithheld(REASON_BUNDLE_MISMATCH)
    _require_whole_surfaces(bundle.surfaces)
    _require_one_bundle(bundle)


def _require_whole_surfaces(surfaces: tuple[DeliveredSurface, ...]) -> None:
    named = [entry.surface for entry in surfaces]
    if len(set(named)) != len(named):
        # Collapsing duplicates into a set first would let a store holding two
        # copies of one surface reconcile as though it held one.
        raise DeliveryWithheld(REASON_DUPLICATE_SURFACE)
    if set(named) - set(REQUIRED_SURFACES):
        raise DeliveryWithheld(REASON_UNKNOWN_SURFACE)
    if set(named) != set(REQUIRED_SURFACES):
        raise DeliveryWithheld(REASON_MISSING_SURFACE)


def _require_one_bundle(bundle: DeliveredBundle) -> None:
    for entry in bundle.surfaces:
        if entry.bundle_id != bundle.record.bundle_id:
            # The whole defence against serving one run's PDF beside another
            # run's workbook. A surface built for another bundle names one.
            raise DeliveryWithheld(REASON_BUNDLE_MISMATCH)


class ReportRequestService(Protocol):
    """Where a caller's report job is asked for and read back.

    Both methods take the caller's own session identifier, so the boundary is
    enforced by whatever satisfies this contract rather than checked afterwards
    by the route. A job belonging to another session is absent, not forbidden.

    `request_session_report` returns whether *this* call created the job, in the
    same shape `FactPackageService.build_session_package` uses. Re-requesting is
    the same request, so it returns the same job: the idempotency key that makes
    that true belongs to the store, and deriving a second one here would be a
    second answer to the same question.
    """

    def request_session_report(
        self,
        *,
        session_id: str,
        now: datetime,
    ) -> tuple[ReportJobView, bool]: ...

    def get_session_job(
        self,
        *,
        session_id: str,
        job_id: str,
        now: datetime,
    ) -> ReportJobView | None: ...


class DeliveredBundleReader(Protocol):
    """Where one job's delivered report is read back from.

    Scoped to the caller's session for the same reason the job contract is: a
    delivery belonging to another session is absent here, not refused, so no
    route has to decide how much of another caller's report to describe.
    """

    def get_session_bundle(
        self,
        *,
        session_id: str,
        job_id: str,
        now: datetime,
    ) -> DeliveredBundle | None: ...


class ReportArtifactReader(Protocol):
    """Resolve verified report bytes only through the caller's session."""

    def get_session_artifact(
        self,
        *,
        session_id: str,
        job_id: str,
        artifact_kind: str,
        now: datetime,
    ) -> ArtifactDocument | None: ...


@dataclass(frozen=True, slots=True)
class ReportServices:
    """The collaborators the report surface needs, injected as one unit.

    Both are Protocols, so a deployment still substitutes either half freely and
    the whole surface is exercisable against fakes. They travel together because
    they are one feature: a caller able to request a report and poll it but never
    to fetch what it produced has been given two thirds of a contract, and a
    surface that could be configured that way is a surface that will be.
    """

    jobs: ReportRequestService
    bundles: DeliveredBundleReader
    artifacts: ReportArtifactReader | None = None
    #: The catalog routes read a package to rebuild the bundle they answer from.
    #: Optional for the same reason `artifacts` is: a deployment that supplies no
    #: reader declares no catalog group rather than declaring one that refuses.
    packages: SessionPackageReader | None = None


__all__ = [
    "DeliveredBundle",
    "DeliveredBundleReader",
    "DeliveredSurface",
    "DeliveryWithheld",
    "JobEvidenceContradicted",
    "JobOutcome",
    "ReportJobView",
    "ReportPackageMissing",
    "ReportRequestService",
    "ReportArtifactReader",
    "ReportServices",
    "job_outcome",
    "reconcile_delivery",
]
