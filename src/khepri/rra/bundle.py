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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Protocol

from khepri.rra.analysis import basket, comparison, concentration, growth
from khepri.rra.facts import UNIT_RATIO, Fact, FactPackage, RefusedResult
from khepri.rra.narrative import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    NARRATIVE_VERSION,
    REQUIRED_LANGUAGES,
    NarrativeDraft,
)
from khepri.rra.profiling import canonical_json

# The bundle document is hashed to name a bundle, so any change to its shape
# moves every bundle id. Two bundles built from identical inputs on either side
# of such a change must not claim one schema version while having different
# identities, or stored evidence cannot tell the two document contracts apart.
#
#   v2  `sections` joins the document
#   v3  every figure carries `section`, and `sections` arrives populated
#   v4  a caveat is a (code, section) pair rather than a bare code
#   v5  `figures` is ordered by governed section rather than by derivation
#   v6  a bucket figure's `metric` is its fact's metric, not the measure behind it
#
# The section model ships as several independently verifiable slices, and each
# one that moves the document earns a version. That is version churn on purpose:
# every string here named a shape that really existed on `main`, which is worth
# more than a tidy sequence.
BUNDLE_VERSION = "rra006.bundle.v6"

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

# Figure labels that are governed vocabulary rather than customer text. A bucket
# label is a product or branch name and is final; a comparison mode is an internal
# identifier, and printing `period_over_period` on an Arabic axis is the same class
# of failure as printing a metric code there. `rendering.charts` asks this set which
# kind a label is, because this module owns the vocabulary and that one imports it.
GOVERNED_FIGURE_LABELS = frozenset(comparison.GOVERNED_MODES)

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

# A section whose figures could not be drawn. Returning no chart is not by itself
# a disclosure -- the section would simply look sparse, and a reader could not tell
# "there was nothing to show" from "we could not show it". This carries that.
CAVEAT_CHART_NOT_DRAWN = "chart_not_drawn"

# How many points of a concentration curve reach a surface, and why there is a limit
# at all. The ranked set is the *full* distinct-value set, which admissibility bounds
# only by the upload size: a 50 MB file can carry hundreds of thousands of distinct
# products. Every point becomes two figures, and at roughly half a million ranks each
# language's worksheet passes Excel's 1,048,576-row limit -- where `_write_row`
# ignores XlsxWriter's failed-write return while the surface claim still lists every
# figure, so a workbook missing its tail reconciles perfectly.
#
# So the curve is sampled at evenly spaced ranks, always including the last, and the
# sampling is disclosed. Every published share is a measured one; what is bounded is
# how many of them are published, exactly as `MAX_COMPARISON_BUCKETS` bounds a
# comparison and says so.
MAX_CURVE_POINTS = 100
CAVEAT_CURVE_SAMPLED = "curve_points_sampled"

SECTION_PRESENT = "present"
SECTION_REFUSED = "refused"
GOVERNED_SECTION_STATES = frozenset({SECTION_PRESENT, SECTION_REFUSED})

# Why a governed analysis refused, and the whole vocabulary a surface has to be
# able to translate. Every surface renders a refused section by looking its
# reason up in a per-language table, so a code outside this set reaches a reader
# as a blank or untranslated refusal while the bundle stays valid -- the same
# hazard `GOVERNED_REASONS` exists to close for bundle refusals, and the same
# reason a reason code may never carry customer-derived text.
#
# Adding a code is deliberate: a family that needs a new one adds it here in the
# slice that introduces it, rather than passing a string through.
SECTION_REASON_PRIOR_WINDOW_ABSENT = "prior_window_absent"
# Spelled to match the fact package's `REASON_INPUT_UNAVAILABLE` rather than
# given a section-flavoured synonym: a family that refuses for this reason hands
# its own code straight to the section, and two spellings of one condition would
# make the hand-off a translation nobody would remember to keep honest.
SECTION_REASON_REQUIRED_INPUT_UNAVAILABLE = "required_input_unavailable"
SECTION_REASON_AGGREGATE_UNAVAILABLE = "aggregate_unavailable"
SECTION_REASON_DISTINCT_SET_UNCOMPUTABLE = "distinct_set_uncomputable"
SECTION_REASON_UNITS_ABSENT = "units_absent"
SECTION_REASON_DECOMPOSITION_NOT_ADDITIVE = "decomposition_not_additive"
SECTION_REASON_TRANSACTION_IDENTIFIER_ABSENT = "transaction_identifier_absent"
# The fact package's own wording, reused rather than restated: `RRA-004` refuses
# the transaction count with this when the identifier column has gaps, and the
# basket family reports the cause the package recorded.
SECTION_REASON_INCOMPLETE_IDENTIFIERS = "incomplete_transaction_identifiers"

