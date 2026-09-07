"""Fail closed on a two-population bundle that is not the shape RRA-006 admits.

RRA-006 §Two-population bundle is a sibling of ``ReportBundle``, not a section
inside one. These predicates keep that shape: one omitted narrative, one
chart-less section, both operands beside every delta, and RRA-008 §Composite
provenance on every evidence record. RCA-005 §Comparison retention by name is
why the checks raise rather than persist a partial bundle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from khepri.rra.analysis.comparison_package import COMPARISON_CROSSVERSION_VERSION
from khepri.rra.bundle import (
    NARRATIVE_OMITTED,
    SECTION_CROSSVERSION,
    SECTION_PRESENT,
    CitedEvidence,
    CitedFigure,
    StatedCaveat,
)
from khepri.rra.crossversion_bundle import (
    CROSSVERSION_ADMITTED_CAVEAT,
    CROSSVERSION_BUNDLE_VERSION,
    CROSSVERSION_FIGURE_LABELS,
    LABEL_BASELINE,
    LABEL_DIFFERENCE,
    LABEL_PERCENTAGE_DIFFERENCE,
    LABEL_SUBJECT,
)
from khepri.rra.narrative import NARRATIVE_VERSION, REQUIRED_LANGUAGES

if TYPE_CHECKING:
    from khepri.rra.bundle import ChartSpec
    from khepri.rra.crossversion_bundle import (
        CrossVersionBundle,
        CrossVersionCitationProvenance,
        CrossVersionIdentity,
        CrossVersionPackageIdentity,
        CrossVersionRefusal,
        CrossVersionSection,
    )

__all__ = [
    "require_bundle",
    "require_identity",
    "require_package_identity",
    "require_refusal",
    "require_section",
]


def require_package_identity(identity: CrossVersionPackageIdentity) -> None:
    """Every operand identity field RRA-006 §Identity names must be present."""
    require_present(identity.dataset_version_id)
    require_present(identity.package_digest)
    require_present(identity.profile_digest)
    require_present(identity.source_sha256_hex)
    require_present(identity.coverage_manifest_identity)


def require_present(value: str) -> None:
    if value:
        return
    raise ValueError("cross-version package identity is incomplete")


def require_identity(identity: CrossVersionIdentity) -> None:
    """The ordered pair and the versions that name one two-population bundle."""
    require_distinct_operands(identity.subject, identity.baseline)
    require_comparison_formula(identity.comparison_formula_version)
    require_narrative_version(identity.narrative_version)
    require_identity_bundle_version(identity.bundle_version)
    require_citations(identity.citations)


def require_distinct_operands(
    subject: CrossVersionPackageIdentity,
    baseline: CrossVersionPackageIdentity,
) -> None:
    if subject != baseline:
        return
    raise ValueError("cross-version identity requires an ordered pair")


def require_comparison_formula(version: str) -> None:
    if version == COMPARISON_CROSSVERSION_VERSION:
        return
    raise ValueError("cross-version identity has the wrong formula version")


def require_narrative_version(version: str) -> None:
    if version == NARRATIVE_VERSION:
        return
    raise ValueError("cross-version identity has the wrong narrative version")


def require_identity_bundle_version(version: str) -> None:
    if version == CROSSVERSION_BUNDLE_VERSION:
        return
    raise ValueError("cross-version identity has the wrong bundle version")


def require_citations(citations: tuple[CrossVersionCitationProvenance, ...]) -> None:
    if citations:
        return
    raise ValueError("cross-version identity has no composite provenance")


def require_section(section: CrossVersionSection) -> None:
    """The sibling's one present, deliberately chart-less section."""
    require_section_id(section.section_id)
    require_section_state(section.state)
    require_section_reason_absent(section.reason)
    require_section_chartless(section.chart)
    require_section_populated(section.figure_ids)
    require_distinct_figure_ids(section.figure_ids)


def require_section_id(section_id: str) -> None:
    if section_id == SECTION_CROSSVERSION:
        return
    raise ValueError("cross-version section identity or state changed")


def require_section_state(state: str) -> None:
    if state == SECTION_PRESENT:
        return
    raise ValueError("cross-version section identity or state changed")


def require_section_reason_absent(reason: str | None) -> None:
    if reason is None:
        return
    raise ValueError("cross-version section must be populated and chart-less")


def require_section_chartless(chart: ChartSpec | None) -> None:
    if chart is None:
        return
    raise ValueError("cross-version section must be populated and chart-less")


def require_section_populated(figure_ids: tuple[str, ...]) -> None:
    if figure_ids:
        return
    raise ValueError("cross-version section must be populated and chart-less")


def require_distinct_figure_ids(figure_ids: tuple[str, ...]) -> None:
    if len(set(figure_ids)) == len(figure_ids):
        return
    raise ValueError("cross-version section repeats a figure")


def require_refusal(refusal: CrossVersionRefusal) -> None:
    """A refused pair delivers wording and no bundle."""
    require_refusal_languages(refusal.wording)
    require_refusal_figures_absent(refusal.figures)
    require_refusal_bundle_absent(refusal.bundle)


def require_refusal_languages(wording: dict[str, str]) -> None:
    if set(wording) == set(REQUIRED_LANGUAGES):
        return
    raise ValueError("cross-version refusal must cover every language")


