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

from decimal import Decimal

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


@pytest.mark.parametrize("language", [LANGUAGE_ENGLISH, LANGUAGE_ARABIC])
@pytest.mark.parametrize("kind", [CHART_BAR, CHART_GROUPED_BAR, CHART_LINE])
def test_labels_sit_in_a_band_beneath_the_plot(kind: str, language: str) -> None:
    """Every mark ends at or above the plot foot; every label is placed below it."""
    for values in ((Decimal(100), Decimal(300)), (Decimal(-100), Decimal(300))):
        view = chart_of(kind=kind, values=values, language=language)
        assert view is not None
        assert Decimal(view.height) == charts.CHART_HEIGHT > charts.PLOT_HEIGHT
        for mark in view.marks:
            assert Decimal(mark.y) + Decimal(mark.height) <= charts.PLOT_HEIGHT
        for label in view.labels:
            assert charts.PLOT_HEIGHT < Decimal(label.y) < charts.CHART_HEIGHT


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
      if (box.top < canvas.top - 0.5 || box.bottom > canvas.bottom + 0.5 ||
          box.left < canvas.left - 0.5 || box.right > canvas.right + 0.5) {
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


def _collisions(documents: dict[str, str], *, width: int, media: str) -> dict[str, list]:
    from playwright.sync_api import sync_playwright

    found: dict[str, list] = {}
    with sync_playwright() as play:
        browser = play.chromium.launch()
        try:
            for language in LANGUAGES:
                page = browser.new_page(viewport={"width": width, "height": 1000})
                page.emulate_media(media=media)
                page.set_content(documents[language], wait_until="load")
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
def test_no_chart_word_meets_a_mark_on_the_web_report() -> None:
    _assert_no_collisions(_collisions(web_documents(), width=1440, media="screen"))


@pytest.mark.browser
@needs_chromium
def test_no_chart_word_meets_a_mark_on_the_printed_report() -> None:
    documents = printed_documents()
    _assert_no_collisions(_collisions(documents, width=a4_content_width_px(), media="print"))