# Which reasons may refuse an entire section. That is a narrower question than
# "which reasons can this family produce", and the two come apart wherever a
# family has more than one metric: `RRA-008` refuses "the affected result", so a
# family losing one of its metrics keeps the section present and carrying the
# other. A code that can only kill one metric therefore belongs on that result,
# beside the figures, and never on the section state -- a refused section carries
# no figures at all, so putting it here would suppress a figure that survived.
#
# A governed code is also not a licence to use it on any section: a growth
# section explaining itself with basket analysis's missing transaction identifier
# is a contextually impossible refusal, and it would be hashed into the bundle
# and rendered to a reader as authoritative.
#
#   period comparison  no prior-window coverage for either governed mode
#   concentration      the full distinct set cannot be computed, or its
#                      aggregate is unavailable -- both take the whole family
#   growth             zero units, or a non-additive decomposition
#   basket             no mapped transaction identifier, which `RRA-008`
#                      requires for *both* basket metrics
#
# Basket is the case that shows the distinction. `RRA-008` requires an admissible
# dimension for attach rate only, and the merged plan gates attach rate alone on
# the pending `RRA-004` amendment, so `dimension_absent` and
# `aggregate_unavailable` each kill attach rate while items per transaction --
# `METRIC_UNITS / METRIC_TRANSACTIONS`, both already governed facts -- survives.
# Neither may refuse the section. `dimension_absent` is not defined in this
# module at all: it can never be a section state, so it belongs with the fact
# package's result-level reasons, which is where the basket slice will put it.
#
# `SECTION_OVERVIEW` states no reason. It carries `RRA-004` headline figures
# rather than an `RRA-008` family, and `RRA-004` refuses individual metrics
# inside the package instead of an analysis section. A slice that finds the
# overview genuinely needs a governed refusal adds it here, with its authority.
#
# One deliberate omission to save the next reader the deduction: growth is a
# two-period computation, so an absent prior window looks like it should refuse
# it. `RRA-008` does not say so -- it names only zero units and non-additivity
# for growth -- so it is not asserted here. The growth slice adds it if the
# implementation proves it necessary, which is a one-line change in the obvious
# place, and is a better outcome than this table quietly claiming authority the
# specification does not give it.
#
# Comparison carries two, and the second is the case that proves the omission
# above is a real risk rather than a tidy principle. `comparison.derive` refuses
# with the reason its modes actually gave, and a compared period holding only
# null revenue gives `required_input_unavailable` -- the window was present and
# the measure was not. With only `prior_window_absent` permitted here, assembling
# that refusal into its section had two outcomes and both were wrong: raise on a
# valid package, or relabel the refusal as a missing window and tell a reader the
# opposite of what happened. A section that cannot state its family's refusal
# reason does not fail closed, it fails misleadingly.

SECTION_REASONS: dict[str, frozenset[str]] = {
    SECTION_OVERVIEW: frozenset(),
    SECTION_COMPARISON: frozenset(
        {
            SECTION_REASON_PRIOR_WINDOW_ABSENT,
            SECTION_REASON_REQUIRED_INPUT_UNAVAILABLE,
        }
    ),
    SECTION_CONCENTRATION: frozenset(
        {
            SECTION_REASON_DISTINCT_SET_UNCOMPUTABLE,
            SECTION_REASON_AGGREGATE_UNAVAILABLE,
        }
    ),
    SECTION_GROWTH: frozenset(
        {
            SECTION_REASON_UNITS_ABSENT,
            SECTION_REASON_DECOMPOSITION_NOT_ADDITIVE,
            # Two rows whose authority is reachability, as for the comparison
            # section: growth decomposes the same window the comparison states, so
            # it fails the same two ways. A dataset short of two settled periods
            # has no change to decompose, and an absent revenue trend has nothing
            # to decompose at all. Neither is "units absent", and a section that
            # cannot state its family's actual reason does not fail closed -- it
            # fails misleadingly.
            SECTION_REASON_PRIOR_WINDOW_ABSENT,
            SECTION_REASON_REQUIRED_INPUT_UNAVAILABLE,
        }
    ),
    SECTION_BASKET: frozenset(
        {
            SECTION_REASON_TRANSACTION_IDENTIFIER_ABSENT,
            # One more, and only one. `RRA-008` requires a transaction identifier
            # for both basket metrics, so its absence is the single failure that
            # takes the whole family -- and a column with gaps is that same
            # failure with a different cause, which the fact package already
            # distinguishes when it refuses the transaction count. Reporting it as
            # "identifier absent" would name a cause that did not occur.
            #
            SECTION_REASON_INCOMPLETE_IDENTIFIERS,
            # And one that is per-metric *and* whole-family, depending on what
            # else the dataset has. An absent units measure refuses items per
            # transaction while attach rate stands -- carried on the result, not
            # here. But a dataset with an identifier and neither units nor a
            # product or category dimension states nothing at all, and then the
            # section is refused and needs a reason it can say.
            #
            # `aggregate_unavailable` stays off this list, and provably can: it
            # refuses attach rate only, and reaching a whole-family refusal
            # requires items per transaction to have refused too, whose reason is
            # recorded first.
            SECTION_REASON_REQUIRED_INPUT_UNAVAILABLE,
        }
    ),
}

# Derived, never maintained alongside the table, so the two cannot disagree
# about what a governed reason is.
GOVERNED_SECTION_REASONS = frozenset().union(*SECTION_REASONS.values())

CHART_BAR = "bar"
CHART_GROUPED_BAR = "grouped_bar"
CHART_LINE = "line"
# Three kinds, deliberately. A fourth adds a branch to every dispatching
# function in the chart module, and Code Health scores overall complexity as the
# mean per function. Growth decomposition is conceptually a waterfall and is
# drawn as a grouped bar; the two effects shown beside the total carry the same
# statement.
GOVERNED_CHART_KINDS = frozenset({CHART_BAR, CHART_GROUPED_BAR, CHART_LINE})

# Which kind each section is drawn as. One kind per section, so a globally valid
# kind is not usable anywhere: a surface handed a bar chart where the design
# fixes a line renders the wrong visualization faithfully and reconciles
# perfectly, because reconciliation compares the text beside a chart and never
# the chart.
#
# The authority behind these rows differs, and the difference matters here.
# Concentration is fixed by specification: `RRA-008` requires the "cumulative
# share curve", and a cumulative curve drawn as bars misstates a governed
# requirement rather than merely looking wrong. The other four are design
# decisions recorded in the merged design document -- `RRA-006` requires charts
# rendered from the fact package and names no kinds, and `RRA-008` names only
# the curve. A later design revision may move those four; moving concentration
# would need `RRA-008` to change first.
SECTION_CHART_KINDS: dict[str, str] = {
    SECTION_OVERVIEW: CHART_BAR,
    SECTION_COMPARISON: CHART_GROUPED_BAR,
    SECTION_CONCENTRATION: CHART_LINE,
    SECTION_GROWTH: CHART_GROUPED_BAR,
    SECTION_BASKET: CHART_BAR,
}

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
REASON_UNKNOWN_SECTION = "unknown_section"
REASON_FIGURE_MISPLACED = "figure_misplaced"
REASON_SECTION_NOT_PRESENTED = "section_not_presented"
REASON_SECTION_COVERAGE_DIFFERS = "section_coverage_differs_by_language"
REASON_SECTION_ORDER_DIFFERS = "section_order_differs_by_language"
REASON_CHART_FIGURE_NOT_STATED = "chart_figure_not_stated"

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
        REASON_UNKNOWN_SECTION,
        REASON_FIGURE_MISPLACED,
        REASON_SECTION_NOT_PRESENTED,
        REASON_SECTION_COVERAGE_DIFFERS,
        REASON_SECTION_ORDER_DIFFERS,
        REASON_CHART_FIGURE_NOT_STATED,
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
        _require_distinct_figures(self.figure_ids, "chart")

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
        # `_require_section` runs first, so everything after it may index the
        # per-section tables by `section_id` without re-checking membership.
        _require_section(self.section_id)
        _require_section_state(self.state)
        _require_section_reason(self.section_id, self.state, self.reason)
        _require_distinct_figures(self.figure_ids, "section")
        _require_chart_within(self.chart, self.figure_ids)
        _require_chart_kind(self.section_id, self.chart)
        _require_refusal_is_bare(self.state, self.figure_ids, self.chart)
        _require_presence_is_populated(self.state, self.figure_ids)

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


