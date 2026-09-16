"""The composition that lets a semantic view reach a real projection (`RCA-007`).

`RCA-006` orchestrates and `RRA-014` projects, and until this module existed the
two could not meet: `SemanticQueryActions` loads `AnalysisRun` rows and `project`
admits a `RenderableBundle`, so every composed request refused for an
incompatible source shape. `SV1-08` measured that rather than assuming it. This
module is the bridge, and `src/khepri/runtime/` is where it belongs --
`workspace_recording.py` records that `R7-01` §3 forbids either package importing
the other, so the composition layer is "the one place that may know" both.

**What this module does not do.** It performs no arithmetic, selects no metric,
drops no caveat and invents no evidence. It turns a scoped run into the bundle
that run's package already describes and hands it to `RRA-014`, whose refusal,
empty outcome or projection comes back unchanged.

**What it deliberately does do, named rather than hidden.** `ReportBundle.of`
runs `RRA-004`'s derivation -- `KHEPRI-DEC-032` measured it calling
`family.derive` and `concentration.curve_series`. Every other caller of that
constructor publishes no figure, and a semantic view does. `RCA-007` put that
question to the owner with its counter-argument stated, and merging it was the
ruling: determinism is protected by checks rather than by avoidance. The two
checks are here and both fail closed -- the digest (`FR-153`) and the versions
the run recorded at delivery (`FR-157`).

`FR-157` calls those a triple; the run records a pair. `AnalysisRun` carries
`package_version` and `formula_version` and no mapping version, so there is
nothing on the run to compare a third against -- and nothing needs to be. The
run names its package *by digest*, `FactPackageRecord.verify` refuses a record
whose mapping version disagrees with its document, and the digest hashes that
document: a package with a different mapping version has a different digest and
no run reaches it. `test_the_mapping_version_is_bound_by_the_digest_not_by_a_comparison`
asserts that rather than leaving it as a claim in prose.

**Every miss is the same miss.** `FR-151` and `RCA-006` `FR-146` require an
absent package, a cross-scope one, a run that never derived one and a document
that no longer matches its digest to be indistinguishable. They are: each
returns `None`, and `SemanticQueryActions` turns that into the one content-free
unavailable outcome it builds in one place. Nothing here reports which condition
held, and nothing here logs that one did.

**Scope comes from the run, and that is not a shortcut.** `SemanticQueryActions`
loaded each run through `get_analysis_run(source_id, owner_id)`, so a run in hand
is already evidence of the scope it was read under. Reading its package under
`run.owner_id` therefore cannot cross an organization, and the alternative --
widening `RRA-014`'s protocol to carry a scope -- would edit the seam `RCA-007`
excludes touching.

**`RCA-009` `FR-172`-`FR-176`: the one composition branch.** `PeriodComparisonView`
is the sole published definition whose `accepted_source_shape` is
`SHAPE_TWO_POPULATION`, and this adapter is its one successor branch over the
`RCA-007` default above. `_is_two_population` selects it from the published
definition's own declared shape, never from the view's name or id, so a
future definition change routes correctly with no edit here. Every other view
falls through to the unmodified single-population path unchanged. The branch
derives one comparison operand per source through the `FR-180` shared seam,
admits the ordered pair through the same seam, and hands the admitted bundle to
the existing projection -- it performs no arithmetic, aggregation, ordering
inference, or refusal derivation of its own. A refused pair returns `None`
rather than a `ViewRefusal`: the comparison causes are `RRA-008`'s own and carry
no `RRA-014` wording, so naming one here would publish a refusal with no
governed text in either language. `FR-175` admits exactly this reading -- "the
existing governed refusal or unavailable outcome".
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from khepri.rra.bundle import ReportBundle
from khepri.rra.package_source import rebuild_fact_package
from khepri.rra.packages import FactPackageRecord, PackageCorrupted
from khepri.rra.semantic_views import projection
from khepri.rra.semantic_views.contracts import SHAPE_TWO_POPULATION, SemanticViewDefinition
from khepri.rra.semantic_views.registry import UnknownView, define_view
from khepri.runtime.comparison_operands import (
    ComparisonOperand,
    OperandRequest,
    admit_pair,
    derive_operand,
)

if TYPE_CHECKING:
    from khepri.runtime.comparison_assembly import ComparisonAssemblyPorts

__all__ = ["OwnedPackageReader", "SemanticViewAdapter"]


class OwnedPackageReader(Protocol):
    """The one read this composition may perform (`RCA-007` §Scope)."""

    def get_owned_package(
        self, package_digest: str, owner_id: str
    ) -> FactPackageRecord | None:
        """One published package by digest under that organization's scope."""
        ...


