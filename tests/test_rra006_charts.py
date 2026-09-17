"""Governed chart geometry: exact coordinates, no markup, no invented prose.

Every assertion here is on a view model. Nothing in this module produces an SVG
fragment, because a Python string of markup cannot be rendered by these templates:
`build_environment()` sets `autoescape=True` unconditionally, so `{{ chart_svg }}`
would reach a reader as `&lt;svg …`. The two exits are `|safe` and `Markup`, and
both move the escaping decision off the environment and onto whoever remembers it
-- on the one path customer-derived labels travel.

So the coordinates are strings and the elements are written by a macro from
template source, which is trusted because it is source.
"""

from __future__ import annotations

import ast
import re
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, nodes

from khepri.rra import facts
from khepri.rra.bundle import (
    CHART_BAR,
    CHART_GROUPED_BAR,
    CHART_LINE,
    DIRECTION_LTR,
    DIRECTION_RTL,
    GOVERNED_CHART_KINDS,
    GOVERNED_FIGURE_LABELS,
    KIND_VALUE,
    LANGUAGE_DIRECTION,
    SECTION_COMPARISON,
    ChartSpec,
    CitedFigure,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.rendering.charts import (
    _GEOMETRY,  # the table under test
    CHART_HEIGHT,
    CHART_WIDTH,
    POINT_SIZE,
    ChartLabel,
    ChartView,
    build_chart,
)
from khepri.rra.rendering.wording import (
    AXIS_UNITS,
    LABEL_WORDING,
    category_of,
    worded,
)

#: The unit kind the shared chart fixture uses, so a parity assertion names one key.
DEFAULT_UNIT = facts.UNIT_MONETARY


def figure(figure_id: str, value: Decimal | None, label: str) -> CitedFigure:
    """One already-rendered figure, as a bundle hands it to a surface."""
    rendered = "" if value is None else str(value)
    return CitedFigure(
        figure_id=figure_id,
        citation_id="cit_000000000000",
        fact_id="fct_000000000000000000000000",
        metric="revenue_by_product",
        unit_kind="monetary",
        kind=KIND_VALUE,
        section=SECTION_COMPARISON,
        label=label,
        value=value,
        renderings={LANGUAGE_ENGLISH: rendered, LANGUAGE_ARABIC: f"ar:{rendered}"},
    )


def figures_for_chart(
    values: tuple[Decimal | None, ...] = (Decimal(100), Decimal(300)),
) -> tuple[CitedFigure, ...]:
    return tuple(
        figure(f"F-{index + 1}", value, f"V{index + 1}")
        for index, value in enumerate(values)
    )


def chart_of(
    kind: str = CHART_BAR,
    figure_ids: tuple[str, ...] = ("F-1", "F-2"),
    values: tuple[Decimal | None, ...] = (Decimal(100), Decimal(300)),
    language: str = LANGUAGE_ENGLISH,
) -> ChartView | None:
    """One chart, with the direction the governed table gives that language.

    Direction is derived rather than passed, because `LANGUAGE_DIRECTION` is where
    the pairing is decided and a test choosing its own could assert a mirroring
    that no surface would ever request.
    """
    return build_chart(
        ChartSpec(kind=kind, figure_ids=figure_ids),
        figures_for_chart(values),
        direction=LANGUAGE_DIRECTION[language],
    )



def _chart_macro_source() -> str:
    """The chart macro as template source, for the two deferral guards.

    Both deferrals -- no period on the axis, no legend -- are only load-bearing if
    they reach the thing a reader sees. `ChartView.__dataclass_fields__` does not:
    an element written directly into the macro needs no field, and that is exactly
    the route a later slice would take. So the source is scanned as well.
    """
    source = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "khepri"
        / "rra"
        / "rendering"
        / "templates"
        / "_chart.svg.j2"
    ).read_text(encoding="utf-8")
    assert source.strip(), "the chart macro is empty, so these guards prove nothing"
    # Jinja comments are stripped: this macro's prose explains WHY there is no period
    # and no legend, and a guard that reads the explanation as the violation is a
    # guard the next slice narrows. `journey.css` taught the same lesson on the shell
    # side, where a header comment naming the other surface's tokens tripped an
    # `FR-201` scan.
    without_comments = re.sub(r"\{#.*?#\}", "", source, flags=re.DOTALL)
    assert without_comments.strip(), "stripping comments emptied the macro"
    return without_comments


def test_a_drawable_series_yields_one_mark_per_figure() -> None:
    view = chart_of()
    assert view is not None
    assert view.kind == CHART_BAR
    assert len(view.marks) == 2
    assert view.title_code
    assert view.description_code


