"""The tombstone allowlist (`W1-03`; `RCA-005` `FR-112`, `KHEPRI-DEC-033` §3).

What survives a deletion, as a type. `KHEPRI-DEC-033` §3 defines a tombstone "by what it **may**
contain, never by what was removed", and gives each subject its allowlist: for a dataset version,
the opaque identifiers, the instants, the upload's digests, size and media type, the manifest
*digest*, the mapping version and the admission outcome *code*; for an analysis run, the
identifiers, the instants, the package digest, the package and formula versions, and one state code
per report section. Nothing else. The live profile document holds sanitized customer column headers
and min/max values, and the coverage manifest holds free text -- none of it may outlive the
customer's withdrawal of the content it describes.

**Built by construction.** `VersionTombstone.project` and `RunTombstone.project` name every field
they copy. Neither reads the live record's field list, so a field added to `DatasetVersion` or
`AnalysisRun` later does not arrive here by default -- it has to be named, and naming it fails
`test_w103_tombstone_projection.py`'s equality until the same commit says §3 permits it. The plan
(`G3-04`) names the alternative as this slice's one risk: `del d["filename"]`, a tombstone built by
removing fields, carries every field nobody thought to remove.

**Sealed, like the records they are projected from.** A tombstone persists and is read back by the
history spine (`FR-117`: "the row remains so history does not silently shorten"), so it follows
`records.py`'s two-door rule: `project` is its creation door and `_from_storage` its reconstruction
door, and `dataclasses.replace` cannot widen one after the fact.

**The section vocabulary is translated, not copied.** The report bundle publishes `present` or
`refused` for each section (`rra/bundle.py`); §3 admits `answered`, `caveated` or `refused`.
`present` says a surface drew the section, which is a rendering outcome; a retention record keeps
the *analysis* outcome, and `present` with a caveat scoped to the section is `caveated`.
`SectionStates.from_rendering` is that translation. The bundle's constants are restated here rather
than imported because `R7-01` §3 forbids `khepri.rca` importing `khepri.rra`; the drift test in
`test_w103_tombstone_projection.py` asserts the restatement from the one module that may import
both.

**Where section states come from.** The live `AnalysisRun` record carries none -- `RCA-005`'s
domain table puts "quality (answered, caveated or refused per section)" on the run, and neither
`W1-01`'s contract nor `W1-02`'s table holds it yet -- and the store cannot read the bundle. So the
caller that deletes supplies them per run, and a run for which none are supplied is projected with
each section `None`: §3 says *may* contain, and a `started` or `failed` run has no sections at all.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime

from khepri.rca.records import Sealed, register_sealed, through_door
from khepri.rca.workspace.contracts import (
    AdmittedSource,
    AnalysisRun,
    DatasetVersion,
    RunSubject,
    VersionLifecycle,
)
from khepri.rca.workspace.schema import (
    SECTION_STATE_ANSWERED,
    SECTION_STATE_CAVEATED,
    SECTION_STATE_CODES,
    SECTION_STATE_REFUSED,
    TOMBSTONE_SECTIONS,
)

# The report bundle's per-section vocabulary, restated (see the module docstring). A surface
# either drew a section or disclosed why it could not; nothing else is published.
RENDERED_PRESENT = "present"
RENDERED_REFUSED = "refused"
RENDERED_STATES = (RENDERED_PRESENT, RENDERED_REFUSED)

# Content-free, per the refusal discipline in `rca/errors.py`: each names the constraint and never
# the rejected value, so a refusal cannot echo a caller's input into a log.
SECTION_STATE_FAILURE = "Section state is not one of the states KHEPRI-DEC-033 section 3 names."
RENDERED_STATE_FAILURE = "Rendered section state is not one the report bundle publishes."
SECTIONS_FAILURE = "Section states must name every report section, and no other."


def _retention_code(rendered: str, caveated: bool) -> str:
    """One section's rendering outcome, as the retention outcome it means.

    `refused` wins over a caveat: a section that was not drawn was not answered with a caveat,
    it was not answered. Fail-closed on a code outside the rendering vocabulary rather than
    passing it through -- `answered` arriving *here* means a caller skipped the translation and is
    presenting a retention code as if the bundle had published it.
    """
    if rendered not in RENDERED_STATES:
        raise ValueError(RENDERED_STATE_FAILURE)
    if rendered == RENDERED_REFUSED:
        return SECTION_STATE_REFUSED
    return SECTION_STATE_CAVEATED if caveated else SECTION_STATE_ANSWERED


@dataclass(frozen=True, slots=True)
class SectionStates:
    """One governed state code per report section, as one value.

    One field per section rather than a mapping, so the *set* of sections is a property of the
    type -- a section that is not a field is unrepresentable, which is the same shape `W1-02` gave
    the five columns. The field set is asserted equal to `TOMBSTONE_SECTIONS` in
    `test_w103_tombstone_projection.py`, so the validation loop below cannot skip a field it does
    not name.

    Unsealed, because it is an argument to a door and not a record that survives one -- the same
    reasoning as `AdmittedSource`. Validating in `__post_init__` is what `Sealed` forbids its
    subclasses, and is exactly what this type is for.
    """

    overview: str
    comparison: str
    concentration: str
    growth: str
    basket: str

    def __post_init__(self) -> None:
        for section in TOMBSTONE_SECTIONS:
            if getattr(self, section) not in SECTION_STATE_CODES:
                raise ValueError(SECTION_STATE_FAILURE)

    @classmethod
    def from_rendering(
        cls, rendered: Mapping[str, str], caveated: Collection[str] = ()
    ) -> SectionStates:
        """Translate what the bundle published about each section into what §3 may keep.

        `rendered` maps every report section to `present` or `refused`; `caveated` names the
        sections a section-scoped caveat qualifies. Every section is required and no other is
        admitted: a report that says nothing about a section has not answered it, and this
        projection does not invent an answer for it.
        """
        if set(rendered) != set(TOMBSTONE_SECTIONS):
            raise ValueError(SECTIONS_FAILURE)

        def code(section: str) -> str:
            return _retention_code(rendered[section], section in caveated)

        return cls(
            overview=code("overview"),
            comparison=code("comparison"),
            concentration=code("concentration"),
            growth=code("growth"),
            basket=code("basket"),
        )


def section_codes(sections: SectionStates | None) -> dict[str, str | None]:
    """Each section's code, or `None` for each when a run has no sections to record."""
    if sections is None:
        return dict.fromkeys(TOMBSTONE_SECTIONS)
    return {section: getattr(sections, section) for section in TOMBSTONE_SECTIONS}


