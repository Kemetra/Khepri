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

from decimal import Decimal

from khepri.rra.bundle import (
    CHART_BAR,
    CHART_GROUPED_BAR,
    CHART_LINE,
    DIRECTION_LTR,
    DIRECTION_RTL,
    GOVERNED_FIGURE_LABELS,
    KIND_VALUE,
    LANGUAGE_DIRECTION,
    SECTION_COMPARISON,
    ChartSpec,
    CitedFigure,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.rendering.charts import (
    CHART_HEIGHT,
    CHART_WIDTH,
    POINT_SIZE,
    ChartLabel,
    ChartView,
    build_chart,
)
from khepri.rra.rendering.wording import LABEL_WORDING, category_of, worded


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
