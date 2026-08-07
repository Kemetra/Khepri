# RRA-009 Phase 1b: HTML and PDF Business/Audit Split — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the web and print surfaces into a business report a retail owner reads for the finding and a separated governed audit-evidence region carrying every identifier — with no identifier in the business body's visible text, no figure or caveat missing from the audit region, and the PDF appendix rendered from the same partial as the HTML evidence page so the two can never disagree.

**Architecture:** The audit region is authored **once**, as a Jinja macro in a new `_evidence.html.j2` partial, following the `_chart.svg.j2` precedent already imported at `report.html.j2:1`. Three consumers render it: a new standalone `report.evidence.html.j2` page (HTML), a new `{% block appendix %}` filled by `report.pdf.html.j2` (PDF), and nothing else. `HtmlSurface` gains a second field `evidence: dict[str, str]` rather than extra keys in `documents`, which leaves `html.py:191`'s two-key invariant and its test untouched. No figure is recomputed, no value is dropped, and no reconcile contract changes — verified: `reconcile` (`bundle.py:1271-1314`) validates the `SurfaceContent` claim and never parses a rendered document, so relocating a field is claim-neutral.

**Tech Stack:** Python 3.13, Jinja2 (`StrictUndefined`, unconditional autoescape), pytest. No new dependencies.

## Prerequisite

**Plan 1 tasks 2–4 must land before this plan's Task 5.** Only `METRIC_WORDING` (plan 1 Task 1) is merged, at `e1747d3`. This plan consumes two accessors that do not exist yet:

- `wording.refusal_message(reason: str, *, context: str, language: str) -> str` — plan 1 Tasks 2 and 3
- `wording.caveat_message(code: str, language: str) -> str` — plan 1 Task 4

Tasks 1–4 and 7–8 of this plan do not depend on them and may proceed in parallel with plan 1. **Do not re-define those tables here** — a second definition is a second place for the vocabulary to disagree.

## Two vocabulary gaps found while verifying this plan, which change its scope

Both were discovered by rendering the existing test fixture and comparing it against plan 1's tables. Neither is visible from the design package, and both would surface as `REASON_SURFACE_FAILED` on a customer's report rather than as a test failure, so both are handled explicitly below rather than left for an executing agent to hit.

**Gap 1 — the rendered metric set is larger than the governed metric vocabulary.** Plan 1's `METRIC_WORDING` covers the 13 codes `docs/reporting/business-report-information-architecture.md` §B.5 names. The fixture bundle renders **26** distinct metrics, so 13 have no business name:

```
basket_attach_rate            basket_items_per_transaction
concentration_curve           concentration_distinct_values
concentration_ranked_values   concentration_top_decile_share
concentration_top_quartile_share
revenue_by_period             revenue_by_product
revenue_delta_absolute        revenue_delta_percent
units_by_period               units_by_product
```

Reproduce with:
```bash
uv run python -c "
from tests.test_rra006_html_sections import ROWS, package_for
from khepri.rra.bundle import ReportBundle
from khepri.rra.rendering import wording
b = ReportBundle.of(package_for(ROWS))
print(sorted({f.metric for f in b.figures} - set(wording.METRIC_WORDING['en'])))"
```

§B.5 anticipated four of these as "derived labels the surfaces also need — **not** part of the 13-key assertion, because they are not governed metric codes" (items per sale, attach rate, concentration bucket share, cumulative share). The other nine are the `_by_period` / `_by_product` / `_delta_*` series-and-bucket variants, which §B.5 did not enumerate at all.

**Consequence for Task 3:** `metric_business_name` cannot be called unguarded on every cell. Task 3 handles this and the plan does **not** silently extend plan 1's 13-key import guard — that guard asserts the *governed* vocabulary and widening it to 26 would make it assert something weaker.

**Gap 2 — some caveat codes are composite `<result>:<reason>` pairs, not bare vocabulary codes.** The fixture carries:

```
revenue_delta_absolute.year_over_year:prior_window_absent
revenue_delta_percent.year_over_year:prior_window_absent
```

A `chrome.caveat_prose[caveat.code]` lookup raises `KeyError` on these, caught at `bundle.py:1213-1219` as `REASON_SURFACE_FAILED` — no report published. Plan 1's `CAVEAT_WORDING` keys the 12 bare vocabulary codes and cannot key these, because the result prefix is mode-qualified and unbounded.

**These are not caveats at all — they are result-tier refusals travelling as caveats**, and `bundle.py:1552-1572` says so in its own words: a partially refusing family has no other channel, its section is present, and "`SECTION_REASONS` will not admit a per-metric reason as a section state," so "the reason travels as a caveat scoped to the section." The code is built at `bundle.py:1570` as `f"{refusal.metric}:{refusal.reason}"`.

**This is a clean fit rather than a workaround.** Plan 1 Task 3 words exactly this vocabulary as the *result* tier, with a `{metric}` placeholder — `"{metric} is not shown — ... The other figures in this section are unaffected."` The part before the colon is the result identity that fills `{metric}`; the part after is the governed reason that selects the message. So Task 5 splits on the last colon and routes to `refusal_message(reason, context="result", language=...)`, and no new vocabulary is needed.

**Consequence for Task 5:** caveat prose is resolved by a helper handling both shapes, not a bare dict subscript.

---

## Global Constraints

- **Recompute nothing and drop nothing.** `html.py:1-9` states the rule the module exists to hold: the view model carries `text`, the arithmetic happened once in `bundle`, and no `Decimal` is in reach. `FigureCell` has no `value` field on purpose (`html.py:141-148`). Relocating a field is permitted; recomputing or deleting one is not.
- **The audit region is generated for every report, always.** Never conditional, never a delivery-time filter. `REQUIRED_SURFACES` is compared for exact equality in seven places (`bundle.py:1222`, `pipeline.py:156`, `pipeline.py:345`, `reports.py:253`, `delivery_persistence.py:349`, `benchmark_trial.py:164`, and `delivery_persistence.py:346-350` which raises `DeliveryCorrupted`). Whether a customer's *copy* presents it is a render variant decided before storage — out of scope for this plan, which always renders both regions.
- **The disclosure is immutable.** `bundle.py:1319-1323` compares it in full; shortening, softening, or re-translating it raises `disclosure_altered`. It stays in the business body verbatim.
- **Every caveat needs prose, and the set must be complete.** `bundle.py:1324` compares `frozenset(entry.caveats) != frozenset(bundle.caveats)` — set *equality*, not containment. A business region showing a friendly subset fails to reconcile.
- **Identifiers survive in an attribute only where the reader uses them.** An `id=` anchor is navigation and survives; `data-figure-id` serves tooling and is removed from the business body. Leak detection therefore tests **visible text with tags stripped**, never raw markup — otherwise every legitimate anchor reads as a leak.
- **`StrictUndefined` is on.** A context key a template asks for and the renderer did not supply raises at render time rather than producing an empty string. Every new template key must be supplied in `build_context` or the page fails closed — which is the intended behaviour, not a hazard to work around.
- **Add no chart kind.** `GOVERNED_CHART_KINDS` stays at three. The plan relocates and re-words; it draws nothing new.
- **PDF does not fork.** `report.pdf.html.j2:18` extends `report.html.j2` and fills only the blocks the parent left empty. The appendix is a new empty block in the parent, filled by the child — not a second template.
- **Never mark anything `|safe`.** `report.html.j2:6-11` states why: a page with one exemption has an escaping convention, not a guarantee. Customer labels, caveat prose, and refusal prose are all escaped.

---

## File Structure

- **Create:** `src/khepri/rra/rendering/templates/_evidence.html.j2` — the audit region as one `{% macro evidence(...) %}`, authored once and rendered by both surfaces.
- **Create:** `src/khepri/rra/rendering/templates/report.evidence.html.j2` — the standalone Technical Evidence page wrapper; imports and calls the partial.
- **Modify:** `src/khepri/rra/rendering/templates/report.html.j2` — remove identifier columns from the business figure table; replace the bare `<code>{{ section.reason }}</code>` with five-part prose; word the caveat lists; add the colophon; add `{% block appendix %}{% endblock %}`.
- **Modify:** `src/khepri/rra/rendering/templates/report.pdf.html.j2` — fill `{% block appendix %}` with the shared partial.
- **Modify:** `src/khepri/rra/rendering/html.py` — add `evidence` to `HtmlSurface` with its own key-set guard; add `EVIDENCE_TEMPLATE_NAME`; extend `_CHROME` with business and evidence wording keys; add the audit view model and the business/audit context keys; render the evidence document per language.
- **Modify:** `src/khepri/rra/rendering/templates/report.css` — style the business statement rows, refusal cards, and colophon.
- **Modify:** `src/khepri/rra/rendering/templates/report.print.css` — keep the appendix's page break and running header. Note `main > section { break-before: page }` (`report.print.css:105-112`) already breaks any new direct child of `main`.
- **Modify (tests):** `tests/test_rra006_html_sections.py`, `tests/test_rra006_html_surface.py`, `tests/test_rra006_pdf_sections.py`, `tests/test_rra006_pdf_surface.py`.
- **Create (tests):** `tests/test_rra009_business_audit_split.py` — the new contract: tier separation, leak detection against visible text, coverage completeness.

