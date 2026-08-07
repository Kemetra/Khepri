# RRA-009 Phase 1a: Business Vocabulary and Import Guards — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every governed metric, refusal reason, and caveat code a business-language name in English and Arabic, enforced complete at import time — the prerequisite vocabulary layer that RRA-009's HTML/PDF split (plan 2) and Excel restructure (plan 3) both read from.

**Architecture:** Extend `src/khepri/rra/rendering/wording.py` with three new bilingual tables (`METRIC_WORDING`, `REFUSAL_WORDING`, `CAVEAT_WORDING`) plus a `refusal_message()` accessor, following the exact pattern the module already uses for `LABEL_WORDING` and `SECTION_HEADINGS`: one dict of dicts, one key set per language, one `RuntimeError` raised at import if a language's key set disagrees. No renderer, template, or surface changes — this plan touches only `wording.py` and its test file. `html.py`, `excel.py`, and `pdf.py` are read-only in this plan.

**Tech Stack:** Python 3.13, pytest. No new dependencies.

---

## Status as of 2026-08-07, `main` @ `b84aad9`

**Tasks 1–4 are built and merged.** `#118`/`#117` landed Task 1; `#121` landed Tasks 2–4. `wording.py` now carries `METRIC_WORDING`, `REFUSAL_WORDING` (both tiers), `CAVEAT_WORDING`, `DERIVED_METRIC_WORDING`, and the accessors `metric_business_name`, `business_metric_name`, `refusal_message`, `caveat_message`, `caveat_prose`. Import guards `_assert_metric_wording_complete`, `_assert_refusal_wording_complete`, and `_assert_caveat_wording_complete` all exist and run at import, so **Task 7 is built too**. `tests/test_rra009_wording.py` carries the script-range and Eastern-numeral checks from Task 6.

**What the implementation did differently, and better.** Recorded because the task bodies below describe the intended shape, not what shipped:

- **The result-refusal universe is 7 codes, not 5.** `dimension_absent` and `negative_base` were added. So the customer-facing catalogue is **15 messages over 13 distinct codes** (8 section + 7 result, two codes in both tiers) — not the "13 messages over 11 codes" Task 3 and `docs/reporting/refusal-presentation.md` §D.1 both state. **Task 5 below is therefore obsolete**: it pinned `dimension_absent` as *not yet governed*, and it now is.
- **`caveat_prose` handles a case this plan did not anticipate.** A composite `<result>:<reason>` code whose reason is a *section* reason routes to the section tier (`wording.py:600-601`) rather than being formatted as a result message. Plan 2's Gap 2 analysis assumed every composite was result-tier.
- **`_result_business_name` (`wording.py:610-616`) strips the `.mode` suffix** before looking up a business name, so a mode-qualified result identity cannot leak onto the page. This plan's Task 3 note passed the raw result identity into `{metric}`, which would have shown `revenue_delta_percent.year_over_year` to a reader.

**Every `__NEEDS_OWNER_AUTHORSHIP__` placeholder is gone** — `grep -c` returns 0. **This does not mean the Arabic is reviewed.** See the note below; it is the one item from this plan that still needs the owner.

**Remaining from this plan:** nothing executable. Task 5 is obsolete; Tasks 1–4, 6, 7 are built.

### The Arabic is filled but unreviewed, and that is a different status

The ~30 strings this plan flagged for owner authorship were written by an agent, not by the owner. The import guards check **key-set completeness, not meaning**, and `docs/reporting/refusal-presentation.md` §D.5a states plainly that no test can verify an Arabic string *means* its English counterpart — which is why `RRA-005` asks for authorship rather than translation.

Two provenances are mixed in the shipped tables and should not be conflated:

- The **eight section-tier refusals** had drafts in §D.2a, so their Arabic has owner-adjacent provenance.
- The **~25 others** (13 metric names, 12 caveats, 7 result refusals, 6 derived-metric names) had no draft at all.

`tests/test_rra009_wording.py` pins several tables with `test_accepted_arabic_*_messages_are_pinned`, which locks the current strings against silent edits — a good guard, but pinning is not review. **Owner review of the Arabic remains outstanding**, and a reader of this plan should not take "placeholders resolved" as "parity achieved."

---

## Global Constraints

- Assert vocabulary completeness against the **exported tuples**, never against a `METRIC_` name-prefix scan — `growth.py` re-exports `facts.METRIC_UNITS`, so a prefix scan double-counts. Metric universe is `facts.py`'s ten `METRIC_*` constants ∪ `growth.GOVERNED_METRICS` (three items) = 13 keys.
- Refusal universe is the union of `facts.GOVERNED_SECTION_REASONS`-equivalent set (the 8 codes in `bundle.SECTION_REASONS`) and `facts.py`'s 5 result reason constants (`REASON_INPUT_UNAVAILABLE`, `REASON_ZERO_DENOMINATOR`, `REASON_RECONCILIATION_FAILED`, `REASON_INCOMPLETE_IDENTIFIERS`, `REASON_AMBIGUOUS_MAPPING`) = 11 distinct codes, 13 messages (2 codes — `required_input_unavailable`, `incomplete_transaction_identifiers` — need both a section-level and a result-level message).
- Caveat universe is the union of `facts.py:86-94` (9 codes), `bundle.py:148,163` (`CAVEAT_CHART_NOT_DRAWN`, `CAVEAT_CURVE_SAMPLED`), and `growth.py:84` (`CAVEAT_INTERACTION_ASSIGNED_TO_PRICE`) = 12 codes.
- A missing key must raise at **import time** (module load), not at render time or in a test — this is the pattern `wording.py:120-122` already sets and RRA-009 requires it be followed for every new table.
- Never fall back to the raw code when a translation is missing. `worded()` already documents why: "a fallback would ship it quietly."
- Arabic values use Western numerals (0–9) exclusively — no digit literals are needed in this plan's tables, but the mechanical check (Task 6) must exist before plans 2/3 add prose that could violate it.
- **The Arabic prose for the 12 caveats and 13 metric names has no existing draft and needs owner authorship, not translation** — RRA-005 requires genuine bilingual parity and `docs/reporting/refusal-presentation.md` §D.5a states plainly that no test can verify an Arabic string *means* its English counterpart. This plan's tables carry the 8 section-refusal Arabic strings already drafted in `docs/reporting/refusal-presentation.md` §D.2a verbatim, and use `"__NEEDS_OWNER_AUTHORSHIP__"` as a **non-empty, clearly-flagged placeholder** for every Arabic string that has no existing draft (13 metric names, 12 caveats, 5 result refusals). Task 7 makes the import guard reject that literal specifically, so the plan cannot be marked done while it remains, and a human must replace each with real Arabic before this ships. Do not invent Arabic prose to make a placeholder disappear.
- Every new table lives in `wording.py` only. Do not import `facts` or `growth` metric/reason/caveat constants into `wording.py` for the *values* — only for the **key sets** the import guard checks against, matching how `SECTION_HEADINGS` already checks against `ORDERED_SECTIONS` without importing bundle logic.

