"""One benchmark dataset, taken through the report path and measured.

**What actually runs here.** The deterministic work is really done: the dataset
bytes are materialized and profiled, the retail mapping is inferred, admissibility
is assessed, the immutable fact package is built, one bundle is bound, every
surface is rendered, and each is reconciled against that bundle. A harness that
timed a stub would produce numbers about nothing, so the part of the path that is
the same in every environment is executed rather than simulated.

**What stays a port, and why.** The renderers and the narrative provider are
injected. Those are exactly the boundaries the *approved environment* defines --
a pinned Chromium, a workbook writer, a provider with a governed timeout -- and a
benchmark run with substituted ones measures a different environment from the
approved one. Injecting them keeps that substitution visible in the run's
configuration instead of hidden in this module.

**What is deliberately not measured.** Nothing is delivered. `DeliveryStore` writes
to a database inside a session's retention boundary, and a benchmark has no
session, no owner, and no consent -- inventing one to time an insert would create
customer-shaped state to measure a duration. So the measured path ends at
reconciled surfaces, and the storage and delivery stages of the RRA-007 vocabulary
are outside this reading. Any evidence produced from these measurements is
evidence about the path up to reconciliation and must not be read as more.

**Why a refused narrative is not a complete bundle.** `pipeline` refuses to deliver
a report whose commentary was refused: building a facts-only report instead is a
*different* report from the one that was requested. A benchmark counting that as a
complete bundle would certify an objective the delivery contract never met, so a
provider that did not answer measures no surfaces at all.

**Content-free by construction.** The dataset is synthetic and its bytes never
leave this module. What the outcome carries is a monotonic reading, surface names
from a closed vocabulary, and a boolean.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.benchmark_workload import BenchmarkDataset
from khepri.rra.bundle import (
    REQUIRED_SURFACES,
    BundleAssembler,
    BundleResult,
    ReportBundle,
    SurfaceRenderer,
)
from khepri.rra.facts import AdmittedInput, FactPackage, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import NarrativeDraft
from khepri.rra.profiling import build_profile
from khepri.rra.source_contract import (
    BasisDeclaration,
    ContractAttribution,
    EventDeclaration,
    IdentityDeclaration,
    SourceContract,
    build_source_contract,
)


class NarrativeSource(Protocol):
    """Whatever composes grounded prose in the approved environment.

    Narrower than `NarrativeAdapter` on purpose: a benchmark needs the latency of
    composing and validating a draft, not the request-building contract. `None`
    means the provider did not answer, which is the state `NarrativeService`
    already reports as a refusal.
    """

    def draft(self, package: FactPackage) -> NarrativeDraft | None: ...


@dataclass(frozen=True, slots=True)
class TrialPorts:
    """The collaborators an approved benchmark environment supplies."""

    renderers: Sequence[SurfaceRenderer]
    narrator: NarrativeSource | None = None


@dataclass(frozen=True, slots=True)
class TrialOutcome:
    """What one measured report run produced, without any of its content."""

    started_at_ms: int
    surfaces: tuple[str, ...]
    complete: bool

    def __post_init__(self) -> None:
        _require_whole_report(self.surfaces, self.complete)


class DeterministicReportTrial:
    """The report path for one dataset, run once and reported on."""

    def __init__(
        self,
        *,
        ports: TrialPorts,
        monotonic_ms: Callable[[], int],
    ) -> None:
        self._narrator = ports.narrator
        self._assembler = BundleAssembler(renderers=ports.renderers)
        self._clock = monotonic_ms

    def run(self, dataset: BenchmarkDataset) -> TrialOutcome:
        """Profile, calculate, narrate, render, reconcile -- and time none of it.

        The reading taken here is only *when this trial began*. How long it took
        is the harness's measurement, because a trial that timed itself could
        report a duration shorter than the work it did.
        """
        started_at_ms = self._clock()
        bundle = self._bundle(build_benchmark_package(dataset))
        if bundle is None:
            return TrialOutcome(started_at_ms=started_at_ms, surfaces=(), complete=False)
        return _outcome(started_at_ms, self._assembler.assemble(bundle))

    def _bundle(self, package: FactPackage) -> ReportBundle | None:
        """One report bound to one package, or nothing to render at all."""
        if self._narrator is None:
            return ReportBundle.of(package)
        narrative = self._narrator.draft(package)
        if narrative is None:
            return None
        return ReportBundle.of(package, narrative=narrative)


def build_benchmark_package(dataset: BenchmarkDataset) -> FactPackage:
    """The immutable fact package one synthetic dataset produces.

    The whole intake calculation, not a shortcut through it: a package built by
    any other route would measure a path no report is ever produced by.
    """
    profile = build_profile(
        content=dataset.content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=dataset.digest,
    )
    contract = _benchmark_contract()
    mapping = build_mapping(profile, contract=contract)
    return build_fact_package(
               AdmittedInput(
                   content=dataset.content,
                   media_type=CSV_MEDIA_TYPE,
                   profile=profile,
                   mapping=mapping,
                   decision=assess_admissibility(profile, mapping),
                   contract=contract,
               ),
           )


def _benchmark_contract() -> SourceContract:
    """What the synthetic benchmark extract means.

    The declaration is true of the generated data by construction -- the
    generator emits posted sales in one currency, one row per line -- so it is
    recorded rather than inferred, exactly as `RRA-003` requires of a real one.

    Constant rather than parameterised: the benchmark measures the cost of the
    calculation path, and a contract that varied per trial would vary the
    mapping and stop the trials from being comparable.
    """
    return build_source_contract(
        attribution=ContractAttribution(
            contract_id="src_benchmark",
            evidence="Synthetic benchmark dataset generated by khepri.rra.benchmark.",
        ),
        events=EventDeclaration(
            event_kind_column=None,
            sale_only=True,
            status_column=None,
            posted_only=True,
            currency_column=None,
            currency_code="EGP",
        ),
        identity=IdentityDeclaration(
            event_key_columns=(),
            unique_line_grain_attested=True,
            # `benchmark_rows` emits `TXN-%08d` from a per-dataset ordinal, so
            # the identifier is unique across the package by construction and
            # needs no composite key.
            transaction_id_column="transaction_id",
            transaction_key_components=(),
            transaction_id_unique_package_wide=True,
        ),
        basis=BasisDeclaration(
            revenue_vat_exclusive=True,
            revenue_is_net_of_returns=False,
            units_are_integral=True,
            cost_is_extended=True,
            discount_is_additive=True,
        ),
    )


def _outcome(started_at_ms: int, result: BundleResult) -> TrialOutcome:
    """Completion is taken from the assembler's own answer, not from a count.

    `BundleResult.surfaces` is `None` for every incomplete attempt, whatever the
    attempt happened to render first, so nothing here has to infer completeness
    from the names in the record.
    """
    return TrialOutcome(
        started_at_ms=started_at_ms,
        surfaces=result.attempt.surfaces,
        complete=result.surfaces is not None,
    )


def _require_whole_report(surfaces: tuple[str, ...], complete: bool) -> None:
    if not complete:
        return
    if surfaces != REQUIRED_SURFACES:
        raise ValueError("A complete bundle names every required surface.")


__all__ = [
    "DeterministicReportTrial",
    "NarrativeSource",
    "TrialOutcome",
    "TrialPorts",
    "build_benchmark_package",
]
