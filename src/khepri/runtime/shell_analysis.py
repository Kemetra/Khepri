"""Analysis detail's view model (`W1-06`; `RCA-005` `FR-118`, `FR-119`; blueprint §7.4, §10).

Shapes one run for the detail template the way `shell_workspace.py` shapes rows: every decision --
which copy key names the state, whether an artifact may be offered, what the Passport leads with and
what stays behind audit detail -- is made here in Python and tested here. The template iterates.

## The Passport's two tiers

`FR-119` puts period, data reference, coverage, timestamp and methodology/version context on the
Passport and keeps digests and machine identifiers behind contextual audit detail, never leading.
`Passport` therefore carries the customer-facing tier only, and `AuditDetail` the digests and
identifiers, so a template cannot reach for a digest from the Passport by mistake -- the value is
not on the object.

## Trust state is the report's own words

The quality groups are `definitions.summarize`'s over the rebuilt bundle (`shell_provenance.py`),
worded through the report's component chrome (`COMPONENT_CHROME`, `RRA-012` FR-095a) and its
section headings (`SECTION_HEADINGS`). This module authors no adjective for a state: the plan's
named risk for the spine was a second trust vocabulary, and the same risk holds one surface down.

## Artifacts

An artifact is offered only for a completed run whose bindings name every required surface --
`_report_key`'s rule, reused -- as a `POST` handoff per kind (`shell_artifact_handoff.py`), never as
a report-API address in a template. `FR-118`: artifacts are reached from here and from nowhere else.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from khepri.rca.workspace.contracts import RUN_STARTED
from khepri.rca.workspace.schema import (
    SECTION_STATE_ANSWERED,
    SECTION_STATE_CAVEATED,
    SECTION_STATE_REFUSED,
    TOMBSTONE_SECTIONS,
)
from khepri.rca.workspace.tombstones import SectionStates, section_codes
from khepri.rra.rendering.wording import COMPONENT_CHROME, SECTION_HEADINGS
from khepri.rra.report_artifacts import REQUIRED_ARTIFACT_KINDS
from khepri.runtime.shell_provenance import Provenance
from khepri.runtime.shell_workspace import (
    RUN_STATE_COPY,
    Moment,
    UnrenderableRecord,
    moment,
    report_key,
    worded,
)

#: How a list of section names reads in each language: the Arabic comma, not the Latin one.
_SEPARATORS = {"en": ", ", "ar": "، "}

#: `KHEPRI-DEC-033` §3's three codes, in the order the groups are presented, each with the
#: report chrome key that words it. No adjective of this shell's.
_GROUP_LABELS = (
    (SECTION_STATE_ANSWERED, "quality_answered"),
    (SECTION_STATE_CAVEATED, "quality_caveated"),
    (SECTION_STATE_REFUSED, "quality_refused"),
)

#: The artifacts detail may hand off, by the kind the address names, in the order they are offered:
#: the report and its evidence to read, then the other formats -- the journey's report step groups
#: them the same way. Each carries its copy key; the report-API target lives in the handoff module.
ARTIFACT_KINDS: tuple[tuple[str, str], ...] = (
    ("web", "artifact_web"),
    ("evidence", "artifact_evidence"),
    ("pdf", "artifact_pdf"),
    ("excel", "artifact_excel"),
)


@dataclass(frozen=True, slots=True)
class TrustGroup:
    """One quality group -- answered, answered with caveats, refused -- and the sections in it,
    both already worded in the report's language."""

    label: str
    sections: tuple[str, ...]
    #: The sections as one run of text, joined in Python with the language's separator, so the
    #: template applies no filter (the `W1-05` scan refuses aggregating filters on templates).
    sections_text: str


@dataclass(frozen=True, slots=True)
class Passport:
    """The customer tier of `FR-119`: what the analysis covered and when it ran. No digest here."""

    covered_start: str
    covered_end: str
    timezone: str
    scope: str | None
    row_count: int
    data_anchor: str
    data_submitted: Moment
    mapping_version: str
    package_version: str | None
    formula_version: str | None


@dataclass(frozen=True, slots=True)
class AuditDetail:
    """The audit tier: identifiers and digests, behind a disclosure and never leading."""

    run_id: str
    version_id: str
    package_digest: str | None
    manifest_digest: str
    upload_digest: str
    artifact_digests: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ArtifactAction:
    kind: str
    label_key: str


@dataclass(frozen=True, slots=True)
class RunRecord:
    """One run as the history read returned it: the run, its version, and its bindings."""

    run: Any
    version: Any
    bindings: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class VersionChange:
    """One governed identifier that differs between the previous run and this one."""

    label_key: str
    earlier: str
    later: str


@dataclass(frozen=True, slots=True)
class AvailabilityChange:
    """One section whose quality group differs between the two runs, in the report's words."""

    section: str
    earlier: str
    later: str


@dataclass(frozen=True, slots=True)
class MethodologyChange:
    """The Methodology Change Notice (`FR-116`, `W1-08`): what differs, and which analysis it
    differs from. A difference and nothing else -- no figure from either run is here to compare."""

    previous_run_id: str
    versions: tuple[VersionChange, ...]
    availability: tuple[AvailabilityChange, ...]


@dataclass(frozen=True, slots=True)
class DetailView:
    """Everything the detail template renders for one run."""

    run_id: str
    state_key: str
    started: Moment
    completed: Moment | None
    passport: Passport | None
    trust: tuple[TrustGroup, ...]
    quality_title: str
    artifacts: tuple[ArtifactAction, ...]
    artifacts_key: str | None
    audit: AuditDetail
    #: `W1-08`: set by the surface once the previous completed run is known; `None` when there is
    #: none, or when every governed version is the same.
    change: MethodologyChange | None = None


