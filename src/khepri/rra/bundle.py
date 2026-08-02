"""One report bundle behind every surface it is published through.

**The failure this exists to prevent.** Three surfaces rendering the same
report is three chances to render it differently. A web page that totals a
column, a workbook whose cell holds a formula, and a PDF laid out in a separate
pass will disagree eventually, and the disagreement will be found by a customer
rather than by a test. RRA-006 excludes independent surface calculations for
exactly that reason.

So the arithmetic happens *once*, here. A bundle carries every figure already
rendered, in both languages, and a surface may only present renderings it was
given. That turns "do the three surfaces agree?" — a question answerable only
by comparing three computations and hoping — into "did this surface use what it
was handed?", which is decidable from one surface at a time.

**Identity.** A bundle is named by a digest over its whole content, not by its
version strings. Fact identifiers are derived from metric, scope and formula
version, so two entirely different datasets produce identical identifiers and
identical version strings; only the profile and source digests tell those
apart, and only a digest over the content tells apart two reports built from
the same data with different narrative. Every surface echoes the digest it was
built for, which is what stops a retry from delivering yesterday's PDF beside
today's workbook.

**The generation timestamp is deliberately not part of that digest, or of this
module.** RRA-006 asks for both a bound generation timestamp and deterministic
regeneration, and a timestamp inside the digest makes those two requirements
contradict: identical inputs would produce a different name on every run. The
identity here is therefore purely a function of content, so regenerating from
the same package and narrative reproduces the same `bundle_id`. When a bundle
was produced is a fact about the run, and belongs to the record that stores it.

**What this module does not do.** It does not render anything. There is no
HTML, no PDF, no workbook here, and no layout, font, or tagging decision. A
surface is modelled by the content it claims to present, and this checks that
claim against the bundle. Whether the PDF is genuinely tagged, or Arabic
genuinely runs right to left on screen, is a property of a renderer and of a
test that opens its output. What can be checked from here is that the surface
declares the direction the language actually reads in, and that every figure,
caveat and disclosure it shows came from the bundle.

**One number about the payload, and never the payload.** A surface also reports
how many bytes it produced, because RRA-007 records output size per stage and a
renderer is the only thing that holds both the bytes and the claim about them. A
count is all that crosses: no document, blob, or path reaches this module, and
nothing here can be reconstructed from a size. It is the one figure on a surface
that reconciliation cannot judge, which is stated where it is declared.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Protocol

from khepri.rra.facts import FactPackage
from khepri.rra.narrative import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    NARRATIVE_VERSION,
    REQUIRED_LANGUAGES,
    NarrativeDraft,
)
from khepri.rra.profiling import canonical_json

# v2 carries `sections` in the bundle document. That document is hashed to name
# a bundle, so the shape change moved every bundle id -- including for a bundle
# whose sections are empty. Two bundles built from identical inputs on either
# side of it must not claim one schema version while having different
# identities, or stored evidence cannot tell the two document contracts apart.
BUNDLE_VERSION = "rra006.bundle.v2"

SURFACE_WEB = "web"
SURFACE_PDF = "pdf"
SURFACE_EXCEL = "excel"
REQUIRED_SURFACES = (SURFACE_WEB, SURFACE_PDF, SURFACE_EXCEL)

# Which way each governed language reads. The layout itself is invisible from
# here; the declaration is not, and a surface that thinks Arabic reads left to
# right has not laid it out correctly by accident.
DIRECTION_RTL = "rtl"
DIRECTION_LTR = "ltr"
LANGUAGE_DIRECTION = {LANGUAGE_ARABIC: DIRECTION_RTL, LANGUAGE_ENGLISH: DIRECTION_LTR}

# A figure is addressed by where it sits, not by what it means. A scalar fact
# has one value; a series or a comparison has one per bucket, and a row count
# beside it, and a surface prints all of them.
KIND_VALUE = "value"
KIND_ROWS = "rows"

# Whether the report carries narrative, and if not, why. RRA-006 requires the
# reader be told which, so it is a governed value rather than a sentence
# somebody remembered to write.
NARRATIVE_INCLUDED = "included"
NARRATIVE_REFUSED = "refused"
NARRATIVE_OMITTED = "omitted"
GOVERNED_NARRATIVE_STATES = frozenset(
    {NARRATIVE_INCLUDED, NARRATIVE_REFUSED, NARRATIVE_OMITTED}
)

OUTCOME_DELIVERED = "delivered"
OUTCOME_INCOMPLETE = "incomplete"

# The figure-bearing analysis sections, in governed order. Order is data rather
# than a renderer's choice: a renderer permitted to choose it would let the PDF
# and the workbook disagree about what a reader sees first, and both would still
# reconcile, because reconciliation compares strings and not sequence.
#
# This covers analysis sections only. The template's caveats, commentary,
# citations and provenance sections hold no `CitedFigure`, so they are not
# `Section`s and keep their present place on every surface.
SECTION_OVERVIEW = "overview"
SECTION_COMPARISON = "comparison"
SECTION_CONCENTRATION = "concentration"
SECTION_GROWTH = "growth"
SECTION_BASKET = "basket"
ORDERED_SECTIONS = (
    SECTION_OVERVIEW,
    SECTION_COMPARISON,
    SECTION_CONCENTRATION,
    SECTION_GROWTH,
    SECTION_BASKET,
)

SECTION_PRESENT = "present"
SECTION_REFUSED = "refused"
GOVERNED_SECTION_STATES = frozenset({SECTION_PRESENT, SECTION_REFUSED})

CHART_BAR = "bar"
CHART_GROUPED_BAR = "grouped_bar"
CHART_LINE = "line"
# Three kinds, deliberately. A fourth adds a branch to every dispatching
# function in the chart module, and Code Health scores overall complexity as the
# mean per function. Growth decomposition is conceptually a waterfall and is
# drawn as a grouped bar; the two effects shown beside the total carry the same
# statement.
GOVERNED_CHART_KINDS = frozenset({CHART_BAR, CHART_GROUPED_BAR, CHART_LINE})

REASON_UNKNOWN_SURFACE = "unknown_surface"
REASON_MISSING_SURFACE = "missing_surface"
REASON_DUPLICATE_SURFACE = "duplicate_surface"
REASON_SURFACE_FAILED = "surface_failed"
REASON_BUNDLE_MISMATCH = "bundle_mismatch"
REASON_UNKNOWN_LANGUAGE = "unknown_language"
REASON_MISSING_LANGUAGE = "missing_language"
REASON_WRONG_DIRECTION = "wrong_direction"
REASON_UNKNOWN_FIGURE = "unknown_figure"
REASON_FIGURE_NOT_RECONCILED = "figure_not_reconciled"
REASON_FIGURE_COVERAGE_DIFFERS = "figure_coverage_differs_by_language"
REASON_CAVEAT_COVERAGE_DIFFERS = "caveat_coverage_differs_by_language"
REASON_DISCLOSURE_ALTERED = "disclosure_altered"
REASON_NARRATIVE_STATE_CONFLICT = "narrative_state_conflict"

# Everything a bundle refusal may be recorded as. `BundleRefused` is public, so
# a renderer can raise it carrying any text it likes, while the attempt record
# claims to hold no customer content. That claim needs a gate rather than a
# convention — the same gate the narrative reasons needed.
GOVERNED_REASONS = frozenset(
    {
        REASON_UNKNOWN_SURFACE,
        REASON_MISSING_SURFACE,
        REASON_DUPLICATE_SURFACE,
        REASON_SURFACE_FAILED,
        REASON_BUNDLE_MISMATCH,
        REASON_UNKNOWN_LANGUAGE,
        REASON_MISSING_LANGUAGE,
        REASON_WRONG_DIRECTION,
        REASON_UNKNOWN_FIGURE,
        REASON_FIGURE_NOT_RECONCILED,
        REASON_FIGURE_COVERAGE_DIFFERS,
        REASON_CAVEAT_COVERAGE_DIFFERS,
        REASON_DISCLOSURE_ALTERED,
        REASON_NARRATIVE_STATE_CONFLICT,
    }
)

# The disclosure every surface must carry, in both governed languages and for
# each narrative state. Held here rather than composed by a renderer: a
# disclosure a surface writes for itself is a disclosure a surface can soften,
# and "this was generated automatically" is exactly the sentence a rendering
# pass has an incentive to make smaller.
_DISCLOSURE: dict[str, dict[str, str]] = {
    NARRATIVE_INCLUDED: {
        LANGUAGE_ENGLISH: (
            "This analysis was generated automatically from the data you supplied. "
            "Every figure is cited to the fact package named in this report. "
            "The written commentary was generated automatically and checked against "
            "those figures."
        ),
        LANGUAGE_ARABIC: (
            "أُنشئ هذا التحليل تلقائيًا من البيانات التي قدمتها. "
            "كل رقم موثّق بالإسناد إلى حزمة الحقائق المذكورة في هذا التقرير. "
            "أُنشئ التعليق المكتوب تلقائيًا وجرى التحقق منه مقابل تلك الأرقام."
        ),
    },
    NARRATIVE_REFUSED: {
        LANGUAGE_ENGLISH: (
            "This analysis was generated automatically from the data you supplied. "
            "Every figure is cited to the fact package named in this report. "
            "No written commentary is included: it was refused because it could not "
            "be verified against those figures."
        ),
        LANGUAGE_ARABIC: (
            "أُنشئ هذا التحليل تلقائيًا من البيانات التي قدمتها. "
            "كل رقم موثّق بالإسناد إلى حزمة الحقائق المذكورة في هذا التقرير. "
            "لا يتضمن التقرير تعليقًا مكتوبًا: فقد رُفض لتعذّر التحقق منه مقابل تلك الأرقام."
        ),
    },
    NARRATIVE_OMITTED: {
        LANGUAGE_ENGLISH: (
            "This analysis was generated automatically from the data you supplied. "
            "Every figure is cited to the fact package named in this report. "
            "No written commentary is included: none was requested for this report."
        ),
        LANGUAGE_ARABIC: (
            "أُنشئ هذا التحليل تلقائيًا من البيانات التي قدمتها. "
            "كل رقم موثّق بالإسناد إلى حزمة الحقائق المذكورة في هذا التقرير. "
            "لا يتضمن التقرير تعليقًا مكتوبًا: إذ لم يُطلب أي تعليق لهذا التقرير."
        ),
    },
}

# Arabic-Indic digits and the separators that accompany them.
_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_ARABIC_DECIMAL = "٫"
_ARABIC_GROUP = "٬"
_ASCII_DIGITS = "0123456789"


class BundleRefused(ValueError):
    """A bundle could not be assembled, or a surface could not be trusted.

    Carries a governed reason code rather than renderer text, so a refusal can
    be recorded without echoing anything a renderer produced.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class SurfaceUnavailable(Exception):
    """A renderer could not produce its surface. Raised by renderers, never here."""


