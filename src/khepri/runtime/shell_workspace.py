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
contract identifiers, and `DatasetVersion` does not appear on screen. A `DataRow` carries none of
those fields, so the template cannot render what it was never given; contextual audit detail is
`W1-06`'s.

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
from khepri.runtime.workspace import ADMISSION_ADMITTED

#: The copy key for each operational state a run can hold. A mapping rather than string
#: concatenation so a state the copy does not name fails here, at the row, and not as a
#: `StrictUndefined` inside the template.
RUN_STATE_COPY = {
    RUN_STARTED: "run_state_started",
    RUN_COMPLETED: "run_state_completed",
    RUN_FAILED: "run_state_failed",
}

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

    Every field is a copy key or a value the customer submitted. Nothing here is a digest, a
    mapping version or an identifier.
    """

    submitted: Moment
    media_type: str
    admission_key: str
    readiness_key: str
    retention_key: str
    uses: tuple[WorkRow, ...]


@dataclass(frozen=True, slots=True)
class OverviewView:
    """What Overview shows: the latest work, the latest data, and what needs attention."""

    latest_work: WorkRow | None
    latest_data: DataRow | None
    attention: tuple[WorkRow, ...]


def moment(instant: datetime) -> Moment:
    """A stored instant, stated in UTC. A naive value is read as UTC, which is what the store
    writes; it is not guessed to be local."""
    aware = instant if instant.tzinfo is not None else instant.replace(tzinfo=UTC)
    utc = aware.astimezone(UTC)
    return Moment(at=utc.isoformat(), text=utc.strftime(_MOMENT_TEXT))


def work_row(run: Any) -> WorkRow:
    return WorkRow(state_key=RUN_STATE_COPY[run.state], started=moment(run.started_at))


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


def data_row(version: Any, runs: Iterable[Any]) -> DataRow:
    """One version's row. `runs` is the whole scope; the ones that used this version are kept, in
    the order the reader returned them, and they decide the row's readiness with the record."""
    uses = tuple(work_row(run) for run in runs if run.version_id == version.version_id)
    return DataRow(
        submitted=moment(version.created_at),
        media_type=str(version.upload_media_type),
        admission_key=(
            "data_admitted"
            if version.admission_outcome == ADMISSION_ADMITTED
            else "data_not_admitted"
        ),
        readiness_key=_readiness(version, uses),
        retention_key="retention_kept",
        uses=uses,
    )


def data_rows(versions: Iterable[Any], runs: Iterable[Any]) -> tuple[DataRow, ...]:
    """Every version in the scope as a row, in the reader's order."""
    scope_runs = tuple(runs)
    return tuple(data_row(version, scope_runs) for version in versions)


def overview_view(versions: Iterable[Any], runs: Iterable[Any]) -> OverviewView:
    """The first run and the first version the reader returned, and every failed run.

    "Needs attention" is a failed run and nothing else in this slice: it is the one retained state
    a customer can act on (`FR-114`, run again). Blueprint §7.1 says the section is rendered only
    when non-empty, so an empty tuple is what the template tests for.
    """
    first_versions = tuple(versions)
    scope_runs = tuple(runs)
    return OverviewView(
        latest_work=work_row(scope_runs[0]) if scope_runs else None,
        latest_data=data_row(first_versions[0], scope_runs) if first_versions else None,
        attention=tuple(work_row(run) for run in scope_runs if run.state == RUN_FAILED),
    )


__all__ = [
    "RUN_STATE_COPY",
    "DataRow",
    "Moment",
    "OverviewView",
    "WorkRow",
    "data_rows",
    "moment",
    "overview_view",
]