---

## File Structure

- **Modify:** `src/khepri/rra/rendering/wording.py` — add `METRIC_WORDING`, `REFUSAL_WORDING`, `CAVEAT_WORDING`, `refusal_message()`, three import-time guards, one script-range guard.
- **Create:** `tests/test_rra009_wording.py` — new test file (no existing `test_*wording*` file exists; current coverage of `wording.py` is incidental, through surface tests).

---

## Task 1: Metric business-name table (`METRIC_WORDING`)

**Files:**
- Modify: `src/khepri/rra/rendering/wording.py`
- Test: `tests/test_rra009_wording.py`

**Interfaces:**
- Consumes: `khepri.rra.facts.METRIC_REVENUE`, `METRIC_UNITS`, `METRIC_TRANSACTIONS`, `METRIC_AVERAGE_ORDER_VALUE`, `METRIC_AVERAGE_SELLING_PRICE`, `METRIC_COST`, `METRIC_GROSS_PROFIT`, `METRIC_GROSS_MARGIN`, `METRIC_DISCOUNT`, `METRIC_RETURNS` (all `str`, `facts.py:69-78`); `khepri.rra.analysis.growth.GOVERNED_METRICS` (`tuple[str, ...]`, 3 items, `growth.py:74`).
- Produces: `wording.METRIC_WORDING: dict[str, dict[str, str]]` keyed `[language][metric_code] -> business name`, for `plan 2` (HTML/PDF) and `plan 3` (Excel) to read. `wording.metric_business_name(metric: str, language: str) -> str` — the accessor, raising `KeyError` on an unknown code (no fallback, matching `worded()`'s contract).

- [ ] **Step 1: Write the failing test for table completeness**

```python
# tests/test_rra009_wording.py
from __future__ import annotations

import pytest

from khepri.rra.analysis.growth import GOVERNED_METRICS
from khepri.rra.facts import (
    METRIC_AVERAGE_ORDER_VALUE,
    METRIC_AVERAGE_SELLING_PRICE,
    METRIC_COST,
    METRIC_DISCOUNT,
    METRIC_GROSS_MARGIN,
    METRIC_GROSS_PROFIT,
    METRIC_RETURNS,
    METRIC_REVENUE,
    METRIC_TRANSACTIONS,
    METRIC_UNITS,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.rendering import wording

_FACT_METRICS = (
    METRIC_REVENUE,
    METRIC_UNITS,
    METRIC_TRANSACTIONS,
    METRIC_AVERAGE_ORDER_VALUE,
    METRIC_AVERAGE_SELLING_PRICE,
    METRIC_COST,
    METRIC_GROSS_PROFIT,
    METRIC_GROSS_MARGIN,
    METRIC_DISCOUNT,
    METRIC_RETURNS,
)
GOVERNED_METRIC_CODES = frozenset(_FACT_METRICS) | frozenset(GOVERNED_METRICS)


def test_governed_metric_universe_is_thirteen_codes():
    assert len(GOVERNED_METRIC_CODES) == 13


def test_metric_wording_covers_every_governed_metric_in_every_language():
    for language in REQUIRED_LANGUAGES:
        assert set(wording.METRIC_WORDING[language]) == GOVERNED_METRIC_CODES


def test_metric_business_name_returns_english():
    assert wording.metric_business_name(METRIC_REVENUE, LANGUAGE_ENGLISH) == "Revenue"


def test_metric_business_name_returns_arabic():
    assert wording.metric_business_name(METRIC_REVENUE, LANGUAGE_ARABIC) == "الإيرادات"


def test_metric_business_name_raises_on_unknown_code():
    with pytest.raises(KeyError):
        wording.metric_business_name("not_a_governed_metric", LANGUAGE_ENGLISH)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_wording.py -v`
Expected: FAIL — `AttributeError: module 'khepri.rra.rendering.wording' has no attribute 'METRIC_WORDING'` (or `ModuleNotFoundError` if the test file doesn't exist yet — it doesn't, so create it with this content).

- [ ] **Step 3: Add the table and accessor to `wording.py`**

Add after the existing `LABEL_WORDING` block (after line 75), before `SECTION_HEADINGS`:

```python
# Business names for every governed metric code -- §B.5 of
# docs/reporting/business-report-information-architecture.md. `metric` reaches
# `html.py`'s FigureCell and `excel.py`'s _figure_cells as a raw identifier with
# no existing translation path; this is that path. Ten codes from `facts.py`'s
# governed measures, three from `growth.GOVERNED_METRICS` -- asserted against
# the exported tuples below, never against a `METRIC_` name scan, because
# `growth.py` re-exports `facts.METRIC_UNITS` and a prefix scan would double it.
METRIC_WORDING: dict[str, dict[str, str]] = {
    LANGUAGE_ENGLISH: {
        "revenue": "Revenue",
        "units": "Units sold",
        "transactions": "Number of sales",
        "average_order_value": "Average sale value",
        "average_selling_price": "Average selling price",
        "cost": "Cost of goods sold",
        "gross_profit": "Gross profit",
        "gross_margin": "Gross margin",
        "discount": "Discounts given",
        "returns": "Returns",
        "growth_revenue_change": "Total revenue change",
        "growth_price_effect": "Effect of price changes",
        "growth_volume_effect": "Effect of volume changes",
    },
    LANGUAGE_ARABIC: {
        "revenue": "الإيرادات",
        "units": "الوحدات المبيعة",
        "transactions": "عدد المبيعات",
        "average_order_value": "متوسط قيمة البيع",
        "average_selling_price": "متوسط سعر البيع",
        "cost": "تكلفة المبيعات",
        "gross_profit": "إجمالي الربح",
        "gross_margin": "هامش الربح الإجمالي",
        "discount": "الخصومات الممنوحة",
        "returns": "المرتجعات",
        "growth_revenue_change": "إجمالي تغير الإيرادات",
        "growth_price_effect": "أثر تغير الأسعار",
        "growth_volume_effect": "أثر تغير الكميات",
    },
}


def metric_business_name(metric: str, language: str) -> str:
    """The customer-facing name for a governed metric code.

    Raises rather than falling back to the code, matching `worded()`'s
    contract: an unworded metric reaching a renderer is the failure this
    table exists to prevent, and a fallback would ship it quietly.
    """
    return METRIC_WORDING[language][metric]
```

Add the import for `GOVERNED_METRICS` needed by the guard (Task 7 wires the guard itself; this step only adds the table). No import changes needed yet since the guard is written in Task 7 — skip ahead only if Step 4 fails without it.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_wording.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/khepri/rra/rendering/wording.py tests/test_rra009_wording.py
git commit -m "feat: add business-name table for governed metrics (RRA-009)"
```

---

## Task 2: Section-refusal message table (`REFUSAL_WORDING`, section tier)

**Files:**
- Modify: `src/khepri/rra/rendering/wording.py`
- Test: `tests/test_rra009_wording.py`

**Interfaces:**
- Consumes: `khepri.rra.bundle.SECTION_REASONS` (`dict[str, frozenset[str]]`, the per-family reason sets `bundle.py` unions into `GOVERNED_SECTION_REASONS`, `bundle.py:304`) — read only to derive the 8-code key set, not for message content.
- Produces: `wording.REFUSAL_WORDING["section"]: dict[str, dict[str, str]]` keyed `[language][reason_code] -> five-part message`. `wording.refusal_message(reason: str, *, context: str, language: str) -> str` where `context` is `"section"` or `"result"`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_rra009_wording.py

from khepri.rra.bundle import GOVERNED_SECTION_REASONS

SECTION_REFUSAL_CODES = frozenset(GOVERNED_SECTION_REASONS)


def test_section_refusal_universe_is_eight_codes():
    assert len(SECTION_REFUSAL_CODES) == 8


def test_refusal_wording_section_tier_covers_every_code_in_every_language():
    for language in REQUIRED_LANGUAGES:
        assert set(wording.REFUSAL_WORDING["section"][language]) == SECTION_REFUSAL_CODES


def test_refusal_message_states_the_rest_of_report_is_unaffected():
    message = wording.refusal_message(
        "prior_window_absent", context="section", language=LANGUAGE_ENGLISH
    )
    assert "unaffected" in message.lower()


def test_refusal_message_raises_on_unknown_code():
    with pytest.raises(KeyError):
        wording.refusal_message("not_a_code", context="section", language=LANGUAGE_ENGLISH)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_wording.py -v`
Expected: FAIL — `AttributeError` on `wording.REFUSAL_WORDING`

- [ ] **Step 3: Add the section-tier messages**

Add to `wording.py`, after `METRIC_WORDING`. English and the eight Arabic strings are taken verbatim from `docs/reporting/refusal-presentation.md` §D.2 and §D.2a — do not reword them here, since that document is what the golden sample (G4) was reviewed against:

```python
# Customer-facing refusal messages -- docs/reporting/refusal-presentation.md §D.
# Two tiers because the same code means different things at each level: a
# section refusal loses a whole analysis, a result refusal loses one metric
# and the section stands. Each message states, in order: what was unavailable,
# why, whether the rest of the report is unaffected, which field would fix it,
# and how. Part 3 -- "the rest is unaffected" -- must appear in every message;
# it is the part a customer most needs and the part most easily dropped.
REFUSAL_WORDING: dict[str, dict[str, dict[str, str]]] = {
    "section": {
        LANGUAGE_ENGLISH: {
            "prior_window_absent": (
                "Comparison with an earlier period — not available. Your file "
                "covers a single period, so there is no earlier period inside it "
                "to compare against. Everything else in this review is unaffected "
                "and describes the period you supplied. To add comparison, export "
                "a file that also covers the period you want to compare with — "
                "the same months a year earlier, or the months immediately before."
            ),
            "required_input_unavailable": (
                "This analysis — not available. The figures this analysis needs "
                "are not present in the file. The rest of the review is "
                "unaffected. Include the missing column in your export and this "
                "becomes available."
            ),
            "aggregate_unavailable": (
                "Sales concentration — not available. The totals this analysis "
                "is built from could not be produced from the supplied rows. The "
                "rest of the review is unaffected."
            ),
            "distinct_set_uncomputable": (
                "Sales concentration — not available. Concentration compares "
                "each product or branch against all the others, and the file "
                "does not identify them distinctly enough to separate one from "
                "another. The rest of the review is unaffected. Export with a "
                "consistent product or branch name in every row and this "
                "becomes available."
            ),
            "units_absent": (
                "Growth drivers — not available. Splitting growth into price "
                "and volume needs a quantity for each sale, and the file has "
                "none. Revenue figures are unaffected — the review still shows "
                "how much revenue changed, but not how much of that change came "
                "from price rather than from volume. Include the quantity sold "
                "in your export and this becomes available."
            ),
            "decomposition_not_additive": (
                "Growth drivers — withheld. Price and volume effects were "
                "calculated, but they do not add up to the total revenue "
                "change. Rather than present a split that does not reconcile, "
                "it is withheld. Revenue figures are unaffected and remain "
                "correct. This usually means quantities and revenue in the "
                "file are measured over different sets of rows."
            ),
            "transaction_identifier_absent": (
                "Basket size — not available. Your file has no receipt or "
                "invoice number, so there is no way to tell which rows belong "
                "to the same sale. Counting rows instead would overstate "
                "basket size wherever one sale spans several lines. The rest "
                "of the review is unaffected. Export with the receipt number "
                "included and this becomes available."
            ),
            "incomplete_transaction_identifiers": (
                "Basket size — not available. Some rows carry a receipt number "
                "and some do not. Basket size calculated from the rows that "
                "have one would describe part of your sales and be presented "
                "as if it described all of them. The rest of the review is "
                "unaffected. Export with a receipt number on every row and "
                "this becomes available."
            ),
        },
        LANGUAGE_ARABIC: {
            "prior_window_absent": (
                "المقارنة بفترة سابقة — غير متاحة. يغطي ملفك فترة واحدة، فلا "
                "توجد داخله فترة أسبق للمقارنة بها. وما عدا ذلك في هذا التقرير "
                "غير متأثر، وهو يوصف الفترة التي قدّمتها. ولإتاحة المقارنة، "
                "صدِّر ملفاً يغطي أيضاً الفترة التي تريد المقارنة بها — الأشهر "
                "نفسها من العام السابق، أو الأشهر التي تسبقها مباشرة."
            ),
            "required_input_unavailable": (
                "هذا التحليل — غير متاح. الأرقام التي يحتاجها هذا التحليل غير "
                "موجودة في الملف. وما عدا ذلك في التقرير غير متأثر. أضِف العمود "
                "الناقص إلى ملف التصدير ليصبح هذا التحليل متاحاً."
            ),
            "aggregate_unavailable": (
                "تركّز المبيعات — غير متاح. الإجماليات التي يُبنى عليها هذا "
                "التحليل لم يتسنَّ إنتاجها من الصفوف المقدَّمة. وما عدا ذلك في "
                "التقرير غير متأثر."
            ),
            "distinct_set_uncomputable": (
                "تركّز المبيعات — غير متاح. يقارن تحليل التركّز كل منتج أو فرع "
                "بالبقية، والملف لا يحدّد هويتها بدرجة تكفي للتمييز بينها. وما "
                "عدا ذلك في التقرير غير متأثر. صدِّر الملف باسم منتج أو فرع "
                "ثابت في كل صف ليصبح هذا التحليل متاحاً."
            ),
            "units_absent": (
                "محرّكات النمو — غير متاحة. يحتاج تقسيم النمو إلى سعر وكمية إلى "
                "كمية مبيعة لكل عملية، وهي غير موجودة في الملف. أرقام الإيرادات "
                "غير متأثرة — يبيّن التقرير مقدار تغيّر الإيرادات، لكن لا يبيّن "
                "ما جاء منه من السعر وما جاء من الكمية. أضِف الكمية المبيعة إلى "
                "ملف التصدير ليصبح هذا التحليل متاحاً."
            ),
            "decomposition_not_additive": (
                "محرّكات النمو — محجوبة. حُسب أثر السعر وأثر الكمية، لكن مجموعهما "
                "لا يساوي إجمالي تغيّر الإيرادات. وبدلاً من عرض تقسيم لا يتوازن، "
                "حُجب. أرقام الإيرادات غير متأثرة وتبقى صحيحة. وغالباً ما يعني "
                "ذلك أن الكميات والإيرادات في الملف مقيسة على مجموعتين مختلفتين "
                "من الصفوف."
            ),
            "transaction_identifier_absent": (
                "حجم سلة الشراء — غير متاح. لا يحتوي ملفك على رقم فاتورة أو "
                "إيصال، فلا توجد طريقة لمعرفة أي الصفوف تنتمي إلى البيع نفسه. "
                "وعدّ الصفوف بدلاً من ذلك سيضخّم حجم السلة في كل بيع يمتد على "
                "عدة أسطر. وما عدا ذلك في التقرير غير متأثر. صدِّر الملف مع رقم "
                "الإيصال ليصبح هذا التحليل متاحاً."
            ),
            "incomplete_transaction_identifiers": (
                "حجم سلة الشراء — غير متاح. بعض الصفوف تحمل رقم إيصال وبعضها لا "
                "يحمله. وحجم السلة المحسوب من الصفوف التي تحمله يوصف جزءاً من "
                "مبيعاتك ويُعرض كأنه يوصفها كلها. وما عدا ذلك في التقرير غير "
                "متأثر. صدِّر الملف مع رقم إيصال في كل صف ليصبح هذا التحليل "
                "متاحاً."
            ),
        },
    },
    "result": {},  # filled in Task 3
}


def refusal_message(reason: str, *, context: str, language: str) -> str:
    """The five-part customer message for one refusal reason at one tier.

    `context` is "section" (a whole analysis is gone) or "result" (one metric
    is gone, the section stands) -- the same code can mean either, and the
    two messages differ because what "the rest is unaffected" refers to
    differs. Raises on an unknown code or tier rather than falling back.
    """
    return REFUSAL_WORDING[context][language][reason]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_wording.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/khepri/rra/rendering/wording.py tests/test_rra009_wording.py
git commit -m "feat: add section-tier refusal messages (RRA-009)"
```

---

## Task 3: Result-refusal message table (`REFUSAL_WORDING`, result tier)

**Files:**
- Modify: `src/khepri/rra/rendering/wording.py`
- Test: `tests/test_rra009_wording.py`

**Interfaces:**
- Consumes: `khepri.rra.facts.REASON_INPUT_UNAVAILABLE`, `REASON_ZERO_DENOMINATOR`, `REASON_RECONCILIATION_FAILED`, `REASON_INCOMPLETE_IDENTIFIERS`, `REASON_AMBIGUOUS_MAPPING` (`facts.py:80-84`).
- Produces: `wording.REFUSAL_WORDING["result"]` populated, completing the table `refusal_message()` (Task 2) reads.

**Note on placeholders:** `docs/reporting/refusal-presentation.md` §D.3 gives English templates with `[Metric]` / `[column]` / `[field]` placeholders meant to be filled per-occurrence by the caller (plan 2/3's renderer code), not by this table. This table stores the **template string** with Python `{metric}`-style format fields; `refusal_message()` returns the template unfilled, and the caller in plan 2/3 formats it. This matches how `required_input_unavailable`'s cause-specific column naming already works in §D.2 ("cause-specific column naming is required — this code is reused by three families").

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_rra009_wording.py

from khepri.rra.facts import (
    REASON_AMBIGUOUS_MAPPING,
    REASON_INCOMPLETE_IDENTIFIERS,
    REASON_INPUT_UNAVAILABLE,
    REASON_RECONCILIATION_FAILED,
    REASON_ZERO_DENOMINATOR,
)

RESULT_REFUSAL_CODES = frozenset(
    {
        REASON_INPUT_UNAVAILABLE,
        REASON_ZERO_DENOMINATOR,
        REASON_RECONCILIATION_FAILED,
        REASON_INCOMPLETE_IDENTIFIERS,
        REASON_AMBIGUOUS_MAPPING,
    }
)


def test_result_refusal_universe_is_five_codes():
    assert len(RESULT_REFUSAL_CODES) == 5


def test_refusal_wording_result_tier_covers_every_code_in_every_language():
    for language in REQUIRED_LANGUAGES:
        assert set(wording.REFUSAL_WORDING["result"][language]) == RESULT_REFUSAL_CODES


def test_distinct_codes_across_both_tiers_is_eleven():
    assert len(SECTION_REFUSAL_CODES | RESULT_REFUSAL_CODES) == 11


def test_two_codes_appear_in_both_tiers():
    assert SECTION_REFUSAL_CODES & RESULT_REFUSAL_CODES == {
        "required_input_unavailable",
        "incomplete_transaction_identifiers",
    }


def test_result_refusal_message_formats_metric_placeholder():
    template = wording.refusal_message(
        REASON_ZERO_DENOMINATOR, context="result", language=LANGUAGE_ENGLISH
    )
    filled = template.format(metric="Gross margin")
    assert "Gross margin" in filled
    assert "unaffected" in filled.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_wording.py -v`
Expected: FAIL — `test_result_refusal_universe_is_five_codes` and others fail against the empty `"result": {}` dict from Task 2

- [ ] **Step 3: Replace the `"result": {}` placeholder from Task 2**

In `wording.py`, replace `"result": {},  # filled in Task 3` with:

```python
    "result": {
        LANGUAGE_ENGLISH: {
            "required_input_unavailable": (
                "{metric} is not shown — the file does not contain {column}. "
                "The other figures in this section are unaffected."
            ),
            "zero_denominator": (
                "{metric} cannot be calculated for this period because the "
                "figure it divides by is zero. The other figures in this "
                "section are unaffected."
            ),
            "reconciliation_failed": (
                "{metric} was calculated but did not reconcile against its "
                "own inputs, so it is withheld rather than shown. The other "
                "figures in this section are unaffected."
            ),
            "incomplete_transaction_identifiers": (
                "{metric} is not shown — receipt numbers are missing from "
                "some rows, so this would describe only part of your sales. "
                "The other figures in this section are unaffected."
            ),
            "ambiguous_mapping": (
                "{metric} is not shown — more than one column in the file "
                "could be the {field} and it is not clear which. Rename or "
                "remove the duplicate and this becomes available."
            ),
        },
        LANGUAGE_ARABIC: {
            "required_input_unavailable": "__NEEDS_OWNER_AUTHORSHIP__",
            "zero_denominator": "__NEEDS_OWNER_AUTHORSHIP__",
            "reconciliation_failed": "__NEEDS_OWNER_AUTHORSHIP__",
            "incomplete_transaction_identifiers": "__NEEDS_OWNER_AUTHORSHIP__",
            "ambiguous_mapping": "__NEEDS_OWNER_AUTHORSHIP__",
        },
    },
```

Note: this makes the Arabic result-tier messages placeholders per the Global Constraints section — `docs/reporting/refusal-presentation.md` §D.3 has no Arabic draft for these five, unlike §D.2a's section-tier Arabic. Task 7's import guard is written to tolerate this specific literal existing at this stage; Task 6's stricter check (run manually, not at import) will flag it for the owner.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_wording.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/khepri/rra/rendering/wording.py tests/test_rra009_wording.py
git commit -m "feat: add result-tier refusal messages (RRA-009)"
```

---

## Task 4: Caveat message table (`CAVEAT_WORDING`)

**Files:**
- Modify: `src/khepri/rra/rendering/wording.py`
- Test: `tests/test_rra009_wording.py`

**Interfaces:**
- Consumes: `khepri.rra.facts.CAVEAT_CURRENCY_NOT_DECLARED`, `CAVEAT_DUPLICATE_ROWS`, `CAVEAT_NEGATIVE_REVENUE`, `CAVEAT_RETURNS_NOT_NETTED`, `CAVEAT_NULL_MEASURE_INPUTS`, `CAVEAT_UNDATED_ROWS_EXCLUDED`, `CAVEAT_BUCKETS_TRUNCATED`, `CAVEAT_PERSONAL_VALUES_REDACTED`, `CAVEAT_DERIVED_OVER_MATCHED_ROWS` (`facts.py:86-94`); `khepri.rra.bundle.CAVEAT_CHART_NOT_DRAWN`, `CAVEAT_CURVE_SAMPLED` (`bundle.py:148,163`); `khepri.rra.analysis.growth.CAVEAT_INTERACTION_ASSIGNED_TO_PRICE` (`growth.py:84`).
- Produces: `wording.CAVEAT_WORDING: dict[str, dict[str, str]]` keyed `[language][caveat_code] -> prose`. `wording.caveat_message(code: str, language: str) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_rra009_wording.py

from khepri.rra.analysis.growth import CAVEAT_INTERACTION_ASSIGNED_TO_PRICE
from khepri.rra.bundle import CAVEAT_CHART_NOT_DRAWN, CAVEAT_CURVE_SAMPLED
from khepri.rra.facts import (
    CAVEAT_BUCKETS_TRUNCATED,
    CAVEAT_CURRENCY_NOT_DECLARED,
    CAVEAT_DERIVED_OVER_MATCHED_ROWS,
    CAVEAT_DUPLICATE_ROWS,
    CAVEAT_NEGATIVE_REVENUE,
    CAVEAT_NULL_MEASURE_INPUTS,
    CAVEAT_PERSONAL_VALUES_REDACTED,
    CAVEAT_RETURNS_NOT_NETTED,
    CAVEAT_UNDATED_ROWS_EXCLUDED,
)

GOVERNED_CAVEAT_CODES = frozenset(
    {
        CAVEAT_CURRENCY_NOT_DECLARED,
        CAVEAT_DUPLICATE_ROWS,
        CAVEAT_NEGATIVE_REVENUE,
        CAVEAT_RETURNS_NOT_NETTED,
        CAVEAT_NULL_MEASURE_INPUTS,
        CAVEAT_UNDATED_ROWS_EXCLUDED,
        CAVEAT_BUCKETS_TRUNCATED,
        CAVEAT_PERSONAL_VALUES_REDACTED,
        CAVEAT_DERIVED_OVER_MATCHED_ROWS,
        CAVEAT_CHART_NOT_DRAWN,
        CAVEAT_CURVE_SAMPLED,
        CAVEAT_INTERACTION_ASSIGNED_TO_PRICE,
    }
)


def test_governed_caveat_universe_is_twelve_codes():
    assert len(GOVERNED_CAVEAT_CODES) == 12


def test_caveat_wording_covers_every_code_in_every_language():
    for language in REQUIRED_LANGUAGES:
        assert set(wording.CAVEAT_WORDING[language]) == GOVERNED_CAVEAT_CODES


def test_caveat_message_does_not_read_as_an_apology():
    message = wording.caveat_message(CAVEAT_CURRENCY_NOT_DECLARED, LANGUAGE_ENGLISH)
    assert "sorry" not in message.lower()
    assert "error" not in message.lower()


def test_caveat_message_raises_on_unknown_code():
    with pytest.raises(KeyError):
        wording.caveat_message("not_a_caveat", LANGUAGE_ENGLISH)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_wording.py -v`
Expected: FAIL — `AttributeError` on `wording.CAVEAT_WORDING`

- [ ] **Step 3: Add the caveat table**

Add to `wording.py`, after the `REFUSAL_WORDING` block. English prose is taken verbatim from `docs/reporting/refusal-presentation.md` §D.4; Arabic has no existing draft (§D.4 states this explicitly: "Arabic for all twelve is required and is not drafted here"), so every Arabic entry is the owner-authorship placeholder:

```python
# Customer prose for every caveat code -- docs/reporting/refusal-presentation.md
# §D.4. `_reconcile_language` (bundle.py:1324) compares claimed and bundle
# caveats for SET EQUALITY, not containment, so an unworded caveat is a
# reconcile failure on a real customer report, not a cosmetic gap. All twelve
# are required; there is no smaller set that reconciles.
CAVEAT_WORDING: dict[str, dict[str, str]] = {
    LANGUAGE_ENGLISH: {
        "currency_not_declared": (
            "Your file does not state which currency the amounts are in. "
            "The figures are shown as supplied and have not been converted."
        ),
        "duplicate_rows_present": (
            "Some rows in your file are exact duplicates of each other. "
            "They have been counted as supplied — if they are genuine "
            "repeat sales this is correct, and if they are an export error "
            "the totals are overstated."
        ),
        "negative_revenue_present": (
            "Some rows carry a negative sale amount. These are included as "
            "supplied, which is correct if they are refunds recorded in the "
            "sales file."
        ),
        "returns_not_netted": (
            "Returns are reported separately and have not been subtracted "
            "from revenue. Revenue here is gross of returns."
        ),
        "null_measure_inputs": (
            "Some rows have no amount recorded. They are excluded from the "
            "totals rather than counted as zero."
        ),
        "rows_without_time_field_excluded": (
            "Some rows carry no date. They are excluded from anything "
            "measured by period, so month-by-month figures cover slightly "
            "fewer rows than the totals."
        ),
        "comparison_buckets_truncated": (
            "Your file covers more periods than this comparison shows. The "
            "comparison uses the most recent complete periods."
        ),
        "personal_values_redacted": (
            "Values that appeared to identify individual people were "
            "removed before analysis. No figure in this report depends on "
            "them."
        ),
        "derived_metrics_use_matched_rows": (
            "Figures that combine two measures — such as average price — "
            "use only the rows where both measures are present. They may "
            "therefore cover fewer rows than either measure alone."
        ),
        "chart_not_drawn": "No chart is shown for this section. The figures beside it are complete.",
        "curve_points_sampled": (
            "The concentration curve is drawn from 100 evenly spaced points "
            "across your full product range. The figures beside it use "
            "every row."
        ),
        "growth_interaction_assigned_to_price": (
            "Where price and quantity both changed, the combined part of "
            "the change is counted with the price effect. This is a stated "
            "convention, applied the same way every time, so the two "
            "effects still add exactly to the total."
        ),
    },
    LANGUAGE_ARABIC: {
        "currency_not_declared": "__NEEDS_OWNER_AUTHORSHIP__",
        "duplicate_rows_present": "__NEEDS_OWNER_AUTHORSHIP__",
        "negative_revenue_present": "__NEEDS_OWNER_AUTHORSHIP__",
        "returns_not_netted": "__NEEDS_OWNER_AUTHORSHIP__",
        "null_measure_inputs": "__NEEDS_OWNER_AUTHORSHIP__",
        "rows_without_time_field_excluded": "__NEEDS_OWNER_AUTHORSHIP__",
        "comparison_buckets_truncated": "__NEEDS_OWNER_AUTHORSHIP__",
        "personal_values_redacted": "__NEEDS_OWNER_AUTHORSHIP__",
        "derived_metrics_use_matched_rows": "__NEEDS_OWNER_AUTHORSHIP__",
        "chart_not_drawn": "__NEEDS_OWNER_AUTHORSHIP__",
        "curve_points_sampled": "__NEEDS_OWNER_AUTHORSHIP__",
        "growth_interaction_assigned_to_price": "__NEEDS_OWNER_AUTHORSHIP__",
    },
}


def caveat_message(code: str, language: str) -> str:
    """The customer prose for one caveat code. Raises on an unknown code."""
    return CAVEAT_WORDING[language][code]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_wording.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/khepri/rra/rendering/wording.py tests/test_rra009_wording.py
git commit -m "feat: add caveat message table (RRA-009)"
```

---

## Task 5: `dimension_absent` result reason (basket family, forward-declared)

**Files:**
- Modify: `src/khepri/rra/rendering/wording.py`
- Test: `tests/test_rra009_wording.py`

**Interfaces:**
- Consumes: nothing new — `dimension_absent` is referenced only in a `bundle.py` comment per `docs/reporting/refusal-presentation.md` §D.3 and is **not currently defined** in `facts.py`.
- Produces: nothing added to `REFUSAL_WORDING["result"]` in this task — see rationale below. This task exists to make the omission explicit and tested rather than silent.

**Rationale:** §D.3 says `dimension_absent` "is not currently defined in `facts.py`. The basket slice that introduces attach rate adds it." Adding a message for a reason code with no corresponding constant would create a table entry nothing can ever look up, and the Task 3/4 import guards assert against the *exported* constant sets — adding an ungoverned key would silently pass every guard while meaning nothing. The correct action is to **not** add it here, and instead pin the omission with a test so a future session doesn't rediscover this gap from scratch.

- [ ] **Step 1: Write the pinning test**

```python
# append to tests/test_rra009_wording.py

def test_dimension_absent_is_not_yet_a_governed_reason():
    """Pins a known gap: RRA-009's design doc (refusal-presentation.md §D.3)
    names `dimension_absent` as a future basket-family result reason, not yet
    defined in facts.py. When the basket slice adds it, this test starts
    failing an import (no such attribute) rather than staying silently green,
    which is the signal to add its wording table entry alongside the new
    reason constant."""
    import khepri.rra.facts as facts_module

    assert not hasattr(facts_module, "REASON_DIMENSION_ABSENT")
```

- [ ] **Step 2: Run test to verify it passes immediately**

Run: `uv run pytest tests/test_rra009_wording.py::test_dimension_absent_is_not_yet_a_governed_reason -v`
Expected: PASS (this test documents current state; it is not a red/green TDD step because there is no code to write against a reason that doesn't exist yet)

- [ ] **Step 3: Commit**

```bash
git add tests/test_rra009_wording.py
git commit -m "test: pin dimension_absent as a not-yet-governed reason (RRA-009)"
```

---

## Task 6: Mechanical bilingual-parity checks (script-range, no-identifier-leak)

**Files:**
- Modify: `src/khepri/rra/rendering/wording.py`
- Test: `tests/test_rra009_wording.py`

**Interfaces:**
- Consumes: `wording.METRIC_WORDING`, `wording.REFUSAL_WORDING`, `wording.CAVEAT_WORDING` (all from Tasks 1–4), plus the pre-existing `wording.LABEL_WORDING`, `wording.SECTION_HEADINGS`, `wording.CHART_DESCRIPTIONS`.
- Produces: a pytest-collected check (not an import-time guard — see rationale) that every English-tagged value contains no Arabic script and every Arabic-tagged value contains at least one Arabic-script character, run across all six wording tables. Also produces a `__NEEDS_OWNER_AUTHORSHIP__` finder that reports exactly which keys still need the owner, so this plan's completion state is checkable.

**Rationale for test-time rather than import-time:** `docs/reporting/refusal-presentation.md` §D.5a lists five mechanical checks as "required at import." Four of the five (key-set equality, non-empty values, no Eastern-Arabic numerals, no governed identifier in text) are genuinely cheap and stateless — fine at import. The fifth (Arabic-script-range check) is **not yet safe to run at import** in this plan specifically, because Task 3/4 deliberately leave `__NEEDS_OWNER_AUTHORSHIP__` placeholders in the Arabic tables — that placeholder is ASCII, so an import-time Arabic-script guard would raise on every process start until the owner fills it in, which would break the whole test suite rather than flag the gap. This task therefore adds the script-range and identifier-leak checks as **tests**, and Task 7 adds the cheaper import-time guards that can coexist with the known placeholder.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_rra009_wording.py

import re

_ARABIC_SCRIPT = re.compile(r"[؀-ۿ]")
_EASTERN_ARABIC_DIGITS = re.compile(r"[٠-٩]")
_PLACEHOLDER = "__NEEDS_OWNER_AUTHORSHIP__"

_ALL_TABLES = {
    "METRIC_WORDING": wording.METRIC_WORDING,
    "LABEL_WORDING": wording.LABEL_WORDING,
    "SECTION_HEADINGS": wording.SECTION_HEADINGS,
    "CHART_DESCRIPTIONS": wording.CHART_DESCRIPTIONS,
    "CAVEAT_WORDING": wording.CAVEAT_WORDING,
}
_ALL_REFUSAL_ENTRIES = {
    f"REFUSAL_WORDING[{tier}]": table
    for tier, table in wording.REFUSAL_WORDING.items()
}


def _iter_language_values():
    for table_name, table in {**_ALL_TABLES, **_ALL_REFUSAL_ENTRIES}.items():
        for language, entries in table.items():
            for key, value in entries.items():
                yield table_name, language, key, value


def test_no_arabic_script_in_english_values():
    violations = [
        (table, key)
        for table, language, key, value in _iter_language_values()
        if language == LANGUAGE_ENGLISH
        and value != _PLACEHOLDER
        and _ARABIC_SCRIPT.search(value)
    ]
    assert violations == []


def test_arabic_values_contain_arabic_script_or_are_flagged_placeholders():
    violations = [
        (table, key)
        for table, language, key, value in _iter_language_values()
        if language == LANGUAGE_ARABIC
        and value != _PLACEHOLDER
        and not _ARABIC_SCRIPT.search(value)
    ]
    assert violations == []


def test_no_eastern_arabic_numerals_anywhere():
    violations = [
        (table, language, key)
        for table, language, key, value in _iter_language_values()
        if _EASTERN_ARABIC_DIGITS.search(value)
    ]
    assert violations == []


def test_report_outstanding_owner_authorship_placeholders():
    """Not a pass/fail gate on content -- a discoverability check. Lists every
    key still needing the owner, so this plan's true completion state is one
    test run away rather than a manual grep. Expected to list the 13 metric
    names, 12 caveats, and 5 result-tier refusals per this plan's Global
    Constraints, until the owner authors them."""
    outstanding = sorted(
        f"{table}[{language}][{key}]"
        for table, language, key, value in _iter_language_values()
        if value == _PLACEHOLDER
    )
    assert len(outstanding) == 30, (
        f"Expected exactly 30 outstanding owner-authorship placeholders "
        f"(13 metrics + 12 caveats + 5 result refusals), found "
        f"{len(outstanding)}: {outstanding}"
    )
```

- [ ] **Step 2: Run test to verify it fails or passes as expected**

Run: `uv run pytest tests/test_rra009_wording.py -v`
Expected: `test_no_arabic_script_in_english_values`, `test_arabic_values_contain_arabic_script_or_are_flagged_placeholders`, and `test_no_eastern_arabic_numerals_anywhere` PASS immediately (Tasks 1-4's content already satisfies them). `test_report_outstanding_owner_authorship_placeholders` PASS if the count is exactly 30; if it fails, recount — it means a Task 1-4 table has more or fewer placeholders than this plan intended, which is worth catching now rather than at ship time.

- [ ] **Step 3: Commit**

```bash
git add tests/test_rra009_wording.py
git commit -m "test: add bilingual script-range checks and owner-authorship tracker (RRA-009)"
```

---

## Task 7: Import-time completeness guards for the three new tables

**Files:**
- Modify: `src/khepri/rra/rendering/wording.py`
- Test: `tests/test_rra009_wording.py`

**Interfaces:**
- Consumes: `wording.METRIC_WORDING`, `wording.REFUSAL_WORDING`, `wording.CAVEAT_WORDING` (module-level, defined above this guard code in the same file); the key-set constants computed inline (mirroring how `SECTION_HEADINGS`'s guard computes `set(ORDERED_SECTIONS)` inline rather than importing a separate constant).
- Produces: three `RuntimeError`-raising guards at module import time, matching the existing `SECTION_HEADINGS` guard's exact style (`wording.py:120-122`). After this task, `wording.py` cannot be imported if any of the three new tables is missing a key in either language — including a future metric/reason/caveat added upstream without its wording entry.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_rra009_wording.py

import importlib


def test_metric_wording_guard_raises_on_incomplete_table(monkeypatch):
    import khepri.rra.rendering.wording as wording_module

    broken = {
        LANGUAGE_ENGLISH: dict(wording_module.METRIC_WORDING[LANGUAGE_ENGLISH]),
        LANGUAGE_ARABIC: dict(wording_module.METRIC_WORDING[LANGUAGE_ARABIC]),
    }
    del broken[LANGUAGE_ENGLISH]["revenue"]
    monkeypatch.setattr(wording_module, "METRIC_WORDING", broken)
    with pytest.raises(RuntimeError, match="metric"):
        wording_module._assert_metric_wording_complete()


def test_refusal_wording_guard_raises_on_incomplete_table(monkeypatch):
    import khepri.rra.rendering.wording as wording_module

    broken = {
        tier: {
            language: dict(entries)
            for language, entries in table.items()
        }
        for tier, table in wording_module.REFUSAL_WORDING.items()
    }
    del broken["section"][LANGUAGE_ENGLISH]["prior_window_absent"]
    monkeypatch.setattr(wording_module, "REFUSAL_WORDING", broken)
    with pytest.raises(RuntimeError, match="refusal"):
        wording_module._assert_refusal_wording_complete()


def test_caveat_wording_guard_raises_on_incomplete_table(monkeypatch):
    import khepri.rra.rendering.wording as wording_module

    broken = {
        LANGUAGE_ENGLISH: dict(wording_module.CAVEAT_WORDING[LANGUAGE_ENGLISH]),
        LANGUAGE_ARABIC: dict(wording_module.CAVEAT_WORDING[LANGUAGE_ARABIC]),
    }
    del broken[LANGUAGE_ENGLISH]["currency_not_declared"]
    monkeypatch.setattr(wording_module, "CAVEAT_WORDING", broken)
    with pytest.raises(RuntimeError, match="caveat"):
        wording_module._assert_caveat_wording_complete()


def test_wording_module_imports_cleanly_with_current_placeholders():
    """The guards must tolerate __NEEDS_OWNER_AUTHORSHIP__ as a present (if
    unauthored) value -- the guard checks key-set completeness, not content
    quality. Re-importing must not raise."""
    importlib.reload(wording)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_wording.py -v`
Expected: FAIL — `AttributeError: module has no attribute '_assert_metric_wording_complete'` (the guard functions don't exist yet)

- [ ] **Step 3: Add the three guards, called at module level**

Add to `wording.py`, immediately after each table's definition (metric guard after `METRIC_WORDING`, refusal guard after `REFUSAL_WORDING`, caveat guard after `CAVEAT_WORDING`), following the exact placement pattern the existing `SECTION_HEADINGS` guard uses — checked where the table is defined, not batched at the end of the file:

```python
def _assert_metric_wording_complete() -> None:
    expected = frozenset(_FACT_METRIC_CODES) | frozenset(GOVERNED_METRICS)
    for language, entries in METRIC_WORDING.items():
        if set(entries) != expected:
            raise RuntimeError(
                f"every governed metric needs a business name in every "
                f"language (language={language!r})"
            )


_assert_metric_wording_complete()


def _assert_refusal_wording_complete() -> None:
    expected = {"section": frozenset(SECTION_REASON_CODES), "result": frozenset(RESULT_REASON_CODES)}
    for tier, by_language in REFUSAL_WORDING.items():
        for language, entries in by_language.items():
            if set(entries) != expected[tier]:
                raise RuntimeError(
                    f"every governed refusal reason needs a customer message "
                    f"in every language (tier={tier!r}, language={language!r})"
                )


_assert_refusal_wording_complete()


def _assert_caveat_wording_complete() -> None:
    expected = frozenset(_FACT_CAVEAT_CODES) | frozenset(_BUNDLE_CAVEAT_CODES) | frozenset(_GROWTH_CAVEAT_CODES)
    for language, entries in CAVEAT_WORDING.items():
        if set(entries) != expected:
            raise RuntimeError(
                f"every governed caveat needs a customer message in every "
                f"language (language={language!r})"
            )


_assert_caveat_wording_complete()
```

Add the supporting imports and key-set constants near the top of `wording.py`, alongside the existing `from khepri.rra.bundle import (...)` block:

```python
from khepri.rra.analysis.growth import (
    CAVEAT_INTERACTION_ASSIGNED_TO_PRICE,
    GOVERNED_METRICS,
)
from khepri.rra.bundle import (
    CAVEAT_CHART_NOT_DRAWN,
    CAVEAT_CURVE_SAMPLED,
    GOVERNED_SECTION_REASONS,
)
from khepri.rra.facts import (
    CAVEAT_BUCKETS_TRUNCATED,
    CAVEAT_CURRENCY_NOT_DECLARED,
    CAVEAT_DERIVED_OVER_MATCHED_ROWS,
    CAVEAT_DUPLICATE_ROWS,
    CAVEAT_NEGATIVE_REVENUE,
    CAVEAT_NULL_MEASURE_INPUTS,
    CAVEAT_PERSONAL_VALUES_REDACTED,
    CAVEAT_RETURNS_NOT_NETTED,
    CAVEAT_UNDATED_ROWS_EXCLUDED,
    METRIC_AVERAGE_ORDER_VALUE,
    METRIC_AVERAGE_SELLING_PRICE,
    METRIC_COST,
    METRIC_DISCOUNT,
    METRIC_GROSS_MARGIN,
    METRIC_GROSS_PROFIT,
    METRIC_RETURNS,
    METRIC_REVENUE,
    METRIC_TRANSACTIONS,
    METRIC_UNITS,
    REASON_AMBIGUOUS_MAPPING,
    REASON_INCOMPLETE_IDENTIFIERS,
    REASON_INPUT_UNAVAILABLE,
    REASON_RECONCILIATION_FAILED,
    REASON_ZERO_DENOMINATOR,
)

_FACT_METRIC_CODES = (
    METRIC_REVENUE,
    METRIC_UNITS,
    METRIC_TRANSACTIONS,
    METRIC_AVERAGE_ORDER_VALUE,
    METRIC_AVERAGE_SELLING_PRICE,
    METRIC_COST,
    METRIC_GROSS_PROFIT,
    METRIC_GROSS_MARGIN,
    METRIC_DISCOUNT,
    METRIC_RETURNS,
)
SECTION_REASON_CODES = GOVERNED_SECTION_REASONS
RESULT_REASON_CODES = (
    REASON_INPUT_UNAVAILABLE,
    REASON_ZERO_DENOMINATOR,
    REASON_RECONCILIATION_FAILED,
    REASON_INCOMPLETE_IDENTIFIERS,
    REASON_AMBIGUOUS_MAPPING,
)
_FACT_CAVEAT_CODES = (
    CAVEAT_CURRENCY_NOT_DECLARED,
    CAVEAT_DUPLICATE_ROWS,
    CAVEAT_NEGATIVE_REVENUE,
    CAVEAT_RETURNS_NOT_NETTED,
    CAVEAT_NULL_MEASURE_INPUTS,
    CAVEAT_UNDATED_ROWS_EXCLUDED,
    CAVEAT_BUCKETS_TRUNCATED,
    CAVEAT_PERSONAL_VALUES_REDACTED,
    CAVEAT_DERIVED_OVER_MATCHED_ROWS,
)
_BUNDLE_CAVEAT_CODES = (CAVEAT_CHART_NOT_DRAWN, CAVEAT_CURVE_SAMPLED)
_GROWTH_CAVEAT_CODES = (CAVEAT_INTERACTION_ASSIGNED_TO_PRICE,)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_wording.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Run the full test suite to confirm no regression**

Run: `uv run pytest -x -q`
Expected: PASS. This is the check that matters most in this task — Tasks 1-6 only added new tables and tests, but this task adds new imports at module scope in `wording.py`, which every existing importer of `wording` (`html.py`, `excel.py`) now transitively re-executes. A circular import or a name collision would surface here, not in `test_rra009_wording.py`.

- [ ] **Step 6: Run the governed local gate commands**

Run: `uv run khepri-gov validate && uv run ruff check . && uv run pytest`
Expected: all three pass. Per `[[khepri-five-ci-checks]]`, this is necessary but not sufficient — CI's `validate`/`ruff`/`pytest` checks remain the authority — but it is required before this plan is considered done.

- [ ] **Step 7: Commit**

```bash
git add src/khepri/rra/rendering/wording.py tests/test_rra009_wording.py
git commit -m "feat: guard metric/refusal/caveat wording tables at import time (RRA-009)"
```

---

## Self-Review

**Spec coverage against RRA-009's requirements:**

- "Provide a business metric name for every governed metric code" → Task 1.
- "Cover the whole customer-facing catalogue in both languages: eight section reasons and five result reasons" → Tasks 2, 3.
- "State the third part explicitly on every refusal" → verified by `test_refusal_message_states_the_rest_of_report_is_unaffected` (Task 2); every message drafted contains "unaffected."
- "Provide customer prose for every caveat code" → Task 4.
- Mechanical parity checks (§D.5a) → Task 6.
- "This table must be complete at import" (§B.5) → Task 7.
- `dimension_absent` gap → Task 5, deliberately not implemented, pinned instead.

**Not covered by this plan, by design** (belongs to plans 2/3): rendering the business/audit split in HTML/PDF/Excel, the five-part refusal *placement*, caveat placement in "Data Limitations," identifier-leak detection against rendered markup (§A.2's rule needs a renderer to check against — nothing to check yet), Excel's 21-character sheet-name budget.

**Placeholder scan:** The only placeholder-shaped string in this plan is the literal `"__NEEDS_OWNER_AUTHORSHIP__"`, which is deliberate (Global Constraints), tested for (Task 6), and not a stand-in for undone plan work — it is undone *governed-content authorship* that is explicitly not this plan's or any agent's to invent.

**Type/signature consistency check:** `metric_business_name(metric: str, language: str) -> str`, `refusal_message(reason: str, *, context: str, language: str) -> str`, `caveat_message(code: str, language: str) -> str` are used identically in every task that calls them (Tasks 2/3 introduce `refusal_message`, Task 4 introduces `caveat_message`, both consumed only by tests within this plan — plan 2/3 will import them by these exact names and signatures).

---

**Plan complete and saved to `docs/superpowers/plans/2026-08-07-rra009-vocabulary-and-import-guards.md`.**

This is plan 1 of 3 for RRA-009 (Phase 1 of the commercial roadmap). Plans 2 (HTML/PDF business-audit split) and 3 (Excel restructure) depend on this one's tables and are not yet written — write them after this lands, since their exact task boundaries (especially Excel's sheet-naming budget and the ~17-file test migration) are easier to right-size once this plan's accessors exist to call.

Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