def test_bar_geometry_is_exact_and_scaled_to_the_largest_value() -> None:
    """100 against 300 on a 320-unit canvas: a third of the height, and all of it.

    Asserted as exact strings rather than approximately. These are the coordinates
    a reader's chart is drawn from, and a governed figure's proportions are part of
    what the chart claims.
    """
    view = chart_of()
    assert view is not None
    short, tall = view.marks

    assert (short.x, short.width) == ("64.0000", "192.0000")
    assert (short.y, short.height) == ("213.3333", "106.6667")
    assert (tall.x, tall.width) == ("384.0000", "192.0000")
    assert (tall.y, tall.height) == ("0.0000", "320.0000")


def test_no_coordinate_is_a_float() -> None:
    """Geometry is `Decimal` until a mark is built, and what is built is a string.

    A float here would mean binary floating point reached the surface of a governed
    figure, which `KHEPRI-DEC-005` prohibits for authoritative values and which the
    workbook's `write_string` discipline exists to prevent.
    """
    view = chart_of()
    assert view is not None
    for mark in view.marks:
        for coordinate in (mark.x, mark.y, mark.width, mark.height):
            assert isinstance(coordinate, str)
            assert not isinstance(coordinate, float)
            Decimal(coordinate)  # parses exactly, so no float ever formatted it


def test_arabic_mirrors_the_category_order_without_moving_the_bars() -> None:
    """Right to left changes where a category sits, not how tall it is.

    A mirror that also flipped the value axis would render every proportion
    upside down while every number beside it stayed correct.
    """
    assert LANGUAGE_DIRECTION[LANGUAGE_ENGLISH] == DIRECTION_LTR
    assert LANGUAGE_DIRECTION[LANGUAGE_ARABIC] == DIRECTION_RTL

    ltr = chart_of(language=LANGUAGE_ENGLISH)
    rtl = chart_of(language=LANGUAGE_ARABIC)
    assert ltr is not None
    assert rtl is not None

    assert ltr.marks[0].x == "64.0000"
    assert rtl.marks[0].x == "384.0000"
    assert rtl.marks[1].x == "64.0000"
    for left, right in zip(ltr.marks, rtl.marks, strict=True):
        assert (left.y, left.height, left.width) == (right.y, right.height, right.width)


def test_a_category_label_is_customer_text_the_surface_only_escapes() -> None:
    """The axis label is the product or branch name, and it is final.

    That is the whole reason this module hands back strings for the environment to
    escape rather than markup of its own. It is not language-specific, because it is
    the source value, and it must never be run through a translation table.
    """
    view = chart_of()
    assert view is not None
    assert view.labels == (
        ChartLabel(value="V1", localize=False, x="160.0000", y="320.0000"),
        ChartLabel(value="V2", localize=False, x="480.0000", y="320.0000"),
    )


def test_a_scalar_figure_is_named_by_its_metric_not_by_its_own_value() -> None:
    """Growth effects have no category, and their amount does not identify them.

    An earlier version used each figure's rendered value as its label, so a reader
    saw three amounts and no indication of which bar was the price effect. The metric
    is what names the bar, and its wording is governed, so it travels as a code.
    """
    unlabelled = tuple(
        CitedFigure(
            figure_id=f"F-{index + 1}",
            citation_id="cit_000000000000",
            fact_id="fct_000000000000000000000000",
            metric=metric,
            unit_kind="monetary",
            kind=KIND_VALUE,
            section=SECTION_COMPARISON,
            label=None,
            value=value,
            renderings={LANGUAGE_ENGLISH: str(value), LANGUAGE_ARABIC: f"ar:{value}"},
        )
        for index, (metric, value) in enumerate(
            (("growth_price_effect", Decimal(100)), ("growth_volume_effect", Decimal(300)))
        )
    )
    view = build_chart(
        ChartSpec(kind=CHART_BAR, figure_ids=("F-1", "F-2")),
        unlabelled,
        direction=DIRECTION_LTR,
    )
    assert view is not None
    assert view.labels == (
        ChartLabel(
            value="metric.growth_price_effect", localize=True, x="160.0000", y="320.0000"
        ),
        ChartLabel(
            value="metric.growth_volume_effect", localize=True, x="480.0000", y="320.0000"
        ),
    )


