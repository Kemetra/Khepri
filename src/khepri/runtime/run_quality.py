"""A completed run's per-section quality, as the retention vocabulary records it (`W1-06`).

The bundle is rebuilt from the stored package exactly as the catalog's package-scoped routes rebuild
it (`report_api._session_bundle`), which `KHEPRI-DEC-032` reads as admissible because it publishes
no figure. This module publishes none either: it asks the bundle which sections answered, which
carried a caveat and which refused (`definitions.summarize`) and states each as one of
`KHEPRI-DEC-033` §3's three codes -- the same translation `W1-03` makes when a run is tombstoned,
made once here at completion so the live run and its tombstone say the same thing.

Kept apart from `workspace_recording.py` on purpose: that module's source is scanned for admission
and derivation internals it must not import, and the rebuild is a *read* of a published package,
not a derivation. Here the read has one caller and one docstring saying what it is.
"""

from __future__ import annotations

from khepri.rca.workspace.schema import (
    SECTION_STATE_ANSWERED,
    SECTION_STATE_CAVEATED,
    SECTION_STATE_REFUSED,
    TOMBSTONE_SECTIONS,
)
from khepri.rca.workspace.tombstones import SectionStates
from khepri.rra.bundle import ReportBundle
from khepri.rra.definitions import summarize
from khepri.rra.package_source import rebuild_fact_package
from khepri.rra.packages import FactPackageRecord

PACKAGE_MISMATCH_FAILURE = "The stored fact package does not match its own digest."
SECTIONS_MISMATCH_FAILURE = "The report bundle does not name every governed section exactly once."


class PackageDoesNotVerify(ValueError):
    """The stored document rebuilds to a package other than the one its digest names."""


def section_states_of(record: FactPackageRecord) -> SectionStates:
    """Each governed section's outcome for the package this record holds."""
    package = rebuild_fact_package(record.document)
    if package.digest != record.package_digest:
        raise PackageDoesNotVerify(PACKAGE_MISMATCH_FAILURE)
    summary = summarize(ReportBundle.of(package))
    caveated = set(summary.caveated_sections)
    codes = {
        s: SECTION_STATE_CAVEATED if s in caveated else SECTION_STATE_ANSWERED
        for s in summary.answered_sections
    }
    codes.update({s: SECTION_STATE_REFUSED for s, _reason in summary.refusals})
    if set(codes) != set(TOMBSTONE_SECTIONS):
        raise PackageDoesNotVerify(SECTIONS_MISMATCH_FAILURE)
    return SectionStates(**codes)


__all__ = ["PackageDoesNotVerify", "section_states_of"]