`excel.py` and its tests are **out of scope** and belong to plan 3.

---

## Task 1: Add the `evidence` field to `HtmlSurface`, rendered empty

**Files:**
- Modify: `src/khepri/rra/rendering/html.py`
- Test: `tests/test_rra009_business_audit_split.py` (create)

**Interfaces:**
- Consumes: `HtmlSurface` (`html.py:178-194`), `REQUIRED_LANGUAGES` (`narrative.py:75`).
- Produces: `HtmlSurface.evidence: dict[str, str]`, keyed by language exactly as `documents` is, guarded by its own key-set check. `HtmlReportRenderer.render_html()` returns it populated. Tasks 2–6 fill its content; this task establishes the field and proves the two-key invariant on `documents` is unaffected.

**Why a second field rather than more keys in `documents`:** `html.py:190-192` raises `ValueError("An HTML surface publishes exactly the governed languages.")` when `set(self.documents) != set(REQUIRED_LANGUAGES)`. An `evidence_en` key would break that invariant and `tests/test_rra006_html_surface.py:181` with it. RRA-009 requires "a distinct web page," which is a separate document — so a separate field is both the compliant and the non-breaking shape.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rra009_business_audit_split.py
"""RRA-009: the business report and the separated audit-evidence region.

The bundle helpers here mirror `tests/test_rra006_html_sections.py`'s `page()`
so this file can assert on both regions without re-deriving a fact package.
"""

from __future__ import annotations

import re

from khepri.rra.bundle import ReportBundle
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.rendering.html import HtmlReportRenderer

# The existing fixture builders, verified present at
# `tests/test_rra006_html_sections.py:38,47`. `ROWS` is five rows over five days;
# `ROWS[:2]` is the two-day slice that settles no prior period, which is how the
# existing suite produces a refused `comparison` section (see `:133`).
from tests.test_rra006_html_sections import ROWS, package_for


def _bundle(rows: list | None = None) -> ReportBundle:
    return ReportBundle.of(package_for(rows or ROWS))


def _surface(rows: list | None = None):
    return HtmlReportRenderer().render_html(_bundle(rows))


def test_evidence_is_published_for_every_governed_language():
    surface = _surface()
    assert set(surface.evidence) == set(REQUIRED_LANGUAGES)


def test_evidence_is_non_empty_for_every_language():
    surface = _surface()
    for language in REQUIRED_LANGUAGES:
        assert surface.evidence[language].strip()


def test_documents_still_publishes_exactly_two_languages():
    """The invariant `html.py:190-192` already holds, restated here because this
    task adds a sibling field and the failure mode would be widening that check
    instead of adding beside it."""
    surface = _surface()
    assert set(surface.documents) == set(REQUIRED_LANGUAGES)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_business_audit_split.py -v`
Expected: FAIL — `AttributeError: 'HtmlSurface' object has no attribute 'evidence'`

- [ ] **Step 3: Add the field, the guard, and the template constant**

In `html.py`, add beside `TEMPLATE_NAME` (line 69):

```python
EVIDENCE_TEMPLATE_NAME = "report.evidence.html.j2"
```

Replace the `HtmlSurface` dataclass (`html.py:178-194`) with:

```python
@dataclass(frozen=True, slots=True)
class HtmlSurface:
    """The rendered pages, beside the claim `bundle.reconcile` will judge.

    Both are returned together because they are derived from one pass over the
    bundle. A renderer that built the claim separately from the page could
    reconcile perfectly while shipping a page that says something else.

    `evidence` is a sibling of `documents` rather than more keys inside it.
    RRA-009 requires the audit region be carried as a distinct web page, and
    `documents` publishes exactly the governed languages -- a guarantee a third
    key would silently widen. Both regions are generated for every report; which
    one a customer's copy presents is a delivery concern this surface does not
    decide.
    """

    content: SurfaceContent
    documents: dict[str, str]
    evidence: dict[str, str]

    def __post_init__(self) -> None:
        _require_governed_documents(self.documents, "documents")
        _require_governed_documents(self.evidence, "evidence")


def _require_governed_documents(documents: dict[str, str], name: str) -> None:
    if set(documents) != set(REQUIRED_LANGUAGES):
        raise ValueError(f"An HTML surface publishes exactly the governed languages in {name}.")
    for language, document in documents.items():
        _require_text(document, f"{name}[{language}]")
```

In `render_html` (`html.py:218-229`), render the evidence document and pass it:

```python
    def render_html(self, bundle: ReportBundle) -> HtmlSurface:
        """Render both regions, and the claim about what they present."""
        template = self._environment.get_template(TEMPLATE_NAME)
        evidence_template = self._environment.get_template(EVIDENCE_TEMPLATE_NAME)
        cells = {language: build_cells(bundle, language) for language in REQUIRED_LANGUAGES}
        contexts = {
            language: build_context(bundle, language, cells[language])
            for language in REQUIRED_LANGUAGES
        }
        documents = {
            language: template.render(contexts[language]) for language in REQUIRED_LANGUAGES
        }
        evidence = {
            language: evidence_template.render(contexts[language])
            for language in REQUIRED_LANGUAGES
        }
        return HtmlSurface(
            content=build_content(
                bundle,
                cells,
                # Both regions are the surface, so both are measured. A size
                # covering the business page alone would describe part of what
                # was produced and read like a measurement of all of it.
                output_size_bytes=_document_bytes(documents) + _document_bytes(evidence),
            ),
            documents=documents,
            evidence=evidence,
        )