@dataclass(frozen=True, slots=True)
class BundleIdentity:
    """The exact provenance every surface of one report shares.

    Both kinds of identifier are here on purpose. `package_version` and its
    siblings name the *schema* a report was built under and are identical
    across every report this release produces; `profile_digest` and
    `source_sha256_hex` name the *data*. A reader asking which upload this is
    gets an answer from the second pair, and which code read it from the first.
    """

    package_version: str
    formula_version: str
    mapping_version: str
    narrative_version: str
    profile_digest: str
    source_sha256_hex: str
    monetary_precision: int
    row_count: int

    def as_document(self) -> dict[str, object]:
        return {
            "bundle_version": BUNDLE_VERSION,
            "package_version": self.package_version,
            "formula_version": self.formula_version,
            "mapping_version": self.mapping_version,
            "narrative_version": self.narrative_version,
            "profile_digest": self.profile_digest,
            "source_sha256_hex": self.source_sha256_hex,
            "monetary_precision": self.monetary_precision,
            "row_count": self.row_count,
        }

    @classmethod
    def of(cls, package: FactPackage) -> BundleIdentity:
        return cls(
            package_version=package.package_version,
            formula_version=package.formula_version,
            mapping_version=package.mapping_version,
            narrative_version=NARRATIVE_VERSION,
            profile_digest=package.profile_digest,
            source_sha256_hex=package.source_sha256_hex,
            monetary_precision=package.monetary_precision,
            row_count=package.row_count,
        )