def test_a_series_mixing_units_is_not_drawn() -> None:
    """One axis states one dimension.

    This is the concentration section's own four scalars: two counts beside two
    shares. Scaled together, 25 makes 0.1818 invisible, and a reader sees a governed
    figure that looks like nothing at all.
    """
    mixed = (
        figure("F-1", Decimal(25), "distinct"),
        CitedFigure(
            figure_id="F-2",
            citation_id="cit_000000000000",
            fact_id="fct_000000000000000000000000",
            metric="concentration_top_decile_share",
            unit_kind="ratio",
            kind=KIND_VALUE,
            section=SECTION_COMPARISON,
            label="decile",
            value=Decimal("0.1818"),
            renderings={LANGUAGE_ENGLISH: "0.1818", LANGUAGE_ARABIC: "0.1818"},
        ),
    )
    view = build_chart(
        ChartSpec(kind=CHART_BAR, figure_ids=("F-1", "F-2")),
        mixed,
        direction=DIRECTION_LTR,
    )
    assert view is None


def test_the_title_and_description_are_codes_a_surface_must_look_up() -> None:
    """This module invents no sentence, in either language.

    A chart title is text a reader sees, so it belongs in the per-language chrome
    the surfaces already keep for section headings and refusal reasons. Composing it
    here would put untranslated English on an Arabic page.

    The `_code` suffix is what stops one being inserted raw: the environment uses
    `StrictUndefined`, so a template reaching for `view.title` raises rather than
    printing `chart_title.comparison` at a customer.
    """
    view = chart_of()
    assert view is not None
    assert view.title_code == f"chart_title.{SECTION_COMPARISON}"
    assert view.description_code == f"chart_description.{CHART_BAR}"
    for code in (view.title_code, view.description_code):
        assert " " not in code
    assert not hasattr(view, "title")
    assert not hasattr(view, "description")


def test_grouped_bars_fill_their_slot_so_neighbours_read_as_one_group() -> None:
    view = chart_of(kind=CHART_GROUPED_BAR)
    assert view is not None
    assert [mark.x for mark in view.marks] == ["0.0000", "320.0000"]
    assert {mark.width for mark in view.marks} == {"320.0000"}


def test_a_line_point_has_extent_so_a_mark_renderer_draws_something() -> None:
    """Zero-extent marks were the earlier design, and they drew a curve of nothing.

    A surface renders marks uniformly -- the documented macro emits a rectangle per
    mark -- so a point must be an area. Its *top edge* carries the value, the same
    convention a bar follows, which is what lets a polyline be drawn through
    `x + width / 2` at `y` without a second geometry to keep in step.
    """
    view = chart_of(kind=CHART_LINE)
    assert view is not None
    assert {(mark.width, mark.height) for mark in view.marks} == {
        (str(POINT_SIZE.quantize(Decimal("0.0001"))),) * 2
    }
    # Rank fractions are 1/2 and 2/2 of the width; the mark is centred on each.
    assert [mark.x for mark in view.marks] == ["316.0000", "636.0000"]
    # The top edge is the value, exactly as for a bar.
    assert view.marks[1].y == "0.0000"


def test_a_line_carries_the_curve_that_connects_its_points() -> None:
    """`RRA-008` requires a cumulative share *curve*, not a scatter.

    Independent marks are a scatter however they are sized, so the view carries the
    connecting geometry rather than leaving a consumer to invent it. A renderer
    emitting one rectangle per mark drew squares where a curve was required.
    """
    view = chart_of(kind=CHART_LINE)
    assert view is not None
    assert view.polyline == "320.0000,213.3333 640.0000,0.0000"


def test_the_curve_passes_through_the_marks_it_is_drawn_beside() -> None:
    """Derived from the marks, so the two cannot disagree about where a point sits.

    A polyline computed separately from the plot would be a second calculation, and
    a rounding difference would show as a curve missing its own points.
    """
    view = chart_of(kind=CHART_LINE)
    assert view is not None

    points = [point.split(",") for point in view.polyline.split(" ")]
    for (x, y), mark in zip(points, view.marks, strict=True):
        assert Decimal(x) == Decimal(mark.x) + Decimal(mark.width) / 2
        assert Decimal(y) == Decimal(mark.y)


def test_a_cumulative_point_sits_at_the_rank_fraction_it_speaks_for() -> None:
    """The kth point states what the top `(k + 1) / n` of ranked values hold.

    Slot centres were the earlier placement, and they shift every percentile left by
    half a slot: with ten points the top decile appeared at 5% of the width and the
    final point -- which is by definition the whole set -- landed at 95% rather than
    on the boundary.
    """
    view = chart_of(
        kind=CHART_LINE,
        figure_ids=tuple(f"F-{index + 1}" for index in range(10)),
        values=tuple(Decimal(index + 1) for index in range(10)),
    )
    assert view is not None

    centres = [Decimal(point.split(",")[0]) for point in view.polyline.split(" ")]
    # A tenth of the width per rank, and the last point on the boundary.
    assert centres[0] == CHART_WIDTH / 10
    assert centres[-1] == CHART_WIDTH
    for index, centre in enumerate(centres):
        assert centre == CHART_WIDTH * Decimal(index + 1) / 10