def _require_section_state(state: str) -> None:
    # Membership, checked before any rule that constrains the valid states. A
    # state outside the set satisfies all of those by never matching any -- so
    # `pending` with no reason would construct, and a renderer branching on
    # `state == SECTION_REFUSED` would draw it as a present section.
    if state not in GOVERNED_SECTION_STATES:
        raise ValueError("unknown section state")


def _require_section_reason(section_id: str, state: str, reason: str | None) -> None:
    """A refusal states a reason its own analysis can produce; presence states none.

    Checked against the section rather than against the whole vocabulary. A
    globally governed code is not a licence to use it anywhere: growth analysis
    cannot fail for want of a transaction identifier, so a growth section
    stating that reason is explaining itself with another family's condition,
    and the explanation is hashed into the bundle and rendered as authoritative.

    `None` is a member of no section's set, so this covers a refusal that states
    no reason at all, one that invents a code, and one that borrows a governed
    code from another analysis -- three failures with one comparison.
    """
    if state == SECTION_PRESENT and reason is not None:
        raise ValueError("present section states a reason")
    if state != SECTION_REFUSED:
        return
    if reason not in SECTION_REASONS[section_id]:
        raise ValueError("section states no reason its own analysis can produce")


def _require_distinct_figures(figure_ids: tuple[str, ...], subject: str) -> None:
    """No figure appears twice, checked before anything compares sets.

    `_require_chart_within` compares `frozenset`s, and a set comparison cannot
    see multiplicity: a chart plotting `("F-1", "F-1")` is a subset of a section
    holding `("F-1",)`, so it passes and serializes unchanged. A renderer then
    iterates the tuple and draws one governed value as two marks, which states a
    second data point that does not exist. The same duplicate in a section's own
    figures prints the same row twice.
    """
    if len(set(figure_ids)) != len(figure_ids):
        raise ValueError(f"{subject} repeats a figure")


def _require_chart_within(chart: ChartSpec | None, figure_ids: tuple[str, ...]) -> None:
    if chart is None:
        return
    if not frozenset(chart.figure_ids) <= frozenset(figure_ids):
        raise ValueError("chart plots a figure outside its section")


def _require_chart_kind(section_id: str, chart: ChartSpec | None) -> None:
    """A section is drawn as its own kind, not as any governed kind.

    Reconciliation compares the text beside a chart and never the chart, so a
    section handed the wrong kind renders faithfully and reconciles perfectly
    while showing the reader the wrong visualization. Concentration is the case
    that matters most: `RRA-008` requires a cumulative share *curve*, and bars
    drawn over cumulative shares misstate a governed requirement.
    """
    if chart is None:
        return
    if chart.kind != SECTION_CHART_KINDS[section_id]:
        raise ValueError("chart kind is not the kind this section is drawn as")


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


def _require_presence_is_populated(state: str, figure_ids: tuple[str, ...]) -> None:
    """A present section presents something.

    The state model has exactly two members, so a present section holding no
    figures is a third state wearing the first one's name: it claims an analysis
    succeeded while showing nothing, and carries no reason because present
    sections may not. A reader then cannot tell it from a populated section that
    happens to look sparse, which is the distinction the refusal path exists to
    preserve. An analysis that produced nothing refuses.
    """
    if state != SECTION_PRESENT:
        return
    if not figure_ids:
        raise ValueError("present section states no figure")


@dataclass(frozen=True, slots=True)
class StatedCaveat:
    """One caveat, and the section it qualifies -- or none, for the whole report.

    A flat tuple of codes left a hole the figure model had already closed.
    `RRA-008` caveats are per-family: a caveat naming a truncated comparison
    window belongs to the comparison, not to the report. With codes alone, a
    surface could render that caveat under the basket section and reconcile
    perfectly, because the comparison against `bundle.caveats` saw only the code.

    Pairing the code with its section closes it without a new refusal reason.
    The existing set comparison now compares pairs, so a misplaced caveat fails
    it exactly as a missing one does.

    `section=None` is a report-level caveat belonging to no single analysis --
    `currency_not_declared` qualifies the dataset, not one family. Those render
    in the report's own caveats section; section-scoped ones render inside the
    section they qualify.
    """

    code: str
    section: str | None

    def __post_init__(self) -> None:
        if self.section is None:
            return
        _require_section(self.section)

    def as_document(self) -> dict[str, object]:
        return {"code": self.code, "section": self.section}


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
    section: str
    label: str | None
    value: Decimal | None
    renderings: dict[str, str]

    def __post_init__(self) -> None:
        _require_section(self.section)

    def as_document(self) -> dict[str, object]:
        return {
            "figure_id": self.figure_id,
            "citation_id": self.citation_id,
            "fact_id": self.fact_id,
            "metric": self.metric,
            "unit_kind": self.unit_kind,
            "kind": self.kind,
            "section": self.section,
            "label": self.label,
            "value": None if self.value is None else str(self.value),
            "renderings": dict(sorted(self.renderings.items())),
        }


