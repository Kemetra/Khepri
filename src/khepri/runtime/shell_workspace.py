"""The rows Overview and the Data surface render (`W1-05`; `RCA-005` `FR-120`, `FR-122`).

**Python shapes the rows; the templates iterate.** The `G3-04` plan's acceptance for this slice is
"a scan proves no template computes, rounds or sums", and `test_no_shell_template_computes` reads
every expression in every shell template for arithmetic and the aggregating filters. So every
decision about what a row says is made here, where it can be tested against the record it came
from: which copy key names a run's state, whether a data version is in use, which runs used which
data. A template that received bare records would have had to decide those things itself.

**No figure is produced here either.** `FR-120` forbids a KPI, chart or business figure on
Overview, and the plan names the risk that a count of retained rows is presented as one. Nothing
in this module counts. Overview receives the first run, the first data version, the failed runs
one by one, and nothing that says how many of anything there are. `test_overview_carries_no_figure`
asserts the rendered text carries no digit outside its `<time>` elements.

**The reader's order is kept.** `SqlWorkspaceRecordStore` returns each scope newest first
(`FR-117`), so "latest" is the first record returned and no sort happens here or in the template
-- one definition of the order, in the store, with the tie-break it chose.

**Customer vocabulary.** Blueprint §7.2: rows do not lead with mapping versions, digests or
contract identifiers, and `DatasetVersion` does not appear on screen. A `DataRow` carries an
opaque identifier only as its non-visible HTML anchor, so an Analysis can identify the exact Data
row it used without exposing that identifier as copy; contextual audit detail is `W1-06`'s.

**Retention reads as a word.** A version or run this module receives is one the store still holds
as active -- `dataset_versions_for_scope` and `analysis_runs_for_scope` filter on
`RETENTION_ACTIVE` -- so every row says *kept*, and says nothing about expiry:
`KHEPRI-DEC-033` §5 forbids any surface claiming content expires automatically until `W1-07`
ships the sweep. Tombstone rows are the Analyses spine's (`FR-117`) and arrive with it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from khepri.rca.workspace.contracts import RUN_COMPLETED, RUN_FAILED, RUN_STARTED
from khepri.rca.workspace.tombstones import RunTombstone, VersionTombstone
from khepri.rra.report_artifacts import REQUIRED_ARTIFACT_KINDS
from khepri.runtime.workspace import ADMISSION_ADMITTED


class UnrenderableRecord(ValueError):
    """A retained row carries a code this surface has no governed word for.

    `RRA-012` `FR-094`'s rule, applied to the shell: a code without a rendering fails closed rather
    than reaching the reader as the code string, a blank, or -- the case review on `#373` found --
    a plausible neighbouring word. The dispatcher turns it into the uniform unavailable surface.
    The message names the constraint and never the value, per `rca/errors.py`'s discipline.
    """


UNRENDERABLE_FAILURE = "a retained row carries a code this surface cannot word"

#: The copy key for each operational state a run can hold. A mapping rather than string
#: concatenation so a state the copy does not name fails here, at the row, and not as a
#: `StrictUndefined` inside the template.
RUN_STATE_COPY = {
    RUN_STARTED: "run_state_started",
    RUN_COMPLETED: "run_state_completed",
    RUN_FAILED: "run_state_failed",
}

#: The copy key for each admission outcome a version can carry. One entry, because `W1-04` refuses
#: an inadmissible source before a version exists, so the only outcome a row can hold is the one
#: that admitted it. The column accepts any string; this mapping is what makes a typo, a corrupt
#: value or a future code a refusal rather than a fabricated "Not admitted" (review on `#373`).
ADMISSION_COPY = {ADMISSION_ADMITTED: "data_admitted"}

#: How a timestamp reads. One format for both languages, in UTC and marked as such, because the
#: product has no user time-zone setting and a localized date is a decision `RRA-012`'s wording
#: layer owns for the report; the shell states the instant and lets `<time datetime>` carry it.
_MOMENT_TEXT = "%Y-%m-%d %H:%M UTC"


@dataclass(frozen=True, slots=True)
class Moment:
    """An instant as a template renders it: machine-readable `at`, visible `text`."""

    at: str
    text: str


@dataclass(frozen=True, slots=True)
class WorkRow:
    """One analysis run as a row: what state it is in and when it started."""

    state_key: str
    started: Moment


@dataclass(frozen=True, slots=True)
class DataRow:
    """One data version as a row, with the runs that used it beneath it.

    Every visible field is a copy key or a value the customer submitted. The opaque anchor is
    routing metadata and never rendered as customer-visible text.
    """

    anchor: str
    submitted: Moment
    media_type: str
    admission_key: str
    readiness_key: str
    retention_key: str
    uses: tuple[WorkRow, ...]


@dataclass(frozen=True, slots=True)
class DataReference:
    """Which data entry a run used, as a row states it (`FR-117`).

    `anchor` is the entry's place on the Data surface -- the row's `id` there -- so two entries
    submitted at the same instant are still two references, and a reader can follow one to the
    entry itself. It is the opaque version identifier, carried in an `href` and never as text
    (§7.2). `deleted` is set when the entry itself has been deleted: its submission instant is
    still stated from the tombstone, and there is nothing to follow (review on `#374`).
    """

    submitted: Moment
    anchor: str | None
    deleted: bool


@dataclass(frozen=True, slots=True)
class SpineRow:
    """One entry on the Analyses history spine (`FR-117`): a live run or a run's tombstone.

    `deleted` is what makes it a tombstone; a tombstone carries no state and no report word,
    because blueprint §7.3 makes it minimal and `FR-122` makes it read as a tombstone. Nothing
    here is a digest or a section code; the version identifier travels only inside `data`'s
    anchor.
    """

    started: Moment
    data: DataReference | None
    state_key: str | None
    report_key: str | None
    retention_key: str
    deleted: Moment | None


@dataclass(frozen=True, slots=True)
class OverviewView:
    """What Overview shows: the latest work, what is still running, the latest data, and what
    needs attention.

    `processing` is every run still in its started state, not only the newest run: blueprint §7.1
    asks Overview to answer "is anything processing", and a run that started before a newer one
    finished would otherwise vanish from the surface while it was still running (review on
    `#373`). Rendered only when non-empty, like attention.
    """

    latest_work: WorkRow | None
    processing: tuple[WorkRow, ...]
    latest_data: DataRow | None
    attention: tuple[WorkRow, ...]


def moment(instant: datetime) -> Moment:
    """A stored instant, stated in UTC. A naive value is read as UTC, which is what the store
    writes; it is not guessed to be local."""
    aware = instant if instant.tzinfo is not None else instant.replace(tzinfo=UTC)
    utc = aware.astimezone(UTC)
    return Moment(at=utc.isoformat(), text=utc.strftime(_MOMENT_TEXT))


def _worded(table: dict[str, str], code: str) -> str:
    """A copy key for a governed code, or the refusal `UnrenderableRecord`."""
    try:
        return table[code]
    except KeyError:
        raise UnrenderableRecord(UNRENDERABLE_FAILURE) from None


def work_row(run: Any) -> WorkRow:
    return WorkRow(state_key=_worded(RUN_STATE_COPY, run.state), started=moment(run.started_at))


def _uses_by_version(runs: Iterable[Any]) -> dict[str, tuple[WorkRow, ...]]:
    """Every run as a row, grouped under its version in one pass, in the reader's order."""
    grouped: dict[str, list[WorkRow]] = {}
    for run in runs:
        grouped.setdefault(run.version_id, []).append(work_row(run))
    return {version_id: tuple(rows) for version_id, rows in grouped.items()}


