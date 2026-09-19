# `U1` RRA slice 9a — Accessibility evidence, report and evidence surfaces: the execution plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this
> plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Checkboxes in this
> repository are **never ticked after the fact** — read the newest dated status block, not the
> boxes.

**Goal:** Make `RRA-015` `FR-189`'s accessibility floors provable on the report and evidence
surfaces, in both languages, and make any floor without a reachable subject visible as a gap rather
than as a silent pass.

**Architecture:** One new test module, `tests/test_rra015_report_accessibility.py`.
**No source file changes.**

**Tech Stack:** pytest, Playwright (Chromium), Jinja2.

**Spec:** `governance/specifications/RRA-015.md` — `FR-189`.
**Allocation:** `docs/superpowers/plans/2026-09-17-u1-rra-surfaces-allocation-plan.md` §Slice 9a.
**Design:** master specification §11.

---

## Global Constraints

- **Authority is `RRA-015` `FR-189`**, `active`, verified at `535b644`.
- **`tests/` only.** Where a floor fails, the fix opens a follow-on slice under `RRA-015` — or
  under `RRA-010` where the failing file is the journey's — named for the file that fails. An
  evidence slice that edits a stylesheet or template to make its own assertion pass has left its
  scope, and the failure it hid is still in the product.
- **Dependencies are merged:** slice 6 (`#481`), slice 2 (`#495`), slice 3 (`#496`).

---

## Decision 1 — The roster is a reviewed literal, and no independent source exists

`FR-189` requires the floors on "the report **and evidence** surfaces". The plan rules out deriving
that roster from `SECTION_CHART_KINDS`, which maps five *sections* and knows nothing about the
evidence drawer.

**A second candidate was considered and also rejected.** `html.py`'s `TEMPLATE_NAME`,
`EVIDENCE_TEMPLATE_NAME` and `pdf.py`'s `PDF_TEMPLATE_NAME` are **template file names**, not a
surface roster — the same wrong-granularity error one level down. `report.pdf.html.j2` is a print
artifact, not a surface a keyboard user tabs through.

So the roster is a **reviewed literal**: `documents` and `evidence`, the two mappings
`HtmlSurface` exposes, each in `ar` and `en`. Confirmed against `FR-189`'s wording, and the
evidence file says plainly that no independent source exists.

## Decision 2 — The PDF surface is out, on two independent grounds

1. **Authority.** `RRA-015:140` excludes "the PDF renderer beyond the chart rules
   `report.print.css` carries" from this specification's scope.
2. **Subject.** `report.pdf.html.j2` contains **zero** focusable elements against
   `report.html.j2`'s six. "Visible focus on every tab stop", "focus order following document
   order" and "text scaling to 200% without loss of function" have no subject on it.

Either ground alone would be arguable; together they settle it. Had only the second held, the
honest move would have been to include the surface and record its floors as NOT EXERCISED.

## Decision 3 — Charts need `published=True`, and this is the slice's sharpest trap

`FR-189`'s chart clause — `role="img"` with `<title>` and `<desc>` from governed codes — has **no
subject** under the default fixture. Measured:

| Fixture | `<svg>` | `role="img"` | `<desc>` |
|---|---|---|---|
| `package_for(ROWS)` | 0 | 0 | 0 |
| `package_for(ROWS, published=True)` | **3** | **3** | **3** |

A chart belongs to an `RRA-008` family, and only the published triple admits one. A test written
against the default fixture would assert "no chart lacks a title" over **zero charts** and pass,
certifying the clause while measuring nothing
(`khepri-a-run-that-can-only-produce-the-null-case`).

Every chart assertion therefore uses the published fixture **and** asserts the chart count is
non-zero before measuring.

## Decision 4 — Two floors are recorded absences, pinned two-sided

Measured on both surfaces in both languages at `535b644`:

| Floor | Subject | Disposition |
|---|---|---|
| Exactly one `h1`, no skipped level | 1 `h1` per surface | measure |
| No positive `tabindex` | 5 / 2 `tabindex` attributes, none positive | measure |
| `lang` and `dir` server-computed | `ar`/`rtl`, `en`/`ltr` | measure, see Decision 5 |
| Chart `role="img"` + `<title>`/`<desc>` | 3 on the report surface, published | measure |
| Visible focus on every tab stop | focusable elements exist | measure in browser |
| Targets ≥44px on the element itself | focusable elements exist | measure in browser |
| Text scales to 200% | both surfaces | measure in browser |
| Non-colour differentiation for trust states | `badge` 17/2, `caveat` 18/10, `refus` 11/11 | measure |
| **`role="status"` for refusals and progress** | **0 on both surfaces** | **recorded absence** |
| **Labels associated with controls** | **0 form controls on either surface** | **recorded absence** |

**Two** floors are recorded absences, not one. The labels floor joins `role="status"`: both
surfaces render **zero** `<input>`, `<select>` or `<textarea>` elements, because a report is a
read-only presentation. "Labels associated with controls" therefore has no subject, and a test
asserting "every control has a label" over zero controls passes vacuously.

A recorded absence is pinned so it **fails the day a subject ships**, in the shape `#486`
established: assert the implication, and separately assert the antecedent is currently false.

**Heading order is measurable and correct.** Report renders `h1, h2 x7`; evidence renders
`h1, h2 x5`. No level is skipped on either surface.

## Decision 5 — "Server-computed" is a provenance claim, not an output claim

`lang="ar" dir="rtl"` renders identically whether the value was passed in or inferred in the
template. A test reading the output proves nothing about provenance.

Proved instead by asserting no template derives `dir` from anything but the passed-in value, and by
mutating the server-side computation and confirming the rendered output follows.

---

## Task 0 — Record the subject inventory

- [ ] Render both surfaces, both languages, default and published fixtures.
- [ ] Record, per surface: `h1` count, `tabindex` values, positive `tabindex`, `lang`/`dir`,
      `role="status"` count, `role="img"` count.
- [ ] Every floor is classified **measure** or **recorded absence** before a test is written.

## Task 1 — RED: the static floors

- [ ] Exactly one `h1` per surface, and no skipped heading level.
- [ ] No positive `tabindex` on either surface.
- [ ] `lang` and `dir` correct per language, with the extent assertion over the roster.
- [ ] Chart `role="img"` carries both `<title>` and `<desc>`, with a **non-zero chart count**
      asserted first.
- [ ] The two recorded absences, pinned two-sided.

## Task 2 — RED: the browser floors

- [ ] Visible focus on every tab stop, asserted on the focusable element itself.
- [ ] Targets ≥44px **on the element a pointer lands on, not an ancestor**.
- [ ] Text scales to 200% without loss of content or function, and no page-level horizontal
      overflow at any supported width (`RRA-015` §Verification).

## Task 3 — Mutation-test every guard

- [ ] Add a second `h1` → the heading test fails.
- [ ] Add `tabindex="1"` → the positive-tabindex test fails.
- [ ] Remove a chart's `<desc>` → the chart test fails.
- [ ] Render with the default fixture → the chart test **fails on the count assertion**, not
      silently passes. This is the Decision 3 proof.
- [ ] Mutate the server-side `dir` computation → the provenance test fails.
- [ ] Restore each by `git checkout`, never `str.replace`, and **commit nothing uncommitted before
      mutating** — see `khepri-verify-a-fix-against-head-not-the-worktree`.

## Task 4 — Evidence file and gates

- [ ] `docs/superpowers/plans/2026-09-19-u1-rra-slice-9a-evidence.md` with the subject inventory,
      the mutation results, and both recorded absences.
- [ ] `uv run khepri-gov validate`, `uv run ruff check .`, `uv run pytest` — **serially**.
- [ ] CodeScene: the new module scores 10.00.