@dataclass(frozen=True, slots=True)
class ReportBundle:
    """Everything the three surfaces of one report are allowed to present."""

    identity: BundleIdentity
    figures: tuple[CitedFigure, ...]
    caveats: tuple[StatedCaveat, ...]
    narrative_state: str
    sections: tuple[Section, ...] = ()
    narrative: NarrativeDraft | None = None

    def __post_init__(self) -> None:
        _require_governed_section_order(self.sections)
        _require_sections_index_the_figures(self.sections, self.figures)
        _require_caveat_scopes_are_declared(self.sections, self.caveats)

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
            "caveats": [entry.as_document() for entry in self.caveats],
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

        analysed = _analysed(package)
        figures = _in_section_order((*_figures(package), *analysed.figures))
        sections = _sections(figures, analysed.refusals)
        return cls(
            identity=BundleIdentity.of(package),
            figures=figures,
            # Every RRA-004 caveat qualifies the dataset rather than one
            # analysis, so each is report-level. A family's caveat qualifies its
            # own analysis and is scoped to that section: a bare code could be
            # rendered under the basket heading while describing the comparison,
            # and the surface would reconcile perfectly.
            caveats=(
                *(
                    StatedCaveat(code=code, section=None)
                    for code in sorted(set(package.caveats))
                ),
                *analysed.caveats,
                *(
                    StatedCaveat(code=CAVEAT_CHART_NOT_DRAWN, section=entry.section_id)
                    for entry in sections
                    if entry.state == SECTION_PRESENT and entry.chart is None
                ),
            ),
            narrative_state=state,
            sections=sections,
            narrative=narrative,
        )


def _in_section_order(figures: tuple[CitedFigure, ...]) -> tuple[CitedFigure, ...]:
    """Figures in governed section order, stable within each section.

    Every surface walks `sections`, so a figure tuple in a different order makes the
    claim and the file disagree about sequence while agreeing about content -- which
    is what the workbook's per-section sheets exposed: the concentration curve is
    derived last and belongs third.

    Stable, so the order a family stated its facts in is the order a reader sees.
    """
    return tuple(
        sorted(figures, key=lambda figure: ORDERED_SECTIONS.index(figure.section))
    )


def _sections(
    figures: tuple[CitedFigure, ...],
    refused: Mapping[str, str],
) -> tuple[Section, ...]:
    """The sections a bundle declares, in governed order.

    Derived from the figures rather than assembled beside them, so the sections
    a bundle declares and the sections its figures claim cannot disagree --
    `section_ids` is what every surface is reconciled against, and a bundle that
    disagreed with itself would refuse every correct surface.

    A refused family contributes no figures and still gets a section, because a
    reader cannot tell "there was nothing to show" from "we could not show it"
    unless the heading and the reason are both present. Absence is never the
    disclosure.

    A chart is attached only where the section's own figures can be drawn, and
    `is_drawable` is the single place that decides. A section with a spec the
    geometry would refuse promises a chart no surface can draw.
    """
    placed = {
        section_id: tuple(
            figure for figure in figures if figure.section == section_id
        )
        for section_id in ORDERED_SECTIONS
    }
    return tuple(
        _section(section_id, placed[section_id], refused.get(section_id))
        for section_id in ORDERED_SECTIONS
        if placed[section_id] or section_id in refused
    )


def _section(
    section_id: str,
    figures: tuple[CitedFigure, ...],
    reason: str | None,
) -> Section:
    """One section: refused with its reason, or present with its figures.

    A family that stated even one fact is present. Its refusal, if it also
    recorded one, belongs to the affected metric rather than to the section --
    which is the distinction `SECTION_REASONS` enforces by refusing to admit a
    per-metric reason as a section state.
    """
    if not figures:
        return Section(
            section_id=section_id,
            state=SECTION_REFUSED,
            reason=reason,
            figure_ids=(),
            chart=None,
        )
    plotted = _plottable(section_id, figures)
    return Section(
        section_id=section_id,
        state=SECTION_PRESENT,
        reason=None,
        figure_ids=tuple(figure.figure_id for figure in figures),
        chart=(
            ChartSpec(
                kind=SECTION_CHART_KINDS[section_id],
                figure_ids=tuple(figure.figure_id for figure in plotted),
            )
            if is_drawable(plotted)
            else None
        ),
    )


def _plottable(
    section_id: str,
    figures: tuple[CitedFigure, ...],
) -> tuple[CitedFigure, ...]:
    """The figures this section's chart draws, as its family declared them.

    The overview declares none and keeps no chart. Its figures are the package's
    headline totals across every unit the dataset carries -- money beside counts
    beside ratios -- and no single axis states them. Choosing a subset here would be
    this module inventing an analysis nobody specified.

    Row counts are never plotted either. A row count sits beside a value in the table
    as a coverage number, and charting it next to the value it qualifies would put a
    count of rows on the same axis as the money those rows carry.
    """
    family = _FAMILIES.get(section_id)
    if family is None:
        return ()
    return tuple(
        figure
        for figure in figures
        if figure.kind == KIND_VALUE and figure.metric in family.plots
    )


def is_drawable(figures: tuple[CitedFigure, ...]) -> bool:
    """Whether these figures can make a chart at all.

    The rule lives here, with the types, and `rendering.charts` applies it. It
    cannot live there: that module imports this one, so a bundle wanting the same
    answer would have to keep a second copy, and a bundle attaching a spec the
    geometry then refused would promise a chart no surface could draw.

    Four conditions, each for a reason the geometry module states at length: one
    point is a number a table states better; a missing value is a governed gap
    and never a zero on a chart; a domain of no width has nothing to scale by;
    and mixed units on one axis scale a ratio of 0.1818 to invisibility beside a
    count of 25.
    """
    if len(figures) < 2:
        return False
    if any(figure.value is None for figure in figures):
        return False
    if len({figure.unit_kind for figure in figures}) != 1:
        return False
    values = [figure.value for figure in figures if figure.value is not None]
    return min(*values, Decimal(0)) != max(*values, Decimal(0))


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


