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
checks are here and both fail closed -- the digest (`FR-153`) and the version
triple the run recorded at delivery (`FR-157`).

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
"""

from __future__ import annotations

from typing import Protocol

from khepri.rra.bundle import ReportBundle
from khepri.rra.package_source import rebuild_fact_package
from khepri.rra.packages import FactPackageRecord, PackageCorrupted
from khepri.rra.semantic_views import projection

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

    def __init__(self, packages: OwnedPackageReader) -> None:
        """Hold the one package read; the adapter owns no other collaborator."""
        self._packages = packages

    def project(
        self, request: object, sources: tuple[object, ...]
    ) -> projection.ViewOutcome | None:
        """The view this request names over these runs, or the uniform miss.

        `None` means unavailable and says nothing more, which is `FR-146`'s
        requirement rather than an omission. The projection's own refusals --
        an unknown view, an unadmitted metric, an incompatible shape -- are
        `RRA-014`'s and come back as outcomes, not as `None`.
        """
        bundles = self._bundles(sources)
        if bundles is None:
            return None
        return projection.project(request, bundles)  # type: ignore[arg-type]

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
