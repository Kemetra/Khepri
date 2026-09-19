# `U1` RRA slice 9a — evidence

**Slice:** Accessibility evidence, `RRA` report and evidence surfaces (`U1-06`, this family's half).
**Authority:** `RRA-015` `FR-189`, `active`, verified at `535b644`. Design: master specification §11.
**Plan:** `docs/superpowers/plans/2026-09-19-u1-rra-slice-9a-execution-plan.md`.
**Module:** `tests/test_rra015_report_accessibility.py` — 26 collected, **14 browser-marked**
Counted by collection (`pytest -m browser --collect-only`), never by reading the source: a first
draft said "4 browser-marked" and a review corrected it to 6; the review round then parametrized
two browser tests by surface and viewport, taking it to 14. A test count derived by reasoning goes
stale at every refactor.
**Result:** 20 passed, **6 xfailed** — every xfail is a recorded floor failure, below.

**This slice changed no source file.**

---

## Review round: four findings, three of which found MORE defects

CodeRabbit raised four substantive findings after the first push. Each was verified by running,
and three exposed real failures the narrower tests could not see. The module went from
**16 passed / 2 xfailed** to **20 passed / 6 xfailed** — widening did not create defects, it
revealed ones already shipped.

| Finding | Verified | Outcome |
|---|---|---|
| `role="status"` search keyed on the conclusion | refusal panels render `role="note"`, **4 on the unpublished fixture** | the "recorded absence" was FALSE; now a strict xfail |
| function-level xfail hid the evidence surface | `evidence/ar` fails at **135x21px**; `evidence/en` PASSES at 47px | a second, language-specific defect |
| reflow measured at 1180px only | `evidence` overflows by **184px** at 390px, both languages | a third defect |
| `dir` scan was a denylist | `directions[language]` would have passed | tightened to an allowlist |

**The refusal finding is the most serious, and it is `khepri-a-refused-section-still-renders`.**
The first form of the status pin asked "does any `role=status|progressbar|alert` region exist?" —
a search keyed on the *conclusion* the clause requires. A refusal panel is
`data-component="refusal-panel"` with `role="note"`, so the search could never see its subject and
the pin passed over a real failure while claiming the clause had none. The subject is now located
by its own markup.

**A width check was also missing.** A target 10px wide and 44px tall is not a 44px target; the
first form asserted height alone.

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
| Labels associated with controls | **0** form controls | a report is a read-only presentation |
| Non-colour differentiation, **evidence surface** | **0** trust badges | only the report surface renders them |

~~`role="status"` for refusals and progress~~ — **WITHDRAWN.** This was listed as a third absence
and it was wrong. Refusal panels ARE reachable: `data-component="refusal-panel"` with
`role="note"`, 4 of them on the report surface under the unpublished fixture. The absence was an
artifact of searching for the role the clause requires instead of the subject it governs. It is now
Finding 4, a recorded failure.

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
| `uv run pytest tests/test_rra015_report_accessibility.py` | **20 passed, 6 xfailed** |
| `uv run ruff check .` | passed |
| `uv run khepri-gov validate` | passed |
| `uv run pytest` (full suite) | see the pull request |
| CodeScene, new module | see the pull request |


---

## Post-merge correction — one pin was an environment artifact

`main`'s `governance` run on `9342720` FAILED with `XPASS(strict)` on
`test_every_tab_stop_meets_the_target_floor[ar-evidence]`. **The strict marker is what caught it.**
A non-strict xfail would have absorbed the divergence silently and this module would carry a
permanent false defect.

| Case | Local (Windows) | CI (`ubuntu-latest`) | Verdict |
|---|---|---|---|
| `documents/en` | fails 21px | **xfail held** | real `report.css` defect |
| `documents/ar` | fails 21px | **xfail held** | real `report.css` defect |
| `evidence/ar` | fails 135x21px | **XPASSED** | **environment artifact** |
| `evidence/en` | passes 47px | passes | sound |

**Cause.** The Arabic stack is `"Noto Sans Arabic", "IBM Plex Sans Arabic", Cairo`. A
`set_content` page has no HTTP origin, so `@font-face` never fetches and the metric depends on what
the **host** has installed. CI ships those faces; a Windows developer machine falls through to a
shorter fallback — 49 of 50 links at 21px locally, 0 of 50 in CI.

**Two fixes were tried and rejected before the third.**

1. `* { font-family: monospace !important; }` — made the measurement reproducible and **wrong**:
   `evidence/en` then measured 35.8px, a box that exists in no real browser. A reproducible
   measurement of something the product never renders is not evidence about the product.
2. `document.fonts.check(...)` — returns **true** for a family the host lacks, because it answers
   "may this family be used?", not "did it resolve?". The gate passed on a machine rendering the
   fallback. `khepri-set-content-browser-tests-cannot-prove-an-asset-loads` records the same false
   positive from the other direction.

**What shipped.** Render the same Arabic string in the governed stack and in a deliberately absent
family, and compare widths: equal widths mean both fell through to one fallback. The gate applies to
**`evidence/ar` alone** — CI proved `documents/ar` fails *with* the governed face, so a gate covering
Arabic generally would have suppressed a real defect alongside the artifact.

**Three recorded failures remain, all confirmed in CI:** `report.css` target size (both languages)
and the evidence surface's 390px reflow (both languages).

Proving the floor under the **shipped** faces needs an HTTP origin so `@font-face` fetches —
`tests/test_rca011_shell_font_load.py` is the worked example. That is a follow-on slice.
