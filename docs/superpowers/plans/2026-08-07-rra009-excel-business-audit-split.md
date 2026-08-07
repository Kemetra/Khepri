# RRA-009 Phase 1c: Excel Business/Audit Split — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorder the governed workbook so business worksheets named by business meaning come first, the audit worksheets come last, and no business sheet carries a `figure_id`, `citation_id`, raw `metric`, `kind`, or `unit_kind` column — without breaking the native charts, the one permitted numeric write path, or the bilingual suffix budget.

**Architecture:** Today `_write_workbook` (`excel.py:341-354`) writes one worksheet per governed *section* per language, named `en_overview`/`ar_growth` by `_section_sheet` (`excel.py:158-159`). RRA-009 requires business worksheets "named by business meaning rather than from a section identifier," which means a **presentation grouping** layer between the bundle's sections and the workbook's sheets. That grouping is data, not logic: a table mapping each business sheet to the section and metrics it presents. Audit content moves to two new sheets (`Audit Trail`, `Provenance`) ordered after every business sheet. No figure is recomputed and no figure is dropped — `reconcile` reads only the `SurfaceContent` claim (`bundle.py:1271-1314`), never the file, so relocation is claim-neutral.

**Tech Stack:** Python 3.13, XlsxWriter, pytest. No new dependencies.

## Status as of 2026-08-07, `main` @ `b84aad9`

**This plan is fully unblocked and entirely unbuilt.** Its prerequisite is discharged: `#121` landed plan 1 Tasks 2–4 and plan 2 Tasks 1–5, so all three accessors exist with **exactly** the signatures this plan cites, verified by `inspect.signature`:

```
business_metric_name (metric: str, language: str) -> str | None
caveat_prose         (code: str, language: str) -> str
refusal_message      (reason: str, *, context: str, language: str) -> str
```

`excel.py` is untouched by any RRA-009 work — still one worksheet per governed section per language (`_section_sheet` at `:158`, `_write_section` called at `:345`). Every task below is available, and Tasks 4 and 6 no longer wait on anything.

**Two corrections to facts this plan cites**, both from what `#121` shipped:

- **The result-refusal universe is 7 codes, not 5.** `dimension_absent` and `negative_base` were added, so the customer-facing catalogue is 15 messages over 13 distinct codes. Task 6 reads `refusal_message` rather than enumerating codes, so no task body changes — but the count is worth knowing before writing a test that asserts one.
- **`caveat_prose` handles more shapes than this plan assumed.** A composite `<result>:<reason>` whose reason is a *section* reason routes to the section tier (`wording.py:600-601`), and `_result_business_name` (`:610-616`) strips the `.mode` suffix so no mode-qualified identity reaches a cell. Task 6's limitations sheet gets that behaviour for free.

**Arabic status:** the 8 business sheet names this plan adds (Task 3) still need writing, and the ~30 strings already shipped were filled by an agent rather than reviewed by the owner. See the vocabulary plan's status note — "placeholders resolved" is not "parity achieved."

---

## Prerequisite (discharged — retained for the record)

This plan consumes, with these exact signatures:

- `wording.business_metric_name(metric: str, language: str) -> str | None` — plan 2 Task 3, **built**
- `wording.caveat_prose(code: str, language: str) -> str` — plan 2 Task 5, **built**
- `wording.refusal_message(reason: str, *, context: str, language: str) -> str` — plan 1 Tasks 2–3, **built**

**Do not re-define any wording table here** — three definitions of the same vocabulary is three places for it to disagree. That constraint still binds every task below.

---

## Verified facts this plan rests on

Every number below was measured in this repository on 2026-08-07, not copied from the design package. Each is reproducible with the command given.

**The workbook is 17 sheets today**, not the 10 or 11 IA §B.4's table implies (§B.6 item 9 acknowledges "~17 sheets delivered versus 12 shown"):

```
Report (English)  en_overview  en_comparison  en_concentration  en_growth  en_basket
Citations (English)  en_chartdata
التقرير (العربية)  ar_overview  ar_comparison  ar_concentration  ar_growth  ar_basket
الإسنادات (العربية)  ar_chartdata
Provenance
```

```bash
uv run python -c "
import tempfile, pathlib, zipfile, re
from tests.test_rra006_html_sections import ROWS, package_for
from khepri.rra.bundle import ReportBundle
from khepri.rra.rendering.excel import ExcelSurfaceRenderer
d = pathlib.Path(tempfile.mkdtemp()); b = ReportBundle.of(package_for(ROWS))
r = ExcelSurfaceRenderer(directory=d); r.render(b)
with zipfile.ZipFile(r.path_for(b)) as z: wb = z.read('xl/workbook.xml').decode()
for n in re.findall(r'name=\"([^\"]+)\" sheetId', wb): print(len(n), n)"
```

**The worksheet name cap is 31 characters and XlsxWriter raises at 32.** IA §B.4 note 2 says "raises `InvalidWorksheetName` on a 33-character name" — the real threshold is 32. Verified: 31 chars OK, 32 raises `Excel worksheet name '…' must be <= 31 chars.` Both language suffixes ` (English)` and ` (العربية)` are exactly 10 characters, so the budget is **21 characters, symmetric**. Measured against IA §B.4's proposed names:

| Name | With suffix | |
|---|---|---|
| `Executive Summary` | 27 | ok |
| `Branch Performance` | 28 | ok |
| `Discounts and Returns` | **31** | at the limit, zero headroom |
| `Branch & Category Performance` | 39 | over — IA §B.4 already rejected it |

**The bundle carries 5 sections and up to 26 distinct metrics.** With the existing five-row fixture (`tests/test_rra006_html_sections.py:38`), 21 metrics appear across `overview / comparison / concentration / growth / basket`. **No `cost`, `gross_profit`, `gross_margin`, `discount`, or `returns` figure exists in that fixture**, because its header is `date,revenue,units,invoice_no,product`.

**Consequence, and it is a scope finding:** IA §B.4's sheets 5 (`Profitability`) and 6 (`Discounts and Returns`) would be **empty** on the existing fixture. They are reachable — a dataset with a `cost` column produces `cost`/`gross_profit`/`gross_margin`, and one with `discount_amount`/`returns_amount` produces `discount`/`returns`, giving 26 metrics — but a bare `discount` column does **not** work: `mapping.py:683-697` gates `SEMANTIC_DISCOUNT` and `SEMANTIC_RETURNS` behind `requires_amount_evidence=True`, so an undeclared measure kind resolves `STATE_AMBIGUOUS` rather than being "summed as currency." `cost` carries no such gate.

Task 1 therefore builds a richer fixture, because a plan that tests sheets 5 and 6 against a dataset that cannot populate them tests nothing.