def _require_sections_index_the_figures(
    sections: tuple[Section, ...],
    figures: tuple[CitedFigure, ...],
) -> None:
    """The section index and the figures must agree about placement.

    Deriving the sections in `of` protects only callers who use `of`, and the
    constructor is public. A bundle assembled directly could place an overview
    figure while declaring no sections, declare a section indexing a figure id
    that does not exist, or index a figure under a section other than its own --
    and every surface would then copy *both halves* of that contradiction into
    its claim and reconcile against it perfectly, because reconciliation compares
    a surface with the bundle and never the bundle with itself.

    One comparison covers all of it. A figure absent from the index is a missing
    key, an indexed figure that does not exist is an extra one, and a figure
    indexed under the wrong section is a differing value. Refused sections are
    exempt for free: they carry no figures, so they contribute no pairs, and a
    present section always carries at least one.
    """
    indexed = [
        (figure_id, section.section_id)
        for section in sections
        for figure_id in section.figure_ids
    ]
    if len({figure_id for figure_id, _ in indexed}) != len(indexed):
        raise ValueError("bundle indexes one figure under more than one section")
    if dict(indexed) != {figure.figure_id: figure.section for figure in figures}:
        raise ValueError("bundle sections and figures disagree about placement")


def _require_caveat_scopes_are_declared(
    sections: tuple[Section, ...],
    caveats: tuple[StatedCaveat, ...],
) -> None:
    """A scoped caveat needs a section to be rendered in.

    `StatedCaveat` checks the governed vocabulary, which says the name exists --
    not that this report has that section. A caveat scoped to a section the
    bundle never declared has no legal location on any surface: there is no
    heading to put it under, so a renderer either drops it or misfiles it, and
    the caveat still reconciles because reconciliation compares the pair against
    the bundle rather than against the page.

    Report-level caveats are exempt, having no scope to place.
    """
    declared = {section.section_id for section in sections}
    scoped = {caveat.section for caveat in caveats if caveat.section is not None}
    if not scoped <= declared:
        raise ValueError("bundle scopes a caveat to a section it does not declare")


@dataclass(frozen=True, slots=True)
class StatedFigure:
    """A figure as one surface actually presents it, and where it put it.

    `section` is a claim, not a lookup. Nothing validates it on construction and
    nothing copies it from the bundle: a surface that read the bundle's answer
    would agree with itself by definition, and the placement check below would
    pass on every surface including a broken one. An invented name is judged by
    `reconcile` rather than rejected here, so it becomes a governed refusal a
    bundle attempt can record instead of an exception nothing can describe.
    """

    figure_id: str
    text: str
    section: str


@dataclass(frozen=True, slots=True)
class SurfaceLanguage:
    language: str
    direction: str
    sections: tuple[str, ...]
    stated: tuple[StatedFigure, ...]
    caveats: tuple[StatedCaveat, ...]
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
        _reconcile_claimed_section_names(entry)
        _reconcile_charts(entry, bundle)

    coverage = [seen[language] for language in sorted(seen)]
    first = coverage[0]
    for other in coverage[1:]:
        # Equivalent facts in both languages means the same cells, not merely
        # the same count of them. A surface that drops one row from the Arabic
        # table reconciles perfectly language by language.
        if other.shown != first.shown:
            raise BundleRefused(REASON_FIGURE_COVERAGE_DIFFERS)
    _reconcile_sections(coverage)

    # Against the bundle *after* the languages have been compared with each
    # other, so each failure gets the reason that describes it. One language
    # dropping a section is a disagreement between surfaces; both dropping it is
    # a disagreement with the report. Checking the bundle first would report the
    # second reason for the first failure and leave the cross-language codes
    # unreachable, which is a governed reason that can never be recorded.
    for entry in seen.values():
        _reconcile_sections_against_bundle(entry, bundle)


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
        _reconcile_placement(stated, figure)
        if stated.text != figure.renderings.get(entry.language):
            # Text, not value. `500.0` and `500.00` are the same number and a
            # different statement about precision, and a surface is not
            # entitled to choose which one a reader sees.
            raise BundleRefused(REASON_FIGURE_NOT_RECONCILED)


def _reconcile_placement(stated: StatedFigure, figure: CitedFigure) -> None:
    """Where a figure was shown is a claim like the text of it.

    A figure printed under the wrong heading is cited correctly and read
    wrongly: every string matches, so text reconciliation passes, and the
    reader attributes a basket number to growth analysis. The section a surface
    invents is checked before the one it misplaces, so an unknown name and a
    wrong-but-governed name give different reasons.
    """
    if stated.section not in ORDERED_SECTIONS:
        raise BundleRefused(REASON_UNKNOWN_SECTION)
    if stated.section != figure.section:
        raise BundleRefused(REASON_FIGURE_MISPLACED)


def _reconcile_claimed_section_names(entry: SurfaceLanguage) -> None:
    """An invented section name is its own failure, and the most specific one.

    Checked first and per language, before the claim is compared with anything,
    so a surface naming a section that does not exist is told that rather than
    being reported as disagreeing with the bundle or with the other language.
    """
    for section_id in entry.sections:
        if section_id not in ORDERED_SECTIONS:
            raise BundleRefused(REASON_UNKNOWN_SECTION)


def _reconcile_sections_against_bundle(
    entry: SurfaceLanguage,
    bundle: ReportBundle,
) -> None:
    """Compared against the bundle, because the bundle is what knows.

    Against the other language it would catch only a disagreement between
    surfaces. A section missing from *both* leaves them agreeing with each other
    and disagreeing with the report that was assembled, and a refused section
    carries no figures at all -- so nothing derived from figure rows could ever
    notice either case.

    Claiming more than the bundle assembled fails the same comparison, and
    should: a heading for an analysis nobody ran is as wrong as a missing one.
    """
    if entry.sections != bundle.section_ids:
        raise BundleRefused(REASON_SECTION_NOT_PRESENTED)