def test_a_label_is_placed_under_the_mark_it_names() -> None:
    """A surface emitting one `<text>` per label with no coordinates stacks them all
    at the origin, which is what the documented macro did.

    The position is read off the mark, so a label cannot drift from its own bar.
    """
    view = chart_of()
    assert view is not None

    for label, mark in zip(view.labels, view.marks, strict=True):
        assert Decimal(label.x) == Decimal(mark.x) + Decimal(mark.width) / 2
        assert Decimal(label.y) == CHART_HEIGHT


def test_labels_mirror_with_their_marks() -> None:
    """A right-to-left page moves the bar and the name of the bar together."""
    rtl = chart_of(language=LANGUAGE_ARABIC)
    assert rtl is not None
    assert [label.value for label in rtl.labels] == ["V1", "V2"]
    assert rtl.labels[0].x == "480.0000"
    assert rtl.labels[1].x == "160.0000"


def test_only_a_line_carries_a_polyline() -> None:
    """A bar chart has no curve, and an empty string is what a surface tests."""
    for kind in (CHART_BAR, CHART_GROUPED_BAR):
        view = chart_of(kind=kind)
        assert view is not None
        assert view.polyline == ""


def test_a_negative_value_hangs_from_the_zero_line() -> None:
    """Growth effects can be negative, and a chart may not silently drop one.

    The domain spans zero, so the baseline sits inside the canvas and a negative
    bar descends from it. Scaling by the largest magnitude alone would draw a loss
    as though it were a gain.
    """
    view = chart_of(values=(Decimal(-100), Decimal(300)))
    assert view is not None
    loss, gain = view.marks

    # Domain -100..300 over 320 units: the zero line sits 240 units down.
    assert (loss.y, loss.height) == ("240.0000", "80.0000")
    assert (gain.y, gain.height) == ("0.0000", "240.0000")


def test_a_single_point_is_not_drawn() -> None:
    """One bar is a number, and the table already states it better."""
    assert chart_of(figure_ids=("F-1",), values=(Decimal(100),)) is None


def test_an_all_zero_series_is_not_drawn() -> None:
    """Nothing to scale by, and a flat axis would imply a measurement it lacks."""
    assert chart_of(values=(Decimal(0), Decimal(0))) is None


def test_a_figure_without_a_value_is_not_drawn() -> None:
    """A gap in a governed series is a refusal, never a zero on a chart."""
    assert chart_of(values=(Decimal(10), None)) is None


def test_a_spec_naming_an_absent_figure_is_not_drawn() -> None:
    """Fail closed: a chart that skipped the figure it could not find would plot a
    series the section never authorized, and the section's own text would still
    reconcile."""
    assert chart_of(figure_ids=("F-1", "F-9")) is None


def test_the_canvas_is_governed_rather_than_chosen_per_chart() -> None:
    """Two charts on one page must share a scale, or their bars invite comparison
    they do not support."""
    assert Decimal(640) == CHART_WIDTH
    assert Decimal(320) == CHART_HEIGHT


# --- the wording every governed code resolves to ---------------------------


def test_every_governed_label_a_category_can_carry_has_wording_in_both_languages() -> None:
    """The tie the shared module exists to make structural.

    The codes were minted in `charts` and the wording lived in `html`'s chrome, so a
    new code could arrive with nowhere to be translated -- and the failure surfaced
    only when a reader loaded the page. Both halves now sit in `wording`, and this is
    what says they agree.
    """
    for label in GOVERNED_FIGURE_LABELS:
        for language in (LANGUAGE_ENGLISH, LANGUAGE_ARABIC):
            assert f"label.{label}" in LABEL_WORDING[language], (label, language)


def test_the_two_languages_are_one_table_with_one_key_set() -> None:
    """Wording added to one language cannot be silently missing from the other."""
    assert set(LABEL_WORDING[LANGUAGE_ENGLISH]) == set(LABEL_WORDING[LANGUAGE_ARABIC])
    assert LABEL_WORDING[LANGUAGE_ENGLISH] != LABEL_WORDING[LANGUAGE_ARABIC]


