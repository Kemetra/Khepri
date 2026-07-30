"""The stages one leased report job runs through, in order, once.

**What this fills.** `ReportWorker` is a lease, heartbeat, and retry harness
with a hole where report generation belongs: it takes an injected handler and
nothing supplied one. This module is that handler. It owns the *order* of the
stages and nothing else — the fact package is published elsewhere, the
narrative is validated elsewhere, reconciliation is decided in `bundle`, and
the surfaces are rendered by code that has yet to be written. What is decided
here is that a report is loaded, narrated, rendered, reconciled, and delivered
in that sequence, and that a failure anywhere in it delivers nothing.

**Every stage is a separately callable method.** `load_package`,
`compose_narrative`, `assemble`, and `deliver` are public and each takes what
the previous one returned. That is so a later change can time or trace each
boundary without reaching inside a single long method — the stage names in
`telemetry.STAGES` already exist for that change, and no measurement is taken
here.

**Why there is no `try` in this module.** RRA-007 requires a lost lease to
abandon the run: `LeaseLost` means another worker owns this job, and a second
worker delivering the same report is the failure leases exist to prevent. Both
collaborators that could hide it already contain their own broad handlers —
`NarrativeService.compose` turns any provider exception into a refusal, and
`BundleAssembler.assemble` turns any renderer exception into an incomplete
bundle. A heartbeat inside either of those would be swallowed, so heartbeats
sit strictly *between* stages and this module catches nothing at all. For the
same reason no renderer is handed `execution.heartbeat`: a per-surface
heartbeat would run inside the assembler's `except Exception`, and a lost lease
would surface as a bundle refusal instead of a lost lease.

**Why a refused narrative stops the run.** `NarrativeService` deliberately
leaves this decision to the delivery contract, and RRA-006 authorizes a
facts-only report whose disclosure says the commentary was refused. This
pipeline does not deliver one. Building a facts-only report is a *different*
report from the one this job was queued for, and choosing to publish it is an
authorization this slice was not granted. `ReportBundle.of(...,
narrative_refused=True)` remains available to whatever contract is granted it.

**Idempotency is asked of the store, not inferred.** A delivered job is
recognized by an existing delivery record rather than by rebuilding the bundle
and comparing names. Rebuilding would mean asking a provider for prose again,
and prose is the one input that is not deterministic — the second run would
produce a different `bundle_id` and read as a different report. So the question
asked is "was this job already delivered", which the store can answer before
any stage runs.

**No clock.** RRA-006 binds a generation timestamp to a bundle, and `bundle`
keeps it out of the bundle's identity so that regeneration reproduces the same
name. When a report was produced is a fact about the run and belongs to the
record that stores it, so the store stamps it and this module never sees one.
That is also what makes `bundle_id` a usable test of determinism here.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from khepri.rra.bundle import (
    GOVERNED_NARRATIVE_STATES,
    REQUIRED_SURFACES,
    BundleAssembler,
    BundleAttempt,
    ReportBundle,
    SurfaceContent,
    SurfaceRenderer,
)
from khepri.rra.bundle import GOVERNED_REASONS as BUNDLE_REASONS
from khepri.rra.facts import FactPackage
from khepri.rra.jobs import ReportJob
from khepri.rra.narrative import GOVERNED_REASONS as NARRATIVE_REASONS
from khepri.rra.narrative import (
    NarrativeAdapter,
    NarrativeDraft,
    NarrativeService,
)
from khepri.rra.worker import WorkerExecution

PIPELINE_VERSION = "rra006.pipeline.v1"

# No fact package was published for this job's session. The report cannot be
# built from anything else, so there is nothing to fall back to.
REASON_PACKAGE_MISSING = "fact_package_missing"
# A stage failed for a reason outside every governed vocabulary. Coarse on
# purpose: it says only that a stage failed, so nothing a provider or renderer
# wrote is echoed into a record documented as content-free.
REASON_STAGE_FAILED = "stage_failed"

PIPELINE_REASONS = frozenset({REASON_PACKAGE_MISSING, REASON_STAGE_FAILED})

# Every reason a pipeline failure may be recorded as. The narrative and bundle
# vocabularies are carried through rather than flattened into one pipeline
# reason: a provider timeout and a surface that would not reconcile are
# different operational facts, and an operator reading only `stage_failed`
# learns neither.
GOVERNED_REASONS = PIPELINE_REASONS | NARRATIVE_REASONS | BUNDLE_REASONS


class ReportPipelineFailed(RuntimeError):
    """A stage refused, and nothing was delivered.

    Carries a governed reason code rather than collaborator text, for the same
    reason `NarrativeRefused` and `BundleRefused` do: this reason reaches
    operational evidence that claims to hold no customer content, and that
    claim needs a gate rather than a convention.
    """

    def __init__(self, reason: str) -> None:
        governed = reason if reason in GOVERNED_REASONS else REASON_STAGE_FAILED
        super().__init__(governed)
        self.reason = governed


class FactPackageSource(Protocol):
    """Where a leased job's immutable fact package is read from.

    Keyed by the whole job rather than by a session identifier, because the
    source has to enforce the session's own isolation boundary and a bare
    string does not carry the owner.
    """

    def load(self, job: ReportJob) -> FactPackage | None: ...


@dataclass(frozen=True, slots=True)
class DeliveryRecord:
    """Content-free evidence that one job's report was delivered.

    Every field is an opaque identifier, a content address, a governed version,
    a narrative state, or a surface name. There is no field a label, a figure, a
    caveat, or a provider sentence could occupy.

    `session_id` is here rather than left to a lookup for two reasons. RRA-006
    stores published outputs under the same expiry and deletion boundary as the
    input, so the store has to know which session's boundary applies at the
    moment it writes. And RRA-007 correlates operational evidence with the
    opaque session identifier, which `OperationalEvent` requires — a record
    naming only the job would make the later telemetry slice re-derive it.
    """

    job_id: str
    session_id: str
    bundle_id: str
    package_version: str
    narrative_state: str
    surfaces: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text(self.job_id, "job_id")
        _require_text(self.session_id, "session_id")
        _require_text(self.bundle_id, "bundle_id")
        _require_text(self.package_version, "package_version")
        if self.narrative_state not in GOVERNED_NARRATIVE_STATES:
            raise ValueError("narrative_state must be a governed state.")
        if self.surfaces != REQUIRED_SURFACES:
            # A record naming two surfaces is a record of a partial export,
            # which RRA-006 calls an incomplete bundle rather than a delivery.
            raise ValueError("A delivered report names every required surface.")

    def as_document(self) -> dict[str, object]:
        return {
            "pipeline_version": PIPELINE_VERSION,
            "job_id": self.job_id,
            "session_id": self.session_id,
            "bundle_id": self.bundle_id,
            "package_version": self.package_version,
            "narrative_state": self.narrative_state,
            "surfaces": list(self.surfaces),
        }

    @classmethod
    def of(cls, job: ReportJob, attempt: BundleAttempt) -> DeliveryRecord:
        return cls(
            job_id=job.job_id,
            session_id=job.session_id,
            bundle_id=attempt.bundle_id,
            package_version=attempt.package_version,
            narrative_state=attempt.narrative_state,
            surfaces=attempt.surfaces,
        )


@dataclass(frozen=True, slots=True)
class ReportDelivery:
    """One whole report, offered to a store as a single unit.

    The surfaces are handed over together and checked together. A store given
    them one at a time could commit the workbook and then fail on the PDF,
    which is the mixture of versions RRA-006 forbids.
    """

    record: DeliveryRecord
    bundle: ReportBundle
    surfaces: tuple[SurfaceContent, ...]

    def __post_init__(self) -> None:
        _require_every_surface(self.surfaces)
        _require_named_bundle(self.record, self.bundle)
        _require_one_bundle_behind_every_surface(self.surfaces, self.bundle)


class DeliveryStore(Protocol):
    """Where a delivered report and its content-free evidence are kept."""

    def find_delivery(self, job_id: str) -> DeliveryRecord | None: ...

    def deliver(self, delivery: ReportDelivery) -> DeliveryRecord: ...


@dataclass(frozen=True, slots=True)
class PipelineOutcome:
    """What one run produced, and whether this run is what produced it."""

    record: DeliveryRecord
    delivered: bool


class ReportPipeline:
    """Run the report stages for one leased job, or deliver nothing.

    Callable, so it is the `handler` `ReportWorker` takes. `run` returns the
    outcome for callers that want it; the worker does not.
    """

    def __init__(
        self,
        *,
        packages: FactPackageSource,
        adapter: NarrativeAdapter,
        renderers: Sequence[SurfaceRenderer],
        deliveries: DeliveryStore,
        monotonic_ms: Callable[[], int],
    ) -> None:
        self._packages = packages
        # Constructed here rather than injected: both services own a policy
        # this module must not restate — the narrative service owns provider
        # timeouts and refusals, the assembler owns reconciliation and the
        # all-or-nothing rule. The replaceable parts are the two Protocols.
        self._narrative = NarrativeService(adapter=adapter, monotonic_ms=monotonic_ms)
        self._assembler = BundleAssembler(renderers=renderers)
        self._deliveries = deliveries

    def __call__(self, execution: WorkerExecution) -> None:
        self.run(execution)

    def run(self, execution: WorkerExecution) -> PipelineOutcome:
        """Every stage, in order, with the lease renewed between each.

        The heartbeats are outside every stage rather than inside one, so a
        lost lease reaches the worker as a lost lease. See the module docstring
        for why that placement is load-bearing rather than tidy.
        """
        job = execution.job
        delivered = self._deliveries.find_delivery(job.job_id)
        if delivered is not None:
            # Asked before any stage runs, so a duplicate delivery of this job
            # costs a lookup rather than a provider call and three renders.
            return PipelineOutcome(record=delivered, delivered=False)

        package = self.load_package(job)
        execution.heartbeat()
        narrative = self.compose_narrative(package)
        execution.heartbeat()
        delivery = self.assemble(job, package, narrative)
        execution.heartbeat()
        return PipelineOutcome(record=self.deliver(delivery), delivered=True)

    def load_package(self, job: ReportJob) -> FactPackage:
        """The one immutable package every surface of this report comes from."""
        package = self._packages.load(job)
        if package is None:
            raise ReportPipelineFailed(REASON_PACKAGE_MISSING)
        return package

    def compose_narrative(self, package: FactPackage) -> NarrativeDraft:
        """Grounded Arabic and English prose, or no report at all."""
        result = self._narrative.compose(package)
        if result.narrative is None:
            raise ReportPipelineFailed(result.attempt.reason or REASON_STAGE_FAILED)
        return result.narrative

    def assemble(
        self,
        job: ReportJob,
        package: FactPackage,
        narrative: NarrativeDraft,
    ) -> ReportDelivery:
        """Render every surface and reconcile each against the one package.

        Both happen in `BundleAssembler`, which already refuses to hand back a
        surface it could not reconcile. Splitting them here would mean holding
        an unreconciled surface in this module, which is exactly the state
        `bundle` is designed never to expose.
        """
        bundle = ReportBundle.of(package, narrative=narrative)
        result = self._assembler.assemble(bundle)
        if result.surfaces is None:
            raise ReportPipelineFailed(result.attempt.reason or REASON_STAGE_FAILED)
        return ReportDelivery(
            record=DeliveryRecord.of(job, result.attempt),
            bundle=bundle,
            surfaces=result.surfaces,
        )

    def deliver(self, delivery: ReportDelivery) -> DeliveryRecord:
        """Persist the whole report, which is the first durable side effect."""
        return self._deliveries.deliver(delivery)


def _require_text(value: str, name: str) -> None:
    if not value:
        raise ValueError(f"{name} is required.")


def _require_every_surface(surfaces: tuple[SurfaceContent, ...]) -> None:
    """Refuse a delivery that is not the whole report.

    Ordered rather than counted, so two copies of the workbook cannot stand in
    for the PDF that never rendered.
    """
    if tuple(entry.surface for entry in surfaces) != REQUIRED_SURFACES:
        raise ValueError("A delivery carries every required surface exactly once.")


def _require_named_bundle(record: DeliveryRecord, bundle: ReportBundle) -> None:
    """Refuse evidence that names a report other than the one being delivered."""
    if record.bundle_id != bundle.bundle_id:
        raise ValueError("The delivery record names another bundle.")


def _require_one_bundle_behind_every_surface(
    surfaces: tuple[SurfaceContent, ...],
    bundle: ReportBundle,
) -> None:
    """Refuse a surface built for some other bundle.

    Deliberately redundant: `bundle.reconcile` already rejected this during
    assembly. It is checked again because this object is what a store writes,
    and so is the last place a surface from one run could arrive beside a
    bundle from another.
    """
    for entry in surfaces:
        if entry.bundle_id != bundle.bundle_id:
            raise ValueError("A surface was built for another bundle.")


__all__ = [
    "GOVERNED_REASONS",
    "PIPELINE_VERSION",
    "REASON_PACKAGE_MISSING",
    "REASON_STAGE_FAILED",
    "DeliveryRecord",
    "DeliveryStore",
    "FactPackageSource",
    "PipelineOutcome",
    "ReportDelivery",
    "ReportPipeline",
    "ReportPipelineFailed",
]