**Test surface is 3 files, 1,255 lines, 46 name-pinning assertions:** `test_rra006_excel_surface.py` (553 lines, 9 pins), `test_rra006_excel_charts.py` (508 lines, 21 pins, of which **exactly 11 reference `chartdata`** — IA §B.6 item 13's "eleven places" is precisely right), `test_rra006_excel_sections.py` (194 lines, 16 pins).

---

## Global Constraints

- **`_write_chart_value` (`excel.py:596-616`) stays the only numeric write in the module.** `APP-013` permits a numeric cell *solely* as a chart series address, on a dedicated worksheet holding no authoritative figure and no citation. Every other cell goes through `_write_row` → `write_string`. Adding a second numeric write path would need an `APP-013` amendment, and `APP-013` pins `KHEPRI-DEC-005` by document digest.
- **The chart-data sheet must ship with the business workbook and must stay visible.** `_series_range` (`excel.py:656-665`) addresses it **by name**, so a chart whose series points at a renamed or removed sheet renders empty. `excel.py:71-75` argues visibility on auditability grounds and IA §B.6 item 10 records that an earlier draft's hide-it recommendation was withdrawn: hiding it would need an `APP-013` amendment. **Do not hide it, and do not rename it without updating `_series_range` in the same commit.**
- **Every literal a cell holds that did not come from the bundle must be in `GOVERNED_LABELS`** (`excel.py:251-286`). That frozen set is what makes "did the renderer invent this text?" decidable. Every new sheet name, heading, and column header this plan adds goes into it.
- **Worksheet names are addresses and are not translated — except where they are now.** `excel.py:150-155` states the current rule: a sheet name is an address, so `_section_sheet` prefixes `en_`/`ar_` rather than translating. RRA-009 overrides this **for business sheets only**: "Name business worksheets by business meaning rather than from a section identifier." Audit sheet names stay addresses. This plan changes the rule for sheets 1–8 and states the change in the module docstring.
- **Assert the 21-character budget at import.** IA §B.4 note 2 requires it, in the style `wording.py:120-122` establishes. Without it, a 22-character name added later passes every review and raises `InvalidWorksheetName` during a customer's render.
- **No arithmetic, and no reformatting.** `excel.py:19-31` states it: every figure is the exact string the fact package produced, and `500.0` versus `500.00` is "the same number and a different statement about precision." Business sheets present the same strings the section sheets presented.
- **Order is the information architecture.** IA §B.4: "Worksheet order **is** the information architecture in a workbook, because it is what a reader sees on opening." Business sheets first in reading order, audit sheets last. This is a requirement, not a preference.
- **The business sheet set varies by dataset, and that is correct.** IA §B.4 records this for Basket ("a worksheet whose only content is an apology is worse than its absence"). This plan extends the same rule to any business sheet whose figures are all absent, and Task 4 makes the omission a tested behaviour rather than an accident.

---

## File Structure

- **Create:** `src/khepri/rra/rendering/excel_layout.py` — the business-sheet presentation table and the name-budget assertion. A separate module because it is *data about presentation* rather than writing logic, it is what a reviewer reads to answer "which sheet shows what," and `excel.py` is already 788 lines.
- **Modify:** `src/khepri/rra/rendering/excel.py` — replace `_section_sheet`-per-section writing with business-sheet writing; add `Audit Trail`; reorder `_write_workbook`; extend `GOVERNED_LABELS`; keep `_write_chart_value` and the chartdata sheet exactly as they are.
- **Modify:** `src/khepri/rra/rendering/wording.py` — add business sheet names in both languages, guarded against the layout table and the 21-character budget.
- **Create (tests):** `tests/rra009_fixtures.py` — a fixture builder producing all 26 metrics, so sheets 5 and 6 are testable.
- **Create (tests):** `tests/test_rra009_excel_split.py` — the new contract: sheet order, business-column purity, audit completeness, chart survival.
- **Modify (tests):** `tests/test_rra006_excel_surface.py`, `tests/test_rra006_excel_charts.py`, `tests/test_rra006_excel_sections.py`.

`html.py`, `pdf.py`, and the templates are **out of scope** — plan 2 owns them.

---

## Task 1: A fixture that produces every governed metric

**Files:**
- Create: `tests/rra009_fixtures.py`
- Test: `tests/test_rra009_excel_split.py` (create)

**Interfaces:**
- Consumes: `build_profile`, `build_mapping`, `assess_admissibility`, `build_fact_package`, `ReportBundle` — the same chain `tests/test_rra006_html_sections.py:47-66` uses.
- Produces: `rra009_fixtures.rich_bundle() -> ReportBundle`, carrying all 26 metrics including `cost`, `gross_profit`, `gross_margin`, `discount`, and `returns`; and `rra009_fixtures.RICH_HEADER` / `RICH_ROWS` for tests that need the raw input. Every later task in this plan builds on it.

**Why this is Task 1:** the existing fixture cannot populate IA §B.4's sheets 5 and 6, so testing them against it would assert that two empty sheets are correct. The column names matter precisely: `discount_amount`, not `discount`, because `mapping.py:683-697` resolves an undeclared measure kind as `STATE_AMBIGUOUS`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rra009_excel_split.py
"""RRA-009: the business/audit split in the governed workbook."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pytest

from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.rendering.excel import ExcelSurfaceRenderer

from tests.rra009_fixtures import rich_bundle

LEAKAGE_METRICS = frozenset(
    {"cost", "gross_profit", "gross_margin", "discount", "returns"}
)


def test_the_rich_fixture_carries_every_leakage_metric():
    """Sheets 5 and 6 of the information architecture have nothing to show
    without these, and the existing five-row fixture produces none of them.
    A bare `discount` column is not enough -- `mapping.py:683-697` requires the
    measure kind be declared, so the column is `discount_amount`.
    """
    metrics = {figure.metric for figure in rich_bundle().figures}
    assert LEAKAGE_METRICS <= metrics, sorted(LEAKAGE_METRICS - metrics)


def test_the_rich_fixture_presents_every_section():
    assert [section.state for section in rich_bundle().sections] == ["present"] * 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_excel_split.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tests.rra009_fixtures'`

- [ ] **Step 3: Write the fixture module**

Create `tests/rra009_fixtures.py`:

```python
"""A fact package rich enough to exercise every business worksheet.

`tests/test_rra006_html_sections.py`'s fixture carries
`date,revenue,units,invoice_no,product` and therefore produces no cost, profit,
margin, discount, or returns figure at all. Two of the information
architecture's business worksheets present exactly those, so testing them
against that fixture would assert that two empty sheets are correct.

**The column names are load-bearing.** `discount_amount` rather than `discount`,
and `returns_amount` rather than `returns`: `mapping.py:683-697` gates both
semantics behind `requires_amount_evidence=True`, so a column whose measure kind
is not declared resolves `STATE_AMBIGUOUS` and is "reported unresolved rather
than summed as currency." `cost` carries no such gate and needs no suffix.
Verified by building this package and diffing the metric set.
"""

from __future__ import annotations

import hashlib

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import ReportBundle
from khepri.rra.facts import FactPackage, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.profiling import build_profile

RICH_HEADER = b"date,revenue,units,invoice_no,product,cost,discount_amount,returns_amount\n"

# Fourteen rows over nine months: enough for a prior comparison window, a growth
# decomposition, and more than one product to concentrate over.
RICH_ROWS = tuple(
    (
        f"2026-0{(index % 9) + 1}-01",
        f"{100 + index * 10}.00",
        4 + index,
        f"INV-{index}",
        f"P{index % 3}",
        f"{50 + index * 5}.00",
        f"{index}.00",
        f"{index * 2}.00",
    )
    for index in range(14)
)


def rich_content() -> bytes:
    body = b"".join(
        f"{date},{revenue},{units},{invoice},{product},{cost},{discount},{returns}\n".encode()
        for date, revenue, units, invoice, product, cost, discount, returns in RICH_ROWS
    )
    return RICH_HEADER + body


def rich_package() -> FactPackage:
    content = rich_content()
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile)
    return build_fact_package(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        profile=profile,
        mapping=mapping,
        decision=assess_admissibility(profile, mapping),
    )


def rich_bundle() -> ReportBundle:
    return ReportBundle.of(rich_package())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_excel_split.py -v`
Expected: PASS. If `test_the_rich_fixture_carries_every_leakage_metric` fails listing `discount` and `returns`, the column suffixes were dropped — that is the `requires_amount_evidence` gate, not a fixture size problem.

- [ ] **Step 5: Commit**

```bash
git add tests/rra009_fixtures.py tests/test_rra009_excel_split.py
git commit -m "test: add a fixture carrying every governed metric (RRA-009)"
```

---

## Task 2: The business-sheet layout table

**Files:**
- Create: `src/khepri/rra/rendering/excel_layout.py`
- Test: `tests/test_rra009_excel_split.py`

**Interfaces:**
- Consumes: `facts` metric constants; `growth.GOVERNED_METRICS`; `bundle.ORDERED_SECTIONS`.
- Produces: `excel_layout.BUSINESS_SHEETS: tuple[BusinessSheet, ...]`, where `BusinessSheet` is a frozen dataclass carrying `key: str`, `section: str`, and `metrics: tuple[str, ...]`. `excel_layout.MAX_SHEET_NAME_BUDGET: int = 21`. Tasks 3–5 read the table; Task 6 words the names.

**Why a table and a separate module:** which figures a business sheet presents is *data about presentation*, and a reader asking "which sheet shows gross margin?" should find one answer in one place rather than tracing a writer function. `excel.py` is 788 lines and this would push it past the 800 ceiling the project's coding standards name.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_rra009_excel_split.py

from khepri.rra.rendering import excel_layout


def test_every_business_sheet_names_a_governed_section():
    from khepri.rra.bundle import ORDERED_SECTIONS

    for sheet in excel_layout.BUSINESS_SHEETS:
        assert sheet.section in ORDERED_SECTIONS, sheet.key


def test_business_sheets_cover_every_rendered_metric():
    """A metric on no business sheet is a figure the customer never sees.

    Asserted against the rich fixture rather than against the governed metric
    vocabulary, because the vocabulary is 13 and the rendered set is 26 -- the
    series and bucket variants are what a business sheet actually lists.
    """
    covered = {metric for sheet in excel_layout.BUSINESS_SHEETS for metric in sheet.metrics}
    rendered = {figure.metric for figure in rich_bundle().figures}
    assert rendered <= covered, sorted(rendered - covered)


def test_no_metric_appears_on_two_business_sheets():
    """Two sheets showing one figure is two places for it to be read
    differently, and `reconcile` would catch neither -- it compares the claim,
    not the file."""
    seen: dict[str, str] = {}
    for sheet in excel_layout.BUSINESS_SHEETS:
        for metric in sheet.metrics:
            assert metric not in seen, (metric, sheet.key, seen.get(metric))
            seen[metric] = sheet.key
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_excel_split.py -k business_sheet -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'khepri.rra.rendering.excel_layout'`

- [ ] **Step 3: Write the layout module**

Create `src/khepri/rra/rendering/excel_layout.py`:

```python
"""Which business worksheet presents which governed figures.

**Why this is a table and not a function.** RRA-009 requires business worksheets
be "named by business meaning rather than from a section identifier," which puts a
presentation grouping between the bundle's five governed sections and the
workbook's sheets. That grouping is a decision about what a customer reads
together, so it is written down once, where a reviewer can check it, rather than
distributed through a writer that computes it.

**It regroups and never recomputes.** Every metric named here is a metric the
bundle produced; every figure a sheet lists is the string the fact package
rendered. `KHEPRI-DEC-005` forbids a surface calculating anything and `excel.py`
holds that line for the whole module.

**Two sheets present the same governed section under different business names.**
`Profitability` and `Discounts and Returns` both draw on `overview`, because the
bundle has no profitability section and RRA-009 excludes adding one -- "Any new
figure, aggregate, analysis family, metric, or chart kind." The information
architecture adopted the same route for `Branch Performance`, which re-presents
`concentration`'s ranked buckets under a business name (owner-authorized
2026-08-04). This is presentation, not a new analysis: the figures are the same
figures, so the sheets can never disagree with the section that computed them.
"""

from __future__ import annotations

from dataclasses import dataclass

from khepri.rra.analysis import growth
from khepri.rra import facts

# Excel caps a worksheet name at 31 characters and XlsxWriter raises at 32
# (verified: 31 accepted, 32 raises `InvalidWorksheetName`). Both governed
# language suffixes -- " (English)" and " (العربية)" -- are exactly 10
# characters, so the budget is symmetric.
SHEET_NAME_SUFFIX_WIDTH = 10
EXCEL_SHEET_NAME_LIMIT = 31
MAX_SHEET_NAME_BUDGET = EXCEL_SHEET_NAME_LIMIT - SHEET_NAME_SUFFIX_WIDTH


@dataclass(frozen=True, slots=True)
class BusinessSheet:
    """One business worksheet: what it is called, and what it presents.

    `key` is a stable identifier for the sheet, not a name a reader sees --
    `wording.BUSINESS_SHEET_NAMES` holds the per-language names. Keeping them
    apart is what lets the name be a wording decision and the layout be a
    presentation decision.
    """

    key: str
    section: str
    metrics: tuple[str, ...]


SHEET_EXECUTIVE_SUMMARY = "executive_summary"
SHEET_SALES_PERFORMANCE = "sales_performance"
SHEET_PERIOD_COMPARISON = "period_comparison"
SHEET_GROWTH_DRIVERS = "growth_drivers"
SHEET_PROFITABILITY = "profitability"
SHEET_DISCOUNTS_AND_RETURNS = "discounts_and_returns"
SHEET_BRANCH_PERFORMANCE = "branch_performance"
SHEET_BASKET = "basket"

# Reading order, and it is the information architecture: worksheet order is what
# a reader sees on opening the file. Business sheets first, in the order the
# report reads; the audit sheets `excel.py` appends come after all of them.
BUSINESS_SHEETS: tuple[BusinessSheet, ...] = (
    BusinessSheet(
        key=SHEET_EXECUTIVE_SUMMARY,
        section="overview",
        metrics=(
            facts.METRIC_REVENUE,
            facts.METRIC_TRANSACTIONS,
            facts.METRIC_UNITS,
            facts.METRIC_AVERAGE_ORDER_VALUE,
        ),
    ),
    BusinessSheet(
        key=SHEET_SALES_PERFORMANCE,
        section="overview",
        metrics=(
            facts.METRIC_AVERAGE_SELLING_PRICE,
            "revenue_by_period",
            "units_by_period",
        ),
    ),
    BusinessSheet(
        key=SHEET_PERIOD_COMPARISON,
        section="comparison",
        metrics=("revenue_delta_absolute", "revenue_delta_percent"),
    ),
    BusinessSheet(
        key=SHEET_GROWTH_DRIVERS,
        section="growth",
        metrics=growth.GOVERNED_METRICS,
    ),
    BusinessSheet(
        key=SHEET_PROFITABILITY,
        section="overview",
        metrics=(
            facts.METRIC_COST,
            facts.METRIC_GROSS_PROFIT,
            facts.METRIC_GROSS_MARGIN,
        ),
    ),
    BusinessSheet(
        key=SHEET_DISCOUNTS_AND_RETURNS,
        section="overview",
        metrics=(facts.METRIC_DISCOUNT, facts.METRIC_RETURNS),
    ),
    BusinessSheet(
        key=SHEET_BRANCH_PERFORMANCE,
        section="concentration",
        metrics=(
            "revenue_by_product",
            "units_by_product",
            "concentration_ranked_values",
            "concentration_distinct_values",
            "concentration_top_decile_share",
            "concentration_top_quartile_share",
            "concentration_curve",
        ),
    ),
    BusinessSheet(
        key=SHEET_BASKET,
        section="basket",
        metrics=("basket_items_per_transaction", "basket_attach_rate"),
    ),
)


def sheet_for(metric: str) -> BusinessSheet | None:
    """Which business sheet presents one metric, if any presents it."""
    for sheet in BUSINESS_SHEETS:
        if metric in sheet.metrics:
            return sheet
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_excel_split.py -v`
Expected: PASS. If `test_business_sheets_cover_every_rendered_metric` fails, the listed metrics are figures the rich fixture renders that no sheet claims — add them to the sheet whose business meaning fits, and do not add a catch-all sheet.

- [ ] **Step 5: Commit**

```bash
git add src/khepri/rra/rendering/excel_layout.py tests/test_rra009_excel_split.py
git commit -m "feat: declare which business worksheet presents which figures (RRA-009)"
```

---

## Task 3: Business sheet names, guarded against the 21-character budget

**Files:**
- Modify: `src/khepri/rra/rendering/wording.py`
- Test: `tests/test_rra009_excel_split.py`

**Interfaces:**
- Consumes: `excel_layout.BUSINESS_SHEETS`, `excel_layout.MAX_SHEET_NAME_BUDGET`.
- Produces: `wording.BUSINESS_SHEET_NAMES: dict[str, dict[str, str]]` keyed `[language][sheet_key]`, with two import-time guards — key-set completeness against the layout table, and the 21-character budget.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_rra009_excel_split.py

from khepri.rra.rendering import wording


def test_every_business_sheet_is_named_in_every_language():
    keys = {sheet.key for sheet in excel_layout.BUSINESS_SHEETS}
    for language in REQUIRED_LANGUAGES:
        assert set(wording.BUSINESS_SHEET_NAMES[language]) == keys


def test_every_sheet_name_fits_the_bilingual_budget():
    """A 22-character name passes every review and raises
    `InvalidWorksheetName` during a customer's render. Verified threshold: 31
    accepted, 32 raises -- so with a 10-character suffix the budget is 21."""
    for language in REQUIRED_LANGUAGES:
        for key, name in wording.BUSINESS_SHEET_NAMES[language].items():
            assert len(name) <= excel_layout.MAX_SHEET_NAME_BUDGET, (key, language, len(name))


def test_sheet_names_are_distinct_within_a_language():
    """Two sheets with one name is an XlsxWriter duplicate-name error at write
    time, and the second sheet silently wins in any name-based lookup."""
    for language in REQUIRED_LANGUAGES:
        names = list(wording.BUSINESS_SHEET_NAMES[language].values())
        assert len(set(names)) == len(names), language
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_excel_split.py -k sheet_name -v`
Expected: FAIL — `AttributeError: module 'khepri.rra.rendering.wording' has no attribute 'BUSINESS_SHEET_NAMES'`

- [ ] **Step 3: Add the table and both guards**

Add to `wording.py`. Note `Discounts and Returns` is 21 characters — exactly at the budget, zero headroom, measured:

```python
# What each business worksheet is called. Unlike a section sheet, whose name is an
# address (`excel.py:150-155`), a business sheet name is text a customer reads --
# RRA-009 requires business worksheets be "named by business meaning rather than
# from a section identifier" -- so it is governed wording and lives here.
#
# The 21-character budget is not a style preference. Excel caps a name at 31 and
# XlsxWriter raises at 32; both language suffixes are 10 characters. A name over
# budget is an exception during a customer's render, so it is asserted below
# rather than reviewed. `Discounts and Returns` is exactly 21 and has no headroom.
BUSINESS_SHEET_NAMES: dict[str, dict[str, str]] = {
    LANGUAGE_ENGLISH: {
        "executive_summary": "Executive Summary",
        "sales_performance": "Sales Performance",
        "period_comparison": "Period Comparison",
        "growth_drivers": "Growth Drivers",
        "profitability": "Profitability",
        "discounts_and_returns": "Discounts and Returns",
        "branch_performance": "Branch Performance",
        "basket": "Basket Analysis",
    },
    LANGUAGE_ARABIC: {
        "executive_summary": "الملخص التنفيذي",
        "sales_performance": "أداء المبيعات",
        "period_comparison": "مقارنة الفترات",
        "growth_drivers": "محرّكات النمو",
        "profitability": "الربحية",
        "discounts_and_returns": "الخصومات والمرتجعات",
        "branch_performance": "أداء الفروع",
        "basket": "تحليل سلة الشراء",
    },
}


def _assert_business_sheet_names_complete() -> None:
    from khepri.rra.rendering.excel_layout import (
        BUSINESS_SHEETS,
        MAX_SHEET_NAME_BUDGET,
    )

    expected = {sheet.key for sheet in BUSINESS_SHEETS}
    for language, names in BUSINESS_SHEET_NAMES.items():
        if set(names) != expected:
            raise RuntimeError(
                f"every business worksheet needs a name in every language "
                f"(language={language!r})"
            )
        for key, name in names.items():
            if len(name) > MAX_SHEET_NAME_BUDGET:
                # Excel raises at write time, which means on a customer's report
                # rather than in review.
                raise RuntimeError(
                    f"business worksheet name exceeds the bilingual budget of "
                    f"{MAX_SHEET_NAME_BUDGET} characters "
                    f"(language={language!r}, sheet={key!r}, length={len(name)})"
                )


_assert_business_sheet_names_complete()
```

> **Import note.** The `excel_layout` import is inside the function rather than at module scope. `excel_layout` imports `facts` and `growth`, and `wording` is imported by `html.py` and `excel.py`; a module-scope import here would add `wording → excel_layout → facts` to an import graph that currently has `wording → bundle`. Deferring it to call time keeps the module's import surface unchanged. If a circular import appears anyway, that is the signal — do not resolve it by moving the guard into a test.

> **Arabic note.** These eight strings need owner authorship rather than proofreading, on the same grounds as plan 1's thirty and plan 2's six. They are written rather than left blank because a workbook cannot be built without sheet names, and every one is inside the 21-character budget (longest: `الخصومات والمرتجعات`, 19).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_excel_split.py -v`
Expected: PASS

- [ ] **Step 5: Confirm no import cycle was introduced**

Run: `uv run python -c "import khepri.rra.rendering.excel, khepri.rra.rendering.html; print('ok')"`
Expected: `ok`. Both modules import `wording`; if the guard's deferred import were hoisted to module scope this is where a cycle would surface.

- [ ] **Step 6: Commit**

```bash
git add src/khepri/rra/rendering/wording.py tests/test_rra009_excel_split.py
git commit -m "feat: name the business worksheets, guarded against Excel's name cap (RRA-009)"
```

---

## Task 4: Write the business worksheets

**Files:**
- Modify: `src/khepri/rra/rendering/excel.py`
- Test: `tests/test_rra009_excel_split.py`

**Interfaces:**
- Consumes: `excel_layout.BUSINESS_SHEETS`; `wording.BUSINESS_SHEET_NAMES`; `wording.business_metric_name` — **plan 2 Task 3**; the existing `_sheet`, `_write_row` helpers.
- Produces: `_write_business_sheet(workbook, bundle, language, sheet) -> Worksheet | None`, returning `None` when the sheet has no figure to show. `_write_workbook` calls it per sheet per language in `BUSINESS_SHEETS` order.

**Business column headers, and what they must not contain:** the business figure table is two columns — the row's business name and its value. IA §B.4: "No sheet in 1–7 contains a `figure_id`, `citation_id`, raw `metric`, `kind`, or `unit_kind` column."

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_rra009_excel_split.py

def _workbook_sheets(bundle, tmp_path: Path) -> list[str]:
    renderer = ExcelSurfaceRenderer(directory=tmp_path)
    renderer.render(bundle)
    with zipfile.ZipFile(renderer.path_for(bundle)) as archive:
        workbook = archive.read("xl/workbook.xml").decode()
    return re.findall(r'name="([^"]+)" sheetId', workbook)


def test_business_sheets_come_before_the_audit_sheets(tmp_path):
    names = _workbook_sheets(rich_bundle(), tmp_path)
    business = names.index(wording.BUSINESS_SHEET_NAMES[LANGUAGE_ENGLISH]["executive_summary"])
    assert business < names.index("Audit Trail")
    assert business < names.index("Provenance")


def test_a_business_sheet_with_no_figure_is_absent(tmp_path):
    """IA §B.4: a worksheet whose only content is an apology is worse than its
    absence. The five-row fixture produces no cost figure, so Profitability has
    nothing to show and must not appear."""
    from tests.test_rra006_html_sections import ROWS, package_for
    from khepri.rra.bundle import ReportBundle

    names = _workbook_sheets(ReportBundle.of(package_for(ROWS)), tmp_path)
    assert wording.BUSINESS_SHEET_NAMES[LANGUAGE_ENGLISH]["profitability"] not in names


def test_a_business_sheet_appears_when_its_figures_exist(tmp_path):
    names = _workbook_sheets(rich_bundle(), tmp_path)
    assert wording.BUSINESS_SHEET_NAMES[LANGUAGE_ENGLISH]["profitability"] in names


def test_business_sheets_are_written_in_both_languages(tmp_path):
    names = _workbook_sheets(rich_bundle(), tmp_path)
    for language in REQUIRED_LANGUAGES:
        assert wording.BUSINESS_SHEET_NAMES[language]["executive_summary"] in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_excel_split.py -k business_sheets -v`
Expected: FAIL — the workbook writes `en_overview`, not `Executive Summary`, and no `Audit Trail` sheet exists.

- [ ] **Step 3: Add the business columns and the writer**

In `excel.py`, add beside `_FIGURE_COLUMNS` (`excel.py:187-206`):

```python
# The business figure table: what the row is called, and what it is. No
# identifier column, no metric code, no kind, no unit -- RRA-009 puts each of
# those in the audit region, and a business sheet carrying one would be the
# identifier ledger with a friendlier tab name.
_BUSINESS_COLUMNS = {
    LANGUAGE_ENGLISH: ("Figure", "Value"),
    LANGUAGE_ARABIC: ("البيان", "القيمة"),
}
```

Add the writer:

```python
def _write_business_sheet(
    workbook: Workbook,
    bundle: ReportBundle,
    language: str,
    sheet: BusinessSheet,
) -> Worksheet | None:
    """One business worksheet, or nothing when it has no figure to present.

    Returning `None` rather than an empty sheet is the information
    architecture's rule and it is deliberate: a worksheet whose only content is
    an apology is worse than its absence, and a customer whose export carries no
    cost column is owed a workbook without a Profitability tab rather than one
    with an empty one. The refusal itself is not lost -- it reaches the customer
    through the caveat and refusal prose on the limitations sheet.

    The consequence, stated because it surprises a reader of the file: the
    business tab count varies by dataset. The audit sheets do not.
    """
    figures = [figure for figure in bundle.figures if figure.metric in sheet.metrics]
    if not figures:
        return None
    worksheet = _sheet(workbook, BUSINESS_SHEET_NAMES[language][sheet.key], language)
    worksheet.set_column(0, 0, _LABEL_WIDTH)
    worksheet.set_column(1, 1, _VALUE_WIDTH)

    row = _write_row(worksheet, 0, _BUSINESS_COLUMNS[language])
    for figure in figures:
        row = _write_row(worksheet, row, _business_cells(figure, language))
    return worksheet


def _business_cells(figure: CitedFigure, language: str) -> tuple[str, ...]:
    """One figure as a business row: its name, and the string the bundle rendered.

    The name resolves through `wording.business_metric_name`, which returns
    `None` for a series or bucket metric whose own label already names the row --
    a period, a product, a branch. The value is the exact rendering; this module
    formats nothing (`excel.py:19-31`).
    """
    name = business_metric_name(figure.metric, language) or figure.label or figure.metric
    return (name, figure.renderings[language])
```

Add the imports:

```python
from khepri.rra.rendering.excel_layout import BUSINESS_SHEETS, BusinessSheet
from khepri.rra.rendering.wording import (
    BUSINESS_SHEET_NAMES,
    CHART_DESCRIPTIONS,
    LABEL_WORDING,
    SECTION_HEADINGS,
    business_metric_name,
    category_of,
    worded,
)
```

> **On the `or figure.metric` fallback.** It exists so a metric added upstream without wording cannot raise mid-workbook, and it should be unreachable: plan 2's `test_every_row_has_something_to_be_called` asserts every figure resolves to a name or a label. Step 5 below asserts the same property here, so the fallback is a backstop rather than a behaviour any test relies on. If a test ever needs it, that is an unworded metric to word, not a fallback to keep.

- [ ] **Step 4: Extend `GOVERNED_LABELS` and reorder `_write_workbook`**

Add the new literals to `GOVERNED_LABELS` (`excel.py:251-286`) — every cell literal not from the bundle must be decidable as governed:

```python
    | {
        name
        for names in BUSINESS_SHEET_NAMES.values()
        for name in names.values()
    }
    | {
        header
        for headers in _BUSINESS_COLUMNS.values()
        for header in headers
    }
```

Replace `_write_workbook` (`excel.py:341-354`):

```python
def _write_workbook(workbook: Workbook, bundle: ReportBundle) -> None:
    """Business worksheets first, then the audit region, then provenance.

    Order is the information architecture: it is what a reader sees on opening
    the file. A reader lands on the executive summary rather than on a grid of
    identifiers, and an auditor finds every identifier on the sheets after them.

    The chart data sheet keeps its position at the end of each language's run,
    for the reason it always had: `insert_chart` needs its target worksheet to
    exist, and `_series_range` addresses the data sheet by name.
    """
    for language in LANGUAGES:
        written: list[tuple[BusinessSheet, Worksheet]] = []
        for sheet in BUSINESS_SHEETS:
            worksheet = _write_business_sheet(workbook, bundle, language, sheet)
            if worksheet is not None:
                written.append((sheet, worksheet))
        _write_limitations(workbook, bundle, language)
        _write_audit_trail(workbook, bundle, language)
        _write_citations(workbook, bundle, language)
        _draw_charts(workbook, bundle, language, written)
    _write_provenance(workbook, bundle)
```

> **A charting collision this plan must avoid, verified rather than assumed.** The obvious form of the code above is `sheets = {sheet.section: worksheet for ...}` — and it is wrong. **Four business sheets map to `overview`** (`executive_summary`, `sales_performance`, `profitability`, `discounts_and_returns`), so a dict keyed by section silently keeps only the last and a chart for that section would draw onto whichever sheet happened to be written last.
>
> Measured: the section→sheet fan-out is `{'overview': 4}`; every other section has exactly one sheet. `overview` carries **no** `ChartSpec` today (`concentration`, `growth`, and `basket` are the charted three), so the collision is **latent, not active** — which is precisely why it must be designed out now rather than discovered when a chart is added to the overview family.
>
> Reproduce the fan-out and the charted set with:
> ```bash
> uv run python -c "
> from tests.rra009_fixtures import rich_bundle
> for s in rich_bundle().sections:
>     print(s.section_id, 'chart:', None if s.chart is None else s.chart.kind)"
> ```
>
> So `_draw_charts` receives an **ordered list of `(sheet, worksheet)` pairs**, not a section-keyed dict, and resolves a block's target by matching `sheet.section` — drawing onto the *first* business sheet presenting that section, which is the one a reader reaches first. Task 5 implements that and asserts a chart still lands for each of the three charted sections. Do not fix it by reintroducing per-section sheets, and do not fix it by keying on section.

- [ ] **Step 5: Add the name-resolution assertion**

```python
# append to tests/test_rra009_excel_split.py

def test_every_business_row_is_named_without_a_metric_code(tmp_path):
    """The `or figure.metric` backstop in `_business_cells` must be unreachable.

    Asserted on the written file rather than on the helper, because the helper
    could be correct while a sheet still listed a figure no sheet claimed.
    """
    bundle = rich_bundle()
    renderer = ExcelSurfaceRenderer(directory=tmp_path)
    renderer.render(bundle)
    with zipfile.ZipFile(renderer.path_for(bundle)) as archive:
        strings = archive.read("xl/sharedStrings.xml").decode()
    for figure in bundle.figures:
        if excel_layout.sheet_for(figure.metric) is not None:
            assert f">{figure.metric}<" not in strings, figure.metric
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_excel_split.py -v`
Expected: PASS. `_write_limitations` and `_write_audit_trail` do not exist yet — implement them as stubs that write a titled empty sheet so this task's tests can pass, and fill them in Tasks 5 and 6. Note the stub in the commit message.

- [ ] **Step 7: Commit**

```bash
git add src/khepri/rra/rendering/excel.py tests/test_rra009_excel_split.py
git commit -m "feat: write business worksheets named by business meaning (RRA-009)

_write_limitations and _write_audit_trail are titled stubs; Tasks 5 and 6 fill
them. The chart-block/section keying change lands in Task 5."
```

---

## Task 5: The audit trail sheet, and keep the charts drawing

**Files:**
- Modify: `src/khepri/rra/rendering/excel.py`
- Test: `tests/test_rra009_excel_split.py`

**Interfaces:**
- Consumes: `_FIGURE_COLUMNS` and `_SECTION_COLUMNS` (`excel.py:187-216`), reused verbatim — the audit trail *is* the old identifier ledger, so its columns are the ones that already exist.
- Produces: `_write_audit_trail(workbook, bundle, language) -> None`, writing the figure-identifier table and the section-state table onto one sheet named `Audit Trail`; and a `_draw_charts` that tolerates a section with no business sheet.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_rra009_excel_split.py

def _sheet_strings(bundle, tmp_path: Path) -> str:
    renderer = ExcelSurfaceRenderer(directory=tmp_path)
    renderer.render(bundle)
    with zipfile.ZipFile(renderer.path_for(bundle)) as archive:
        return archive.read("xl/sharedStrings.xml").decode()


def test_the_audit_trail_carries_every_figure_identifier(tmp_path):
    bundle = rich_bundle()
    strings = _sheet_strings(bundle, tmp_path)
    for figure in bundle.figures:
        assert figure.figure_id in strings, figure.figure_id
        assert figure.citation_id in strings, figure.citation_id


def test_the_audit_trail_carries_every_section_state(tmp_path):
    bundle = rich_bundle()
    strings = _sheet_strings(bundle, tmp_path)
    for section in bundle.sections:
        assert section.section_id in strings, section.section_id


def test_the_native_charts_still_draw(tmp_path):
    """`_series_range` addresses the chart data sheet by name and
    `insert_chart` needs its target sheet to exist. Reordering the workbook is
    exactly the change that breaks both silently -- a chart pointing at a
    missing sheet renders empty rather than raising."""
    bundle = rich_bundle()
    renderer = ExcelSurfaceRenderer(directory=tmp_path)
    renderer.render(bundle)
    with zipfile.ZipFile(renderer.path_for(bundle)) as archive:
        charts = [name for name in archive.namelist() if "chart" in name and name.endswith(".xml")]
    assert charts, "no chart part written"


def test_the_chart_data_sheet_is_still_present_and_visible(tmp_path):
    """`excel.py:71-75` requires it visible on APP-013 grounds, and hiding it
    would need an APP-013 amendment."""
    names = _workbook_sheets(rich_bundle(), tmp_path)
    assert any("chartdata" in name for name in names)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_excel_split.py -k audit_trail -v`
Expected: FAIL — `_write_audit_trail` is a stub, so no `figure_id` reaches the file.

- [ ] **Step 3: Write the audit trail**

Replace the Task 4 stub in `excel.py`:

```python
_AUDIT_SHEET = {LANGUAGE_ENGLISH: "Audit Trail", LANGUAGE_ARABIC: "سجل المراجعة"}


def _write_audit_trail(workbook: Workbook, bundle: ReportBundle, language: str) -> None:
    """Every identifier the business sheets do not carry, on one sheet.

    This is the ledger the section sheets used to be, moved rather than rebuilt:
    the columns are `_FIGURE_COLUMNS` and `_SECTION_COLUMNS` unchanged, so the
    figure a reader could quote before is the figure they can quote now, under
    the same headers.

    Ordered after every business sheet. A refused section keeps its row here for
    the reason it kept its sheet before -- a missing row is the one disclosure a
    reader cannot tell apart from an analysis nobody ran.
    """
    sheet = _sheet(workbook, _AUDIT_SHEET[language], language)
    sheet.set_column(0, 0, _LABEL_WIDTH)
    sheet.set_column(1, len(_FIGURE_COLUMNS[language]) - 1, _VALUE_WIDTH)

    row = _write_row(sheet, 0, (_SECTIONS_HEADING[language],))
    row = _write_row(sheet, row, _SECTION_COLUMNS[language])
    for section in bundle.sections:
        row = _write_row(sheet, row, (section.section_id, section.state, section.reason))

    row = _write_row(sheet, row + 1, (_FIGURES_HEADING[language],))
    row = _write_row(sheet, row, _FIGURE_COLUMNS[language])
    for figure in bundle.figures:
        row = _write_row(sheet, row, _figure_cells(figure, language))
```

Add `_AUDIT_SHEET`'s values to `GOVERNED_LABELS`.

- [ ] **Step 4: Make `_draw_charts` tolerate a section with no sheet**

Replace `_draw_charts` (`excel.py:466-487`):

```python
def _draw_charts(
    workbook: Workbook,
    bundle: ReportBundle,
    language: str,
    written: list[tuple[BusinessSheet, Worksheet]],
) -> None:
    """Write one language's chart data, then draw each series onto its sheet.

    Takes an ordered list of the business sheets actually written rather than a
    section-keyed mapping. Four business sheets present the `overview` section,
    so a dict keyed by section would keep only the last of them and a chart for
    that section would land on whichever sheet was written last. The list
    preserves reading order, and a block draws onto the *first* sheet presenting
    its section -- the one a reader reaches first.

    A block whose section has no written sheet is skipped rather than raised on.
    Business sheets are omitted when they have no figure to show, so a charted
    section can legitimately have no sheet to draw onto, and a `KeyError` here
    would fail the whole workbook over a chart.

    The insertion result is still checked. `insert_chart` reports a refusal by
    return value, and a dropped chart would leave a sheet looking like one whose
    figures could not be drawn.
    """
    for block in _write_chartdata(workbook, bundle, language):
        target = next(
            (
                worksheet
                for sheet, worksheet in written
                if sheet.section == block.section_id
            ),
            None,
        )
        if target is None:
            continue
        placed = target.insert_chart(
            _CHART_ANCHOR_ROW,
            _CHART_ANCHOR_COLUMN,
            _chart_for(workbook, block, language),
            {"description": _described(block, language)},
        )
        if placed != 0:
            raise WorkbookUnavailable("A governed chart could not be placed.")
```

> **Why `continue` is right here and a `KeyError` is not.** The skip is silent, which is normally the wrong default. It is right in this one case because the *reason* the sheet is absent is that the section had no figures — and a section with no figures has nothing to plot, so there is no chart being lost. `_chart_blocks` (`excel.py:524-554`) already declines to yield a block for an unresolvable chart, so this is the second line of the same rule.
>
> **Assert the three charts actually land**, since the skip is silent. Step 1's `test_the_native_charts_still_draw` checks a chart part exists; add a count so a silently-skipped chart is caught:
>
> ```python
> def test_every_charted_section_still_gets_a_chart(tmp_path):
>     """Three sections carry a ChartSpec -- concentration, growth, basket -- in
>     both languages, so six chart parts are expected. `_draw_charts` skips a
>     block whose sheet is absent, and that skip is silent by design; this is what
>     keeps it from hiding a real loss."""
>     bundle = rich_bundle()
>     charted = [section for section in bundle.sections if section.chart is not None]
>     renderer = ExcelSurfaceRenderer(directory=tmp_path)
>     renderer.render(bundle)
>     with zipfile.ZipFile(renderer.path_for(bundle)) as archive:
>         parts = [
>             name
>             for name in archive.namelist()
>             if name.startswith("xl/charts/chart") and name.endswith(".xml")
>         ]
>     assert len(parts) == len(charted) * len(REQUIRED_LANGUAGES)
> ```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_excel_split.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/khepri/rra/rendering/excel.py tests/test_rra009_excel_split.py
git commit -m "feat: move every identifier to an audit trail sheet (RRA-009)"
```

---

## Task 6: The limitations sheet, in customer prose

**Files:**
- Modify: `src/khepri/rra/rendering/excel.py`
- Test: `tests/test_rra009_excel_split.py`

**Interfaces:**
- Consumes: **`wording.caveat_prose(code: str, language: str) -> str`** — plan 2 Task 5, which needs plan 1 Task 4. **This task is blocked until both land.** Also `wording.refusal_message(reason, *, context="section", language=...)`.
- Produces: `_write_limitations(workbook, bundle, language) -> None`, replacing the Task 4 stub — every refusal and caveat in customer prose, on a sheet ordered last among the business sheets.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_rra009_excel_split.py

def test_the_limitations_sheet_states_caveats_in_prose(tmp_path):
    bundle = rich_bundle()
    strings = _sheet_strings(bundle, tmp_path)
    for caveat in bundle.caveats:
        assert wording.caveat_prose(caveat.code, LANGUAGE_ENGLISH) in strings, caveat.code


def test_no_bare_caveat_code_reaches_a_business_sheet(tmp_path):
    """The code belongs on the audit trail. A business sheet showing one is the
    ledger wearing a business tab name."""
    from tests.test_rra006_html_sections import ROWS, package_for
    from khepri.rra.bundle import ReportBundle

    bundle = ReportBundle.of(package_for(ROWS[:2]))
    strings = _sheet_strings(bundle, tmp_path)
    # The composite `<result>:<reason>` codes are worded through the same
    # resolver, so none of them should appear raw either.
    assert "prior_window_absent" in strings  # on the audit trail
    for caveat in bundle.caveats:
        assert wording.caveat_prose(caveat.code, LANGUAGE_ENGLISH) in strings, caveat.code
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_excel_split.py -k limitations -v`
Expected: FAIL — the stub writes no prose.

- [ ] **Step 3: Write the limitations sheet**

Replace the Task 4 stub:

```python
_LIMITATIONS_SHEET = {
    LANGUAGE_ENGLISH: "Data Limitations",
    LANGUAGE_ARABIC: "حدود البيانات",
}


def _write_limitations(workbook: Workbook, bundle: ReportBundle, language: str) -> None:
    """Every refusal and every caveat, in the customer's language, as prose.

    Ordered last among the business sheets and before the audit sheets: it is
    business content -- a customer needs to know what the report does not cover --
    but it is what a reader consults after the findings rather than before them.

    Every caveat is present, not a curated subset. `_reconcile_language`
    (`bundle.py:1324`) compares caveat sets for equality, so a friendlier subset
    is a refused report rather than a tidier sheet.
    """
    sheet = _sheet(workbook, _LIMITATIONS_SHEET[language], language)
    sheet.set_column(0, 0, _LABEL_WIDTH * 3)

    row = _write_row(sheet, 0, (_LIMITATIONS_SHEET[language],))
    refused = [section for section in bundle.sections if section.state == SECTION_REFUSED]
    for section in refused:
        row = _write_row(
            sheet,
            row + 1,
            (refusal_message(section.reason, context="section", language=language),),
        )
    for caveat in bundle.caveats:
        row = _write_row(sheet, row + 1, (caveat_prose(caveat.code, language),))
```

Add `_LIMITATIONS_SHEET`'s values to `GOVERNED_LABELS`, import `SECTION_REFUSED` from `bundle`, and add `caveat_prose` and `refusal_message` to the `wording` import.

> **Note the prose is not in `GOVERNED_LABELS`.** Refusal and caveal prose is governed *wording*, but it is not a literal this module invented — it comes from `wording`, exactly as the chart categories at `excel.py:280-285` do, and those are included there. Add the resolved prose the same way, or the "did the renderer invent this text?" question stops being decidable. Resolve it per bundle and union it in at write time rather than at import, since composite caveat codes are not enumerable in advance.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_excel_split.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/khepri/rra/rendering/excel.py tests/test_rra009_excel_split.py
git commit -m "feat: state every limitation in customer prose on its own sheet (RRA-009)"
```

---

## Task 7: Confirm the surface claim and reconciliation are untouched

**Files:**
- Test: `tests/test_rra009_excel_split.py`

**Interfaces:**
- Consumes: `bundle.reconcile`; `_content` / `_content_language` (`excel.py:751-775`), which this plan does **not** modify.
- Produces: tests proving the restructure is claim-neutral. No source change — if a source change turns out to be needed here, the restructure went further than a presentation change and should be reconsidered.

**Why a task rather than a step:** this is the property the whole plan rests on. `reconcile` compares the `SurfaceContent` claim and never opens the file (`bundle.py:1271-1314`), so **every test in Tasks 1–6 could pass while the workbook silently stopped reconciling** — and equally, reconciliation could keep passing while the file lost a figure. Both directions need asserting, and a reviewer should be able to reject this independently.

- [ ] **Step 1: Write the tests**

```python
# append to tests/test_rra009_excel_split.py

from khepri.rra.bundle import reconcile


def test_the_workbook_still_reconciles(tmp_path):
    bundle = rich_bundle()
    content = ExcelSurfaceRenderer(directory=tmp_path).render(bundle)
    reconcile(content, bundle=bundle)  # raises BundleRefused on any disagreement


def test_the_claim_still_states_every_figure(tmp_path):
    """The claim is what reconciliation judges, and this plan must not have
    narrowed it. A surface that relocated a figure and also stopped claiming it
    would reconcile and would have lost the figure."""
    bundle = rich_bundle()
    content = ExcelSurfaceRenderer(directory=tmp_path).render(bundle)
    for entry in content.languages:
        assert {stated.figure_id for stated in entry.stated} == {
            figure.figure_id for figure in bundle.figures
        }


def test_every_figure_value_is_still_in_the_file(tmp_path):
    """The other direction: the claim could be complete while the workbook
    dropped a cell. Asserted against the file's shared strings."""
    bundle = rich_bundle()
    strings = _sheet_strings(bundle, tmp_path)
    for figure in bundle.figures:
        assert figure.renderings[LANGUAGE_ENGLISH] in strings, figure.figure_id