def _readiness(version: Any, uses: tuple[WorkRow, ...]) -> str:
    """What has happened to this data, from the record and the runs together.

    Sealing happens on the first *completion* (`record_completion`), so a version whose only run
    started or failed is unsealed while a run of it is listed right beneath -- and "awaiting its
    first analysis" over a row that says "Processing" is the contradiction review on `#373` found.
    Three words, then: used (sealed), analysis started (unsealed, runs), awaiting (nothing yet).
    """
    if version.sealed_at is not None:
        return "data_in_use"
    return "data_analysis_started" if uses else "data_awaiting"


def data_row(version: Any, uses: tuple[WorkRow, ...]) -> DataRow:
    """One version's row, with the runs that used it -- already matched to it by `version_id` --
    beneath it. They decide the row's readiness together with the record."""
    return DataRow(
        anchor=str(version.version_id),
        submitted=moment(version.created_at),
        media_type=str(version.upload_media_type),
        admission_key=_worded(ADMISSION_COPY, version.admission_outcome),
        readiness_key=_readiness(version, uses),
        retention_key="retention_kept",
        uses=uses,
    )


def data_rows(versions: Iterable[Any], runs: Iterable[Any]) -> tuple[DataRow, ...]:
    """Every version in the scope as a row, in the reader's order.

    The runs are grouped under their versions once, so a long history costs one pass over the
    runs and one over the versions rather than one over the runs *per* version (review on `#373`).
    """
    uses = _uses_by_version(runs)
    return tuple(data_row(version, uses.get(version.version_id, ())) for version in versions)


