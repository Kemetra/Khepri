"""What a plotted figure is called, and what that name says in each language.

**Two things, in one module, because they are two halves of one guarantee.** A chart
mark is named either by the customer's own category -- a product, a branch -- or, when
the figure has no category, by a governed code standing for its metric or its
comparison mode. `category_of` makes that choice. `LABEL_WORDING` is what each of
those codes says in each governed language.

They were previously in different modules: the codes were minted in
`rendering.charts` and the wording lived in `rendering.html`'s chrome table, with
nothing tying the two together. A new code could be minted with nowhere to be
translated, and the failure surfaced only when a reader loaded the page --
`StrictUndefined` raising, or worse, `metric.growth_price_effect` reaching an Arabic
axis. Holding both here makes that tie structural, and lets a test assert that every
code this module can produce has wording in both languages.

**Both surfaces need identical wording.** The page draws SVG and the workbook writes a
native chart, and a category that read one way on the page and another in the
spreadsheet would be the two surfaces disagreeing about what a bar is called. One
table, read by both, is what makes that impossible rather than merely unlikely.

**This module invents no arithmetic and reads no value.** It is handed a figure and
returns a name. The number a mark is drawn at comes from the figure's own `Decimal`
and its authoritative text from the figure's own rendering; neither is touched here.
"""

from __future__ import annotations

from dataclasses import dataclass

from khepri.rra.bundle import GOVERNED_FIGURE_LABELS, CitedFigure
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH


@dataclass(frozen=True, slots=True)
class ChartCategory:
    """A mark's name, and whether the surface must translate it before showing it.

    Two kinds of text reach an axis and they must not be confused. A bucket figure
    carries the customer's own product or branch name, which is final and only needs
    escaping. A scalar figure -- a growth price effect, say -- has no category, and
    its *metric* is what identifies the mark; that name is governed wording, so it is
    a code the surface resolves through `LABEL_WORDING`.

    A bare string could not tell those apart, and a surface guessing would either
    print `metric.growth_price_effect` at a reader or run a customer's product name
    through a translation table.
    """

    value: str
    localize: bool


# Every governed code `category_of` can return, in both languages. One table with one
# key set per language, so wording added to one cannot be silently missing from the
# other -- the same discipline the surfaces' own chrome tables follow.
LABEL_WORDING: dict[str, dict[str, str]] = {
    LANGUAGE_ENGLISH: {
        "metric.growth_revenue_change": "Revenue change",
        "metric.growth_price_effect": "Price effect",
        "metric.growth_volume_effect": "Volume effect",
        "label.period_over_period": "Against the previous period",
        "label.year_over_year": "Against the same period last year",
    },
    LANGUAGE_ARABIC: {
        "metric.growth_revenue_change": "التغيّر في الإيرادات",
        "metric.growth_price_effect": "أثر السعر",
        "metric.growth_volume_effect": "أثر الحجم",
        "label.period_over_period": "مقابل الفترة السابقة",
        "label.year_over_year": "مقابل الفترة نفسها من العام الماضي",
    },
}


def category_of(figure: CitedFigure) -> ChartCategory:
    """A mark's category if the figure has one, otherwise the code for its metric.

    An earlier version used the figure's own rendered *value* as its name, which
    showed several amounts and identified none of them.
    """
    if figure.label in GOVERNED_FIGURE_LABELS:
        # A governed label is an internal identifier, not customer text. Treating one
        # as final put `period_over_period` on both the English and the Arabic axis.
        return ChartCategory(value=f"label.{figure.label}", localize=True)
    if figure.label is not None:
        return ChartCategory(value=figure.label, localize=False)
    return ChartCategory(value=f"metric.{figure.metric}", localize=True)


def worded(category: ChartCategory, language: str) -> str:
    """The text one language shows for a category.

    A customer value is returned unchanged -- it is already final, and putting it
    through the table would be this module editing a product name. A governed code is
    looked up, and a missing one raises rather than falling back to the code: an
    identifier shown to a reader is the failure this module exists to prevent, and a
    fallback would ship it quietly.
    """
    if not category.localize:
        return category.value
    return LABEL_WORDING[language][category.value]