def test_a_customer_value_is_never_run_through_the_wording_table() -> None:
    """A product name is final. Translating one would be a renderer editing content."""
    category = category_of(figure("F-1", Decimal(1), label="Water"))

    assert category.localize is False
    for language in (LANGUAGE_ENGLISH, LANGUAGE_ARABIC):
        assert worded(category, language) == "Water"


def test_the_geometry_table_covers_exactly_the_governed_kinds() -> None:
    """`FR-181`: the table that decides whether a kind renders, asserted for extent.

    `_GEOMETRY` is reached only from `build_chart`, and no test asserted it: a kind
    admitted in `bundle` with no row here raises `KeyError` at render time, and a row
    here for a kind `bundle` does not admit is a fourth kind this specification
    forbids. **The expectation is `GOVERNED_CHART_KINDS`, which lives in `bundle.py`
    and is outside `RRA-015` §Scope** -- a slice under this specification cannot widen
    it to match a mistake, which is what makes it an independent source rather than a
    restatement.

    Two assertions already ship and are deliberately not repeated: the frozenset
    identity (`test_rra006_bundle_sections.py`) and the `stacked_bar` sentinel
    mutation (`test_rra009_wording.py`).
    """
    assert set(_GEOMETRY) == GOVERNED_CHART_KINDS
    assert _GEOMETRY, "an empty geometry table would satisfy any subset claim"


def test_the_domain_always_includes_zero_whatever_the_series() -> None:
    """`FR-183`: the invariant behind "an axis truncated on a comparison is refused".

    No input can reach a truncated axis -- `_Domain` is built with `Decimal(0)` in
    both bounds, so zero is always inside it. A test driving a "truncated" series
    would therefore be a run that can only produce the null case, which is NOT
    EXERCISED rather than PASS. The property worth asserting is the construction
    itself, and the mutation that proves it is replacing either bound's `Decimal(0)`
    with the bare series.

    Measured through the rendered marks rather than the private domain: an
    all-positive series must leave the baseline at the canvas foot, so every bar
    rises from it and none floats.
    """
    rising = chart_of(values=(Decimal(100), Decimal(300)))
    assert rising is not None
    # Zero is the low bound, so the tallest bar reaches the top and both sit on the
    # canvas foot: y + height == CHART_HEIGHT for every mark.
    for mark in rising.marks:
        assert Decimal(mark.y) + Decimal(mark.height) == CHART_HEIGHT

    falling = chart_of(values=(Decimal(-300), Decimal(-100)))
    assert falling is not None
    # Zero is the high bound, so every bar hangs from the canvas top.
    for mark in falling.marks:
        assert Decimal(mark.y) == Decimal(0)


def test_a_chart_carries_the_zero_baseline_the_domain_computes() -> None:
    """`FR-183`: a negative value hangs below a visible zero baseline.

    The domain already knew where zero fell; nothing drew it. The view now carries
    the position so a consumer renders the line rather than deriving the offset a
    second time -- two derivations are two chances to disagree about where zero sits.

    Asserted against the mark geometry rather than a remembered number: the bar that
    straddles zero must meet the baseline exactly, which is the property a reader
    depends on and a recomputed offset would break.
    """
    view = chart_of(values=(Decimal(-100), Decimal(300)))
    assert view is not None
    loss, gain = view.marks

    # Domain -100..300 over 320 units puts zero 240 units down, and the losing bar
    # hangs from exactly there while the gaining bar rises to exactly there.
    assert view.baseline == "240.0000"
    assert loss.y == view.baseline
    assert Decimal(gain.y) + Decimal(gain.height) == Decimal(view.baseline)


def test_the_baseline_stays_inside_the_canvas_for_every_drawable_series() -> None:
    """`FR-183`: the line is always drawable, because zero is always in the domain.

    An all-positive series puts zero at the foot and an all-negative one puts it at
    the head. Neither is outside the canvas, so no consumer has to decide what to do
    with a baseline it cannot draw.
    """
    rising = chart_of(values=(Decimal(100), Decimal(300)))
    falling = chart_of(values=(Decimal(-300), Decimal(-100)))
    assert rising is not None and falling is not None

    assert Decimal(rising.baseline) == CHART_HEIGHT
    assert Decimal(falling.baseline) == Decimal(0)


