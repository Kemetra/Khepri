"""`RRA-015` FR-183: a chart's labels are drawn beside its marks, never over them.

SCRUM-21's first acceptance run (A3) found the basket chart drawing its category labels
over the bottoms of its bars, with their descenders clipped, and the axis unit colliding
with the first bar. The cause was geometry: `charts._label` placed every label at
`y = CHART_HEIGHT`, which was the foot of the plotting area itself, so any bar reaching
the zero line at the canvas foot sat underneath its own name.

The plot is unchanged: marks, domain and baseline keep their coordinates. The canvas
grows beneath it by a band for the category labels and a row under that for the axis
unit, which keeps the start-edge, canvas-foot placement `U1-03` gave it (#481).

The geometry is asserted on the view model, and the promise -- no word painted over a
mark, none clipped by the canvas -- is measured in Chromium on the web report and on the
document the PDF renderer printed, in both languages.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from khepri.rra.bundle import CHART_BAR, CHART_GROUPED_BAR, CHART_LINE
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.rendering import charts
from tests.rra_printed_support import (
    LANGUAGES,
    a4_content_width_px,
    printed_documents,
    web_documents,
)
from tests.test_rra006_charts import chart_of
from tests.test_rra006_pdf_surface import chromium_available

needs_chromium = pytest.mark.skipif(
    not chromium_available(),
    reason="the pinned Chromium is not installed; run `playwright install chromium`",
)


def _label_em() -> Decimal:
    """The label's font size in user units, read from the rule that sets it."""
    sheet = (Path(charts.__file__).parent / "templates" / "report.css").read_text(encoding="utf-8")
    block = re.search(r"\.chart__label\s*\{(?P<body>[^}]*)\}", sheet)
    assert block is not None, "report.css states no .chart__label rule"
    size = re.search(r"font-size:\s*(?P<px>\d+)px\s*;", block.group("body"))
    assert size is not None, ".chart__label no longer sets its size in px"
    return Decimal(size.group("px"))


@pytest.mark.parametrize("language", [LANGUAGE_ENGLISH, LANGUAGE_ARABIC])
@pytest.mark.parametrize("kind", [CHART_BAR, CHART_GROUPED_BAR, CHART_LINE])
def test_labels_sit_in_a_band_beneath_the_plot(kind: str, language: str) -> None:
    """Every value lies in the plot; every label's glyphs start below the lowest mark.

    A bar ends at the plot foot at most. A line's point carries its value on its top
    edge and hangs `POINT_SIZE` beneath it, so a point at zero reaches past the foot;
    a label a full em below the lowest mark cannot meet it. Zero is in each series so
    that a point sits at the foot and the test is not passed by a curve that never
    reaches it.
    """
    for values in ((Decimal(0), Decimal(300)), (Decimal(-100), Decimal(300))):
        view = chart_of(kind=kind, values=values, language=language)
        assert view is not None
        assert Decimal(view.height) == charts.CHART_HEIGHT > charts.PLOT_HEIGHT
        lowest = max(Decimal(mark.y) + Decimal(mark.height) for mark in view.marks)
        for mark in view.marks:
            assert Decimal(mark.y) <= charts.PLOT_HEIGHT
        for label in view.labels:
            assert lowest + _label_em() <= Decimal(label.y) < charts.CHART_HEIGHT


#: For every chart: its kind, its label and mark counts, and every overlap between a
#: word and a mark, between two rows of words, or between a word and the canvas edge.
_CHART_COLLISIONS = """() => {
  const meets = (a, b) =>
    Math.min(a.right, b.right) - Math.max(a.left, b.left) > 0.5 &&
    Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 0.5;
  return [...document.querySelectorAll('svg.chart')].map(svg => {
    const canvas = svg.getBoundingClientRect();
    const marks = [...svg.querySelectorAll('.chart__mark')]
      .map(mark => mark.getBoundingClientRect()).filter(box => box.height > 0.5);
    const labels = [...svg.querySelectorAll('.chart__label')];
    const unit = svg.querySelector('.chart__axis-unit');
    const faults = [];
    for (const word of [...labels, unit]) {
      const box = word.getBoundingClientRect();
      const name = word.textContent.trim();
      if (marks.some(mark => meets(box, mark))) faults.push(`over a mark: ${name}`);
      // Top and bottom only. The concentration curve's last point sits on the right
      // edge by design (`charts._rank`), so its label is centred there and half of it
      // leaves the canvas sideways. That is a separate, recorded finding, not A3.
      if (box.top < canvas.top - 0.5 || box.bottom > canvas.bottom + 0.5) {
        faults.push(`clipped by the canvas: ${name}`);
      }
    }
    const unitBox = unit.getBoundingClientRect();
    for (const label of labels) {
      if (meets(label.getBoundingClientRect(), unitBox)) {
        faults.push(`label meets the axis unit: ${label.textContent.trim()}`);
      }
    }
    return {kind: svg.getAttribute('class'), labels: labels.length, marks: marks.length, faults};
  });
}"""


def _collisions(
    documents: dict[str, str], *, width: int, media: str, text: str = "100%"
) -> dict[str, list]:
    from playwright.sync_api import sync_playwright

    found: dict[str, list] = {}
    with sync_playwright() as play:
        browser = play.chromium.launch()
        try:
            for language in LANGUAGES:
                page = browser.new_page(viewport={"width": width, "height": 1000})
                page.emulate_media(media=media)
                page.set_content(documents[language], wait_until="load")
                # Text scaling as `test_rra016_journey_composition` applies it. The axis
                # unit is sized in `rem` and grows with it; the labels do not.
                page.add_style_tag(content=f"html {{ font-size: {text} }}")
                page.evaluate("() => document.fonts.ready")
                found[language] = page.evaluate(_CHART_COLLISIONS)
                page.close()
        finally:
            browser.close()
    return found


def _assert_no_collisions(charts: dict[str, list]) -> None:
    for language in LANGUAGES:
        kinds = {chart["kind"] for chart in charts[language] if chart["labels"]}
        # A3 was seen on the basket bar chart and a negative grouped bar; a fixture
        # that stopped drawing either would pass having measured nothing.
        assert {"chart chart--bar", "chart chart--grouped_bar"} <= kinds, (language, kinds)
        faults = [(chart["kind"], fault) for chart in charts[language] for fault in chart["faults"]]
        assert faults == [], f"{language}: {faults}"


@pytest.mark.browser
@needs_chromium
@pytest.mark.parametrize(("width", "text"), [(1440, "100%"), (390, "200%")])
def test_no_chart_word_meets_a_mark_on_the_web_report(width: int, text: str) -> None:
    """At the desktop width, and at the narrow width under `FR-189`'s 200% text."""
    charts_found = _collisions(web_documents(), width=width, media="screen", text=text)
    _assert_no_collisions(charts_found)


@pytest.mark.browser
@needs_chromium
def test_no_chart_word_meets_a_mark_on_the_printed_report() -> None:
    documents = printed_documents()
    _assert_no_collisions(_collisions(documents, width=a4_content_width_px(), media="print"))