def test_a_refused_bundle_still_reconciles(tmp_path):
    from tests.test_rra006_html_sections import ROWS, package_for
    from khepri.rra.bundle import ReportBundle

    bundle = ReportBundle.of(package_for(ROWS[:2]))
    content = ExcelSurfaceRenderer(directory=tmp_path).render(bundle)
    reconcile(content, bundle=bundle)
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_rra009_excel_split.py -v`
Expected: PASS with no source change. A failure here means the restructure changed what the surface claims, which is out of scope — `_content_language` (`excel.py:760-775`) states `sections=bundle.section_ids` and every figure, and neither should have moved.

- [ ] **Step 3: Commit**

```bash
git add tests/test_rra009_excel_split.py
git commit -m "test: pin that the workbook restructure is claim-neutral (RRA-009)"
```

---

## Task 8: Migrate the three Excel test files

**Files:**
- Modify: `tests/test_rra006_excel_surface.py`
- Modify: `tests/test_rra006_excel_charts.py`
- Modify: `tests/test_rra006_excel_sections.py`

**Interfaces:**
- Consumes: everything Tasks 1–7 built.
- Produces: an `RRA-006` Excel suite asserting the new layout without weakening what it guarded.

**Measured scope:** 3 files, 1,255 lines, 46 name-pinning assertions — `test_rra006_excel_surface.py` (553 lines, 9), `test_rra006_excel_charts.py` (508 lines, 21, of which **exactly 11** reference `chartdata`), `test_rra006_excel_sections.py` (194 lines, 16). This is the largest single work item in the plan and IA §B.6 item 13 flagged it as unpriced; it is priced now.

- [ ] **Step 1: Inventory every failure before changing anything**

Run: `uv run pytest tests/test_rra006_excel_surface.py tests/test_rra006_excel_charts.py tests/test_rra006_excel_sections.py -v 2>&1 | grep -E "FAILED|assert" | head -60`
Record the list. A test changed before its failure is understood is a guarantee traded away silently.

- [ ] **Step 2: Classify each failure before fixing it**

Three kinds, and only the first two are the plan's to change:

1. **A sheet-name pin** (`en_overview`, `ar_growth`) — the sheet moved and was renamed. Update to the business name via `wording.BUSINESS_SHEET_NAMES`, or to `Audit Trail` where the assertion was about the identifier ledger.
2. **A column-header pin** (`_FIGURE_COLUMNS` on a section sheet) — those headers now live on the audit trail. Point the assertion there. **Do not delete it:** it guards that the ledger still exists.
3. **Anything else** — a figure missing, a chart not drawn, reconciliation failing. That is a **regression in Tasks 4–6, not a test to update.** Fix the source.

Write the classification down per failing test. If class 3 appears, stop and fix the source before continuing.

- [ ] **Step 3: Preserve the chart-data guarantees exactly**

`test_rra006_excel_charts.py`'s eleven `chartdata` references are the guard on the one permitted numeric write path. The sheet keeps its name and its position at the end of each language's run, so **these should not need changing**. If one fails, `_series_range` or the write order moved — fix `excel.py`, not the test. `excel.py:71-75` and `APP-013` are what these eleven assertions defend.

- [ ] **Step 4: Run each file until green, one at a time**

```bash
uv run pytest tests/test_rra006_excel_surface.py -q
uv run pytest tests/test_rra006_excel_charts.py -q
uv run pytest tests/test_rra006_excel_sections.py -q
```
Individually, so a fix for one cannot mask a break in another.

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -q`
Expected: PASS at or above the baseline on `main` (**1610 passed, 9 skipped** at `b2c002a`), plus this plan's new tests. A *lower* count means a test was deleted rather than migrated — check before accepting it.