@dataclass(frozen=True, slots=True)
class ChartSpec:
    """What a chart plots, named in figure identifiers and nothing else.

    A spec carries no geometry and no values. It says which governed figures a
    chart is drawn from, so the chart inherits the text reconciliation those
    figures already have instead of needing a parallel mechanism of its own.
    """

    kind: str
    figure_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.kind not in GOVERNED_CHART_KINDS:
            raise ValueError("unknown chart kind")
        if not self.figure_ids:
            raise ValueError("chart plots no figure")

    def as_document(self) -> dict[str, object]:
        return {"kind": self.kind, "figure_ids": list(self.figure_ids)}


@dataclass(frozen=True, slots=True)
class Section:
    """One governed section of a report: its figures, and its chart if it has one.

    A refused section carries no figures and still exists. `RRA-008` refuses the
    affected analysis rather than the report, and a reader cannot tell "there was
    nothing to show" from "we could not show it" unless the heading and the reason
    are both present. Absence is never the disclosure — which is also why section
    coverage can never be inferred from figure rows.
    """

    section_id: str
    state: str
    reason: str | None
    figure_ids: tuple[str, ...]
    chart: ChartSpec | None

    def __post_init__(self) -> None:
        _require_section(self.section_id)
        _require_section_state(self.state, self.reason)
        _require_chart_within(self.chart, self.figure_ids)
        _require_refusal_is_bare(self.state, self.figure_ids, self.chart)

    def as_document(self) -> dict[str, object]:
        return {
            "section_id": self.section_id,
            "state": self.state,
            "reason": self.reason,
            "figure_ids": list(self.figure_ids),
            "chart": None if self.chart is None else self.chart.as_document(),
        }