@dataclass(frozen=True, slots=True)
class VersionSubject:
    """Which version, in which scope -- the pair a version tombstone is keyed by.

    The counterpart of `RunSubject`, for the same reason: pairing the identifier with its scope at
    the type keeps `_from_storage` within the argument threshold without letting a caller hand a
    tombstone another scope's identifier one argument at a time.
    """

    version_id: str
    owner_id: str


@register_sealed
@dataclass(frozen=True, slots=True)
class VersionTombstone(Sealed):
    """What survives a dataset version's deletion: `KHEPRI-DEC-033` §3's first row, exactly.

    The field set equals `VERSION_TOMBSTONE_COLUMNS` plus the scope and the deletion instant, and
    `test_w103_tombstone_projection.py` asserts that as an equality. A `DatasetVersion` today
    carries nothing §3 excludes -- `W1-01` kept the profile document and manifest text off the
    record -- so this type has the same content fields; the point of a separate type is that the
    next field added to `DatasetVersion` does not become a tombstone field by default.
    """

    version_id: str
    owner_id: str
    deleted_at: datetime
    created_at: datetime
    sealed_at: datetime | None
    upload_plaintext_digest: str
    upload_ciphertext_digest: str
    upload_size_bytes: int
    upload_media_type: str
    manifest_digest: str
    mapping_version: str
    admission_outcome: str

    @staticmethod
    def _build(
        subject: VersionSubject,
        source: AdmittedSource,
        lifecycle: VersionLifecycle,
        deleted_at: datetime,
    ) -> VersionTombstone:
        """The constructor call both doors share. See `DatasetVersion._build`."""
        return VersionTombstone(
            version_id=subject.version_id,
            owner_id=subject.owner_id,
            deleted_at=deleted_at,
            created_at=lifecycle.created_at,
            sealed_at=lifecycle.sealed_at,
            upload_plaintext_digest=source.plaintext_digest,
            upload_ciphertext_digest=source.ciphertext_digest,
            upload_size_bytes=source.size_bytes,
            upload_media_type=source.media_type,
            manifest_digest=source.manifest_digest,
            mapping_version=source.mapping_version,
            admission_outcome=source.admission_outcome,
        )

    @classmethod
    def project(cls, version: DatasetVersion, *, deleted_at: datetime) -> VersionTombstone:
        """The creation door: the version's allowlisted fields, named one by one, and the instant
        it ended. Reads nothing about the live record but the fields §3 names."""
        subject = VersionSubject(version_id=version.version_id, owner_id=version.owner_id)
        source = AdmittedSource(
            plaintext_digest=version.upload_plaintext_digest,
            ciphertext_digest=version.upload_ciphertext_digest,
            size_bytes=version.upload_size_bytes,
            media_type=version.upload_media_type,
            manifest_digest=version.manifest_digest,
            mapping_version=version.mapping_version,
            admission_outcome=version.admission_outcome,
        )
        lifecycle = VersionLifecycle(created_at=version.created_at, sealed_at=version.sealed_at)
        with through_door():
            return cls._build(subject, source, lifecycle, deleted_at)

    @classmethod
    def _from_storage(
        cls,
        *,
        subject: VersionSubject,
        source: AdmittedSource,
        lifecycle: VersionLifecycle,
        deleted_at: datetime,
    ) -> VersionTombstone:
        with through_door():
            return cls._build(subject, source, lifecycle, deleted_at)