```

Note the `output_size_bytes` decision, stated rather than left implicit: the audit region is generated for every report, so RRA-007's recorded size includes it. `build_content` takes the size as a parameter and cannot detect a wrong one.

- [ ] **Step 4: Create the minimal evidence template so rendering succeeds**

Create `src/khepri/rra/rendering/templates/report.evidence.html.j2`. Minimal for this task; Task 4 fills the body via the shared partial:

```jinja
{#
  The Technical Evidence page: one document per governed language, carrying the
  identifiers the business report does not show.

  A separate document rather than a section of the report, because RRA-009 asks
  for a distinct web page and because a business report that a customer forwards
  should not carry the audit region inside it by accident. The body comes from
  `_evidence.html.j2`, which the printed appendix renders too -- one author for
  both, so the page and the appendix cannot disagree about a figure.
#}
<!doctype html>
<html lang="{{ language }}" dir="{{ direction }}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ chrome.evidence_title }}</title>
<style>
{% include stylesheet %}
</style>
</head>
<body>
<header>
<h1>{{ chrome.evidence_title }}</h1>
<p>{{ chrome.evidence_intro }}</p>
</header>
<main id="evidence">
</main>
</body>
</html>
```

- [ ] **Step 5: Add the two chrome keys the template asks for**

`StrictUndefined` means a missing key raises at render. Add to **both** language blocks of `_CHROME` (`html.py:77-134`):

```python
        "evidence_title": "Technical evidence",
        "evidence_intro": (
            "Every figure in this report, the identifiers it is filed under, and "
            "the facts it cites. Forward this page to an auditor."
        ),
```

and the Arabic:

```python
        "evidence_title": "الأدلة التقنية",
        "evidence_intro": (
            "كل رقم في هذا التقرير، والمعرّفات المسجّل بها، والحقائق التي يُسند "
            "إليها. أرسِل هذه الصفحة إلى المراجع."
        ),
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_business_audit_split.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Run the surrounding suites to confirm nothing broke**

Run: `uv run pytest tests/test_rra006_html_surface.py tests/test_rra006_pdf_surface.py -q`
Expected: PASS. `HtmlSurface` gained a required field, so any construction site that omits it fails here — that is the point of running these now rather than at the end.

- [ ] **Step 8: Commit**

```bash
git add src/khepri/rra/rendering/html.py src/khepri/rra/rendering/templates/report.evidence.html.j2 tests/test_rra009_business_audit_split.py
git commit -m "feat: publish a separate audit-evidence document per language (RRA-009)"
```

---

## Task 2: Build the audit view model

**Files:**
- Modify: `src/khepri/rra/rendering/html.py`
- Test: `tests/test_rra009_business_audit_split.py`

**Interfaces:**
- Consumes: `FigureCell` (`html.py:141-163`), `_SectionView` (`html.py:433-447`), `bundle.caveats`, `bundle.identity`, `NarrativePassage` (`html.py:165-176`).
- Produces: a new `"audit"` key in `build_context`'s return, holding a `dict[str, object]` with `figures`, `sections`, `caveats`, `citations`, `passages`, and `provenance`. Tasks 4 and 6 render it. Every value is already in the context today — this task groups them under one key so the partial takes one argument instead of six, and so "what is in the audit region" is answerable in one place.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_rra009_business_audit_split.py

from khepri.rra.rendering.html import build_cells, build_context


def _context(language=LANGUAGE_ENGLISH):
    bundle = _bundle()
    return build_context(bundle, language, build_cells(bundle, language))


def test_audit_context_carries_every_region():
    audit = _context()["audit"]
    assert set(audit) == {
        "figures",
        "sections",
        "caveats",
        "citations",
        "passages",
        "provenance",
    }


def test_audit_figures_cover_every_bundle_figure():
    bundle = _bundle()
    context = build_context(bundle, LANGUAGE_ENGLISH, build_cells(bundle, LANGUAGE_ENGLISH))
    audited = {cell.figure_id for cell in context["audit"]["figures"]}
    assert audited == {figure.figure_id for figure in bundle.figures}


def test_audit_caveats_equal_the_bundle_caveats():
    """`bundle.py:1324` compares caveat sets for equality, so the audit region
    showing a subset would be a reconcile failure waiting for a real report."""
    bundle = _bundle()
    context = build_context(bundle, LANGUAGE_ENGLISH, build_cells(bundle, LANGUAGE_ENGLISH))
    audited = {entry["code"] for entry in context["audit"]["caveats"]}
    assert audited == {caveat.code for caveat in bundle.caveats}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_business_audit_split.py -k audit -v`
Expected: FAIL — `KeyError: 'audit'`

- [ ] **Step 3: Add the audit grouping to `build_context`**

In `html.py`, add before `build_context`:

```python
def _audit_region(
    bundle: ReportBundle,
    language: str,
    cells: tuple[FigureCell, ...],
    provenance: tuple[tuple[str, str], ...],
) -> dict[str, object]:
    """Everything the business report does not show, in one place.

    Grouped rather than passed as six separate context keys so the shared
    evidence partial takes one argument, and so "what is in the audit region"
    has a single answer a test can assert against. Nothing is computed here:
    every value is already in the context, and this is a regrouping.

    The caveat entries carry the raw code *beside* its customer prose. The code
    is what an auditor quotes; the prose is what makes the page readable without
    the reader holding the vocabulary in their head.
    """
    return {
        "figures": list(cells),
        "sections": [
            {
                "section_id": section.section_id,
                "state": section.state,
                "reason": section.reason,
            }
            for section in bundle.sections
        ],
        "caveats": [
            {"code": caveat.code, "section": caveat.section} for caveat in bundle.caveats
        ],
        "citations": sorted({cell.citation_id for cell in cells}),
        "passages": list(_passages(bundle.narrative, language)),
        "provenance": provenance,
    }
```

Then in `build_context` (`html.py:340-377`), compute the provenance once and add the key:

```python
    provenance = _provenance(bundle, extra_provenance or {})
    return {
        # ... every existing key unchanged ...
        "provenance": provenance,
        "audit": _audit_region(bundle, language, cells, provenance),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_business_audit_split.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/khepri/rra/rendering/html.py tests/test_rra009_business_audit_split.py
git commit -m "feat: group the audit region into one context key (RRA-009)"
```

---

## Task 3: Add business metric names to the figure cells

**Files:**
- Modify: `src/khepri/rra/rendering/html.py`
- Test: `tests/test_rra009_business_audit_split.py`

**Interfaces:**
- Consumes: `wording.metric_business_name(metric: str, language: str) -> str` — **merged already** at `e1747d3`, so this task has no unmet prerequisite. It raises `KeyError` on any code outside the governed 13.
- Produces: `FigureCell.metric_name: str | None`, the business name where one exists and `None` otherwise. The raw code stays on the cell because the audit region renders it; the business body renders `metric_name` when present and falls back to the row's own label. Task 6 changes the template to use it.

**Why add a field rather than translate in the template:** the template has no access to the wording module, and `_CHROME` is per-language chrome rather than per-figure data. `_row_label` (`html.py:324-337`) already establishes the pattern — translate in the cell builder, hand the template final text.

**Why `str | None` rather than `str`** — this is Gap 1 above. 13 of the 26 rendered metrics have no governed business name, and `metric_business_name` raises on them. Three options were considered:

1. *Extend plan 1's table to 26 keys.* Rejected: the import guard asserts the **governed** metric vocabulary (`facts` ∪ `growth.GOVERNED_METRICS`), and widening it to include `revenue_by_period` would make the guard assert something weaker than it claims. The governed vocabulary is 13; that is a fact about the domain, not a shortfall in the table.
2. *Fall back to the raw code.* Rejected outright: it ships `concentration_top_decile_share` to a reader, which is the exact failure `worded()`'s docstring says a fallback would "ship quietly."
3. **`None`, and the template uses the row's label instead** — with a small second table for the label-less remainder. Adopted, in the corrected form below.

**The obvious version of option 3 is wrong, and this was checked rather than assumed.** "Every unworded metric carries a label" is false. Five metrics are both unworded *and* unlabelled, so a label fallback alone would render a nameless row:

```
concentration_distinct_values      concentration_ranked_values
concentration_top_decile_share     concentration_top_quartile_share
basket_items_per_transaction
```

Reproduce with:
```bash
uv run python -c "
from tests.test_rra006_html_sections import ROWS, package_for
from khepri.rra.bundle import ReportBundle
from khepri.rra.rendering import wording
b = ReportBundle.of(package_for(ROWS))
w = set(wording.METRIC_WORDING['en'])
print([(f.metric, f.label) for f in b.figures if f.metric not in w and f.label is None])"
```

Four of the five are precisely the "derived labels the surfaces also need — **not** part of the 13-key assertion, because they are not governed metric codes" that `business-report-information-architecture.md` §B.5 already enumerates and words in both languages (share of sales, cumulative share, items per sale, attach rate). §B.5 anticipated this need; it simply did not connect it to the metric codes that carry it.

**So the adopted shape is two tables and one resolution order:**

1. `METRIC_WORDING` — the governed 13, from plan 1, import-guarded, unchanged.
2. `DERIVED_METRIC_WORDING` — a new table in `wording.py` for the label-less non-governed metrics, seeded with §B.5's four derived labels plus `concentration_distinct_values` and `concentration_ranked_values`. **Not** import-guarded against a governed vocabulary, because it words codes that are deliberately not in one; guarded instead against "every metric a bundle can render that has no label and no governed name," which Step 1 pins as a test.
3. Anything still unresolved falls back to the row's `label`, which is customer text.

`metric_name` is therefore `str | None`: `None` means "this row is named by its label," and Task 6's template renders `cell.label` in that case. A row that would end up with neither is a test failure in Step 1, not a nameless row on a customer's page.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_rra009_business_audit_split.py

from khepri.rra.facts import METRIC_REVENUE


def test_figure_cells_carry_a_business_metric_name():
    cells = build_cells(_bundle(), LANGUAGE_ENGLISH)
    revenue = next(cell for cell in cells if cell.metric == METRIC_REVENUE)
    assert revenue.metric_name == "Revenue"


def test_business_metric_name_is_translated():
    cells = build_cells(_bundle(), LANGUAGE_ARABIC)
    revenue = next(cell for cell in cells if cell.metric == METRIC_REVENUE)
    assert revenue.metric_name == "الإيرادات"


def test_the_raw_metric_code_survives_on_the_cell():
    """The audit region quotes it, so relocation must not become deletion."""
    cells = build_cells(_bundle(), LANGUAGE_ENGLISH)
    assert all(cell.metric for cell in cells)


def test_every_row_has_something_to_be_called():
    """The invariant the two-table design exists to hold.

    A row is named by its governed business name, by a derived-label name, or by
    its own customer label. A row with none of the three would render nameless,
    and this is the only place that is detectable -- `reconcile` compares the
    figure's *text* and never its name (`bundle.py:1326-1330`), so a nameless row
    reconciles perfectly.
    """
    for language in REQUIRED_LANGUAGES:
        for cell in build_cells(_bundle(), language):
            assert cell.metric_name or cell.label, (cell.metric, language)


def test_a_series_row_is_named_by_its_label_not_a_metric_name():
    """`revenue_by_period` is unworded on purpose: the row says "March", and a
    business name would repeat the column header on every row."""
    cells = build_cells(_bundle(), LANGUAGE_ENGLISH)
    series = [cell for cell in cells if cell.metric == "revenue_by_period"]
    assert series, "fixture carries no revenue_by_period figure"
    assert all(cell.metric_name is None and cell.label for cell in series)


def test_a_labelless_derived_metric_is_named_from_the_derived_table():
    """These five carry neither a governed name nor a label, and are exactly the
    derived labels §B.5 enumerates."""
    cells = build_cells(_bundle(), LANGUAGE_ENGLISH)
    for metric in (
        "basket_items_per_transaction",
        "concentration_top_decile_share",
        "concentration_top_quartile_share",
        "concentration_distinct_values",
        "concentration_ranked_values",
    ):
        matching = [cell for cell in cells if cell.metric == metric]
        assert matching, f"fixture carries no {metric} figure"
        assert all(cell.metric_name for cell in matching), metric
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_business_audit_split.py -k metric -v`
Expected: FAIL — `AttributeError: 'FigureCell' object has no attribute 'metric_name'`

- [ ] **Step 3: Add the derived-metric table to `wording.py`**

Add after `METRIC_WORDING` (which plan 1 Task 1 already landed). The English and Arabic for the first four come from `business-report-information-architecture.md` §B.5's derived-labels table verbatim; the two `concentration_*` set-size codes are not in §B.5 and are worded here:

```python
# Business names for figure metrics that are NOT governed metric codes and carry
# no customer label of their own -- so neither `METRIC_WORDING` nor the row's own
# label can name them, and without this table they would render nameless.
#
# Deliberately not guarded against the governed vocabulary: these codes are not in
# one, which is the whole reason they need a separate table. §B.5 of the
# information architecture enumerates the first four as "derived labels the
# surfaces also need -- not part of the 13-key assertion". The invariant that
# matters is asserted in the surface tests instead: every rendered row resolves to
# a governed name, a derived name, or a label.
DERIVED_METRIC_WORDING: dict[str, dict[str, str]] = {
    LANGUAGE_ENGLISH: {
        "basket_items_per_transaction": "Items per sale",
        "basket_attach_rate": "Attach rate",
        "concentration_top_decile_share": "Share of sales, top tenth",
        "concentration_top_quartile_share": "Share of sales, top quarter",
        "concentration_distinct_values": "Products or branches counted",
        "concentration_ranked_values": "Ranked contribution",
    },
    LANGUAGE_ARABIC: {
        "basket_items_per_transaction": "عدد الأصناف لكل بيع",
        "basket_attach_rate": "معدل الإضافة",
        "concentration_top_decile_share": "نصيب المبيعات، العُشر الأعلى",
        "concentration_top_quartile_share": "نصيب المبيعات، الرُبع الأعلى",
        "concentration_distinct_values": "عدد المنتجات أو الفروع",
        "concentration_ranked_values": "المساهمة مرتّبة",
    },
}


def business_metric_name(metric: str, language: str) -> str | None:
    """A row's business name, or `None` when the row is named by its own label.

    Three sources in order: the governed metric vocabulary, the derived-label
    table, then nothing -- and "nothing" is a real answer rather than a failure,
    because a series or bucket row carries a product, branch, or period name that
    is better than any name this module could supply.

    Never falls back to the raw code. `worded()` gives the reason in its own
    docstring: an identifier shown to a reader is the failure this module exists
    to prevent, and a fallback would ship it quietly.
    """
    governed = METRIC_WORDING[language].get(metric)
    if governed is not None:
        return governed
    return DERIVED_METRIC_WORDING[language].get(metric)
```

> **Arabic note.** The six Arabic strings above need owner authorship rather than proofreading, on the same grounds as plan 1's thirty: `RRA-005` requires genuine parity and §B.5 flags "attach rate" specifically as having "no settled Arabic retail term." They are written rather than left as placeholders because a nameless row is worse than a reviewable draft — but they belong in the same owner review as plan 1's.

- [ ] **Step 4: Add the field and populate it**

In `html.py`, import the resolver alongside the existing `wording` imports (`html.py:59-63`):

```python
from khepri.rra.rendering.wording import (
    CHART_DESCRIPTIONS,
    LABEL_WORDING,
    SECTION_HEADINGS,
    business_metric_name,
)
```

Add the field to `FigureCell` (`html.py:141-163`), after `metric`:

```python
    metric_name: str | None
```

`__post_init__` is **not** extended — `None` is a valid value here, and `_require_text` would reject it. The invariant that a row has *some* name is a surface-level property (a cell may legitimately have no metric name if it has a label), so it is asserted in the tests rather than in the cell constructor.

In `_cell` (`html.py:306-321`), populate it:

```python
        metric=figure.metric,
        metric_name=business_metric_name(figure.metric, language),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_business_audit_split.py -v`
Expected: PASS, including `test_every_row_has_something_to_be_called` across both languages.

- [ ] **Step 6: Confirm plan 1's governed guard is untouched**

Run: `uv run pytest tests/test_rra009_wording.py -q`
Expected: PASS unchanged. This task adds a *second* table beside `METRIC_WORDING` and must not widen plan 1's import guard — that guard asserts the governed vocabulary is completely worded, and adding `revenue_by_period` to it would make it assert something weaker. If a `test_rra009_wording.py` test needed editing to accommodate this task, that is the signal the guard was widened and the change should be reverted.

- [ ] **Step 7: Commit**

```bash
git add src/khepri/rra/rendering/wording.py src/khepri/rra/rendering/html.py tests/test_rra009_business_audit_split.py
git commit -m "feat: name every business row, by metric, derived label, or its own label (RRA-009)"
```

---

## Task 4: Author the shared audit-region partial and fill the evidence page

**Files:**
- Create: `src/khepri/rra/rendering/templates/_evidence.html.j2`
- Modify: `src/khepri/rra/rendering/templates/report.evidence.html.j2`
- Test: `tests/test_rra009_business_audit_split.py`

**Interfaces:**
- Consumes: the `audit` context key (Task 2); `chrome` (`_CHROME`, extended in Task 1); the `{% macro %}` + `{% from ... import %}` pattern established by `_chart.svg.j2:24` and used at `report.html.j2:1`.
- Produces: `{% macro evidence(audit, chrome, caveat_prose) %}` in `_evidence.html.j2`, rendering the six audit regions. Task 6 imports the same macro into the PDF appendix — one author, two surfaces, which is what keeps the page and the appendix from disagreeing about a figure.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_rra009_business_audit_split.py

def _evidence(language=LANGUAGE_ENGLISH):
    return _surface().evidence[language]


def test_evidence_page_carries_every_figure_identifier():
    bundle = _bundle()
    rendered = _evidence()
    for figure in bundle.figures:
        assert figure.figure_id in rendered, figure.figure_id


def test_evidence_page_carries_the_raw_reason_code():
    """The business body states five-part prose; the code lives only here."""
    surface = _surface(ROWS[:2])
    assert "prior_window_absent" in surface.evidence[LANGUAGE_ENGLISH]


def test_evidence_page_carries_provenance_and_citations():
    rendered = _evidence()
    assert "bundle_id" in rendered
    assert "html_surface_version" in rendered


def test_evidence_page_renders_in_both_languages():
    for language in REQUIRED_LANGUAGES:
        assert _evidence(language).strip()
```

Note: `ROWS[:2]` is the two-day slice the existing suite already uses to force a refused `comparison` section (`tests/test_rra006_html_sections.py:133`). Two days settle no prior period, so the comparison family refuses with `prior_window_absent`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_business_audit_split.py -k evidence_page -v`
Expected: FAIL — the evidence page's `<main>` is empty from Task 1, so no identifier appears.

- [ ] **Step 3: Write the partial**

Create `src/khepri/rra/rendering/templates/_evidence.html.j2`:

```jinja
{#
  The audit-evidence region, authored once and rendered twice: as the standalone
  Technical Evidence page, and as the printed report's appendix.

  One author for both is the point. `report.pdf.html.j2`'s own header records why
  a forked print template is refused -- KHEPRI-DEC-005 consolidated bilingual
  rendering so parity, the disclosure, and the figure set are each correct in one
  place. An appendix authored separately from the evidence page would be a second
  place for the figure table to drift, which is the same failure one directory
  down.

  Every identifier the business report removed appears here, and every one of
  them is escaped like any other value: `figure_id` is machine-generated, but a
  page with one exemption in it has an escaping convention rather than a
  guarantee.
#}
{% macro evidence(audit, chrome, caveat_prose) %}
<section id="evidence-figures" aria-labelledby="evidence-figures-heading">
<h2 id="evidence-figures-heading">{{ chrome.figures }}</h2>
<div class="scroller">
<table>
<caption>{{ chrome.figures_caption }}</caption>
<thead>
<tr>
<th scope="col">{{ chrome.figure_reference }}</th>
<th scope="col">{{ chrome.label }}</th>
<th scope="col">{{ chrome.metric }}</th>
<th scope="col">{{ chrome.kind }}</th>
<th scope="col">{{ chrome.unit }}</th>
<th scope="col">{{ chrome.value }}</th>
<th scope="col">{{ chrome.citation }}</th>
</tr>
</thead>
<tbody>
{% for cell in audit.figures %}
<tr>
<th scope="row"><code>{{ cell.figure_id }}</code></th>
<td>{% if cell.label is none %}{{ chrome.total }}{% else %}{{ cell.label }}{% endif %}</td>
<td><code>{{ cell.metric }}</code></td>
<td><code>{{ cell.kind }}</code></td>
<td><code>{{ cell.unit_kind }}</code></td>
<td class="figure">{{ cell.text }}</td>
<td><code>{{ cell.citation_id }}</code></td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</section>
<section id="evidence-sections" aria-labelledby="evidence-sections-heading">
<h2 id="evidence-sections-heading">{{ chrome.section_states }}</h2>
<table>
<thead>
<tr>
<th scope="col">{{ chrome.section_column }}</th>
<th scope="col">{{ chrome.state_column }}</th>
<th scope="col">{{ chrome.reason_column }}</th>
</tr>
</thead>
<tbody>
{% for entry in audit.sections %}
<tr>
<th scope="row"><code>{{ entry.section_id }}</code></th>
<td><code>{{ entry.state }}</code></td>
<td>{% if entry.reason %}<code>{{ entry.reason }}</code>{% else %}{{ chrome.none }}{% endif %}</td>
</tr>
{% endfor %}
</tbody>
</table>
</section>
<section id="evidence-caveats" aria-labelledby="evidence-caveats-heading">
<h2 id="evidence-caveats-heading">{{ chrome.caveats }}</h2>
{% if audit.caveats %}
<dl class="caveats">
{% for caveat in audit.caveats %}
<dt><code>{{ caveat.code }}</code></dt>
<dd>{{ caveat_prose[caveat.code] }}</dd>
{% endfor %}
</dl>
{% else %}
<p>{{ chrome.none }}</p>
{% endif %}
</section>
<section id="evidence-citations" aria-labelledby="evidence-citations-heading">
<h2 id="evidence-citations-heading">{{ chrome.citations }}</h2>
<ul class="citations">
{% for citation in audit.citations %}
<li id="citation-{{ citation }}"><code>{{ citation }}</code></li>
{% endfor %}
</ul>
</section>
{% if audit.passages %}
<section id="evidence-commentary" aria-labelledby="evidence-commentary-heading">
<h2 id="evidence-commentary-heading">{{ chrome.commentary_citations }}</h2>
{% for passage in audit.passages %}
<p><code>{{ passage.section_id }}</code>: {{ chrome.cites }}
{% for cited in passage.cited_fact_ids %}
<code>{{ cited }}</code>
{% endfor %}
</p>
{% endfor %}
</section>
{% endif %}
<section id="evidence-provenance" aria-labelledby="evidence-provenance-heading">
<h2 id="evidence-provenance-heading">{{ chrome.provenance }}</h2>
<dl class="provenance">
{% for name, value in audit.provenance %}
<dt><code>{{ name }}</code></dt>
<dd><code>{{ value }}</code></dd>
{% endfor %}
</dl>
</section>
{% endmacro %}
```

- [ ] **Step 4: Call the partial from the evidence page**

In `report.evidence.html.j2`, add the import as line 1 (matching `report.html.j2:1`) and call it inside `<main>`:

```jinja
{% from "_evidence.html.j2" import evidence %}
```

```jinja
<main id="evidence">
{{ evidence(audit, chrome, caveat_prose) }}
</main>
```

- [ ] **Step 5: Add the chrome keys the partial asks for**

`StrictUndefined` raises on any missing key. Add to both language blocks of `_CHROME`.

The `caveat_prose` map is a **Task 5** deliverable — it needs `wording.caveat_message`, which plan 1 Task 4 has not landed. Until then the macro's third parameter has nothing to receive, so for this task give the macro a two-parameter signature `evidence(audit, chrome)` and render `<dd><code>{{ caveat.code }}</code></dd>`. Task 5 adds the third parameter and the prose. State this in the commit message so the intermediate is not mistaken for the final contract.

English:
```python
        "figure_reference": "Figure",
        "section_states": "Section states",
        "section_column": "Section",
        "state_column": "State",
        "reason_column": "Reason",
        "commentary_citations": "Commentary citations",
```

Arabic:
```python
        "figure_reference": "المعرّف",
        "section_states": "حالات الأقسام",
        "section_column": "القسم",
        "state_column": "الحالة",
        "reason_column": "السبب",
        "commentary_citations": "إسنادات التعليق",
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_business_audit_split.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/khepri/rra/rendering/templates/_evidence.html.j2 src/khepri/rra/rendering/templates/report.evidence.html.j2 src/khepri/rra/rendering/html.py tests/test_rra009_business_audit_split.py
git commit -m "feat: author the audit region once, as a shared partial (RRA-009)

The caveat rows render their raw code for now; Task 5 replaces it with the
customer prose from wording.caveat_message, which does not exist yet."
```

---

## Task 5: Word the refusals and caveats in the business body

**Files:**
- Modify: `src/khepri/rra/rendering/html.py`
- Modify: `src/khepri/rra/rendering/templates/report.html.j2`
- Modify: `src/khepri/rra/rendering/templates/_evidence.html.j2`
- Test: `tests/test_rra009_business_audit_split.py`

**Interfaces:**
- Consumes: **`wording.refusal_message(reason: str, *, context: str, language: str) -> str`** and **`wording.caveat_message(code: str, language: str) -> str`** — from plan 1 Tasks 2–4. **This task is blocked until those land.**
- Produces: `chrome.refusal_prose: dict[str, str]` per language, a top-level `caveat_prose: dict[str, str]` context key resolved per bundle, and a business body carrying no bare reason or caveat code.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_rra009_business_audit_split.py

def test_a_refused_section_states_five_part_prose_not_a_code():
    surface = _surface(ROWS[:2])
    business = surface.documents[LANGUAGE_ENGLISH]
    assert "prior_window_absent" not in _visible_text(business)
    assert "unaffected" in _visible_text(business).lower()


def test_every_caveat_reaches_the_business_body_as_prose():
    bundle = _bundle()
    business = HtmlReportRenderer().render_html(bundle).documents[LANGUAGE_ENGLISH]
    visible = _visible_text(business)
    for caveat in bundle.caveats:
        assert caveat.code not in visible, caveat.code


def _visible_text(document: str) -> str:
    """Rendered text with tags stripped.

    RRA-009 requires leak detection against visible text rather than raw markup:
    a navigation anchor legitimately carries a section id in an `id=` attribute,
    and matching the markup would report every one of them as a leak.
    """
    return re.sub(r"<[^>]+>", " ", document)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_business_audit_split.py -k prose -v`
Expected: FAIL — `report.html.j2:52` renders `<code>{{ section.reason }}</code>`, so the raw code is in the visible text.

- [ ] **Step 3: Add a caveat resolver to `wording.py` that handles both shapes**

A bare dict cannot key a composite code, so resolution is a function. Add to `wording.py`:

```python
# The separator `bundle._section_caveats` uses when a result-tier refusal travels
# as a caveat: `f"{refusal.metric}:{refusal.reason}"` (`bundle.py:1570`). Named
# here so the surface splits on the same character the bundle joined with.
RESULT_CAVEAT_SEPARATOR = ":"


def caveat_prose(code: str, language: str) -> str:
    """Customer prose for one caveat code, of either governed shape.

    Two shapes reach a surface and both must be worded, because
    `_reconcile_language` (`bundle.py:1324`) compares caveat sets for equality
    rather than containment -- an unworded one is a refused report, not a gap.

    A bare code is a caveat proper and is looked up directly. A `<result>:<reason>`
    code is a *result-tier refusal travelling as a caveat*: `bundle.py:1552-1572`
    records why it has no other channel, since its section is present and
    `SECTION_REASONS` will not admit a per-metric reason. Its message is the
    result-tier refusal message, with the result identity filling `{metric}`.

    Split on the *last* separator, not the first. A mode-qualified result like
    `revenue_delta_percent.year_over_year` contains no colon today, but the reason
    never does, so splitting from the right stays correct if a result identity ever
    gains one.
    """
    if RESULT_CAVEAT_SEPARATOR not in code:
        return CAVEAT_WORDING[language][code]
    result, reason = code.rsplit(RESULT_CAVEAT_SEPARATOR, 1)
    return refusal_message(reason, context="result", language=language).format(
        metric=result,
        column=result,
        field=result,
    )
```

> **Note on the `.format` arguments.** Plan 1's result-tier templates use three placeholder names across the five messages — `{metric}`, `{column}`, `{field}` — and any given message uses only one. Passing all three keeps `str.format` from raising `KeyError` on whichever the selected message happens to use. `{column}` and `{field}` name the customer's own export column in plan 1's wording, and the result identity is the closest thing this surface knows; naming a *better* column would require the mapping, which is not in the renderer's reach and is not this plan's to add.

- [ ] **Step 4: Add the wording to the chrome**

In `html.py`, import the two resolvers. Section-tier refusals are a bare dict because a section reason is always a bare governed code; caveats need the function:

```python
from khepri.rra.rendering.wording import (
    CHART_DESCRIPTIONS,
    LABEL_WORDING,
    REFUSAL_WORDING,
    SECTION_HEADINGS,
    business_metric_name,
    caveat_prose,
)
```

Add to each language block of `_CHROME`:

```python
        # Section-tier refusals only. A result-tier refusal qualifies one metric
        # inside a section that stands, and the section-tier message would tell a
        # reader the whole analysis was lost. Result-tier messages reach the page
        # through `caveat_prose`, because that is the channel they travel on.
        "refusal_prose": REFUSAL_WORDING["section"][LANGUAGE_ENGLISH],
```

(and the `LANGUAGE_ARABIC` equivalent in the Arabic block).

Caveat prose is resolved per code rather than held as a map, because the composite codes are not enumerable in advance. Add to `build_context`'s return:

```python
        # Resolved here rather than in the template: a template cannot call a
        # function with keyword arguments, and a map cannot key a composite code.
        "caveat_prose": {
            caveat.code: caveat_prose(caveat.code, language) for caveat in bundle.caveats
        },
```

`_section_views` already carries section-scoped caveat *codes*, so the template looks each up in this map.

- [ ] **Step 5: Replace the bare code in the business template**

In `report.html.j2`, replace line 52:

```jinja
<p class="refused" data-reason="{{ section.reason }}"><code>{{ section.reason }}</code></p>
```

with:

```jinja
<p class="refused">{{ chrome.refusal_prose[section.reason] }}</p>
```

The `data-reason` attribute goes too: it is a tooling hook, not navigation, so the identifier rule in `docs/reporting/presentation-visibility-matrix.md` §A.2 removes it.

Replace both caveat lists (`report.html.j2:83-89` section-scoped, `:94-102` report-level) to render prose:

```jinja
{% if section.caveats %}
<ul class="caveats caveats--section">
{% for code in section.caveats %}
<li>{{ caveat_prose[code] }}</li>
{% endfor %}
</ul>
{% endif %}
```

```jinja
{% if caveats %}
<ul class="caveats">
{% for caveat in caveats %}
<li>{{ caveat_prose[caveat.code] }}</li>
{% endfor %}
</ul>
{% else %}
<p>{{ chrome.none }}</p>
{% endif %}
```

- [ ] **Step 6: Switch the partial's caveat rows to prose beside the code**

In `_evidence.html.j2`, replace the temporary `<dd>{{ caveat.code }}</dd>` from Task 4 with:

```jinja
<dd>{{ caveat_prose[caveat.code] }}</dd>
```

The audit region shows the code in the `<dt>` and the prose in the `<dd>` — an auditor gets both.

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_business_audit_split.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/khepri/rra/rendering/wording.py src/khepri/rra/rendering/html.py src/khepri/rra/rendering/templates/report.html.j2 src/khepri/rra/rendering/templates/_evidence.html.j2 tests/test_rra009_business_audit_split.py
git commit -m "feat: state refusals and caveats as customer prose (RRA-009)"
```

---

## Task 6: Restructure the business figure table and add the colophon

**Files:**
- Modify: `src/khepri/rra/rendering/templates/report.html.j2`
- Modify: `src/khepri/rra/rendering/html.py`
- Modify: `src/khepri/rra/rendering/templates/report.css`
- Test: `tests/test_rra009_business_audit_split.py`

**Interfaces:**
- Consumes: `FigureCell.metric_name` (Task 3); `bundle.bundle_id`.
- Produces: a two-column business figure table (name, value) carrying no `figure_id`, `citation_id`, raw `metric`, `kind`, or `unit_kind`; and `chrome`-driven colophon text carrying the one identifier the business region is allowed — a short report reference derived from `bundle_id`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_rra009_business_audit_split.py

def test_the_business_body_shows_no_figure_or_citation_identifier():
    bundle = _bundle()
    visible = _visible_text(HtmlReportRenderer().render_html(bundle).documents[LANGUAGE_ENGLISH])
    for figure in bundle.figures:
        assert figure.figure_id not in visible, figure.figure_id
        assert figure.citation_id not in visible, figure.citation_id


def test_the_business_body_carries_no_data_figure_id_attribute():
    """Removed from the markup too, not merely hidden: `data-figure-id` is a
    tooling hook and a business report is not a tooling surface."""
    document = _surface().documents[LANGUAGE_ENGLISH]
    assert "data-figure-id" not in document


def test_the_business_body_shows_business_metric_names():
    visible = _visible_text(_surface().documents[LANGUAGE_ENGLISH])
    assert "Revenue" in visible


def test_the_business_body_carries_exactly_one_identifier():
    bundle = _bundle()
    visible = _visible_text(HtmlReportRenderer().render_html(bundle).documents[LANGUAGE_ENGLISH])
    assert bundle.bundle_id[:8].upper() in visible.upper()


def test_figures_are_byte_identical_to_what_the_bundle_produced():
    """Relocation must not become reformatting. `html.py:1-9` leaves the renderer
    no Decimal to format; this asserts the string survived the restructure."""
    bundle = _bundle()
    visible = _visible_text(HtmlReportRenderer().render_html(bundle).documents[LANGUAGE_ENGLISH])
    for figure in bundle.figures:
        assert figure.renderings[LANGUAGE_ENGLISH] in visible
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_business_audit_split.py -k business_body -v`
Expected: FAIL — the six-column table at `report.html.j2:56-80` renders `cell.metric`, `cell.kind`, `cell.unit_kind`, `cell.citation_id` and two `data-figure-id` attributes.

- [ ] **Step 3: Add the report reference to the context**

In `html.py`, add to `build_context`'s return:

```python
        # The one identifier the business region carries. Derived from the bundle
        # identity rather than invented, so a reader quoting it can be matched to
        # the report -- and short enough to read aloud, which a digest is not.
        "report_reference": bundle.bundle_id[:8].upper(),
```

Add to both `_CHROME` language blocks:

```python
        "colophon_reference": "Report reference",
        "colophon_evidence": "Full calculation evidence and data lineage available on request.",
```

Arabic:
```python
        "colophon_reference": "مرجع التقرير",
        "colophon_evidence": "تتوفر أدلة الحساب الكاملة وسلسلة مصدر البيانات عند الطلب.",
```

- [ ] **Step 4: Replace the business figure table**

In `report.html.j2`, replace the table block (`:55-81`) with a two-column business statement:

```jinja
<div class="scroller">
<table class="figures">
<caption>{{ chrome.figures_caption }}</caption>
<thead>
<tr>
<th scope="col">{{ chrome.label }}</th>
<th scope="col">{{ chrome.value }}</th>
</tr>
</thead>
<tbody>
{% for cell in section.cells %}
<tr>
<th scope="row">{% if cell.metric_name %}{{ cell.metric_name }}{% else %}{{ cell.label }}{% endif %}</th>
<td class="figure">{{ cell.text }}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
```

**Note the condition tests `metric_name`, not `label`.** A governed or derived business name wins where one exists; otherwise the row is named by its own label, which for a series or bucket figure is a period, product, or branch the customer supplied — and `_row_label` (`html.py:324-337`) already translated it where it was a governed mode code. Task 3's `test_every_row_has_something_to_be_called` is what guarantees this `{% else %}` is never reached with an empty label.

The reverse condition (`{% if cell.label is none %}`) would be wrong: five metrics carry neither a label nor a governed name and are resolved from the derived table, so testing the label first would render nothing for them.

- [ ] **Step 5: Add the colophon and drop the audit anchors from the nav**

Replace the `citations` and `provenance` nav entries (`report.html.j2:43-44`) — those sections leave the business page — and remove the two `<section>` blocks (`:119-135`). Add before `</main>`:

```jinja
<footer class="colophon">
<p>{{ chrome.colophon_reference }} {{ report_reference }}</p>
<p>{{ chrome.colophon_evidence }}</p>
</footer>
```

The caveats and commentary anchors stay: both are business content.

- [ ] **Step 6: Style the new structures**

Add to `report.css` — a `.colophon` rule, a `.figures` two-column rule, and a `.refused` card rule. Keep logical properties (`margin-inline-start`, not `margin-left`) as `html.py:11-17` requires, so one stylesheet lays out both directions.

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_business_audit_split.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/khepri/rra/rendering/html.py src/khepri/rra/rendering/templates/report.html.j2 src/khepri/rra/rendering/templates/report.css tests/test_rra009_business_audit_split.py
git commit -m "feat: present figures as business statements, not an identifier table (RRA-009)"
```

---

## Task 7: Add the PDF appendix through the shared partial

**Files:**
- Modify: `src/khepri/rra/rendering/templates/report.html.j2`
- Modify: `src/khepri/rra/rendering/templates/report.pdf.html.j2`
- Modify: `src/khepri/rra/rendering/templates/report.print.css`
- Test: `tests/test_rra009_business_audit_split.py`

**Interfaces:**
- Consumes: the `evidence` macro (Task 4); the `audit` context key (Task 2), which `pdf.py:193` already receives because `_context` calls the shared `build_context`.
- Produces: `{% block appendix %}{% endblock %}` in the parent template, filled by the PDF child. No change to `pdf.py` — the appendix is a template concern and the module already passes the context that feeds it.

**Why this task is nearly free:** `report.pdf.html.j2:18` extends `report.html.j2` and fills blocks the parent left empty; `pdf.py:187-201` builds its context from the shared `build_context` and only adds print keys. So the appendix needs one empty block in the parent, one filled block in the child, and one page-break rule — and `report.print.css:105-112`'s `main > section { break-before: page }` supplies the break already if the appendix sections are direct children of `main`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_rra009_business_audit_split.py

from khepri.rra.rendering.pdf import PDF_TEMPLATE_NAME
from khepri.rra.rendering.html import build_environment


def _printed_html(language=LANGUAGE_ENGLISH) -> str:
    """The PDF template's HTML, rendered without a browser.

    `pdf.py` is deliberately verifiable with no Chromium (`pdf.py:18-23`), and
    this asserts on the markup the printer would be handed rather than on bytes.
    """
    bundle = _bundle()
    template = build_environment().get_template(PDF_TEMPLATE_NAME)
    context = build_context(bundle, language, build_cells(bundle, language))
    context["print_stylesheet_name"] = "report.print.css"
    context["fonts"] = []
    return template.render(context)


def test_the_printed_report_carries_the_appendix():
    bundle = _bundle()
    printed = _printed_html()
    for figure in bundle.figures:
        assert figure.figure_id in printed, figure.figure_id


def test_the_printed_business_body_still_hides_identifiers():
    """The appendix carries them; the body must not. Both live in one document
    here, so this is the assertion that the separation is real and not merely
    a matter of which file the reader opened."""
    printed = _printed_html()
    body = printed.split('id="appendix"')[0]
    assert "data-figure-id" not in body


def test_the_web_report_carries_no_appendix():
    """The parent block is empty on the screen surface: a web reader gets the
    separate evidence page instead, and rendering both would put the audit
    region inside the business page."""
    assert 'id="appendix"' not in _surface().documents[LANGUAGE_ENGLISH]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_rra009_business_audit_split.py -k appendix -v`
Expected: FAIL — no `appendix` block exists, so no identifier appears in the printed HTML.

- [ ] **Step 3: Add the empty block to the parent**

In `report.html.j2`, add immediately before `</main>` (after the colophon from Task 6):

```jinja
{# Filled by the print surface only. The screen surface publishes the audit
   region as a separate document, so a web reader who was not given the evidence
   page does not find it appended to the report they were given. #}
{% block appendix %}{% endblock %}
```

- [ ] **Step 4: Fill it in the PDF child**

In `report.pdf.html.j2`, add the import as line 1 and the block at the end:

```jinja
{% from "_evidence.html.j2" import evidence %}
```

```jinja
{% block appendix %}
<section id="appendix" aria-labelledby="appendix-heading">
<h2 id="appendix-heading">{{ chrome.evidence_title }}</h2>
<p>{{ chrome.evidence_intro }}</p>
</section>
{{ evidence(audit, chrome, caveat_prose) }}
{% endblock %}
```

- [ ] **Step 5: Confirm the page break, and add a running header**

`report.print.css:105-112` already breaks before every `main > section`, and the appendix sections are direct children of `main`, so the break exists. Add a rule so the appendix begins on a fresh page with its own header:

```css
  #appendix {
    break-before: page;
  }
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_rra009_business_audit_split.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/khepri/rra/rendering/templates/report.html.j2 src/khepri/rra/rendering/templates/report.pdf.html.j2 src/khepri/rra/rendering/templates/report.print.css tests/test_rra009_business_audit_split.py
git commit -m "feat: append the audit region to the printed report (RRA-009)"
```

---

## Task 8: Migrate the five existing test files

**Files:**
- Modify: `tests/test_rra006_html_sections.py`
- Modify: `tests/test_rra006_html_surface.py`
- Modify: `tests/test_rra006_pdf_sections.py`
- Modify: `tests/test_rra006_pdf_surface.py`
- Modify: `tests/test_rra006_bundle_section_caveats.py`

**Interfaces:**
- Consumes: everything Tasks 1–7 built.
- Produces: an `RRA-006` suite that asserts the new contract without weakening what it guarded. **This is a contract migration, not a find-and-replace** — these tests currently assert that the identifier ledger is correct, and that ledger has moved.

**Scope note:** five files, measured — `grep -rln "data-figure-id\|chrome\[.metric.\]\|report.html.j2\|HtmlReportRenderer\|PdfReportRenderer\|build_context" tests/*.py`. The design package's "19 files, ~170 references" (`business-report-information-architecture.md` §B.6 item 13) counts Excel's `_section_sheet` and `_FIGURE_COLUMNS` pinning too; that remainder is plan 3's.

- [ ] **Step 1: Run the suite and inventory every failure**

Run: `uv run pytest tests/test_rra006_html_sections.py tests/test_rra006_html_surface.py tests/test_rra006_pdf_sections.py tests/test_rra006_pdf_surface.py tests/test_rra006_bundle_section_caveats.py -v 2>&1 | grep -E "FAILED|assert"`
Expected: a list of failures. Record each before changing anything — a test changed before its failure is understood is a test whose guarantee was traded away silently.

- [ ] **Step 2: Invert the two known contract tests**

`tests/test_rra006_html_sections.py:127`, `test_a_refused_section_renders_its_governed_reason`, asserts `"prior_window_absent" in rendered`. Its guarantee — a reader can tell "nothing to show" from "we could not show it" — is preserved by RRA-009 and stated differently. Replace with:

```python
def test_a_refused_section_explains_itself_without_a_code() -> None:
    """Two days settle no period, so the comparison refuses.

    The guarantee is unchanged from the version this replaces: a reader must be
    able to tell "there was nothing to show" from "we could not show it". What
    changed is where the machine-readable reason lives. RRA-009 puts five-part
    customer prose in the business body and the raw code in the audit region, so
    this asserts both halves rather than relaxing either.
    """
    rendered = page(rows=ROWS[:2])
    assert f'<section id="{SECTION_COMPARISON}"' in rendered
    assert 'class="refused"' in rendered
    assert "prior_window_absent" not in re.sub(r"<[^>]+>", " ", rendered)
    assert "unaffected" in rendered.lower()
```

`test_each_family_has_its_own_heading_and_navigation_entry` (`:99`) asserts a `<section id=...>` and an `href="#..."` for all five sections. Tasks 5–6 keep every section heading and its anchor — only the audit anchors were removed — so this test should still pass. **If it fails, that is a real regression in the nav loop, not a test to update.** Verify before touching it.

- [ ] **Step 3: Update the surface tests for the new field**

`tests/test_rra006_html_surface.py:181` asserts `set(surface.documents) == set(REQUIRED_LANGUAGES)` — unchanged and must keep passing. Line 194 sums `surface.documents.values()` for a size assertion; that now describes part of the surface, since `output_size_bytes` includes the evidence documents (Task 1). Update it to sum both:

```python
    rendered = sum(
        len(document.encode("utf-8"))
        for mapping in (surface.documents, surface.evidence)
        for document in mapping.values()
    )
```

- [ ] **Step 4: Run each file until green, one at a time**

Run each of the five separately, fixing before moving on:
```bash
uv run pytest tests/test_rra006_html_sections.py -q
uv run pytest tests/test_rra006_html_surface.py -q
uv run pytest tests/test_rra006_pdf_sections.py -q
uv run pytest tests/test_rra006_pdf_surface.py -q
uv run pytest tests/test_rra006_bundle_section_caveats.py -q
```
Expected: each PASS. Running them individually keeps a fix for one file from masking a break in another.

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -q`
Expected: PASS, at or above the 1610-passed baseline recorded on `main` at `bc792a0`. A *lower* count means a test was deleted rather than migrated — check before accepting it.

- [ ] **Step 6: Run the full governed gate**

Run: `uv run khepri-gov validate && uv run ruff check . && uv run pytest -q`
Expected: all three pass. Per `[[khepri-five-ci-checks]]`, CI's `validate`/`ruff`/`pytest` remain the authority; CodeScene in particular is not reproducible locally, and this plan adds a template partial and several `_CHROME` entries that will move its numbers.

- [ ] **Step 7: Commit**

```bash
git add tests/
git commit -m "test: migrate the RRA-006 surface suite to the business/audit split (RRA-009)"
```

---

## Self-Review

**Spec coverage against RRA-009's HTML/PDF requirements:**

| RRA-009 requirement | Task |
|---|---|
| "Classify every field a surface renders as Business, Audit, or Internal" | Tasks 2, 6 — the `audit` key is the Audit tier; the business table is the Business tier; `state` and `narrative_state` reach neither |
| "Carry the audit region as a distinct web page, as a PDF appendix following a page break" | Tasks 1, 4 (page), 7 (appendix) |
| "Generate the audit region with every report" | Task 1 — unconditional in `render_html` |
| "Render both regions through the existing shared template rather than forking the PDF surface" | Task 7 — `{% block appendix %}` in the parent, one shared partial |
| "Present a figure as a business statement of name and value… rather than as an identifier table" | Task 6 |
| "Provide a business metric name for every governed metric code" | Task 3 (consuming plan 1 Task 1, merged) |
| "Carry exactly one identifier in the business region: a short human-readable report reference" | Task 6 |
| "Carry the governed automatic-generation disclosure verbatim" | Unchanged — `report.html.j2:31` is not touched by any task |
| "State a customer-facing refusal in five parts… State the third part explicitly on every refusal" | Task 5 (prose from plan 1 Tasks 2–3) |
| "Carry the raw governed reason code only in the audit region" | Tasks 4, 5 |
| "Provide customer prose for every caveat code" | Task 5 (from plan 1 Task 4) |
| "Generate the figure-to-fact and passage-to-fact citation tables… in the audit region" | Task 4 |
| "Retain an identifier in a markup attribute only where the reader uses it" | Task 6 — `data-figure-id` removed, `id=` anchors kept |
| "Detect identifier leakage against rendered visible text rather than raw markup" | Task 5's `_visible_text` helper, used by Tasks 5 and 6 |
| "Relocate a field; never recompute one and never drop one" | Task 6's byte-identical figure test; Task 2's coverage tests |

**Deliberately out of scope, and where it goes:**
- Every Excel requirement — "the final Excel worksheets ordered after every business worksheet," business worksheet naming, the 31-character cap. **Plan 3.**
- "Order the business report by decision relevance rather than by the mechanism that computed it" (IA §B.2's §1–§7 reordering, hero figure, KPI row, lead finding). This plan restructures each section's *presentation* but keeps `bundle.sections` order. Reordering requires deciding where a "lead finding" comes from, which is narrative work beyond a presentation change — flagged rather than silently skipped.
- The render-variant question (IA §B.1's option (i) vs (ii) — whether the customer's copy includes the evidence). This plan always renders both; which one is *delivered* is a delivery-layer concern and IA §B.1 records it as the owner's call.
- Refused-section relocation to §7 with a contracting numbered list (IA §B.2). The doc flags it as owner-confirmable; this plan keeps each refused section in its numbered place with prose under its heading, which is the alternative the same paragraph calls "also defensible" and which preserves a 1:1 map to the bundle's sections. **Assumption stated, not decided by an agent.**

**Placeholder scan:** one intentional intermediate state — Task 4's caveat `<dd>` renders the raw code and the macro takes two parameters until Task 5 adds prose and the third, because `caveat_message` does not exist until plan 1 Task 4 lands. Called out in Task 4's commit message so the intermediate is not mistaken for the final contract. No prose placeholders; no `TBD`.

**Two scope corrections made while self-reviewing, both found by running the fixture rather than reading the design package.** Recorded here because each would otherwise have surfaced as `REASON_SURFACE_FAILED` on a customer's report — the failure mode the vocabulary guards exist to prevent, arriving through a path the guards do not cover:

1. **The rendered metric set is 26 codes, not the governed 13.** `metric_business_name` raises on the other 13, and five of those carry no label either, so neither a governed name nor a label fallback would name them. Resolved by a second `DERIVED_METRIC_WORDING` table and a `str | None` field, with `test_every_row_has_something_to_be_called` as the invariant. Plan 1's governed guard is deliberately *not* widened — Task 3 Step 6 makes editing it the signal that something went wrong.
2. **Two caveat codes are `<result>:<reason>` composites** built at `bundle.py:1570`, which no bare dict can key. These turn out to be result-tier refusals travelling as caveats (`bundle.py:1552-1572` explains why they have no other channel), so plan 1's result-tier messages already word them — resolved by splitting on the last colon rather than by new vocabulary.

Both corrections argue for finishing plan 1 Tasks 2–4 before executing this plan's Task 5, as the Prerequisite section states.

**An assumption this plan makes that the fixture cannot prove.** The 26-metric and 2-composite-caveat counts come from one fixture (`tests/test_rra006_html_sections.py`'s five-row `ROWS`). A real customer dataset may render metrics or composite codes this fixture does not produce. `test_every_row_has_something_to_be_called` is the guard that would catch a new unworded metric in CI rather than on a report, but it only sees what the fixture builds. Worth a wider fixture in plan 3 or a follow-up; not silently assumed away here.

**Type/signature consistency:** `FigureCell` gains `metric_name: str` in Task 3 and is consumed as `cell.metric_name` in Tasks 4 and 6. `HtmlSurface.evidence: dict[str, str]` is added in Task 1 and read as `surface.evidence[language]` in Tasks 4, 5, 7, 8. The `audit` context key is created in Task 2 with six sub-keys and consumed by name in Task 4's macro and Task 7's appendix. `_visible_text` is defined once in Task 5 and reused in Task 6. Plan 1's accessors are named `refusal_message(reason, *, context, language)` and `caveat_message(code, language)` in both plans.

**Prerequisite restated:** Task 5 is blocked on plan 1 Tasks 2–4. Tasks 1–4 and 7–8 are not.