def _require_section(section_id: str) -> None:
    if section_id not in ORDERED_SECTIONS:
        raise ValueError("unknown section")


def _require_section_state(state: str, reason: str | None) -> None:
    # Membership first. The two rules below constrain the *valid* states, and a
    # state outside the set satisfies both of them by never matching either --
    # so `pending` with no reason would construct, and a renderer branching on
    # `state == SECTION_REFUSED` would draw it as a present section.
    if state not in GOVERNED_SECTION_STATES:
        raise ValueError("unknown section state")
    if state == SECTION_REFUSED and reason is None:
        raise ValueError("refused section states no reason")
    if state == SECTION_PRESENT and reason is not None:
        raise ValueError("present section states a reason")


def _require_chart_within(chart: ChartSpec | None, figure_ids: tuple[str, ...]) -> None:
    if chart is None:
        return
    if not frozenset(chart.figure_ids) <= frozenset(figure_ids):
        raise ValueError("chart plots a figure outside its section")


def _require_refusal_is_bare(
    state: str,
    figure_ids: tuple[str, ...],
    chart: ChartSpec | None,
) -> None:
    """A refused section carries nothing, and that is enforced rather than said.

    The surfaces render a refused section as a heading and a reason with no
    table, so figures declared here would be content the bundle authorized and
    no surface presents. A chart is worse than unused: chart reconciliation
    requires every plotted figure to appear in what the surface stated, and a
    refused section states none, so it would refuse the whole bundle over a
    chart that should never have existed.
    """
    if state != SECTION_REFUSED:
        return
    if figure_ids or chart is not None:
        raise ValueError("refused section states figures or a chart")


@dataclass(frozen=True, slots=True)
class CitedFigure:
    """One figure, already rendered for every language that will show it.

    `renderings` is the point of this type. A surface is handed the text and
    may only reproduce it, so "did the workbook round this differently from the
    PDF?" cannot arise — neither of them rounded anything.

    `figure_id` addresses the cell; `citation_id` names the fact a reader is
    pointed at. Both are needed: a series has one citation and many cells.
    """

    figure_id: str
    citation_id: str
    fact_id: str
    metric: str
    unit_kind: str
    kind: str
    label: str | None
    value: Decimal | None
    renderings: dict[str, str]

    def as_document(self) -> dict[str, object]:
        return {
            "figure_id": self.figure_id,
            "citation_id": self.citation_id,
            "fact_id": self.fact_id,
            "metric": self.metric,
            "unit_kind": self.unit_kind,
            "kind": self.kind,
            "label": self.label,
            "value": None if self.value is None else str(self.value),
            "renderings": dict(sorted(self.renderings.items())),
        }


