"""The Methodology Change Notice behind Analysis detail (`W1-08`; `RCA-005` `FR-116`; blueprint
§7.4).

Where a run's governed versions -- mapping, package, formula -- differ from the previous completed
run's, detail says so before the Passport, names each identifier that differs, and states that the
two analyses are not numerically comparable. A *difference*, never a comparison: no figure from
either run is read here, and availability that moved is stated in the report's own quality words
(`RRA-012`), taken from the section outcomes each run retained (`KHEPRI-DEC-033` §3).

Availability alone raises no Notice. A section that refused under one methodology and answered
under the same one is the data's story, not the method's, and saying "methodology changed" over
it would be a claim the record does not make.

Kept beside `shell_analysis.py` rather than in it so the detail module's shape stays what
`W1-06` left, and this notice's rules read in one place.
"""

from __future__ import annotations

from typing import Any

from khepri.rca.workspace.contracts import RUN_COMPLETED
from khepri.rca.workspace.schema import TOMBSTONE_SECTIONS
from khepri.rca.workspace.tombstones import SectionStates
from khepri.rra.rendering.wording import SECTION_HEADINGS
from khepri.runtime.shell_analysis import (
    AvailabilityChange,
    MethodologyChange,
    RunRecord,
    VersionChange,
    group_by_section,
    heading_of,
)

#: The three governed identifiers a Notice compares, each with the copy key that names it.
_GOVERNED = (
    ("notice_mapping", lambda record: record.version.mapping_version),
    ("notice_package", lambda record: record.run.package_version),
    ("notice_formula", lambda record: record.run.formula_version),
)


def previous_completed(run: Any, runs: tuple[Any, ...]) -> Any | None:
    """The run a Notice compares against: the most recent *completed* run started before this
    one, over the same dataset version where one exists, else over any (`FR-116`: "the same or a
    related dataset version" -- the scope's other versions are this organization's data too). A
    started or failed run is not a methodology to compare against."""
    earlier = sorted((r for r in runs if _completed_before(r, run)), key=_order, reverse=True)
    same = [r for r in earlier if r.version_id == run.version_id]
    return next(iter(same or earlier), None)


def methodology_change(
    current: RunRecord,
    previous: RunRecord | None,
    outcomes: tuple[SectionStates | None, SectionStates | None],
    language: str,
) -> MethodologyChange | None:
    """The Notice for `current` against `previous`, or `None` when there is no previous run or
    every governed version is the same."""
    if previous is None:
        return None
    versions = tuple(
        VersionChange(key, read(previous), read(current))
        for key, read in _GOVERNED
        if read(previous) != read(current)
    )
    if not versions:
        return None
    return MethodologyChange(
        previous_run_id=previous.run.run_id,
        versions=versions,
        availability=_availability_changes(outcomes, language),
    )


def _availability_changes(
    outcomes: tuple[SectionStates | None, SectionStates | None], language: str
) -> tuple[AvailabilityChange, ...]:
    """Each section whose quality group differs between the two runs, in the record's order."""
    before, after = outcomes
    if before is None or after is None:
        return ()
    earlier, later = group_by_section(before, language), group_by_section(after, language)
    headings = SECTION_HEADINGS[language]
    return tuple(
        AvailabilityChange(heading_of(headings, s), earlier[s], later[s])
        for s in TOMBSTONE_SECTIONS
        if earlier[s] != later[s]
    )


def _order(run: Any) -> tuple[Any, str]:
    return (run.started_at, run.run_id)


def _completed_before(candidate: Any, run: Any) -> bool:
    return candidate.state == RUN_COMPLETED and _order(candidate) < _order(run)


__all__ = ["methodology_change", "previous_completed"]