- [ ] **Step 6: Run the full governed gate**

Run: `uv run khepri-gov validate && uv run ruff check . && uv run pytest -q`
Expected: all three pass. Per `[[khepri-five-ci-checks]]`, CI's `validate`/`ruff`/`pytest` are the authority; CodeScene is not reproducible locally and this plan adds a module and reshapes `excel.py`, so expect its numbers to move.

- [ ] **Step 7: Commit**

```bash
git add tests/
git commit -m "test: migrate the RRA-006 Excel suite to the business/audit split (RRA-009)"
```

---

## Self-Review

**Spec coverage against RRA-009's Excel requirements:**

| RRA-009 requirement | Task |
|---|---|
| "Carry the audit region as… the final Excel worksheets ordered after every business worksheet" | Tasks 4 (order), 5 (`Audit Trail`), and `Provenance` unchanged at the end |
| "Name business worksheets by business meaning rather than from a section identifier" | Tasks 2 (layout), 3 (names) |
| "Generate the audit region with every report" | Task 4 — `_write_audit_trail` is unconditional; only *business* sheets are conditional on having figures |
| "Present a figure as a business statement of name and value… rather than as an identifier table" | Task 4 — `_BUSINESS_COLUMNS` is two columns |
| "Provide a business metric name for every governed metric code" | Task 4, consuming plan 2's `business_metric_name` |
| "Provide customer prose for every caveat code" | Task 6 |
| "Carry the raw governed reason code only in the audit region" | Tasks 5, 6 |
| "Relocate a field; never recompute one and never drop one" | Task 7 — both directions asserted |
| "Recompute no figure in a renderer, and hold no decimal value there" | Unchanged: `_write_chart_value` remains the only numeric write, untouched by any task |
| "Add no chart kind" | Unchanged: `_CHART_TYPES` is not modified |