@dataclass(frozen=True, slots=True)
class ReportBundle:
    """Everything the three surfaces of one report are allowed to present."""

    identity: BundleIdentity
    figures: tuple[CitedFigure, ...]
    caveats: tuple[str, ...]
    narrative_state: str
    sections: tuple[Section, ...] = ()
    narrative: NarrativeDraft | None = None

    def __post_init__(self) -> None:
        _require_governed_section_order(self.sections)

    @property
    def section_ids(self) -> tuple[str, ...]:
        """The ordered sections this bundle declares.

        What a surface's own section claim is reconciled against. Deriving that
        claim from the figures a surface stated would make a refused section
        invisible -- it carries none -- and would let a section dropped from
        every language reconcile, because the surfaces would agree with each
        other while disagreeing with the report that was assembled.
        """
        return tuple(entry.section_id for entry in self.sections)

    @property
    def bundle_id(self) -> str:
        """Content address of this bundle, and the name every surface echoes.

        Over the content rather than the versions. A fact identifier is derived
        from metric, scope and formula version, so two different datasets reach
        identical identifiers and identical version strings — and two reports
        over the same data with different commentary are still two reports. The
        narrative is inside this document for that second reason; leaving it
        out would let a bundle whose prose changed keep the old name.
        """
        return hashlib.sha256(canonical_json(self.as_document()).encode()).hexdigest()

    def figure(self, figure_id: str) -> CitedFigure | None:
        return next(
            (entry for entry in self.figures if entry.figure_id == figure_id),
            None,
        )

    def disclosure(self, language: str) -> str:
        return _DISCLOSURE[self.narrative_state][language]

    def as_document(self) -> dict[str, object]:
        return {
            "identity": self.identity.as_document(),
            "figures": [entry.as_document() for entry in self.figures],
            "caveats": list(self.caveats),
            "narrative_state": self.narrative_state,
            "sections": [entry.as_document() for entry in self.sections],
            "narrative": _narrative_document(self.narrative),
            "disclosure": {
                language: self.disclosure(language) for language in sorted(REQUIRED_LANGUAGES)
            },
        }

    @classmethod
    def of(
        cls,
        package: FactPackage,
        *,
        narrative: NarrativeDraft | None = None,
        narrative_refused: bool = False,
    ) -> ReportBundle:
        """Bind one package, and at most one narrative, into a single report.

        A refusal and an omission are told apart by the caller rather than
        inferred from a missing narrative, because they say different things to
        a reader: one means the commentary could not be trusted, the other that
        none was asked for. Guessing between them from `narrative is None`
        would announce a refusal every time a caller simply wanted facts.
        """
        if narrative is not None and narrative_refused:
            # A narrative that was refused is not a narrative that arrived, and
            # a caller claiming both has not decided which report this is.
            raise BundleRefused(REASON_NARRATIVE_STATE_CONFLICT)
        if narrative is not None:
            state = NARRATIVE_INCLUDED
        elif narrative_refused:
            state = NARRATIVE_REFUSED
        else:
            state = NARRATIVE_OMITTED

        return cls(
            identity=BundleIdentity.of(package),
            figures=_figures(package),
            caveats=tuple(sorted(set(package.caveats))),
            narrative_state=state,
            narrative=narrative,
        )


def _require_governed_section_order(sections: tuple[Section, ...]) -> None:
    """The bundle may not choose its own section order, and neither may a caller.

    `section_ids` is the authority every surface's section claim is reconciled
    against, so an order assembled wrongly here is an order every surface
    follows and then reconciles against perfectly. Validating each `Section`
    individually is not enough: five valid sections in the wrong sequence are
    five valid sections.

    A subset is allowed and a reordering is not, so the comparison is against
    `ORDERED_SECTIONS` filtered to what was claimed rather than against the
    whole tuple.
    """
    claimed = [entry.section_id for entry in sections]
    if len(set(claimed)) != len(claimed):
        raise ValueError("bundle repeats a section")
    if claimed != [entry for entry in ORDERED_SECTIONS if entry in set(claimed)]:
        raise ValueError("bundle states sections out of governed order")


@dataclass(frozen=True, slots=True)
class StatedFigure:
    """A figure as one surface actually presents it."""

    figure_id: str
    text: str


@dataclass(frozen=True, slots=True)
class SurfaceLanguage:
    language: str
    direction: str
    stated: tuple[StatedFigure, ...]
    caveats: tuple[str, ...]
    disclosure: str

    @property
    def shown(self) -> frozenset[str]:
        return frozenset(entry.figure_id for entry in self.stated)


@dataclass(frozen=True, slots=True)
class SurfaceContent:
    """What a renderer says its surface presents. Untrusted until reconciled.

    `output_size_bytes` is how large the payload behind this claim turned out to
    be, and it is the only thing this module ever learns about that payload.
    RRA-007 records output size per stage, and the size is knowable only where
    the bytes are: a claim carrying structure alone left it unrecordable
    anywhere. The number travels, the payload does not, and nothing can be
    reconstructed from a count of bytes.

    It is deliberately *not* reconciled. `reconcile` compares a claim against
    the bundle, and the bundle carries no payload to compare a size to. Whether
    the number is the size of what was really written is proven where the
    artifact exists — each renderer's own tests open its output and measure it —
    which is the same division of labour as tagging and reading direction.
    """

    surface: str
    bundle_id: str
    languages: tuple[SurfaceLanguage, ...]
    output_size_bytes: int

    def __post_init__(self) -> None:
        _require_size(self.output_size_bytes)


