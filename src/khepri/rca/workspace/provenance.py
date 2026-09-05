"""The provenance record a completed run retains (`W1-06`; `RCA-005` `FR-119`; `KHEPRI-DEC-033` §2).

`KHEPRI-DEC-033`'s matrix gives the **provenance record** its own row: "with the run; the tombstone
keeps its digests". The raw upload and the analysis session's content end on their own horizons --
the upload seven days after sealing, the session's content on `content_expires_at` -- while the run
lives with the organization. So what the Analysis Passport states must be written *at completion*,
from the admission and the package the run binds, into a row that lives with the run; read back
later through session-gated services it would vanish on a timer the decision says it outlives.
Review on `#376` found the surface reading it that way.

The record carries the Passport's customer tier -- the attested period and its day boundary, the
coverage scope, who attested, the admitted row count -- and one governed state code per report
section, `KHEPRI-DEC-033` §3's vocabulary (`answered`, `caveated`, `refused`), which is also what
the run's tombstone keeps. No figure, no digest: the digests are on the run and the version.

Written once, never rewritten (`_refuse_any_update`), deleted only with its run (`W1-07`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from khepri.rca.workspace.schema import (
    FAMILY_SECTIONS,
    TOMBSTONE_SECTIONS,
    RunProvenanceRow,
)
from khepri.rca.workspace.tombstones import SectionStates
from khepri.rca.workspace.unit_of_work import reading, writing


@dataclass(frozen=True, slots=True)
class RunProvenance:
    """What one completed run retains for its Passport and its trust state."""

    run_id: str
    owner_id: str
    covered_start: date
    covered_end: date
    timezone: str
    aggregate_scope: str | None
    attested_by: str
    row_count: int
    sections: SectionStates
    #: The `RRA-008` family version each family ran under, by section (`FAMILY_SECTIONS`), as the
    #: build that ran stamped it. Empty for a run completed before `20260905_0025`, which retained
    #: none: absence is "not recorded" and is never read as a version that changed (`FR-116`).
    family_versions: Mapping[str, str] = field(default_factory=dict)


class SqlRunProvenanceStore:
    """The provenance record, written once at completion and read by scope."""

    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory

    def record(self, provenance: RunProvenance, *, now: datetime) -> RunProvenance:
        """Retain one run's provenance. Joins the completion's unit of work, so the run cannot be
        `completed` without its Passport or carry a Passport without being completed."""
        with writing(self._factory) as database:
            database.add(
                RunProvenanceRow(
                    run_id=provenance.run_id,
                    owner_id=provenance.owner_id,
                    covered_start=provenance.covered_start,
                    covered_end=provenance.covered_end,
                    timezone=provenance.timezone,
                    aggregate_scope=provenance.aggregate_scope,
                    attested_by=provenance.attested_by,
                    row_count=provenance.row_count,
                    recorded_at=now,
                    **{
                        f"section_{section}": getattr(provenance.sections, section)
                        for section in TOMBSTONE_SECTIONS
                    },
                    **{
                        f"family_{section}_version": provenance.family_versions.get(section)
                        for section in FAMILY_SECTIONS
                    },
                )
            )
        return provenance

    def for_run(self, run_id: str, owner_id: str) -> RunProvenance | None:
        """The run's provenance, within one scope; `None` for a run not yet completed."""
        with reading(self._factory) as database:
            row = database.scalar(
                select(RunProvenanceRow).where(
                    RunProvenanceRow.run_id == run_id, RunProvenanceRow.owner_id == owner_id
                )
            )
        return None if row is None else _provenance_from_row(row)

    def for_scope(self, owner_id: str) -> tuple[RunProvenance, ...]:
        """Every retained record in one scope, in one read -- what a surface listing the scope's
        runs asks for, so its cost does not grow with the runs it lists (review on `#376`)."""
        with reading(self._factory) as database:
            rows = database.scalars(
                select(RunProvenanceRow)
                .where(RunProvenanceRow.owner_id == owner_id)
                .order_by(RunProvenanceRow.run_id)
            )
            return tuple(_provenance_from_row(row) for row in rows)


def _provenance_from_row(row: RunProvenanceRow) -> RunProvenance:
    return RunProvenance(
        run_id=row.run_id,
        owner_id=row.owner_id,
        covered_start=row.covered_start,
        covered_end=row.covered_end,
        timezone=row.timezone,
        aggregate_scope=row.aggregate_scope,
        attested_by=row.attested_by,
        row_count=row.row_count,
        sections=SectionStates(
            **{section: getattr(row, f"section_{section}") for section in TOMBSTONE_SECTIONS}
        ),
        # `W1-08`'s family versions, read here rather than in `for_run` alone: both read paths go
        # through this helper, and a scope-level read that dropped them would leave the Notice
        # comparing nothing on every surface that lists runs (`FR-116`). Absent for a run
        # completed before `20260905_0025`, which is "not recorded", never a version that changed.
        family_versions={
            section: version
            for section in FAMILY_SECTIONS
            if (version := getattr(row, f"family_{section}_version")) is not None
        },
    )


__all__ = ["RunProvenance", "SqlRunProvenanceStore"]