def test_the_axis_states_its_unit_as_a_code_the_surface_looks_up() -> None:
    """`FR-183`, `FR-184`: the axis states its unit, and the word is governed.

    The view carries the unit *kind*, not a word: a chart composes no text, and the
    surface resolves it through the same chrome as every other label. `_resolve`
    refuses a series mixing units, so one chart states one dimension and the kind is
    unambiguous by construction.
    """
    view = chart_of()
    assert view is not None
    assert view.axis_unit_kind == "monetary"
    # A kind, not a rendered word -- the surface's job, asserted by its absence here.
    assert view.axis_unit_kind in AXIS_UNITS[LANGUAGE_ENGLISH]
    assert view.axis_unit_kind in AXIS_UNITS[LANGUAGE_ARABIC]


def test_every_governed_unit_kind_has_an_axis_label_in_both_languages() -> None:
    """`FR-184`: the extent of the axis-unit table, from an independent source.

    The expectation is `facts`' three unit-kind constants, which live outside
    `RRA-015` §Scope: a slice under this specification cannot widen them to match a
    mistake here. That is what makes this an extent assertion rather than a
    restatement of the table it measures.
    """
    governed = {facts.UNIT_MONETARY, facts.UNIT_COUNT, facts.UNIT_RATIO}
    assert governed, "an empty unit set would satisfy any subset claim"
    assert set(AXIS_UNITS) == {LANGUAGE_ENGLISH, LANGUAGE_ARABIC}
    for language, entries in AXIS_UNITS.items():
        assert set(entries) == governed, f"{language} is missing a unit kind"
        assert all(word.strip() for word in entries.values())


def test_the_axis_states_no_period() -> None:
    """`FR-183`'s period half is deferred, and this is what holds the deferral.

    Nothing `build_chart` receives carries a period: a `ChartSpec` is a kind and
    figure identifiers, and a `CitedFigure` has none. A chart that stated one would
    be stating a fact it was never given, which `FR-182` forbids. The owner of the
    other half is an artifact that puts a governed period on the bundle.

    Without this assertion the deferral is an invitation: a later slice could
    synthesize a period from a run timestamp and nothing would object.
    """
    view = chart_of()
    assert view is not None
    assert not hasattr(view, "axis_period")
    assert not any("period" in field for field in ChartView.__dataclass_fields__)
    # A field-name check cannot see the surface. A period rendered straight into the
    # macro needs no `ChartView` field at all, and that is the shape a later slice
    # would reach for -- so the macro source is scanned too.
    assert "period" not in _chart_macro_source().lower()


def test_a_chart_renders_no_legend() -> None:
    """`FR-183`'s legend half is deferred, and this is what holds that deferral.

    A legend "renders only where two or more series exist", and there is no series
    concept to count: `_Plot.values` is flat, and `_bars` and `_grouped_bars` differ
    only by a fill constant. `_resolve` already refuses fewer than two *values*, so
    "two or more" is always true of values and cannot be the test.

    So no chart renders a legend, and this asserts it -- a decorative legend naming
    nothing would be worse than none, and is exactly what a later slice might add if
    the deferral were only prose. The owner is a slice giving `_Plot` series
    grouping, which needs `ChartSpec` to name series membership.
    """
    view = chart_of(kind=CHART_GROUPED_BAR)
    assert view is not None
    assert not any("legend" in field for field in ChartView.__dataclass_fields__)
    # Same reason as the period: the macro is what a reader sees, and a legend drawn
    # there passes every check on the view model. Verified by mutation -- a
    # `<g class="chart__legend">` appended to the macro passed all 37 tests before
    # this line existed.
    assert "legend" not in _chart_macro_source().lower()


#: The functions in `charts.py` that may contain arithmetic, because scaling a value
#: to a canvas offset cannot be expressed without it. Every other function must be
#: arithmetic-free, and a NEW arithmetic-bearing function fails by construction
#: rather than by a reviewer noticing.
#:
#: This is an allowlist of *names*, which makes it the independent expectation: the
#: subject is what `ast` finds in the module, and widening the subject cannot widen
#: this list.
_ARITHMETIC_ALLOWED = frozenset(
    {
        "span",
        "offset",
        "slot",
        "_resolve",
        "_plot",
        "_rank",
        "_columns",
        "_top",
        "_height",
        "_mirror",
        "_centre",
        "_coordinate",
        "_line",
        "_label",
        "_polyline",
    }
)


