# `U1` RRA slice 9a — evidence

**Slice:** Accessibility evidence, `RRA` report and evidence surfaces (`U1-06`, this family's half).
**Authority:** `RRA-015` `FR-189`, `active`, verified at `535b644`. Design: master specification §11.
**Plan:** `docs/superpowers/plans/2026-09-19-u1-rra-slice-9a-execution-plan.md`.
**Module:** `tests/test_rra015_report_accessibility.py` — 18 tests, 4 browser-marked.
**Result:** 16 passed, **2 xfailed** — the xfails are a recorded floor failure, below.

**This slice changed no source file.**

---

## Finding 1 — An `FR-189` floor FAILS, recorded not fixed

**The report surface's "On this page" navigation anchors render at 21px against `FR-189`'s
44px floor.**

| Surface | Tab stop | Height |
|---|---|---|
| `documents` | `<a href="#overview">Overview</a>` and 4 siblings | **21px** |
| `evidence` | `.evidence-link` anchors | 47px — passes |

`src/khepri/rra/rendering/templates/report.css` declares **zero** minimum target-size rules —
no `44px`, no `min-height`, no `min-block-size`.

**Not fixed here, deliberately.** The allocation plan: "where a floor fails, the fix lands in the
slice that owns that file, not here… An evidence slice that edits a stylesheet or a template to
make its own assertion pass has left its scope, and the failure it hid is still in the product."

Recorded as `@pytest.mark.xfail(strict=True)` so it fails the day the floor is met — an xfail that
silently starts passing is a defect ledger nobody reads. **A follow-on slice under `RRA-015`,
named for `report.css`, owns the fix.**

The floor was split out of the focus test into its own case. Two floors sharing one test lets one
failure mask the other's result (`khepri-redundant-guards-need-separate-evidence`).

## Finding 2 — "Server-computed" cannot be proved by reading the output

`FR-189` requires `lang` and `dir` "server-computed". `dir="rtl"` renders identically whether the
value was passed in or computed in the template, so an output assertion cannot distinguish them.

Mutation M4 replaced `dir="{{ direction }}"` with `dir="{{ 'rtl' if language == 'ar' else 'ltr' }}"`:

| Test | Result |
|---|---|
| `test_lang_and_dir_are_present_and_paired_on_every_surface` | **passed** — the output was byte-identical and correct |
| `test_no_template_infers_direction_from_anything_but_the_passed_value` | **failed** — caught the provenance move |

That 1-failed/1-passed split is the proof: only the template-reading test can see the change. See
`khepri-shape-checks-cannot-establish-provenance`.

## Finding 3 — Three floors have no reachable subject

Each is pinned two-sided: the implication is asserted, and a companion test records that the
antecedent is false today, so the pin fails the day a subject ships.

| Floor | Subject | Why |
|---|---|---|
| `role="status"` for refusals and progress | **0** on both surfaces | neither renders a refusal region or progress affordance |
| Labels associated with controls | **0** form controls | a report is a read-only presentation |
| Non-colour differentiation, **evidence surface** | **0** trust badges | only the report surface renders them |

**The third was nearly missed by a substring count.** A first probe counted the substring `badge`
and reported `2` on the evidence surface; a class-attribute match reports `0`. Those two
occurrences sit in the embedded stylesheet, not the markup. Measuring the substring is exactly how
a surface with no subject gets reported as covered.

---

## Decisions

**The roster is a reviewed literal; no independent source exists.** The allocation plan rules out
`SECTION_CHART_KINDS` — five *sections*, blind to the evidence drawer. A second candidate,
`html.py`'s `TEMPLATE_NAME`/`EVIDENCE_TEMPLATE_NAME` plus `pdf.py`'s `PDF_TEMPLATE_NAME`, is the
same wrong-granularity error one level down: template file **names**, not surfaces. The roster is
`HtmlSurface`'s two mappings, and an extent assertion refuses a renderer exposing more.

**The PDF surface is out, on two independent grounds.** `RRA-015:140` excludes the PDF renderer
from scope, **and** `report.pdf.html.j2` carries zero focusable elements against
`report.html.j2`'s six. Either alone would be arguable; together they settle it.

**Charts need `published=True`.** A chart belongs to an `RRA-008` family and only the published
triple admits one:

| Fixture | `<svg>` across all four surface/language pairs |
|---|---|
| `package_for(ROWS)` | **0** |
| `package_for(ROWS, published=True)` | **12** (3 per report document) |

A chart test on the default fixture asserts "no chart lacks a `<desc>`" over **zero charts** and
passes, certifying the clause while measuring nothing. The shipped test asserts a non-zero count
first, and the default fixture was re-run to confirm the count assertion is what fails.

---

## Mutation results

Every mutant restored by `git checkout`, after committing the module — see
`khepri-verify-a-fix-against-head-not-the-worktree`, the trap that cost a cycle in slice 3.

| # | Mutant | Expected | Result |
|---|---|---|---|
| M1 | second `<h1>` in `report.html.j2` | heading test fails | **1 failed** |
| M2 | `tabindex="1"` on a `<nav>` | tabindex test fails | **1 failed** |
| M3 | `<desc>` renamed in `_chart.svg.j2` | chart test fails | **1 failed** |
| M4 | `dir` computed inline in the template | **provenance** test fails, output test passes | **1 failed, 1 passed** |
| M5 | default (unpublished) fixture | chart count assertion fails | **0 charts — confirmed** |

---

## Gates

| Gate | Result |
|---|---|
| `uv run pytest tests/test_rra015_report_accessibility.py` | **16 passed, 2 xfailed** |
| `uv run ruff check .` | passed |
| `uv run khepri-gov validate` | passed |
| `uv run pytest` (full suite) | see the pull request |
| CodeScene, new module | see the pull request |