def _reconcile_charts(entry: SurfaceLanguage, bundle: ReportBundle) -> None:
    """Every plotted figure is also a figure this language says it presented.

    `ChartSpec.figure_ids` is already a subset of its section's figures by
    construction, and those are reconciled by exact string comparison. This
    closes the one gap that leaves: the surface could omit a plotted figure from
    what it claims to present, leaving a mark on a chart with no reconciled text
    behind it.
    """
    for section in bundle.sections:
        if section.chart is None:
            continue
        if not frozenset(section.chart.figure_ids) <= entry.shown:
            raise BundleRefused(REASON_CHART_FIGURE_NOT_STATED)


def _reconcile_sections(coverage: list[SurfaceLanguage]) -> None:
    """The languages agree on which sections they showed, and in what order.

    Strictly redundant once every language has been compared against the bundle:
    two tuples each equal to `bundle.section_ids` are equal to each other. Kept
    because these are governed reason codes naming a real and distinct failure,
    and because a later change relaxing the bundle comparison to a subset rule
    would otherwise take the cross-language guarantee with it silently.
    """
    first = coverage[0].sections
    for other in coverage[1:]:
        if frozenset(other.sections) != frozenset(first):
            raise BundleRefused(REASON_SECTION_COVERAGE_DIFFERS)
        if other.sections != first:
            raise BundleRefused(REASON_SECTION_ORDER_DIFFERS)


@dataclass(frozen=True, slots=True)
class _Analysed:
    """What the four `RRA-008` families contributed to one bundle.

    Carried as one value because the three parts are decided together: a family
    either placed figures in its section, or refused it with a reason, and either
    way its caveats belong to that section alone.
    """

    figures: tuple[CitedFigure, ...]
    refusals: dict[str, str]
    caveats: tuple[StatedCaveat, ...]


# Which module states each analysis section. A table rather than four calls in a
# row, so a family cannot be wired to the wrong section and every one of them is
# reached the same way.
@dataclass(frozen=True, slots=True)
class _Family:
    """One analysis family, and the three questions the assembly asks it.

    `refusals` is not optional decoration. A family can state some results and refuse
    others -- a comparison with a prior period but no prior year, a basket with items
    per transaction and no dimension for attach rate -- and `RRA-008` refuses the
    affected *result*. Recording only the facts would leave a reader unable to tell a
    refused metric from one nobody asked for.

    `names` recovers the scope a fact was derived under, and only where that scope
    distinguishes one of the family's facts from another. Without it every attach-rate
    row carries the same metric and no label, so two products render as two identical
    rows. With it applied indiscriminately the opposite happens: growth's three
    effects all share one mode, so labelling them by it would give three different
    bars the same name and hide the metric that actually tells them apart.

    `plots` names the metrics this family's chart draws, and the family declares them
    because only the family knows. A rule inferred here would be wrong for at least
    one section whichever way it was written: grouping by metric breaks growth, whose
    three *different* metrics are exactly what its grouped bar compares; grouping by
    unit breaks concentration, whose curve shares a unit with the two shares derived
    from it and would be drawn twice.

    A section states more than it draws, always. The rest stays in the table, which is
    the authoritative presentation.
    """

    derive: object
    refusals: object
    names: object
    plots: frozenset[str]


_FAMILIES = {
    SECTION_COMPARISON: _Family(
        derive=comparison.derive,
        refusals=comparison.refusals,
        names=lambda fact, package: comparison.mode_of(fact),
        # The absolute deltas, one bar per mode. The percentage deltas are the same
        # comparison restated as a ratio, and charting both puts a fraction on the
        # money axis.
        plots=frozenset({comparison.METRIC_DELTA_ABSOLUTE}),
    ),
    SECTION_CONCENTRATION: _Family(
        derive=concentration.derive,
        refusals=lambda package: (),
        # No label. Every concentration fact shares one dimension, so naming it per
        # row distinguishes nothing, and the curve's own points are labelled by rank.
        # What tells the four scalars apart is their metric.
        names=lambda fact, package: None,
        # The curve, which is what `RRA-008` requires drawn. The four scalars are read
        # from the table beside it.
        plots=frozenset({concentration.METRIC_CURVE}),
    ),
    SECTION_GROWTH: _Family(
        derive=growth.derive,
        refusals=lambda package: (),
        # No label, for the same reason: all three effects share one mode. The
        # metric is what says which effect a row or a bar is, and a chart resolves it
        # through the per-language table.
        names=lambda fact, package: None,
        # All three, because the point of the chart is that two effects sum to the
        # change beside them. They share a unit, so they share an axis honestly.
        plots=frozenset(growth.GOVERNED_METRICS),
    ),
    SECTION_BASKET: _Family(
        derive=basket.derive,
        refusals=basket.refusals,
        names=basket.attached_value_of,
        # The attach rates, one bar per value. Items per transaction is a different
        # statement about the whole dataset and is not one of the bars.
        plots=frozenset({basket.METRIC_ATTACH_RATE}),
    ),
}


def _analysed(package: FactPackage) -> _Analysed:
    """Run every governed family and place what each of them said.

    This is the seam the four families were built behind: until it existed they
    could state facts that no surface would ever carry. A family refusing is not
    an error here -- `RRA-008` refuses the affected analysis and not the report,
    so a refusal becomes a section a reader can see.
    """
    figures: list[CitedFigure] = []
    refusals: dict[str, str] = {}
    caveats: list[StatedCaveat] = []
    for section_id, family in _FAMILIES.items():
        stated = family.derive(package)
        refused = family.refusals(package)
        if isinstance(stated, RefusedResult):
            # The section's own reason is the family's summary, which names one cause.
            # Two modes can refuse for different reasons, and `refusals` is the
            # complete per-mode record -- so the rest still travels as scoped
            # disclosures rather than being dropped with the `continue`.
            refusals[section_id] = stated.reason
            caveats.extend(_scoped(section_id, (), refused))
            continue
        figures.extend(
            _analysis_figure(fact, section_id, family.names(fact, package))
            for fact in stated
        )
        caveats.extend(_scoped(section_id, stated, refused))
    figures.extend(_curve_figures(package))
    return _Analysed(
        figures=tuple(figures),
        refusals=refusals,
        caveats=tuple(caveats),
    )


