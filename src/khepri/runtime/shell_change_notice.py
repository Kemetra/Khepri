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
from khepri.rca.workspace.schema import FAMILY_SECTIONS, TOMBSTONE_SECTIONS
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
    records: tuple[Any | None, Any | None],
    language: str,
) -> MethodologyChange | None:
    """The Notice for `current` against `previous`, or `None` when there is no previous run,
    when `current` has not completed (it has no methodology yet to differ), or when every governed
    version is the same.

    `records` is each run's retained provenance, earlier then later, or `None` where a run
    retained none. Two things are read from it: the `RRA-008` family versions and the section
    outcomes availability is stated from.
    """
    if previous is None or current.run.state != RUN_COMPLETED:
        return None
    earlier_record, later_record = records
    versions = tuple(
        VersionChange(key, read(previous), read(current))
        for key, read in _GOVERNED
        if read(previous) != read(current)
    ) + _family_changes(earlier_record, later_record)
    if not versions:
        return None
    return MethodologyChange(
        previous_run_id=previous.run.run_id,
        versions=versions,
        availability=_availability_changes(
            (
                None if earlier_record is None else earlier_record.sections,
                None if later_record is None else later_record.sections,
            ),
            language,
        ),
    )


def _family_changes(earlier: Any | None, later: Any | None) -> tuple[VersionChange, ...]:
    """Each `RRA-008` family whose version differs between the two runs (`FR-116`).

    **Only where both runs recorded one.** A run completed before `20260905_0025` retained no
    family version, and a missing one is "not recorded", never "a version that changed": comparing
    absence against a real identifier would render a Notice naming `None` as the earlier version
    and claim the two analyses are not numerically comparable, over a run whose methodology may
    not have moved at all. That is the same defect as comparing a run that has not completed, one
    identifier down (review on `#377`).

    Read from `FAMILY_SECTIONS` rather than a list written here, so a fifth family is compared
    without editing this function.
    """
    if earlier is None or later is None:
        return ()
    before, after = earlier.family_versions, later.family_versions
    return tuple(
        VersionChange(f"notice_family_{section}", before[section], after[section])
        for section in FAMILY_SECTIONS
        if section in before and section in after and before[section] != after[section]
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
