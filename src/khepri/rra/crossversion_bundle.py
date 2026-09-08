"""Present one admitted RRA-006 two-population bundle without retaining it.

RRA-006 §Two-population bundle makes this a sibling of ``ReportBundle``;
RRA-008 §Composite provenance and §Operand order bind both source versions in
caller-stated order; RCA-005 §Comparison retention by name keeps the result a
read-time value with no store, persistence path, or retained content class.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from khepri.rra.analysis.comparison_package import OPERAND_ORDER, PairProvenance
from khepri.rra.analysis.dataset_period import DatasetPeriod
from khepri.rra.bundle import (
    NARRATIVE_OMITTED,
    SECTION_CROSSVERSION,
    SECTION_PRESENT,
    ChartSpec,
    CitedEvidence,
    CitedFigure,
    StatedCaveat,
)
from khepri.rra.facts import FactPackage
from khepri.rra.narrative import REQUIRED_LANGUAGES
from khepri.rra.profiling import canonical_json

__all__ = [
    "CAVEAT_CROSSVERSION_ADMITTED_PAIR",
    "CROSSVERSION_BUNDLE_VERSION",
    "CROSSVERSION_FIGURE_LABELS",
    "LABEL_BASELINE",
    "LABEL_DIFFERENCE",
    "LABEL_PERCENTAGE_DIFFERENCE",
    "LABEL_SUBJECT",
    "SECTION_CROSSVERSION",
    "CrossVersionBundle",
    "CrossVersionCitationProvenance",
    "CrossVersionIdentity",
    "CrossVersionPackageIdentity",
    "CrossVersionRefusal",
    "CrossVersionRequest",
    "CrossVersionSection",
    "build_crossversion_bundle",
]

CROSSVERSION_BUNDLE_VERSION = "rra006.crossversion.bundle.v1"
LABEL_SUBJECT = "subject"
LABEL_BASELINE = "baseline"
LABEL_DIFFERENCE = "difference"
LABEL_PERCENTAGE_DIFFERENCE = "percentage_difference"
CROSSVERSION_FIGURE_LABELS = frozenset(
    {
        LABEL_SUBJECT,
        LABEL_BASELINE,
        LABEL_DIFFERENCE,
        LABEL_PERCENTAGE_DIFFERENCE,
    }
)
CAVEAT_CROSSVERSION_ADMITTED_PAIR = "crossversion_admitted_pair"


@dataclass(frozen=True, slots=True)
class CrossVersionRequest:
    """The caller-stated ordered pair and the two asserted organization scopes."""

    subject: FactPackage
    baseline: FactPackage
    subject_organization_scope: str
    baseline_organization_scope: str
    subject_period: DatasetPeriod
    baseline_period: DatasetPeriod


@dataclass(frozen=True, slots=True)
class CrossVersionPackageIdentity:
    """One operand's package identity, source digest, and coverage identity."""

    dataset_version_id: str
    package_digest: str
    profile_digest: str
    source_sha256_hex: str
    coverage_manifest_identity: str
    coverage_signatures: tuple[str, ...]

    def __post_init__(self) -> None:
        from khepri.rra.crossversion_rules import require_package_identity

        require_package_identity(self)

    def as_document(self) -> dict[str, object]:
        return {
            "dataset_version_id": self.dataset_version_id,
            "package_digest": self.package_digest,
            "profile_digest": self.profile_digest,
            "source_sha256_hex": self.source_sha256_hex,
            "coverage_manifest_identity": self.coverage_manifest_identity,
            "coverage_signatures": list(self.coverage_signatures),
        }

    def flat_document(self, role: str) -> dict[str, str]:
        """One governed value per key, prefixed by the operand's role.

        The HTML provenance table and the workbook provenance sheet serialize an
        identity document value by value with `str()`, so a nested document reaches
        a reader as a Python repr. Review of `#408` found exactly that; every value
        here is a single version, digest or identifier, and the signature identities
        are joined rather than listed.
        """
        return {
            f"{role}.dataset_version_id": self.dataset_version_id,
            f"{role}.package_digest": self.package_digest,
            f"{role}.profile_digest": self.profile_digest,
            f"{role}.source_sha256_hex": self.source_sha256_hex,
            f"{role}.coverage_manifest_identity": self.coverage_manifest_identity,
            f"{role}.coverage_signatures": ",".join(self.coverage_signatures),
        }


@dataclass(frozen=True, slots=True)
class CrossVersionCitationProvenance:
    """One citation's composite pair provenance, as RRA-006 §Identity records it."""

    citation_id: str
    metric: str
    pair: PairProvenance

    def as_document(self) -> dict[str, object]:
        return {
            "citation_id": self.citation_id,
            "metric": self.metric,
            **self.pair.as_document(),
        }

    def provenance_pairs(self) -> tuple[tuple[str, str], ...]:
        """The pair as the ordered `(key, value)` pairs an evidence record carries.

        One derivation, used by assembly to fill `CitedEvidence.provenance` and by
        the rules to check it, so the two cannot drift.
        """
        document = dict(self.pair.as_document())
        document["operand_order"] = ",".join(document["operand_order"])
        return tuple((key, str(value)) for key, value in document.items())