def trust_groups(sections: SectionStates | None, language: str) -> tuple[TrustGroup, ...]:
    """The run's retained section outcomes, grouped and worded in the report's own words; empty
    groups are omitted. The codes are `KHEPRI-DEC-033` §3's; the labels are the report component
    chrome's (`RRA-012`) and the section names its headings (`RRA-011`). Nothing is computed.
    """
    if sections is None:
        return ()
    chrome = COMPONENT_CHROME[language]
    headings = SECTION_HEADINGS[language]
    codes = section_codes(sections)
    groups = tuple(
        (label, [s for s in TOMBSTONE_SECTIONS if codes[s] == code])
        for code, label in _GROUP_LABELS
    )
    separator = _SEPARATORS[language]
    return tuple(
        TrustGroup(
            label=chrome[key],
            sections=(named := tuple(heading_of(headings, s) for s in sections)),
            sections_text=separator.join(named),
        )
        for key, sections in groups
        if sections
    )


def group_by_section(sections: SectionStates, language: str) -> dict[str, str]:
    """Each section's quality group label, from the same codes `trust_groups` presents."""
    chrome = COMPONENT_CHROME[language]
    labels = {code: chrome[key] for code, key in _GROUP_LABELS}
    return {section: labels[code] for section, code in section_codes(sections).items()}


def heading_of(headings: dict[str, str], section_id: str) -> str:
    try:
        return headings[section_id]
    except KeyError:
        raise UnrenderableRecord("A section has no governed heading.") from None


def detail_view(
    record: RunRecord,
    provenance: Provenance | None,
    *,
    language: str,
    prefix: str,
) -> DetailView:
    """Shape one run and its version for the detail template. `prefix` is the organization's
    address tail, which the Passport's data reference is built under."""
    run, version = record.run, record.version
    bound = {binding.surface: binding.artifact_digest for binding in record.bindings}
    availability = availability_key(report_key(run, frozenset(bound)), provenance)
    offers = availability == "report_available"
    return DetailView(
        run_id=run.run_id,
        state_key=worded(RUN_STATE_COPY, run.state),
        started=moment(run.started_at),
        completed=None if run.completed_at is None else moment(run.completed_at),
        passport=_passport(version, run, provenance, prefix=prefix),
        trust=trust_groups(None if provenance is None else provenance.sections, language),
        quality_title=COMPONENT_CHROME[language]["quality_summary"],
        artifacts=_artifact_actions(offers),
        artifacts_key=_artifacts_key(run, availability, offers),
        audit=AuditDetail(
            run_id=run.run_id,
            version_id=version.version_id,
            package_digest=run.package_digest,
            manifest_digest=version.manifest_digest,
            upload_digest=version.upload_plaintext_digest,
            artifact_digests=tuple(
                (kind, bound[kind]) for kind in REQUIRED_ARTIFACT_KINDS if kind in bound
            ),
        ),
    )


def _artifact_actions(offers: bool) -> tuple[ArtifactAction, ...]:
    if not offers:
        return ()
    return tuple(ArtifactAction(kind, key) for kind, key in ARTIFACT_KINDS)


def _passport(
    version: Any, run: Any, provenance: Provenance | None, *, prefix: str
) -> Passport | None:
    if provenance is None:
        return None
    return Passport(
        covered_start=provenance.covered_start.isoformat(),
        covered_end=provenance.covered_end.isoformat(),
        timezone=provenance.timezone,
        scope=provenance.aggregate_scope,
        row_count=provenance.row_count,
        data_anchor=f"{prefix}/data#data-{version.version_id}",
        data_submitted=moment(version.created_at),
        mapping_version=version.mapping_version,
        package_version=run.package_version,
        formula_version=run.formula_version,
    )


def availability_key(availability: str, provenance: Provenance | None) -> str:
    """The report's availability as the surfaces state it, on the spine and in detail alike.

    `report_key` reads the bindings; this reads the session behind them. A report is offered only
    while the run's session can still be resumed -- the handoff has nothing to hand off otherwise
    (`W1-07` reconciles artifact retention with the session's horizon) -- so a bound report whose
    session has ended, or whose run retained no provenance, is stated as one that can no longer
    be opened rather than as available (review on `#376` round 2).
    """
    if availability != "report_available":
        return availability
    return "report_available" if _resumable(provenance) else "report_unreachable"


def _resumable(provenance: Provenance | None) -> bool:
    """Whether there is a session to hand the report off from: a record, still reachable."""
    return provenance is not None and provenance.reachable


def _artifacts_key(run: Any, availability: str, offers: bool) -> str | None:
    """Which sentence stands where the artifacts would: none when they are offered."""
    if offers:
        return None
    if run.state == RUN_STARTED or availability == "report_not_yet":
        return "artifacts_not_yet"
    if availability == "report_unreachable":
        return "artifacts_unreachable"
    return "artifacts_none"


__all__ = [
    "ARTIFACT_KINDS",
    "ArtifactAction",
    "AuditDetail",
    "AvailabilityChange",
    "DetailView",
    "MethodologyChange",
    "Passport",
    "RunRecord",
    "VersionChange",
    "TrustGroup",
    "availability_key",
    "detail_view",
    "group_by_section",
    "heading_of",
    "trust_groups",
]
