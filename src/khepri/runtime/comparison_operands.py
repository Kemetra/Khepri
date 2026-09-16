"""`RCA-009` `FR-180`: the one shared seam that derives a comparison operand.

The comparison operand derivation is relocated here from
`khepri.runtime.comparison_assembly`, not reimplemented: this module states
no calculation, completeness, timezone, compatibility, provenance, ordering,
refusal, or isolation semantics beyond what that module already stated.
Completeness remains the `RRA-003` coverage manifest's answer -- `_complete`
asks `admits_completeness` -- and is never inferred from period bounds. Run
*selection* from a version identifier stays with `comparison_assembly`; this
seam is addressed by a run its caller already read.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

from khepri.rca.workspace.contracts import AnalysisRun
from khepri.rca.workspace.provenance import RunProvenance
from khepri.rra.aggregates import granularity_for
from khepri.rra.analysis.comparison_narrative import refusal_wording
from khepri.rra.analysis.dataset_period import (
    CAUSE_RETAIL_DAY,
    CAUSE_UNORDERED_PAIR,
    DatasetPeriod,
)
from khepri.rra.coverage import CompletenessQuery, CoverageManifest, admits_completeness
from khepri.rra.crossversion_assembly import assemble_crossversion
from khepri.rra.crossversion_bundle import CrossVersionRefusal, CrossVersionRequest
from khepri.rra.datasets import DatasetProfileRecord, ProfilingService, stored_manifest
from khepri.rra.facts import FactPackage
from khepri.rra.package_source import rebuild_fact_package
from khepri.rra.packages import (
    FactPackageRecord,
    FactPackageService,
    PackageCorrupted,
    PackageRefused,
)
from khepri.runtime.job_sessions import JobSession
from khepri.runtime.run_quality import PACKAGE_MISMATCH_FAILURE, PackageDoesNotVerify

if TYPE_CHECKING:
    # Deferred to break the import cycle: `comparison_assembly` imports this module
    # to delegate to `derive_operand`/`admit_pair`, so this module cannot import
    # `ComparisonAssemblyPorts` from `comparison_assembly` at runtime. Every use below
    # is a type annotation, resolved as a string under `from __future__ import
    # annotations`, so the deferred import is sufficient.
    from khepri.runtime.comparison_assembly import ComparisonAssemblyPorts

#: Coverage manifests attest calendar ``date`` values, not datetimes. The
#: attested retail day therefore starts at hour 0 of the manifest timezone.
#: Derived from the retained type, not supplied as a comparison default.
_CALENDAR_DAY_HOUR = 0

_PACKAGE_FAULTS = (PermissionError, PackageCorrupted, PackageRefused, PackageDoesNotVerify)


@dataclass(frozen=True, slots=True)
class ComparisonOperand:
    package: FactPackage
    period: DatasetPeriod
    aggregate_scope: str | None
    run_id: str
    #: The manifest's timezone: the retail day boundary every attested day is stated in.
    timezone: str


@dataclass(frozen=True, slots=True)
class OperandLoad:
    operand: ComparisonOperand | None
    incomplete: bool


@dataclass(frozen=True, slots=True)
class _RunPackage:
    run: AnalysisRun
    session: JobSession
    package: FactPackage


@dataclass(frozen=True, slots=True)
class OperandRequest:
    ports: ComparisonAssemblyPorts
    owner_id: str
    run: AnalysisRun
    now: datetime


@dataclass(frozen=True, slots=True)
class _OperandAsk:
    ports: ComparisonAssemblyPorts
    owner_id: str
    run: AnalysisRun
    now: datetime
    bound: _RunPackage


@dataclass(frozen=True, slots=True)
class PairAdmission:
    bundle: object | None
    cause: str | None
    wording: dict[str, str]


def derive_operand(request: OperandRequest) -> OperandLoad:
    """One run's governed operand, or why the pair cannot use it.

    `FR-180`: this is the one derivation that states a comparison operand.
    Completeness stays the `RRA-003` coverage manifest's answer -- `_complete`
    asks `admits_completeness` -- and is never inferred from period bounds.

    Run *selection* is not here. `comparison_assembly` selects the latest
    completed run for a version identifier; `SemanticQueryActions` supplies a
    run it already read under the caller's scope. Both arrive holding a run.
    """
    run = request.run
    if run.package_digest is None:
        return OperandLoad(None, False)
    session = _session_of(request.ports, run.run_id, request.owner_id)
    if session is None:
        return OperandLoad(None, False)
    record = _package_record(request.ports.packages, session.session_id, request.now)
    if record is None:
        return OperandLoad(None, False)
    try:
        package = _verified_package(record)
    except PackageDoesNotVerify:
        return OperandLoad(None, False)
    if package is None:
        return OperandLoad(None, False)
    if run.package_digest != package.digest:
        return OperandLoad(None, False)
    bound = _RunPackage(run=run, session=session, package=package)
    return _operand_from(
        _OperandAsk(
            ports=request.ports,
            owner_id=request.owner_id,
            run=run,
            now=request.now,
            bound=bound,
        )
    )


def _operand_from(ask: _OperandAsk) -> OperandLoad:
    bound = ask.bound
    provenance = ask.ports.provenance.for_run(bound.run.run_id, ask.owner_id)
    if provenance is None:
        return OperandLoad(None, True)
    profile = _profile_record(ask.ports.profiling, bound.session.session_id, ask.now)
    if profile is None:
        return OperandLoad(None, True)
    manifest = _manifest_of(profile)
    if manifest is None:
        return OperandLoad(None, True)
    period = _dataset_period(ask.bound.run.version_id, provenance, manifest)
    operand = ComparisonOperand(
        package=bound.package,
        period=period,
        aggregate_scope=manifest.aggregate_scope,
        run_id=bound.run.run_id,
        timezone=manifest.timezone,
    )
    return OperandLoad(operand, False)


def _manifest_of(profile: DatasetProfileRecord) -> CoverageManifest | None:
    """The stored manifest, or None when the profile carries none or it no longer reads.

    `stored_manifest` is a read that is not re-admitted: bare subscripts and date parsing
    raise on a document whose manifest section has drifted, and `ManifestRefused` is a
    `ValueError`. A corrupted package already loads as `None` here; a corrupted manifest
    gets the same treatment, so the pair refuses as incomplete with its one audit event.
    """
    try:
        return stored_manifest(profile)
    except (KeyError, ValueError):
        return None


def _session_of(ports: ComparisonAssemblyPorts, run_id: str, owner_id: str) -> JobSession | None:
    job_id = ports.reports.job_id_for_run(run_id, owner_id)
    if job_id is None:
        return None
    return ports.jobs.job(job_id, owner_id)


def _package_record(
    packages: FactPackageService, session_id: str, now: datetime
) -> FactPackageRecord | None:
    try:
        return packages.get_session_package(session_id=session_id, now=now)
    except _PACKAGE_FAULTS:
        return None


def _profile_record(
    profiling: ProfilingService, session_id: str, now: datetime
) -> DatasetProfileRecord | None:
    try:
        return profiling.get_session_profile(session_id=session_id, now=now)
    except PermissionError:
        return None


def _verified_package(record: FactPackageRecord) -> FactPackage | None:
    try:
        package = rebuild_fact_package(record.document)
    except (KeyError, TypeError, ValueError):
        return None
    if package.digest != record.package_digest:
        raise PackageDoesNotVerify(PACKAGE_MISMATCH_FAILURE)
    return package


def _dataset_period(
    version_id: str, provenance: RunProvenance, manifest: CoverageManifest
) -> DatasetPeriod:
    start, end = provenance.covered_start, provenance.covered_end
    return DatasetPeriod(
        dataset_version_id=version_id,
        start=start,
        end=end,
        granularity=_granularity(manifest),
        retail_day_start_hour=_CALENDAR_DAY_HOUR,
        complete=_complete(manifest, start, end),
    )


def _granularity(manifest: CoverageManifest) -> str:
    days = [day for _scope, day in manifest.covered_pairs]
    return granularity_for(days)


def _complete(manifest: CoverageManifest, start: date, end: date) -> bool:
    scopes = tuple(sorted(manifest.scopes))
    if not scopes:
        return False
    return all(_scope_complete(manifest, scope, start, end) for scope in scopes)


def _scope_complete(manifest: CoverageManifest, scope: str, start: date, end: date) -> bool:
    query = CompletenessQuery(
        input_digest=manifest.input_digest,
        source_contract_digest=manifest.source_contract_digest,
        scope=scope,
        start=start,
        end=end,
    )
    return admits_completeness(manifest, query)


def _cross_request(
    owner_id: str, subject: ComparisonOperand, baseline: ComparisonOperand
) -> CrossVersionRequest:
    return CrossVersionRequest(
        subject=subject.package,
        baseline=baseline.package,
        subject_organization_scope=owner_id,
        baseline_organization_scope=owner_id,
        subject_period=subject.period,
        baseline_period=baseline.period,
        subject_aggregate_scope=subject.aggregate_scope,
        baseline_aggregate_scope=baseline.aggregate_scope,
    )


def admit_pair(
    owner_id: str, subject: ComparisonOperand, baseline: ComparisonOperand
) -> PairAdmission:
    """The admitted two-population bundle, or the one cause that refused it.

    `FR-180`: every refusal cause stays the one the existing path already
    produces. The retail-day comparison is here rather than in either caller
    because a caller that skipped it would admit a pair the other refuses --
    an incompatibility degrading into another result, which §Invariants bars.
    """
    if subject.run_id == baseline.run_id:
        # `ComparisonActions._shape_refused` refuses a self-pair before assembly and
        # `_admission_cause` does not -- it checks scope and package compatibility,
        # neither of which sees one run named twice. A caller that reached assembly
        # without passing that earlier gate would compare a period against itself and
        # be admitted. The cause is the one the comparison path already produces.
        return PairAdmission(
            None, CAUSE_UNORDERED_PAIR, dict(refusal_wording(CAUSE_UNORDERED_PAIR))
        )
    built = assemble_crossversion(_cross_request(owner_id, subject, baseline))
    if isinstance(built, CrossVersionRefusal):
        return PairAdmission(None, built.cause, dict(built.wording))
    if subject.timezone != baseline.timezone:
        # `RRA-008` §Period rule refuses a pair whose periods differ in retail-day boundary,
        # and the coverage manifest's timezone is that boundary. The frozen period type
        # carries an hour, not a zone, so the family's predicate cannot see this; the
        # comparison is made here, once every frozen predicate has admitted the pair, under
        # the cause the family already froze. Its proper home is the predicate itself, which
        # is an owner amendment recorded in the roadmap row (owner's reading, 2026-09-08).
        return PairAdmission(None, CAUSE_RETAIL_DAY, dict(refusal_wording(CAUSE_RETAIL_DAY)))
    return PairAdmission(built, None, {})