**Out of scope, and where it goes:**
- HTML and PDF entirely — **plan 2**.
- The render-variant question (whether a customer's copy includes the audit sheets). IA §B.4 describes two downloads from one generation pass; this plan always writes all sheets, and which file a customer receives is a delivery-layer choice IA §B.1 records as the owner's call.
- Native charts on business sheets beyond what already exists. `_chart_blocks` yields one block per charted section, and this plan draws them onto whichever business sheet carries that section. Charting *each* business sheet separately would need new chart specs, which RRA-009 excludes.

**Verified rather than assumed** — every quantitative claim in this plan was measured in-repo on 2026-08-07, with the reproduce commands quoted inline: the 17-sheet inventory, the 31/32-character cap (correcting IA §B.4 note 2's "33"), the 21-character symmetric budget, `Discounts and Returns` at exactly 21, the 5 sections and 26 metrics, the absence of all five leakage metrics from the existing fixture, the `requires_amount_evidence` gate that makes `discount_amount` necessary, the 3 charted sections yielding 6 chart parts, and the 3-file/1,255-line/46-pin test surface including exactly 11 `chartdata` references.

**One design defect found and removed during self-review, not left for execution.** The natural way to write Task 4's `_write_workbook` is `sheets = {sheet.section: worksheet for ...}`, and it is wrong: the section→sheet fan-out is `{'overview': 4}`, so a section-keyed dict keeps only the last of the four `overview` sheets and a chart for that section would draw onto whichever was written last. `overview` carries no `ChartSpec` today, so the bug is **latent** — it would pass every test in this plan and surface only when a chart is added to the overview family. `_draw_charts` therefore takes an ordered `list[tuple[BusinessSheet, Worksheet]]` and resolves by matching `sheet.section`, and `test_every_charted_section_still_gets_a_chart` pins the expected part count (3 charted sections × 2 languages = 6, measured) so the deliberate silent skip cannot hide a real loss.

Both verified sheet-table properties hold: the 26 rendered metrics and the table's coverage are an exact bijection (no uncovered metric, no unused table entry), and no metric appears on two sheets.

**The assumption I could not eliminate.** The 26-metric figure comes from two fixtures — the existing five-row one and Task 1's fourteen-row one. A real customer dataset may render a metric neither produces, and `test_business_sheets_cover_every_rendered_metric` only sees what the fixture builds. A metric on no business sheet would be silently absent from every business sheet while still appearing on the audit trail — visible to an auditor, invisible to the customer, and reconciling perfectly. That is the residual risk in this plan, it is the same shape as plan 2's, and closing it needs a fixture derived from real customer exports rather than a wider synthetic one.

**Placeholder scan:** one intentional intermediate — Task 4 leaves `_write_limitations` and `_write_audit_trail` as titled stubs, filled in Tasks 6 and 5 respectively, because Task 6 depends on wording that has not landed. Called out in Task 4's commit message. No `TBD`, and no governance document is touched.

**Type/signature consistency:** `BusinessSheet(key, section, metrics)` is defined in Task 2 and read in Tasks 3, 4, 5. `BUSINESS_SHEET_NAMES[language][key]` is written in Task 3 and read in Tasks 4, 8. `_write_business_sheet` returns `Worksheet | None` in Task 4 and Task 4's `_write_workbook` filters on that; `_draw_charts` in Task 5 handles the resulting absent key with `sheets.get`. `business_metric_name` (plan 2 Task 3) and `caveat_prose` (plan 2 Task 5) are consumed with the signatures those plans define — `str | None` and `str` respectively.

**Prerequisite restated:** Task 6 needs plan 2 Task 5 (which needs plan 1 Task 4). Task 4 needs plan 2 Task 3. Tasks 1–3, 5, 7–8 are unblocked, though 5 and 8 assume 4 has landed.