def _scoped(
    section_id: str,
    stated: tuple[Fact, ...],
    refused: tuple[RefusedResult, ...],
) -> tuple[StatedCaveat, ...]:
    """Everything qualifying one section: its facts' caveats, and its refused results.

    A partially refusing family has no other channel. Its section is present -- it
    stated something -- and `SECTION_REASONS` will not admit a per-metric reason as a
    section state, precisely because a refused section carries no figures and would
    suppress the results that survived. So the reason travels as a caveat scoped to
    the section, which is the governed way to carry a qualification into both
    languages.

    A refusal keeps its result identity. `RefusedResult.metric` is already
    mode-qualified where a family has modes -- `revenue_delta_percent.year_over_year`
    -- and reducing it to the bare reason collapses two different refused results
    that failed for the same cause, leaving a reader told that something was refused
    and not which. So the code is `<result>:<reason>`, which a surface renders
    verbatim like every other governed code.

    Deduplicated and sorted, so a rerun produces the same document.
    """
    codes = {code for fact in stated for code in fact.caveats}
    codes |= {f"{refusal.metric}:{refusal.reason}" for refusal in refused}
    return tuple(
        StatedCaveat(code=code, section=section_id) for code in sorted(codes)
    )


def _curve_figures(package: FactPackage) -> tuple[CitedFigure, ...]:
    """The concentration curve, as one figure per ranked point.

    The four concentration scalars are two counts beside two ratios, so they share no
    axis and are refused as a chart -- correctly. The curve is what `RRA-008` asks to
    be drawn, and it reaches a surface the way a trend does: a `FactSeries` whose
    buckets become figures sharing one citation.
    """
    series = concentration.curve_series(package)
    if series is None:
        return ()
    document = series.as_document()
    points = _sampled(list(document["points"]))
    return tuple(
        figure
        for position, point in enumerate(points)
        for figure in _bucket(document, point, position, SECTION_CONCENTRATION)
    )


def _sampled(points: list[object]) -> list[object]:
    """At most `MAX_CURVE_POINTS` of a curve, evenly spaced, ending on the last.

    The last point is kept unconditionally because it is the whole ranked set by
    definition: a curve that stopped short of it would understate concentration at
    the only rank a reader can check against 100%.
    """
    if len(points) <= MAX_CURVE_POINTS:
        return points
    step = len(points) / MAX_CURVE_POINTS
    kept = {int(index * step) for index in range(MAX_CURVE_POINTS)}
    kept.add(len(points) - 1)
    return [point for index, point in enumerate(points) if index in kept]