def overview_view(versions: Iterable[Any], runs: Iterable[Any]) -> OverviewView:
    """The first run and the first version the reader returned, and every failed run.

    "Needs attention" is a failed run and nothing else in this slice: it is the one retained state
    a customer can act on (`FR-114`, run again). Blueprint §7.1 says the section is rendered only
    when non-empty, so an empty tuple is what the template tests for.
    """
    first_versions = tuple(versions)
    scope_runs = tuple(runs)
    latest_data = None
    if first_versions:
        first = first_versions[0]
        latest_data = data_row(
            first, tuple(work_row(run) for run in scope_runs if run.version_id == first.version_id)
        )
    return OverviewView(
        latest_work=work_row(scope_runs[0]) if scope_runs else None,
        processing=tuple(work_row(run) for run in scope_runs if run.state == RUN_STARTED),
        latest_data=latest_data,
        attention=tuple(work_row(run) for run in scope_runs if run.state == RUN_FAILED),
    )


def _report_key(run: Any, bound_surfaces: frozenset[str]) -> str:
    """Whether the run's report can be offered, from the bindings rather than from the state.

    `FR-111` makes completion imply every required artifact is bound, so a completed run with a
    partial set is a corrupt record the whole surface must refuse, not a completed row with an
    unavailable report. A run still running has no report *yet*; one that failed has none to offer.
    """
    if run.state == RUN_STARTED:
        return "report_not_yet"
    if run.state == RUN_COMPLETED:
        if set(REQUIRED_ARTIFACT_KINDS) <= bound_surfaces:
            return "report_available"
        raise UnrenderableRecord(UNRENDERABLE_FAILURE)
    return "report_unavailable"


def _data_references(
    versions: Iterable[Any], tombstones: Iterable[Any]
) -> dict[str, DataReference]:
    """Every data entry a row may refer to: live versions by anchor, deleted ones by their
    tombstone's instant. A version deleted between two reads appears in both and the tombstone
    wins, the same way a run's does."""
    references = {
        version.version_id: DataReference(
            submitted=moment(version.created_at), anchor=str(version.version_id), deleted=False
        )
        for version in versions
    }
    for tombstone in tombstones:
        if isinstance(tombstone, VersionTombstone):
            references[tombstone.version_id] = DataReference(
                submitted=moment(tombstone.created_at), anchor=None, deleted=True
            )
    return references


def spine_rows(
    runs: Iterable[Any],
    tombstones: Iterable[Any],
    versions: Iterable[Any],
    bindings: Iterable[Any],
) -> tuple[SpineRow, ...]:
    """The spine: live runs and run tombstones, newest start first (`FR-117`, blueprint §7.3).

    The store returns runs newest first and tombstones oldest deletion first; the two are merged
    here by the instant each run started, so the history reads in the order it happened and a
    deletion's own instant is stated on the row rather than used to place it. This is the one
    ordering decision made outside the store, and it is a merge of two ordered reads, not a
    filter: every run and every *run* tombstone the reader returned is a row. The store's
    tombstone read returns both kinds; a version tombstone is the Data surface's story and arrives
    there with `W1-07`, so it is set aside here by type rather than by a field it lacks.
    """
    scope_tombstones = tuple(tombstones)
    references = _data_references(versions, scope_tombstones)
    bound: dict[str, set[str]] = {}
    for binding in bindings:
        bound.setdefault(binding.run_id, set()).add(binding.surface)
    gone = {
        tombstone.run_id: SpineRow(
            started=moment(tombstone.started_at),
            data=references.get(tombstone.version_id),
            state_key=None,
            report_key=None,
            retention_key="retention_deleted",
            deleted=moment(tombstone.deleted_at),
        )
        for tombstone in scope_tombstones
        if isinstance(tombstone, RunTombstone)
    }
    # A run both live and tombstoned is one deleted between two reads of the same history; the
    # deletion is the later fact and the row reads as a tombstone (`FR-127`, review on `#374`).
    live = [
        SpineRow(
            started=moment(run.started_at),
            data=references.get(run.version_id),
            state_key=_worded(RUN_STATE_COPY, run.state),
            report_key=_report_key(run, frozenset(bound.get(run.run_id, ()))),
            retention_key="retention_kept",
            deleted=None,
        )
        for run in runs
        if run.run_id not in gone
    ]
    return tuple(sorted(live + list(gone.values()), key=lambda row: row.started.at, reverse=True))


__all__ = [
    "ADMISSION_COPY",
    "RUN_STATE_COPY",
    "UnrenderableRecord",
    "DataReference",
    "DataRow",
    "Moment",
    "OverviewView",
    "SpineRow",
    "WorkRow",
    "data_rows",
    "moment",
    "overview_view",
    "spine_rows",
]