class SurfaceRenderer(Protocol):
    """A replaceable renderer.

    The concrete web, PDF and workbook writers are separate changes; this is
    the contract each of them will satisfy.

    `render` returns the size of the payload beside the claim about it, because
    a renderer is the only thing that ever holds both. Returning the payload
    itself would put report bytes on the one path operational evidence is read
    from, and RRA-007's evidence is content-free.
    """

    @property
    def surface(self) -> str: ...

    def render(self, bundle: ReportBundle) -> SurfaceContent: ...


@dataclass(frozen=True, slots=True)
class BundleAttempt:
    """The record of one assembly, carrying no customer content by construction.

    Every field is a governed version string, a digest, a surface name, a
    reason code, or a state. There is no field a caveat, a label, a figure or a
    renderer's error message could occupy.
    """

    bundle_version: str
    bundle_id: str
    package_version: str
    narrative_state: str
    surfaces: tuple[str, ...]
    outcome: str
    reason: str | None

    def as_document(self) -> dict[str, object]:
        return {
            "bundle_version": self.bundle_version,
            "bundle_id": self.bundle_id,
            "package_version": self.package_version,
            "narrative_state": self.narrative_state,
            "surfaces": list(self.surfaces),
            "outcome": self.outcome,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class BundleResult:
    attempt: BundleAttempt
    surfaces: tuple[SurfaceContent, ...] | None

    @property
    def incomplete(self) -> bool:
        return self.surfaces is None


class BundleAssembler:
    def __init__(self, *, renderers: Sequence[SurfaceRenderer]) -> None:
        self._renderers = tuple(renderers)

    def assemble(self, bundle: ReportBundle) -> BundleResult:
        """Render every required surface, or deliver none of them.

        RRA-006 calls a partial export an incomplete bundle, and the reason is
        not tidiness: a customer holding a PDF from one run beside a workbook
        from the next holds two reports that disagree, with nothing on either
        to say so. A surface that fails, or that cannot reconcile, therefore
        discards the whole attempt rather than itself.

        Retrying is safe because nothing here depends on when it runs. The same
        package and narrative rebuild the same `bundle_id`, so a second attempt
        either produces the same bundle or a visibly different one.
        """
        produced: dict[str, SurfaceContent] = {}
        for renderer in self._renderers:
            try:
                content = renderer.render(bundle)
                reconcile(content, bundle=bundle)
            except BundleRefused as refusal:
                return self._incomplete(bundle, produced, refusal.reason)
            except Exception:  # noqa: BLE001 - see below
                # A renderer raising anything at all is a renderer that did not
                # produce its surface. The reason is coarse deliberately: it
                # says only that the surface failed, so nothing the renderer
                # wrote is echoed into the record.
                return self._incomplete(bundle, produced, REASON_SURFACE_FAILED)
            if content.surface in produced:
                # Two renderers claiming one surface would leave which of them
                # was delivered decided by iteration order.
                return self._incomplete(bundle, produced, REASON_DUPLICATE_SURFACE)
            produced[content.surface] = content

        if set(produced) != set(REQUIRED_SURFACES):
            return self._incomplete(bundle, produced, REASON_MISSING_SURFACE)

        return BundleResult(
            attempt=self._attempt(
                bundle,
                REQUIRED_SURFACES,
                OUTCOME_DELIVERED,
                None,
            ),
            surfaces=tuple(produced[surface] for surface in REQUIRED_SURFACES),
        )

    def _incomplete(
        self,
        bundle: ReportBundle,
        produced: dict[str, SurfaceContent],
        reason: str,
    ) -> BundleResult:
        return BundleResult(
            # The surfaces that did render are named so a retry can be reasoned
            # about, but not one of them is returned.
            attempt=self._attempt(
                bundle,
                tuple(sorted(produced)),
                OUTCOME_INCOMPLETE,
                reason if reason in GOVERNED_REASONS else REASON_SURFACE_FAILED,
            ),
            surfaces=None,
        )

    def _attempt(
        self,
        bundle: ReportBundle,
        surfaces: tuple[str, ...],
        outcome: str,
        reason: str | None,
    ) -> BundleAttempt:
        return BundleAttempt(
            bundle_version=BUNDLE_VERSION,
            bundle_id=bundle.bundle_id,
            package_version=bundle.identity.package_version,
            narrative_state=bundle.narrative_state,
            surfaces=surfaces,
            outcome=outcome,
            reason=reason,
        )


def reconcile(content: SurfaceContent, *, bundle: ReportBundle) -> None:
    """Refuse a surface that presents anything the bundle did not supply."""
    if content.surface not in REQUIRED_SURFACES:
        raise BundleRefused(REASON_UNKNOWN_SURFACE)
    if content.bundle_id != bundle.bundle_id:
        # The whole defence against mixing runs. A surface built for another
        # bundle names another bundle, whatever else it looks like.
        raise BundleRefused(REASON_BUNDLE_MISMATCH)

    offered = [entry.language for entry in content.languages]
    if len(set(offered)) != len(offered):
        # Collapsing duplicates into a mapping would reconcile the last entry
        # and hand back a surface still carrying the others.
        raise BundleRefused(REASON_BUNDLE_MISMATCH)
    seen = {entry.language: entry for entry in content.languages}
    if set(seen) - set(REQUIRED_LANGUAGES):
        raise BundleRefused(REASON_UNKNOWN_LANGUAGE)
    if set(seen) != set(REQUIRED_LANGUAGES):
        raise BundleRefused(REASON_MISSING_LANGUAGE)

    for entry in seen.values():
        _reconcile_language(entry, bundle)

    coverage = [seen[language] for language in sorted(seen)]
    first = coverage[0]
    for other in coverage[1:]:
        # Equivalent facts in both languages means the same cells, not merely
        # the same count of them. A surface that drops one row from the Arabic
        # table reconciles perfectly language by language.
        if other.shown != first.shown:
            raise BundleRefused(REASON_FIGURE_COVERAGE_DIFFERS)


def _reconcile_language(entry: SurfaceLanguage, bundle: ReportBundle) -> None:
    if entry.direction != LANGUAGE_DIRECTION[entry.language]:
        raise BundleRefused(REASON_WRONG_DIRECTION)
    if entry.disclosure != bundle.disclosure(entry.language):
        # Compared in full rather than searched for a phrase. A disclosure that
        # has been shortened, softened, or translated afresh is not the
        # governed disclosure, and a keyword search would accept all three.
        raise BundleRefused(REASON_DISCLOSURE_ALTERED)
    if frozenset(entry.caveats) != frozenset(bundle.caveats):
        raise BundleRefused(REASON_CAVEAT_COVERAGE_DIFFERS)
    for stated in entry.stated:
        figure = bundle.figure(stated.figure_id)
        if figure is None:
            raise BundleRefused(REASON_UNKNOWN_FIGURE)
        if stated.text != figure.renderings.get(entry.language):
            # Text, not value. `500.0` and `500.00` are the same number and a
            # different statement about precision, and a surface is not
            # entitled to choose which one a reader sees.
            raise BundleRefused(REASON_FIGURE_NOT_RECONCILED)


def _figures(package: FactPackage) -> tuple[CitedFigure, ...]:
    """Render every citable figure the package carries, once, for both languages.

    Series points and comparison buckets are figures as much as a scalar total
    is: they are the numbers a table prints. Each is addressed by a
    `figure_id`, because one citation covers many cells and a surface has to be
    able to say which cell it is showing.
    """
    rendered: list[CitedFigure] = []
    for fact in package.facts:
        rendered.append(
            _figure(
                citation_id=fact.citation_id,
                fact_id=fact.fact_id,
                metric=fact.metric,
                unit_kind=fact.unit_kind,
                kind=KIND_VALUE,
                label=None,
                text=fact.value,
            )
        )

    for entry in package.series:
        document = entry.as_document()
        for position, point in enumerate(document["points"]):
            rendered.extend(_bucket(document, point, position))

    for entry in package.comparisons:
        document = entry.as_document()
        for position, cell in enumerate(document["buckets"]):
            rendered.extend(_bucket(document, cell, position))

    return tuple(rendered)


def _bucket(
    owner: dict[str, object],
    cell: dict[str, object],
    position: int,
) -> tuple[CitedFigure, ...]:
    """The value a bucket carries, and the row count printed beside it.

    A withheld value produces no figure rather than a figure with no text. A
    surface cannot print what was not supplied, and inventing an empty
    rendering here would give it something to print.
    """
    label = str(cell["label"])
    common = {
        "citation_id": str(owner["citation_id"]),
        "fact_id": str(owner["fact_id"]),
        "metric": str(owner["measure"]),
        "unit_kind": str(owner["unit_kind"]),
        "label": label,
        "position": position,
    }
    figures = [
        _figure(kind=KIND_ROWS, text=str(cell["rows"]), **common),
    ]
    if cell.get("value") is not None:
        figures.insert(0, _figure(kind=KIND_VALUE, text=str(cell["value"]), **common))
    return tuple(figures)


def _figure(
    *,
    citation_id: str,
    fact_id: str,
    metric: str,
    unit_kind: str,
    kind: str,
    label: str | None,
    text: str,
    position: int | None = None,
) -> CitedFigure:
    return CitedFigure(
        figure_id=_figure_id(citation_id, kind, position),
        citation_id=citation_id,
        fact_id=fact_id,
        metric=metric,
        unit_kind=unit_kind,
        kind=kind,
        label=label,
        value=_decimal(text),
        renderings=_renderings(text),
    )


def _figure_id(citation_id: str, kind: str, position: int | None) -> str:
    """Address a cell by its coordinates: the citation, the kind, the position.

    The label is deliberately absent. It is customer text, and a figure
    identifier travels further than the figure does — into logs, into a
    workbook's defined names, into whatever a renderer keys its cells by — so
    the name of a cell is not a place to put a store's name.

    Position rather than a digest of the label. A digest would be
    *probabilistic*: two labels can share one, and `aggregates._disambiguate`
    exists in this codebase precisely because six hex characters were not the
    guarantee they looked like. Position is unique by construction within a
    citation, carries no customer text either, and is stable across
    regeneration because buckets are ordered deterministically upstream.
    """
    if position is None:
        return f"{citation_id}/{kind}"
    return f"{citation_id}/{kind}/{position}"


def _renderings(text: str) -> dict[str, str]:
    """The one English and one Arabic form of a supplied figure.

    The English rendering is the package's own string, reproduced rather than
    reformatted: it already carries the precision the fact was computed to, and
    re-rendering it here would make this module the thing deciding how many
    decimal places a governed figure has.

    The Arabic rendering is that same string transliterated character by
    character — every digit to one Arabic-Indic digit, the separators to their
    Arabic counterparts. The two forms differ in script and in nothing else: no
    rounding, no reformatting, no arithmetic.
    """
    return {LANGUAGE_ENGLISH: text, LANGUAGE_ARABIC: _arabic(text)}


def _arabic(text: str) -> str:
    return "".join(_arabic_character(character) for character in text)


def _arabic_character(character: str) -> str:
    if character in _ASCII_DIGITS:
        return _ARABIC_DIGITS[_ASCII_DIGITS.index(character)]
    if character == ".":
        return _ARABIC_DECIMAL
    if character == ",":
        return _ARABIC_GROUP
    return character


def _require_size(value: int) -> None:
    """Refuse a size no payload could have had.

    Non-negative rather than positive: an empty payload is each renderer's own
    invariant to refuse, and each of them does, where the emptiness is visible.
    A negative size is not a small report — it is a broken measurement, and one
    that `OperationalEvent` would refuse long after the stage it was taken at
    had finished.
    """
    if value < 0:
        raise ValueError("output_size_bytes must be non-negative.")


def _decimal(text: str) -> Decimal | None:
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None


def _narrative_document(narrative: NarrativeDraft | None) -> dict[str, object] | None:
    """The narrative as the bundle digest sees it.

    Every word of it, because the prose is part of what makes this report this
    report. Summarizing it to a version or an adapter name would let a bundle
    whose commentary changed keep the name of the one whose commentary it
    replaced.
    """
    if narrative is None:
        return None
    return {
        "adapter_version": narrative.adapter_version,
        "request_digest": narrative.request_digest,
        "languages": [
            {
                "language": entry.language,
                "sections": [
                    {
                        "section_id": section.section_id,
                        "text": section.text,
                        "cited_fact_ids": list(section.cited_fact_ids),
                        "caveats": list(section.caveats),
                        "labels": list(section.labels),
                        "direction": section.direction,
                    }
                    for section in entry.sections
                ],
            }
            for entry in sorted(narrative.languages, key=lambda entry: entry.language)
        ],
    }