@dataclass(frozen=True, slots=True)
class RunTrace:
    """What §3 lets a run's tombstone keep of its execution, as one value.

    The instants and `FR-111`'s provenance -- and not the operational `state`, which is the live
    record's and stays there. Grouped for the reason `RunOutcome` is, and distinct from it because
    `RunOutcome` requires a state and a tombstone has none to give it.
    """

    started_at: datetime
    completed_at: datetime | None
    package_digest: str | None
    package_version: str | None
    formula_version: str | None


@register_sealed
@dataclass(frozen=True, slots=True)
class RunTombstone(Sealed):
    """What survives an analysis run's deletion: `KHEPRI-DEC-033` §3's second row, exactly.

    The field set equals `RUN_TOMBSTONE_COLUMNS` plus the run's identity and the deletion instant.
    `state` is the first field this projection drops rather than copies: §3 keeps "started,
    completed and deleted instants", not the state machine. The five section fields are flat
    rather than nested so the equality against the column allowlist is literal.
    """

    run_id: str
    version_id: str
    owner_id: str
    deleted_at: datetime
    started_at: datetime
    completed_at: datetime | None
    package_digest: str | None
    package_version: str | None
    formula_version: str | None
    section_overview: str | None
    section_comparison: str | None
    section_concentration: str | None
    section_growth: str | None
    section_basket: str | None

    @staticmethod
    def _build(
        subject: RunSubject,
        trace: RunTrace,
        codes: Mapping[str, str | None],
        deleted_at: datetime,
    ) -> RunTombstone:
        """The constructor call both doors share. `codes` is keyed by report section."""
        return RunTombstone(
            run_id=subject.run_id,
            version_id=subject.version_id,
            owner_id=subject.owner_id,
            deleted_at=deleted_at,
            started_at=trace.started_at,
            completed_at=trace.completed_at,
            package_digest=trace.package_digest,
            package_version=trace.package_version,
            formula_version=trace.formula_version,
            section_overview=codes["overview"],
            section_comparison=codes["comparison"],
            section_concentration=codes["concentration"],
            section_growth=codes["growth"],
            section_basket=codes["basket"],
        )

    @classmethod
    def project(
        cls, run: AnalysisRun, *, sections: SectionStates | None, deleted_at: datetime
    ) -> RunTombstone:
        """The creation door. `sections` is keyword-only and has no default, so a caller states
        that it has none rather than forgetting them."""
        subject = RunSubject(run_id=run.run_id, owner_id=run.owner_id, version_id=run.version_id)
        trace = RunTrace(
            started_at=run.started_at,
            completed_at=run.completed_at,
            package_digest=run.package_digest,
            package_version=run.package_version,
            formula_version=run.formula_version,
        )
        with through_door():
            return cls._build(subject, trace, section_codes(sections), deleted_at)

    @classmethod
    def _from_storage(
        cls,
        *,
        subject: RunSubject,
        trace: RunTrace,
        codes: Mapping[str, str | None],
        deleted_at: datetime,
    ) -> RunTombstone:
        with through_door():
            return cls._build(subject, trace, codes, deleted_at)