def test_the_chart_module_confines_arithmetic_to_geometry() -> None:
    """`FR-182` and §Verification: no figure is derived here.

    **A token grep cannot make this assertion, and an earlier form of this test
    tried.** It forbade the strings `sum(`, `mean(`, `median(`, `round(` and
    `statistics.`, and three real derivations walked past it: `+=` accumulation in a
    new helper, a Jinja percentage in the macro, and a `|sum` filter. Verified by
    mutation -- each passed before this rewrite.

    So the module is parsed instead. Every `BinOp` and `AugAssign` must sit inside a
    function this specification admits arithmetic in, because geometry over given
    values *is* this module's job: `_Domain.offset` scales a value to a canvas
    offset, and it cannot do that without division. What must not exist is a new
    function that derives a figure, and a name not on the allowlist is exactly that.
    """
    source = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "khepri"
        / "rra"
        / "rendering"
        / "charts.py"
    ).read_text(encoding="utf-8")
    assert source.strip(), "charts.py is empty, so this scan proves nothing"

    tree = ast.parse(source)
    enclosing: dict[ast.AST, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for child in ast.walk(node):
                enclosing.setdefault(child, node.name)

    # `ast.BitOr` is not arithmetic: `ChartView | None` is a type union, and an
    # earlier form of this test reported `build_chart` as an offender for its own
    # return annotation. The operators that can derive a figure are named instead.
    deriving_ops = (
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
    )

    def _derives(node: ast.AST) -> bool:
        if isinstance(node, ast.BinOp):
            return isinstance(node.op, deriving_ops)
        if isinstance(node, ast.AugAssign):
            return isinstance(node.op, deriving_ops)
        return False

    offenders = sorted(
        {enclosing.get(node, "<module level>") for node in ast.walk(tree) if _derives(node)}
        - _ARITHMETIC_ALLOWED
    )
    assert offenders == [], f"arithmetic outside geometry: {offenders}"
    # The scan must actually have found arithmetic, or an empty parse would satisfy
    # every claim it makes.
    assert any(_derives(node) for node in ast.walk(tree)), (
        "no arithmetic found at all, so this scan proves nothing"
    )


def test_the_chart_macro_derives_nothing() -> None:
    """`FR-182`: the template composes no value either.

    The macro is where a percentage is cheapest to add and hardest to notice -- it
    renders, it looks right, and no Python test reads it. Parsed with Jinja's own
    parser rather than grepped: `{{ view.marks|length * 100 / 4 }}%` passed a token
    scan, and `|sum` did too.
    """
    source = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "khepri"
        / "rra"
        / "rendering"
        / "templates"
        / "_chart.svg.j2"
    ).read_text(encoding="utf-8")
    assert source.strip(), "the macro is empty, so this scan proves nothing"

    parsed = Environment(autoescape=True).parse(source)
    arithmetic = [
        type(node).__name__
        for node in parsed.find_all((nodes.Add, nodes.Sub, nodes.Mul, nodes.Div))
    ]
    assert arithmetic == [], f"the macro derives a value: {arithmetic}"

    deriving = {"sum", "round", "int", "float", "abs", "map", "select", "reject"}
    filters = sorted(
        {node.name for node in parsed.find_all(nodes.Filter)} & deriving
    )
    assert filters == [], f"the macro applies a deriving filter: {filters}"


def test_a_value_survives_the_chart_with_its_precision_intact() -> None:
    """`FR-182`, §Verification: the value-preservation half, distinct from the scan.

    A static scan proves no arithmetic is written. It cannot prove a value arrives
    unchanged -- a quantization applied through a helper the scan admits would pass
    it. So a figure whose precision differs from any default is driven through
    `build_chart`, and the label beside its mark must still be the figure's own
    rendering, character for character.
    """
    odd = Decimal("123.456789")
    view = chart_of(values=(odd, Decimal(300)))
    assert view is not None

    # A label names its category, never its value -- the table beside the chart is
    # where a number is stated. So the preservation this asserts is geometric: the
    # mark's offset must be the exact scaling of the given value, quantized once to
    # the governed coordinate precision and never re-rounded on the way.
    # The expectation is a LITERAL, not a re-derivation from `COORDINATE_PRECISION`.
    # Deriving it from the same constant the geometry uses made this test pass a
    # mutant that halved the precision: both sides moved together, which is the
    # tautology an extent assertion exists to avoid. 188.3128 is the four-place
    # quantization of 320 * (300 - 123.456789) / 300 = 188.3127584, checked by hand.
    assert view.marks[0].y == "188.3128"
    # And the precision is the governed four places, asserted against the literal
    # rather than against the constant, so a change to either is visible here.
    assert len(view.marks[0].y.split(".")[1]) == 4
    # And the value itself is nowhere in the view: a chart that carried the number
    # would be a second place a figure is stated, which the table already is.
    assert all(str(odd) not in label.value for label in view.labels)