class SemanticViewAdapter:
    """`RRA-014`'s projection over `RCA-006`'s organization-scoped runs."""

    def __init__(
        self,
        packages: OwnedPackageReader,
        *,
        operands: ComparisonAssemblyPorts | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """Hold the package read, and optionally the `RCA-009` comparison collaborators.

        `operands` and `now` are both optional and both default to `None` so an
        unwired deployment fails closed (`_compare` returns `None`) rather than
        crashing at construction. Only `PeriodComparisonView` requests reach
        `_compare`; every other view is unaffected by either being absent.
        """
        self._packages = packages
        self._operands = operands
        self._now = now

    def project(
        self, request: object, sources: tuple[object, ...]
    ) -> projection.ViewOutcome | None:
        """The view this request names over these runs, or the uniform miss.

        `None` means unavailable and says nothing more, which is `FR-146`'s
        requirement rather than an omission. The projection's own refusals --
        an unknown view, an unadmitted metric, an incompatible shape -- are
        `RRA-014`'s and come back as outcomes, not as `None`.
        """
        if self._is_two_population(request):
            return self._compare(request, sources)
        bundles = self._bundles(sources)
        if bundles is None:
            return None
        return projection.project(request, bundles)  # type: ignore[arg-type]

    def _is_two_population(self, request: object) -> bool:
        """`FR-172` -- the published definition's own declared shape, never the view's name.

        A string compare against the view id would keep routing this view here
        if its published shape ever changed, which is the opposite of what
        `FR-172` asks. The equality is exact -- `SHAPE_TWO_POPULATION` only,
        not `SHAPE_EITHER_BUNDLE` -- because `MetricAvailabilityView` and
        `ReportEvidenceView` both declare `SHAPE_EITHER_BUNDLE` today and both
        project over exactly one source through the unmodified path; routing
        either into this branch would fail their existing one-source requests
        under `_compare`'s `len(sources) != 2` guard, breaking `FR-172`'s own
        "every other view continues through `RCA-007` unchanged".

        An unpublished view resolves to `None` and falls through to the
        existing single-population path, where `validate` refuses it under the
        cause it already owns -- this branch invents no refusal (`FR-174`).
        """
        definition = _definition_of(request)
        return definition is not None and definition.accepted_source_shape == SHAPE_TWO_POPULATION

    def _compare(
        self, request: object, sources: tuple[object, ...]
    ) -> projection.ViewOutcome | None:
        """`FR-173`-`FR-176` -- the ordered pair, assembled by the governed path.

        Every miss is the same miss. An unwired deployment, a run whose operand
        cannot be derived, a cross-scope pair, wrong arity, and a pair the
        governed path refuses all return `None`, which `SemanticQueryActions`
        maps to the one content-free unavailable outcome (`ports.py`: "`None`
        is part of the contract, not an escape from it"). Nothing here reports
        which condition held.

        A refused pair cannot come back as a `ViewRefusal`: the comparison
        causes are `RRA-008`'s and carry no `RRA-014` wording, so naming one
        would publish a refusal with no governed text in either language
        (`FR-177`). `FR-175` admits exactly this -- "the existing governed
        refusal *or unavailable outcome*".
        """
        if self._operands is None or self._now is None:
            return None
        if len(sources) != 2:
            return None
        pair = self._operands_for(sources)
        if pair is None:
            return None
        owner_id, subject, baseline = pair
        admission = admit_pair(owner_id, subject, baseline)
        if admission.bundle is None:
            return None
        return projection.project(request, (admission.bundle,))  # type: ignore[arg-type]

    def _operands_for(
        self, sources: tuple[object, ...]
    ) -> tuple[str, ComparisonOperand, ComparisonOperand] | None:
        """One operand per run, or `None` if either cannot be derived.

        All-or-nothing, matching `_bundles` and `SemanticQueryActions._scoped_sources`:
        a partial pair would let a two-population view project over one
        population.

        The scope equality check is not redundant. Each run is read under the
        caller's own scope, but nothing before this point has compared the two
        runs' scopes to each other -- `FR-173` requires each source be loaded
        through the *same* requesting organization's opaque scope, and two runs
        from different scopes reaching here would otherwise be compared as
        though they shared one.
        """
        assert self._operands is not None and self._now is not None  # narrowed by `_compare`
        derived: list[tuple[str, ComparisonOperand]] = []
        for source in sources:
            owner_id = getattr(source, "owner_id", None)
            if not isinstance(owner_id, str) or not owner_id:
                return None
            load = derive_operand(
                OperandRequest(
                    ports=self._operands, owner_id=owner_id, run=source, now=self._now()  # type: ignore[arg-type]
                )
            )
            if load.operand is None:
                return None
            derived.append((owner_id, load.operand))
        (subject_owner, subject), (baseline_owner, baseline) = derived
        if subject_owner != baseline_owner:
            return None
        return subject_owner, subject, baseline

    def _bundles(self, sources: tuple[object, ...]) -> tuple[object, ...] | None:
        """Every run's bundle, or `None` if any one of them cannot be built.

        All-or-nothing, matching `SemanticQueryActions._scoped_sources`: a
        partial tuple would let a two-population view project over one
        population and present that as the answer.
        """
        built: list[object] = []
        for source in sources:
            bundle = self._bundle_of(source)
            if bundle is None:
                return None
            built.append(bundle)
        return tuple(built)

    def _bundle_of(self, source: object) -> object | None:
        """One run's governed bundle, or `None` if any check refuses it.

        The read is inside the `try` and not beside it. `_package_from_row`
        calls `FactPackageRecord.verify`, so a stored row that no longer matches
        its digest raises *there*, before this module sees a record at all --
        and an exception escaping here would reach the caller as a broken read
        instead of `FR-146`'s content-free miss, which is a fail-open dressed as
        an error. Found by `test_a_document_that_drifted_from_its_digest_is_unavailable`
        rather than reasoned about in advance.
        """
        run = _as_run(source)
        if run is None:
            return None
        try:
            return self._vouched_bundle(run)
        except PackageCorrupted:
            return None

    def _vouched_bundle(self, run: _Run) -> object | None:
        """The bundle for `run`, once its package answers for itself."""
        record = self._packages.get_owned_package(run.package_digest, run.owner_id)
        if record is None or not _versions_agree(run, record):
            return None
        return _rebuilt_bundle(record)


def _definition_of(request: object) -> SemanticViewDefinition | None:
    """The published definition this request names, or `None`.

    `define_view` raises `UnknownView` rather than returning `None`, and a raise
    escaping here would reach the caller as a broken read instead of `FR-146`'s
    content-free miss -- a fail-open dressed as an error.
    """
    view_id = getattr(request, "view_id", None)
    if not isinstance(view_id, str):
        return None
    try:
        return define_view(view_id)
    except UnknownView:
        return None


class _Run(Protocol):
    """What this module reads from a source, and nothing more."""

    owner_id: str
    package_digest: str | None
    package_version: str | None
    formula_version: str | None


def _as_run(source: object) -> _Run | None:
    """`source` if it is a completed run this module can read, else `None`.

    A run that never completed carries no `package_digest`, and an object that
    is not a run at all carries none of these members. Both answer the uniform
    miss rather than raising, because `FR-146` admits one outcome here.
    """
    members = ("owner_id", "package_digest", "package_version", "formula_version")
    if any(not hasattr(source, member) for member in members):
        return None
    digest = source.package_digest  # type: ignore[attr-defined]
    return None if not isinstance(digest, str) or not digest else source  # type: ignore[return-value]


def _versions_agree(run: _Run, record: FactPackageRecord) -> bool:
    """`FR-157`: the run's recorded versions still name the stored package's.

    The pair the run records, not the triple `FR-157` names -- see the module
    docstring for why the mapping version needs no comparison here.

    A triple that moved after delivery stops the path. Without this a view could
    publish figures under semantics no delivered surface ever ran, which is the
    failure the determinism reading of `RRA-011`:204 names and the one
    `RCA-007`'s merged position undertakes to check rather than assume away.
    """
    return (run.package_version, run.formula_version) == (
        record.package_version,
        record.formula_version,
    )


def _rebuilt_bundle(record: FactPackageRecord) -> object | None:
    """The bundle this record's package describes, or `None` if it cannot vouch.

    `FR-153`, and it is a second check rather than a repeat of the record's own.
    `FactPackageRecord.verify` hashes the *stored document*; this compares the
    digest of the *rebuilt package*, which `package_source.py` explains proves
    the further thing -- that "nothing was lost or invented in rebuilding it".
    A `PackageCorrupted` from either is the caller's to turn into the uniform
    miss.
    """
    package = rebuild_fact_package(record.document)
    if package.digest != record.package_digest:
        return None
    return ReportBundle.of(package)