def _analysis_figure(fact: Fact, section_id: str, label: str | None) -> CitedFigure:
    """One derived fact as a figure in the section that derived it.

    Positioned by nothing: an analysis fact is a scalar, and its citation names
    it uniquely because every family scopes its identities by mode or dimension.
    """
    return CitedFigure(
        figure_id=_figure_id(fact.citation_id, KIND_VALUE, None),
        citation_id=fact.citation_id,
        fact_id=fact.fact_id,
        metric=fact.metric,
        unit_kind=fact.unit_kind,
        kind=KIND_VALUE,
        section=section_id,
        # The scope the family derived this under -- the mode, the dimension, or the
        # dimension value. Without it two attach rates render as two identical rows.
        label=label,
        value=_decimal(fact.value),
        renderings=_renderings(
            fact.value, unit_kind=fact.unit_kind, kind=KIND_VALUE, metric=fact.metric
        ),
    )


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
    section: str = SECTION_OVERVIEW,
) -> tuple[CitedFigure, ...]:
    """The value a bucket carries, and the row count printed beside it.

    A withheld value produces no figure rather than a figure with no text. A
    surface cannot print what was not supplied, and inventing an empty
    rendering here would give it something to print.

    **The metric is the owner's `metric`, not its `measure`.** It used to be the
    measure, and that was the one place in this module where a figure's metric was
    not its fact's metric: `_analysis_figure` records `fact.metric`, so a growth
    effect carried `growth_price_effect` while a revenue trend carried `revenue`
    where its fact says `revenue_by_period`. A measure names the column a series was
    computed over; a metric names what was computed, and a figure's metric is the
    latter everywhere else.

    That inconsistency is what made the concentration curve unchartable.
    `_plottable` asks whether a figure's metric is one the family plots, the
    concentration family plots `concentration_curve`, and every curve figure claimed
    to be `revenue` -- so the one chart `RRA-008` requires by specification was
    attached to no section and drawn on no surface, while every text cell beside it
    reconciled perfectly.
    """
    label = str(cell["label"])
    common = {
        "citation_id": str(owner["citation_id"]),
        "fact_id": str(owner["fact_id"]),
        "metric": str(owner["metric"]),
        "unit_kind": str(owner["unit_kind"]),
        "label": label,
        "position": position,
        "section": section,
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
    section: str = SECTION_OVERVIEW,
    position: int | None = None,
) -> CitedFigure:
    return CitedFigure(
        figure_id=_figure_id(citation_id, kind, position),
        citation_id=citation_id,
        fact_id=fact_id,
        metric=metric,
        unit_kind=unit_kind,
        kind=kind,
        # Every figure the RRA-004 package carries is an overview figure, which is
        # the default. The concentration curve is the one series a family supplies
        # through this path, and it names its own section.
        section=section,
        label=label,
        value=_decimal(text),
        renderings=_renderings(text, unit_kind=unit_kind, kind=kind, metric=metric),
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


def _renderings(
    text: str,
    *,
    unit_kind: str | None = None,
    kind: str = KIND_VALUE,
    metric: str | None = None,
) -> dict[str, str]:
    """The one English and one Arabic form of a supplied figure.

    The English rendering keeps the precision the fact was computed to and adds
    only what makes it legible: digit grouping, and a percent sign for a ratio.
    **`RRA-006` requires "units, formats"** in the same scope line that requires
    accessible tables, and an ungrouped `726919.57` beside a margin printed as
    `0.8665` satisfies neither. The earlier rule here was to reproduce the
    package's string verbatim, on the ground that re-rendering would make this
    module decide a governed figure's precision. That ground is sound and is
    kept: grouping inserts separators and the ratio scaling is exact, so the
    significant digits crossing this function are the ones that entered it.

    **Formatted here rather than in a renderer, deliberately.** This is the one
    place the `Decimal` and its `unit_kind` sit together, and the single string
    all four surfaces copy. `rendering/html.py` refuses to format because four
    renderers formatting independently is four renderers disagreeing about
    precision; that refusal only holds if the string reaching them is already
    the finished one.

    **No currency marker, at any unit.** `facts` appends
    `CAVEAT_CURRENCY_NOT_DECLARED` to every package carrying a monetary fact,
    because the currency is not derivable from an upload. A symbol here would
    assert what that caveat exists to disclaim.

    `unit_kind` is optional so a caller with no unit in hand -- a label, a
    timestamp, anything that is not a measured quantity -- gets the previous
    verbatim behaviour rather than a guess.
    """
    english = _presented(text, unit_kind=unit_kind, kind=kind, metric=metric)
    return {LANGUAGE_ENGLISH: english, LANGUAGE_ARABIC: _arabic(english)}


#: The `UNIT_RATIO` metrics that are *proportions* and therefore presentable as
#: percentages, named rather than inferred.
#:
#: **`unit_kind` does not carry this distinction, and cannot be made to here.**
#: `basket._fact` stamps `UNIT_RATIO` on both of its metrics through one helper:
#: `basket_attach_rate` is a proportion of transactions, while
#: `basket_items_per_transaction` is a *rate* -- 3.6667 items in an average
#: basket. Scaling the second by a hundred prints `366.67%`, which is not a
#: smaller defect than the `0.8665` this slice set out to fix. The honest
#: long-term fix is a fourth unit kind on `Fact`, which is an `RRA-004` change to
#: a digested document and not something a presentation slice may make; this
#: allowlist is the bounded form, and it fails *closed*.
#:
#: A ratio metric absent from this set renders as a plain grouped number, which
#: is wrong-looking rather than wrong. `test_every_ratio_metric_is_classified`
#: enumerates what a rich package actually produces and fails when a new one
#: appears, because an allowlist nobody is forced to extend is an allowlist that
#: silently mis-formats the next metric added.
PERCENTAGE_METRICS = frozenset(
    {
        "gross_margin",
        "revenue_delta_percent",
        "concentration_top_decile_share",
        "concentration_top_quartile_share",
        "concentration_curve",
        "basket_attach_rate",
    }
)

#: The `UNIT_RATIO` metrics that are rates rather than proportions, named so the
#: coverage test can tell "classified as not-a-percentage" from "forgotten".
#:
#: `basket_items_per_transaction` is the whole reason this pair of sets exists: a
#: rich package renders it as `3825.0000` items per basket, which as a percentage
#: is `382500.00%`.
RATE_METRICS = frozenset({"basket_items_per_transaction"})


def _presented(text: str, *, unit_kind: str | None, kind: str, metric: str | None = None) -> str:
    """Group a figure's digits, and scale a ratio to a percentage.

    **A row count is a count whatever it counts.** `KIND_ROWS` figures inherit
    their owner's `unit_kind`, so dispatching on unit alone would take the row
    count beside a margin and print `28200.00%`. The kind is checked first for
    that reason, and the check is not defensive: `_bucket` builds exactly such a
    pair on every aggregated fact.

    A value this cannot parse is returned untouched. Refusing would turn a
    presentation concern into a bundle failure, and the caller already treats a
    non-numeric figure as legitimate -- `_decimal` returns `None` for one.
    """
    if kind == KIND_ROWS:
        return _grouped(text)
    if unit_kind == UNIT_RATIO and metric in PERCENTAGE_METRICS:
        return _percentage(text)
    return _grouped(text)


def _grouped(text: str) -> str:
    """Insert thousands separators, preserving the decimal places as given."""
    parsed = _decimal(text)
    if parsed is None:
        return text
    whole, _, fraction = text.strip().partition(".")
    try:
        grouped = f"{int(whole):,}"
    except ValueError:
        return text
    return f"{grouped}.{fraction}" if fraction else grouped


def _percentage(text: str) -> str:
    """Scale a stored ratio to a percentage at two decimal places.

    **Exact, and therefore free of any rounding mode.** Every ratio-kind fact is
    quantized to `facts.RATIO_PRECISION` -- four places -- by all four producers
    (`facts`, `analysis.basket`, `analysis.comparison`, `analysis.concentration`),
    so multiplying by a hundred moves the point two places and always lands
    within two: `0.8665` is `86.65%` and `1.0000` is `100.00%`, with nothing to
    round away. `test_scaling_a_ratio_by_one_hundred_is_exact` asserts that
    invariant rather than a rounding behaviour, because a rounding mode chosen
    here would be a second rounding on top of the one the fact boundary already
    performed -- and the mode would then have to agree with a decision this
    module does not own.

    The stored `Decimal` stays on the figure's `value`, which is what
    reconciliation and the audit trail read: the percentage is presentation, and
    the figure it was derived from remains addressable.
    """
    parsed = _decimal(text)
    if parsed is None:
        return text
    # `quantize` to two places without a mode: exact by the invariant above, and
    # it raises rather than rounds silently if a producer ever exceeds four
    # places, which is the failure worth hearing about.
    scaled = (parsed * 100).quantize(Decimal("0.01"))
    return f"{_grouped(str(scaled))}%"


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
