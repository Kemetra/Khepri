"""Governed chart geometry as an exact view model.

**This module returns geometry, not markup.** An earlier design had it return an SVG
fragment as a `str`, and these templates cannot render one. `build_environment()`
sets `autoescape=True` unconditionally and `html.py` states the rule outright:
nothing reachable from the bundle is ever marked safe, because a page with one
`|safe` in it has an escaping convention rather than an escaping guarantee. A
`{{ section.chart_svg }}` holding markup reaches the reader as `&lt;svg …`, so the
page would display chart source as text -- on the web surface and, through template
inheritance, on the printed one.

The two exits from that are `|safe` and `Markup`, and they are the same exit: both
move the escaping decision out of the environment and into whoever remembers to
apply it, on the one path customer-derived labels travel. Chart axis labels *are*
customer values.

So the boundary moves instead. This module resolves geometry to strings and a Jinja
macro writes the elements. Tags come from template source, which is trusted because
it is source; labels pass through the same autoescaping as every table cell, which
is what makes a value named `<script>` inert here for the same reason it is inert
there. **Nothing in this module escapes anything** -- escaping here as well would
put `&amp;lt;` in a customer's product name, and escaping here *instead* would move
the guarantee off the environment.

**It invents no prose either.** `title` and `description` are governed codes, for the
same reason the coordinates are not markup: the wording a reader sees belongs in the
per-language tables the surfaces already keep for section headings and refusal
reasons. Composing a sentence here would put untranslated English on an Arabic page.

**Geometry is `Decimal` throughout, and becomes a string only when a mark is built.**
A float coordinate would mean binary floating point reached the surface of a governed
figure, which is the thing `KHEPRI-DEC-005` prohibits and the workbook's
`write_string` discipline exists to prevent.

**The domain spans zero, so a negative value hangs from the baseline.** Growth
decomposition effects are routinely negative. Scaling by the largest magnitude alone
would draw a loss with the same geometry as a gain.

**Undrawable series return `None` rather than raising.** The table is the
authoritative presentation, and a chart may never suppress governed analysis: one
point, an all-zero series, a figure with no value, and a spec naming a figure the
section does not carry all yield no chart and no error. Skipping the missing figure
instead would plot a series the section never authorized, while the section's own
text still reconciled.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from khepri.rra.bundle import (
    CHART_BAR,
    CHART_GROUPED_BAR,
    CHART_LINE,
    DIRECTION_RTL,
    ChartSpec,
    CitedFigure,
)

# One canvas for every chart in a report. Two charts drawn to different scales sit
# on one page inviting a comparison their geometry does not support.
CHART_WIDTH = Decimal(1000)
CHART_HEIGHT = Decimal(400)

# How much of its slot a bar occupies. A plain bar leaves a gap so each reads as its
# own category; a grouped bar fills the slot so neighbours read as one group. That
# is the whole difference between the two kinds here -- what the grouping *means* is
# the section's, and this module invents no structure for it.
BAR_FILL = Decimal("0.6")
GROUPED_FILL = Decimal(1)

# Places kept in a coordinate string. Four, matching the governed ratio precision, so
# a quantized division never has to be rounded again by a renderer.
COORDINATE_PRECISION = 4

_SCALE = Decimal(1).scaleb(-COORDINATE_PRECISION)


@dataclass(frozen=True, slots=True)
class ChartMark:
    """One drawn thing, addressed in canvas units as exact decimal strings."""

    x: str
    y: str
    width: str
    height: str


@dataclass(frozen=True, slots=True)
class ChartView:
    """What a macro needs to draw one chart, and nothing it could misread.

    `title` and `description` are governed codes the surface translates.
    `labels` holds the bundle's own rendering of each value in the requested
    language, so no number is formatted twice.
    """

    kind: str
    title: str
    description: str
    marks: tuple[ChartMark, ...]
    labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Domain:
    """The value range a chart is drawn against, always including zero.

    `zero` is where the baseline falls from the top of the canvas, which is what
    lets a negative bar hang from it rather than being drawn as a positive one.
    """

    low: Decimal
    high: Decimal

    @property
    def span(self) -> Decimal:
        return self.high - self.low

    def offset(self, value: Decimal) -> Decimal:
        """How far below the top of the canvas this value sits."""
        return CHART_HEIGHT * (self.high - value) / self.span

    @property
    def zero(self) -> Decimal:
        return self.offset(Decimal(0))


@dataclass(frozen=True, slots=True)
class _Plot:
    """One resolved, drawable series: its values, its domain, and its direction."""

    values: tuple[Decimal, ...]
    domain: _Domain
    mirrored: bool

    @property
    def slot(self) -> Decimal:
        return CHART_WIDTH / len(self.values)


def build_chart(
    spec: ChartSpec,
    figures: tuple[CitedFigure, ...],
    *,
    direction: str,
    language: str,
) -> ChartView | None:
    """The geometry for one chart, or nothing when the series cannot be drawn."""
    resolved = _resolve(spec, figures)
    if resolved is None:
        return None
    plot = _plot(resolved, mirrored=direction == DIRECTION_RTL)
    if plot is None:
        return None
    return ChartView(
        kind=spec.kind,
        title=f"chart_title.{resolved[0].section}",
        description=f"chart_description.{spec.kind}",
        marks=_GEOMETRY[spec.kind](plot),
        labels=tuple(figure.renderings.get(language, "") for figure in resolved),
    )


def _resolve(
    spec: ChartSpec,
    figures: tuple[CitedFigure, ...],
) -> tuple[CitedFigure, ...] | None:
    """The spec's figures in the order it named them, or nothing if one is missing.

    Fail closed rather than skipping: a chart drawn from the figures it happened to
    find would plot a series the section never authorized, and the section's own
    text would still reconcile.
    """
    known = {figure.figure_id: figure for figure in figures}
    found = [known.get(figure_id) for figure_id in spec.figure_ids]
    if any(figure is None for figure in found):
        return None
    return tuple(figure for figure in found if figure is not None)


def _plot(resolved: tuple[CitedFigure, ...], *, mirrored: bool) -> _Plot | None:
    """A drawable series, or nothing.

    Three refusals, all silent by design. One point is a number the table states
    better. A missing value is a governed gap, and a chart may not render it as a
    zero. A domain of no width has nothing to scale by, and a flat axis implies a
    measurement it does not have.
    """
    if len(resolved) < 2:
        return None
    if any(figure.value is None for figure in resolved):
        return None
    values = tuple(figure.value for figure in resolved if figure.value is not None)
    domain = _Domain(low=min(*values, Decimal(0)), high=max(*values, Decimal(0)))
    if domain.span == 0:
        return None
    return _Plot(values=values, domain=domain, mirrored=mirrored)


def _bars(plot: _Plot) -> tuple[ChartMark, ...]:
    """One bar per value, each centred in its slot with a gap either side."""
    return _columns(plot, fill=BAR_FILL)


def _grouped_bars(plot: _Plot) -> tuple[ChartMark, ...]:
    """Bars filling their slots, so neighbours read as one group."""
    return _columns(plot, fill=GROUPED_FILL)


def _line(plot: _Plot) -> tuple[ChartMark, ...]:
    """Points at slot centres, with no extent: a polyline is drawn from coordinates."""
    return tuple(
        ChartMark(
            # A zero-width mark centres itself: `(slot - 0) / 2` is the slot centre.
            x=_coordinate(_placed(plot, index, width=Decimal(0))),
            y=_coordinate(plot.domain.offset(value)),
            width=_coordinate(Decimal(0)),
            height=_coordinate(Decimal(0)),
        )
        for index, value in enumerate(plot.values)
    )


def _columns(plot: _Plot, *, fill: Decimal) -> tuple[ChartMark, ...]:
    """Rectangles rising from, or hanging beneath, the zero line."""
    width = plot.slot * fill
    return tuple(
        ChartMark(
            x=_coordinate(_placed(plot, index, width=width)),
            y=_coordinate(_top(plot, value)),
            width=_coordinate(width),
            height=_coordinate(_height(plot, value)),
        )
        for index, value in enumerate(plot.values)
    )


def _top(plot: _Plot, value: Decimal) -> Decimal:
    """Where a rectangle starts: at the value if it rises, at zero if it hangs."""
    if value < 0:
        return plot.domain.zero
    return plot.domain.offset(value)


def _height(plot: _Plot, value: Decimal) -> Decimal:
    """Always positive: the distance between the value and the zero line."""
    return abs(plot.domain.zero - plot.domain.offset(value))


def _placed(plot: _Plot, index: int, *, width: Decimal) -> Decimal:
    """Where a mark sits along the category axis, mirrored for right-to-left.

    Only the category axis mirrors. Flipping the value axis as well would render
    every proportion upside down while every number beside it stayed correct.
    """
    x = plot.slot * index + (plot.slot - width) / 2
    if plot.mirrored:
        return CHART_WIDTH - x - width
    return x


def _coordinate(value: Decimal) -> str:
    return str(value.quantize(_SCALE))


# Dispatch by kind rather than through an if-chain: a lookup keeps each geometry
# function at its own low complexity, where a chain would add every branch to one.
_GEOMETRY = {
    CHART_BAR: _bars,
    CHART_GROUPED_BAR: _grouped_bars,
    CHART_LINE: _line,
}
