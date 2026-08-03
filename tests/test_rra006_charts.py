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
    KIND_VALUE,
    SECTION_COMPARISON,
    ChartSpec,
    CitedFigure,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.rendering.charts import (
    CHART_HEIGHT,
    CHART_WIDTH,
    build_chart,
)


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
    direction: str = DIRECTION_LTR,
    language: str = LANGUAGE_ENGLISH,
):
    return build_chart(
        ChartSpec(kind=kind, figure_ids=figure_ids),
        figures_for_chart(values),
        direction=direction,
        language=language,
    )


def test_a_drawable_series_yields_one_mark_per_figure() -> None:
    view = chart_of()
    assert view is not None
    assert view.kind == CHART_BAR
    assert len(view.marks) == 2
    assert view.title
    assert view.description


def test_bar_geometry_is_exact_and_scaled_to_the_largest_value() -> None:
    """100 against 300 on a 400-unit canvas: a third of the height, and all of it.

    Asserted as exact strings rather than approximately. These are the coordinates
    a reader's chart is drawn from, and a governed figure's proportions are part of
    what the chart claims.
    """
    view = chart_of()
    assert view is not None
    short, tall = view.marks

    assert (short.x, short.width) == ("100.0000", "300.0000")
    assert (short.y, short.height) == ("266.6667", "133.3333")
    assert (tall.x, tall.width) == ("600.0000", "300.0000")
    assert (tall.y, tall.height) == ("0.0000", "400.0000")


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
    ltr = chart_of(direction=DIRECTION_LTR)
    rtl = chart_of(direction=DIRECTION_RTL, language=LANGUAGE_ARABIC)
    assert ltr is not None
    assert rtl is not None

    assert ltr.marks[0].x == "100.0000"
    assert rtl.marks[0].x == "600.0000"
    assert rtl.marks[1].x == "100.0000"
    for left, right in zip(ltr.marks, rtl.marks, strict=True):
        assert (left.y, left.height, left.width) == (right.y, right.height, right.width)


def test_labels_are_the_renderings_of_the_requested_language() -> None:
    """The bundle already rendered every figure, so nothing here formats a number."""
    english = chart_of(language=LANGUAGE_ENGLISH)
    arabic = chart_of(language=LANGUAGE_ARABIC)
    assert english is not None
    assert arabic is not None

    assert english.labels == ("100", "300")
    assert arabic.labels == ("ar:100", "ar:300")


def test_the_title_and_description_are_codes_rather_than_prose() -> None:
    """This module invents no sentence, in either language.

    A chart title is text a reader sees, so it belongs in the per-language tables
    the surfaces already keep for section headings and refusal reasons. Composing
    it here would put untranslated English on an Arabic page and place governed
    wording in a geometry module.
    """
    view = chart_of()
    assert view is not None
    assert view.title == f"chart_title.{SECTION_COMPARISON}"
    assert view.description == f"chart_description.{CHART_BAR}"
    for code in (view.title, view.description):
        assert " " not in code


def test_grouped_bars_fill_their_slot_so_neighbours_read_as_one_group() -> None:
    view = chart_of(kind=CHART_GROUPED_BAR)
    assert view is not None
    assert [mark.x for mark in view.marks] == ["0.0000", "500.0000"]
    assert {mark.width for mark in view.marks} == {"500.0000"}


def test_a_line_carries_points_rather_than_areas() -> None:
    """A polyline is drawn from coordinates, so a line's marks have no extent."""
    view = chart_of(kind=CHART_LINE)
    assert view is not None
    assert {(mark.width, mark.height) for mark in view.marks} == {("0.0000", "0.0000")}
    assert [mark.x for mark in view.marks] == ["250.0000", "750.0000"]


def test_a_negative_value_hangs_from_the_zero_line() -> None:
    """Growth effects can be negative, and a chart may not silently drop one.

    The domain spans zero, so the baseline sits inside the canvas and a negative
    bar descends from it. Scaling by the largest magnitude alone would draw a loss
    as though it were a gain.
    """
    view = chart_of(values=(Decimal(-100), Decimal(300)))
    assert view is not None
    loss, gain = view.marks

    # Domain -100..300 over 400 units: the zero line sits 300 units down.
    assert (loss.y, loss.height) == ("300.0000", "100.0000")
    assert (gain.y, gain.height) == ("0.0000", "300.0000")


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
    assert Decimal(1000) == CHART_WIDTH
    assert Decimal(400) == CHART_HEIGHT