def require_refusal_figures_absent(figures: tuple[CitedFigure, ...]) -> None:
    if not figures:
        return
    raise ValueError("cross-version refusal carries content")


def require_refusal_bundle_absent(bundle: CrossVersionBundle | None) -> None:
    if bundle is None:
        return
    raise ValueError("cross-version refusal carries content")


def require_bundle(bundle: CrossVersionBundle) -> None:
    """Everything the three surfaces may present for one admitted pair."""
    require_delta_operands(bundle.figures)
    require_omitted_narrative_state(bundle.narrative_state)
    require_absent_narrative(bundle.narrative)
    require_one_section(bundle.sections)
    require_section_indexes_figures(bundle.sections, bundle.figures)
    require_figures_in_section(bundle.figures)
    require_known_labels(bundle.figures)
    require_admitted_caveat(bundle.caveats)
    require_evidence(bundle)


def require_omitted_narrative_state(state: str) -> None:
    if state == NARRATIVE_OMITTED:
        return
    raise ValueError("cross-version narrative must be omitted")


def require_absent_narrative(narrative: object) -> None:
    if narrative is None:
        return
    raise ValueError("cross-version narrative must be omitted")


def require_one_section(sections: tuple[CrossVersionSection, ...]) -> None:
    if len(sections) == 1:
        return
    raise ValueError("cross-version bundle must carry exactly one section")


def require_section_indexes_figures(
    sections: tuple[CrossVersionSection, ...],
    figures: tuple[CitedFigure, ...],
) -> None:
    indexed = sections[0].figure_ids
    expected = tuple(figure.figure_id for figure in figures)
    if indexed == expected:
        return
    raise ValueError("cross-version section and figures disagree")


def require_figures_in_section(figures: tuple[CitedFigure, ...]) -> None:
    for figure in figures:
        require_figure_in_section(figure)


def require_figure_in_section(figure: CitedFigure) -> None:
    if figure.section == SECTION_CROSSVERSION:
        return
    raise ValueError("cross-version figure is outside its section")


def require_known_labels(figures: tuple[CitedFigure, ...]) -> None:
    for figure in figures:
        require_known_label(figure)


def require_known_label(figure: CitedFigure) -> None:
    if figure.label in CROSSVERSION_FIGURE_LABELS:
        return
    raise ValueError("cross-version figure has an unknown operand role")


def require_admitted_caveat(caveats: tuple[StatedCaveat, ...]) -> None:
    expected = (StatedCaveat(CROSSVERSION_ADMITTED_CAVEAT, SECTION_CROSSVERSION),)
    if caveats == expected:
        return
    raise ValueError("cross-version bundle must state its admitted-pair caveat")


def require_delta_operands(figures: tuple[CitedFigure, ...]) -> None:
    grouped: dict[tuple[str, str], set[str | None]] = {}
    for figure in figures:
        grouped.setdefault((figure.fact_id, figure.metric), set()).add(figure.label)
    for labels in grouped.values():
        require_delta_has_operands(labels)


def require_delta_has_operands(labels: set[str | None]) -> None:
    has_delta = bool(labels & {LABEL_DIFFERENCE, LABEL_PERCENTAGE_DIFFERENCE})
    if not has_delta:
        return
    if {LABEL_SUBJECT, LABEL_BASELINE} <= labels:
        return
    raise ValueError("cross-version delta has no complete operands")


def require_evidence(bundle: CrossVersionBundle) -> None:
    require_evidence_matches_figures(bundle.figures, bundle.evidence)
    require_evidence_matches_identity(bundle.evidence, bundle.identity.citations)
    require_evidence_records(bundle.evidence)


def require_evidence_matches_figures(
    figures: tuple[CitedFigure, ...],
    evidence: tuple[CitedEvidence, ...],
) -> None:
    figure_ids = {figure.citation_id for figure in figures}
    evidence_ids = {record.citation_id for record in evidence}
    if figure_ids == evidence_ids:
        return
    raise ValueError("cross-version citations and evidence disagree")


def require_evidence_matches_identity(
    evidence: tuple[CitedEvidence, ...],
    citations: tuple[CrossVersionCitationProvenance, ...],
) -> None:
    evidence_ids = {record.citation_id for record in evidence}
    provenance_ids = {entry.citation_id for entry in citations}
    if evidence_ids == provenance_ids:
        return
    raise ValueError("cross-version citations and evidence disagree")


def require_evidence_records(evidence: tuple[CitedEvidence, ...]) -> None:
    for record in evidence:
        require_evidence_formula(record)
        require_evidence_precision_absent(record)
        require_evidence_inputs_absent(record)
        require_evidence_provenance(record)


def require_evidence_formula(record: CitedEvidence) -> None:
    if record.formula_version == COMPARISON_CROSSVERSION_VERSION:
        return
    raise ValueError("cross-version evidence has the wrong formula version")


def require_evidence_precision_absent(record: CitedEvidence) -> None:
    if record.precision is None:
        return
    raise ValueError("cross-version evidence must use the derived-record convention")


def require_evidence_inputs_absent(record: CitedEvidence) -> None:
    if record.inputs is None:
        return
    raise ValueError("cross-version evidence must use the derived-record convention")


def require_evidence_provenance(record: CitedEvidence) -> None:
    if record.provenance is not None:
        return
    raise ValueError("cross-version evidence is missing composite provenance")
