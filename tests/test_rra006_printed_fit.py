"""`RRA-006`: the printed report keeps every column on the page and every code whole.

SCRUM-21's first acceptance run (A1, A2) found two ways the PDF fell short of the
"tagged and readable PDF" and "right-to-left Arabic layout" `RRA-006` requires:

- **A1.** The Arabic PDF lost the last column of the Overview breakdown. Header cells
  never wrap (`report.css`, `thead th { white-space: nowrap }`), so the longest Arabic
  header forced the table wider than the page. `report.print.css` makes `.scroller`
  overflow visibly so no column is clipped silently, but in right-to-left the overflow
  runs past the page's left edge, off the paper.
- **A2.** Identifiers in the evidence appendix broke mid-word (`valu e`, `monet ary`).
  The screen sheet sets `code { word-break: break-all }`, which lets a table squeeze
  every column below its widest word; seven columns of codes on A4 were squeezed
  until the vocabulary words split.

Both are measured here in Chromium, under print media, at the A4 measure the print
sheet's own `@page` rule leaves, on the document the PDF renderer actually printed.
A stylesheet grep cannot see either defect: both are properties of table layout.
"""

from __future__ import annotations

import pytest

from tests.rra_printed_support import LANGUAGES, a4_content_width_px, printed_documents
from tests.test_rra006_pdf_surface import chromium_available

needs_chromium = pytest.mark.skipif(
    not chromium_available(),
    reason="the pinned Chromium is not installed; run `playwright install chromium`",
)

#: Tables whose box leaves `main`, in whole pixels, with the side they leave by.
_TABLES_PAST_THE_PAGE = """() => {
  const main = document.querySelector('main').getBoundingClientRect();
  return [...document.querySelectorAll('main table')].map(table => {
    const box = table.getBoundingClientRect();
    return {caption: table.caption ? table.caption.textContent.trim() : '',
            columns: table.querySelectorAll('thead th').length,
            start: Math.round(box.left - main.left),
            end: Math.round(main.right - box.right)};
  });
}"""

#: Every alphabetic run inside a metric, kind or unit code of the evidence figures
#: table, with the number of line boxes it occupies. A run on more than one line box
#: has been split. These three columns hold governed vocabulary (`RRA-011` metric
#: codes, figure kinds, unit kinds); the figure and citation references beside them
#: are opaque keys, allowed to wrap where they exceed their column.
_VOCABULARY_RUNS = """() => {
  const rows = [...document.querySelectorAll('.evidence-figure-row')];
  const runs = [];
  for (const row of rows) {
    for (const cell of [...row.children].slice(2, 5)) {
      const code = cell.querySelector('code');
      if (!code || !code.firstChild || code.firstChild.nodeType !== Node.TEXT_NODE) continue;
      const text = code.firstChild.textContent;
      for (const match of text.matchAll(/[A-Za-z]+/g)) {
        const range = document.createRange();
        range.setStart(code.firstChild, match.index);
        range.setEnd(code.firstChild, match.index + match[0].length);
        runs.push({code: text, run: match[0], lines: range.getClientRects().length});
      }
    }
  }
  return runs;
}"""


def _measure(script: str) -> dict[str, list[dict]]:
    from playwright.sync_api import sync_playwright

    width = a4_content_width_px()
    # Printed first: the renderer runs its own Chromium, which cannot start inside this one.
    documents = printed_documents()
    measured: dict[str, list[dict]] = {}
    with sync_playwright() as play:
        browser = play.chromium.launch()
        try:
            for language in LANGUAGES:
                page = browser.new_page(viewport={"width": width, "height": 1000})
                page.emulate_media(media="print")
                page.set_content(documents[language], wait_until="load")
                page.evaluate("() => document.fonts.ready")
                measured[language] = page.evaluate(script)
                page.close()
        finally:
            browser.close()
    return measured


@pytest.mark.browser
@needs_chromium
def test_no_printed_table_leaves_the_page_in_either_language() -> None:
    """A1: every table fits the printable measure, so no column is lost off the paper."""
    tables = _measure(_TABLES_PAST_THE_PAGE)

    for language in LANGUAGES:
        # The defect was on the five-column breakdown; a fixture that stopped
        # publishing it would pass this test having measured nothing.
        assert any(table["columns"] >= 5 for table in tables[language]), language
        past = [table for table in tables[language] if min(table["start"], table["end"]) < 0]
        assert past == [], f"{language}: tables printed past the page edge: {past}"


@pytest.mark.browser
@needs_chromium
def test_no_vocabulary_code_in_the_printed_appendix_splits_mid_word() -> None:
    """A2: `value`, `monetary` and every metric-code segment print on one line each."""
    runs = _measure(_VOCABULARY_RUNS)

    for language in LANGUAGES:
        seen = {run["run"] for run in runs[language]}
        # The two words the acceptance run saw split, so a null fixture cannot pass.
        assert {"value", "monetary"} <= seen, f"{language}: measured {sorted(seen)[:10]}"
        split = sorted(
            {f"{run['run']} in {run['code']}" for run in runs[language] if run["lines"] > 1}
        )
        assert split == [], f"{language}: vocabulary split across lines: {split}"