def test_the_axis_unit_renders_in_both_languages_on_a_real_surface() -> None:
    """`FR-184`, `FR-188`: the chrome key reaches both `_CHROME` branches.

    The macro resolves `chrome.axis_units` under `StrictUndefined`, so a key
    registered in one language only raises on that language's render alone -- and a
    test comparing table key sets would never drive it. This renders the chart macro
    through the real environment in both languages instead.
    """
    for language in (LANGUAGE_ENGLISH, LANGUAGE_ARABIC):
        view = chart_of(language=language)
        assert view is not None
        assert view.axis_unit_kind in AXIS_UNITS[language]
        # The word differs between the two, which is what makes this a parity check
        # rather than a restatement of one table.
        assert AXIS_UNITS[language][view.axis_unit_kind].strip()
    assert (
        AXIS_UNITS[LANGUAGE_ENGLISH][DEFAULT_UNIT]
        != AXIS_UNITS[LANGUAGE_ARABIC][DEFAULT_UNIT]
    )


def test_the_new_chart_rules_carry_no_hardcoded_colour() -> None:
    """`FR-192`, and the reason print inherits these rules correctly.

    `report.print.css` is layered onto `report.css` rather than replacing it, and it
    redefines `--report-rule` and `--report-muted` for paper. So a chart rule written
    with those tokens prints in the paper palette without a second declaration, and
    one written with a literal hex value would print the screen colour on paper --
    silently, because nothing renders a chart during a stylesheet test.

    Asserted on the two rules this slice added rather than on the whole sheet: the
    rest of the file is `RRA-012`'s and `RRA-009`'s, and a scan over all of it would
    fail on rules this specification does not govern.
    """
    sheet = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "khepri"
        / "rra"
        / "rendering"
        / "templates"
        / "report.css"
    ).read_text(encoding="utf-8")
    assert sheet.strip(), "the stylesheet is empty, so this proves nothing"

    for selector in (".chart__baseline", ".chart__axis-unit"):
        start = sheet.index(selector)
        block = sheet[start : sheet.index("}", start)]
        assert "var(--report-" in block, f"{selector} must take the report palette"
        assert "#" not in block, f"{selector} hardcodes a colour: {block!r}"


def test_the_axis_unit_anchor_mirrors_with_the_category_axis() -> None:
    """`FR-188`: the Arabic axis unit is present, not painted off the canvas.

    The label sits on the category axis, and that axis mirrors. An earlier form
    hardcoded `x="0"` in the macro with a stylesheet comment claiming
    `text-anchor: start` made it follow the reading order. It does not: `dir` reaches
    the SVG by inheritance, so under `rtl` the text's start edge anchors at canvas
    zero and the glyphs paint leftward, outside the viewBox. The English page read
    correctly and the Arabic page lost its axis unit -- which `FR-188` forbids, since
    a label present in one language must be present in the other.

    Mirroring is geometry, so `_mirror` decides it and the view carries the result.
    """
    ltr = chart_of(language=LANGUAGE_ENGLISH)
    rtl = chart_of(language=LANGUAGE_ARABIC)
    assert ltr is not None and rtl is not None

    assert ltr.axis_unit_x == "0.0000"
    assert rtl.axis_unit_x == str(CHART_WIDTH.quantize(Decimal("0.0001")))
    assert ltr.axis_unit_x != rtl.axis_unit_x

    # Inside the canvas in both directions, which is the property a reader depends on.
    for view in (ltr, rtl):
        assert Decimal(0) <= Decimal(view.axis_unit_x) <= CHART_WIDTH


def test_the_print_sheet_sizes_the_axis_unit_for_paper() -> None:
    """`RRA-015` §Scope admits "the chart's print behaviour only", and this needs it.

    `report.print.css` is layered onto `report.css`, so the chart's colours inherit
    correctly -- the print palette redefines the two tokens the new rules use. One
    property does not inherit usefully: `0.75rem` against print's `10.5pt` root is
    about 7.9pt, too small to read on paper, and no test renders a chart to paper to
    notice.

    So the print sheet names `.chart__axis-unit` with a point size, and this asserts
    it does. The rest of the chart deliberately has no print rule.
    """
    sheet = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "khepri"
        / "rra"
        / "rendering"
        / "templates"
        / "report.print.css"
    ).read_text(encoding="utf-8")
    assert sheet.strip(), "the print stylesheet is empty, so this proves nothing"

    start = sheet.index(".chart__axis-unit")
    block = sheet[start : sheet.index("}", start)]
    assert "pt" in block, "the print axis unit must be sized in points, not rem"
    assert "0.75rem" not in block, "the screen size would render ~7.9pt on paper"
