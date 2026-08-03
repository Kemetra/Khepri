"""The governed per-language wording that more than one surface has to agree on.

**Why a module rather than each surface's own chrome.** Most of a surface's furniture
is its own: a web page needs a skip link and a workbook does not. But three kinds of
wording are read by two or three surfaces at once -- what a section is called, what a
chart kind does, and what a plotted mark is named -- and every copy of those is a place
the surfaces can drift apart. A section titled one thing on the page and another in the
spreadsheet is one report making two claims about what a reader is looking at.

**Chart categories are the case that forced this.** A mark is named either by the
customer's own category -- a product, a branch -- or, when the figure has no category,
by a governed code standing for its metric or its comparison mode. `category_of` makes
that choice; `LABEL_WORDING` says what each code means. Those two lived in different
modules, the codes minted in `rendering.charts` and the wording in `rendering.html`'s
chrome, with nothing tying them together: a new code could be minted with nowhere to be
translated, and the failure surfaced only when a reader loaded the page --
`StrictUndefined` raising, or worse, `metric.growth_price_effect` reaching an Arabic
axis. Holding both here makes that tie structural, and lets a test assert that every
code `category_of` can produce has wording in both languages.

**This module invents no arithmetic and reads no value.** It is handed a figure and
returns a name. The number a mark is drawn at comes from the figure's own `Decimal` and
its authoritative text from the figure's own rendering; neither is touched here.
"""

from __future__ import annotations

from dataclasses import dataclass

from khepri.rra.bundle import (
    GOVERNED_FIGURE_LABELS,
    ORDERED_SECTIONS,
    CitedFigure,
)
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


# What each governed section is called. The page shows it as a heading, the printed
# report as the heading a page break lands before, and the workbook as the title of the
# chart drawn on that section's sheet -- which is also what makes that chart accessible:
# an embedded object with no programmatic text tells a screen reader nothing about which
# analysis it belongs to.
SECTION_HEADINGS: dict[str, dict[str, str]] = {
    LANGUAGE_ENGLISH: {
        "overview": "Overview",
        "comparison": "Period comparison",
        "concentration": "Concentration",
        "growth": "Growth decomposition",
        "basket": "Basket structure",
    },
    LANGUAGE_ARABIC: {
        "overview": "نظرة عامة",
        "comparison": "مقارنة الفترات",
        "concentration": "التركّز",
        "growth": "تحليل النمو",
        "basket": "بنية السلة",
    },
}

# What each chart kind shows, as the alternative text a reader who cannot see it gets.
# Keyed by the `chart_description.<kind>` codes `charts.ChartView` carries, so a surface
# resolves a description the same way it resolves a category.
CHART_DESCRIPTIONS: dict[str, dict[str, str]] = {
    LANGUAGE_ENGLISH: {
        "chart_description.bar": "Bar chart of the figures in this section",
        "chart_description.grouped_bar": "Grouped bar chart of the figures in this section",
        "chart_description.line": "Cumulative share curve over the ranked values",
    },
    LANGUAGE_ARABIC: {
        "chart_description.bar": "رسم بالأعمدة للأرقام في هذا القسم",
        "chart_description.grouped_bar": "رسم بأعمدة مجمّعة للأرقام في هذا القسم",
        "chart_description.line": "منحنى النصيب التراكمي عبر القيم المرتّبة",
    },
}

# Every governed section has a heading in every governed language, checked at import
# rather than left to a test. A section added to `ORDERED_SECTIONS` without wording
# would otherwise reach a reader as a `KeyError` mid-render on one surface and as a
# missing chart title on another.
for _language, _headings in SECTION_HEADINGS.items():
    if set(_headings) != set(ORDERED_SECTIONS):
        raise RuntimeError("every governed section needs a heading in every language")


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