@dataclass(frozen=True, slots=True)
class CrossVersionIdentity:
    """The ordered pair and shared versions naming one two-population bundle."""

    subject: CrossVersionPackageIdentity
    baseline: CrossVersionPackageIdentity
    package_version: str
    package_formula_version: str
    mapping_version: str
    comparison_formula_version: str
    narrative_version: str
    citations: tuple[CrossVersionCitationProvenance, ...]
    bundle_version: str = CROSSVERSION_BUNDLE_VERSION

    def __post_init__(self) -> None:
        from khepri.rra.crossversion_rules import require_identity

        require_identity(self)

    @property
    def pair_provenance(self) -> tuple[PairProvenance, ...]:
        return tuple(entry.pair for entry in self.citations)

    @property
    def coverage_manifest_identity(self) -> str:
        """A digest of the ordered pair of manifest identities.

        The shared bundle Protocol has one slot for a manifest identity and this
        bundle has two. A digest is what belongs in that slot -- the evidence drawer
        prints it where a report bundle prints its manifest digest -- and both
        underlying identities remain readable, unhashed, in `as_document()`.
        """
        pair = canonical_json(
            [self.subject.coverage_manifest_identity, self.baseline.coverage_manifest_identity]
        )
        return hashlib.sha256(pair.encode()).hexdigest()

    @property
    def coverage_signatures(self) -> tuple[str, ...]:
        return (*self.subject.coverage_signatures, *self.baseline.coverage_signatures)

    @property
    def citations_digest(self) -> str:
        """sha256 over every citation's document, in citation order."""
        serialized = canonical_json([entry.as_document() for entry in self.citations])
        return hashlib.sha256(serialized.encode()).hexdigest()

    def as_document(self) -> dict[str, object]:
        """Flat: one governed version, digest or identifier per key.

        The citations enter as one digest rather than as rows. Review of `#408`
        showed why they must enter at all: a cited retained basis is not a function
        of anything else this document carries, so a bundle whose basis provenance
        was swapped in lockstep with its evidence kept its content address. With the
        digest, any change to any citation renames the bundle, while the provenance
        table still shows one governed value per row.
        """
        return {
            "bundle_version": self.bundle_version,
            "operand_order": ",".join(OPERAND_ORDER),
            "citations_digest": self.citations_digest,
            **self.subject.flat_document(OPERAND_ORDER[0]),
            **self.baseline.flat_document(OPERAND_ORDER[1]),
            "package_version": self.package_version,
            "package_formula_version": self.package_formula_version,
            "mapping_version": self.mapping_version,
            "comparison_formula_version": self.comparison_formula_version,
            "narrative_version": self.narrative_version,
        }


@dataclass(frozen=True, slots=True)
class CrossVersionSection:
    """The sibling's one present, deliberately chart-less section."""

    figure_ids: tuple[str, ...]
    section_id: str = SECTION_CROSSVERSION
    state: str = SECTION_PRESENT
    reason: None = None
    chart: ChartSpec | None = None

    def __post_init__(self) -> None:
        from khepri.rra.crossversion_rules import require_section

        require_section(self)

    def as_document(self) -> dict[str, object]:
        return {
            "section_id": self.section_id,
            "state": self.state,
            "reason": self.reason,
            "figure_ids": list(self.figure_ids),
            "chart": None,
        }


@dataclass(frozen=True, slots=True)
class CrossVersionRefusal:
    """A complete bilingual refusal carrying neither a figure nor a bundle."""

    cause: str
    wording: dict[str, str]
    figures: tuple[CitedFigure, ...] = ()
    bundle: CrossVersionBundle | None = None

    def __post_init__(self) -> None:
        from khepri.rra.crossversion_rules import require_refusal

        require_refusal(self)


@dataclass(frozen=True, slots=True)
class CrossVersionBundle:
    """Everything the three surfaces may present for one admitted pair."""

    identity: CrossVersionIdentity
    figures: tuple[CitedFigure, ...]
    caveats: tuple[StatedCaveat, ...]
    sections: tuple[CrossVersionSection, ...]
    evidence: tuple[CitedEvidence, ...]
    narrative_state: str = NARRATIVE_OMITTED
    narrative: None = None

    def __post_init__(self) -> None:
        from khepri.rra.crossversion_rules import require_bundle

        require_bundle(self)

    @property
    def bundle_version(self) -> str:
        return CROSSVERSION_BUNDLE_VERSION

    @property
    def section_ids(self) -> tuple[str, ...]:
        return tuple(section.section_id for section in self.sections)

    @property
    def bundle_id(self) -> str:
        return hashlib.sha256(canonical_json(self.as_document()).encode()).hexdigest()

    @property
    def is_drawable(self) -> bool:
        return False

    def figure(self, figure_id: str) -> CitedFigure | None:
        return next(
            (figure for figure in self.figures if figure.figure_id == figure_id),
            None,
        )

    def disclosure(self, language: str) -> str:
        from khepri.rra.bundle import _DISCLOSURE

        return _DISCLOSURE[self.narrative_state][language]

    def as_document(self) -> dict[str, object]:
        return {
            "identity": self.identity.as_document(),
            "figures": [figure.as_document() for figure in self.figures],
            "caveats": [caveat.as_document() for caveat in self.caveats],
            "narrative_state": self.narrative_state,
            "sections": [section.as_document() for section in self.sections],
            "narrative": None,
            "disclosure": {
                language: self.disclosure(language) for language in sorted(REQUIRED_LANGUAGES)
            },
        }


def build_crossversion_bundle(
    request: CrossVersionRequest,
) -> CrossVersionBundle | CrossVersionRefusal:
    """Build one admitted pair, or its complete refusal and nothing else."""
    from khepri.rra.crossversion_assembly import assemble_crossversion

    return assemble_crossversion(request)
