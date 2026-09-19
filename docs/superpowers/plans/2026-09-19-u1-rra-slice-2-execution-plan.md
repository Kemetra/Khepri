# `U1` RRA slice 2 — One skip-link mechanism on the journey: the execution plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this
> plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Checkboxes in this
> repository are **never ticked after the fact** — read the newest dated status block, not the
> boxes.

**Goal:** Make `RRA-010` §73's four focus-and-navigation clauses provable on the journey surfaces,
and record which of them had a subject to measure.

**Architecture:** One new test module, `tests/test_rra010_journey_focus.py`, beside the existing
journey evidence. **No source file changes** — see Decision 1, which is the finding that shaped
this slice.

**Tech Stack:** pytest, Playwright (Chromium), FastAPI `TestClient`, Jinja2.

**Spec:** `governance/specifications/RRA-010.md` §73.
**Allocation:** `docs/superpowers/plans/2026-09-17-u1-rra-surfaces-allocation-plan.md` §Slice 2.
**Design:** master specification §G.2.

---

## Global Constraints

- **Authority is `RRA-010` §73** — `active` in `governance/registry.yaml`, verified at `79a0557`.
  The clause: "one skip-link mechanism, correct tab order, and visible focus on every tab stop
  including scroll containers. Consolidating two journey-internal mechanisms is authorized;
  adopting a shell-owned mechanism as the target is not."
- **`tests/` only.** Where a clause fails, the fix lands in the slice that owns the file, not here.
- **The journey half only.** `shell-components.css` is outside `RRA-010` by `RRA-010:30` and is the
  companion plan's slice 2b. **Unifying across both surfaces is authorized by neither plan**
  (`FR-201`). This slice does not edit that file.

---

## Decision 1 — The allocation plan's premise is false, and this slice corrects it

The allocation plan says slice 2 "unifies the **journey** half" of a two-mechanism split, citing
`journey.css:75-76` and `shell-components.css:45,56`.

**There is no split on the journey.** Verified at `79a0557`:

| Fact | Evidence |
|---|---|
| Journey templates linking a stylesheet | exactly one, `base.html.j2:7` to `/beta/assets/journey.css` |
| All five journey pages | `expired`, `processing`, `report`, `review`, `upload` all extend `base.html.j2` |
| `@import` in `journey.css` | none |
| Who links `shell-components.css` | `shell_templates/shell.html.j2:8` and `legal_templates/legal.html.j2:8` only |
| `.skip-link` base selectors delivered to a journey page | **one** |

The two `.skip-link` definitions live in one directory but are **never delivered to the same
page**. `RRA-010` §73's "consolidating two journey-internal mechanisms" therefore has **no
subject**, and its "adopting a shell-owned mechanism as the target is not [authorized]" is what
keeps it that way.

The allocation plan's own rule governs this: "where this plan and a specification disagree, **the
specification wins** and this plan is corrected in place." Task 5 makes that correction.

**This also answers the journey-adoption gate for this slice.** `RRA-010` §73 resolves the question
restrictively and in advance, so slice 2 does not wait on the owner's untaken reading. That reading
still gates any slice that would put a shell-owned component **on** a journey surface; this one does
the opposite.

## Decision 2 — Measure the binding, never the directory

A guard that counts `.skip-link` across `src/khepri/rra/journey/assets/` finds **two** and fails a
correct tree, because `shell-components.css` shares that directory. That is
`khepri-derive-a-guards-input-from-the-binding-not-a-grep` and the `#486` defect verbatim.

Every assertion here derives its input from **what a rendered journey page links**, not from a path
glob. Task 4 mutates both sheets to prove the guard fires on one and stays silent on the other.

## Decision 3 — This is an evidence slice, and says so

All four clauses were measured **compliant before any test was written** (Task 0). No production
file changes. An evidence slice that edits a stylesheet to make its own assertion pass has left its
scope. Per `khepri-an-evidence-slice-records-it-does-not-fix`, the pins are two-sided so a later
regression fails rather than silently passing.

---

## Task 0 — Record the pre-slice measurements

- [ ] Measure, on `/beta/{en,ar}/{upload,review,processing,report}` at 390x844 and 1180x900:
      the delivered `.skip-link` base-selector count; the first tab stop from a clean page load;
      the focused skip link's box height against the 44px floor `RRA-010:134` names; and the
      `.table-region` scroll container's focus outline.
- [ ] Record each result in the evidence file, including the ones that pass.

**Measured at `79a0557`, before this slice:**

| Clause | Subject | Result |
|---|---|---|
| One skip-link mechanism | 1 delivered base selector | **PASS** |
| Correct tab order | first tab stop from page load is `.skip-link` | **PASS** |
| Visible focus, skip link | focused box 46.375px, floor is 44 | **PASS** |
| Visible focus, scroll container | `.table-region` `tabindex="0"`, 3px solid outline | **PASS** |

**A trap this measurement walked into, recorded so the test does not repeat it.** A first attempt
called `link.focus()` and *then* pressed `Tab`, and reported the first tab stop as `.brand` — a
real measurement answering a different question, since focus had already moved past the link. The
tab-order test **must** press `Tab` from a clean page load with no prior `focus()` call. See
`khepri-a-guard-can-answer-a-different-question`.

## Task 1 — RED: the delivered mechanism count

- [ ] Write `test_the_journey_delivers_exactly_one_skip_link_mechanism`.
- [ ] Derive the CSS from the `<link>` tags a rendered journey page carries, asserting the link set
      is exactly `{journey.css}` first — so the day a page links a second sheet, this test says so
      rather than silently widening.
- [ ] Reuse `test_r807_shell_quality.py`'s `_selector_parts` reading: unwrap `:is()`/`:where()`,
      split grouped selectors, and count distinct **base** selectors. Do not import the shell
      module's private helper; restate the reading in this module, since `FR-201` keeps the two
      surfaces' evidence separate.
- [ ] Assert both directions: the base set is exactly `{".skip-link"}`, **and** no other
      `skip`-named base selector exists.

## Task 2 — RED: tab order and focus visibility

- [ ] `test_the_journey_skip_link_is_the_first_tab_stop` — from a clean page load, one `Tab`, in
      both languages across all four steps.
- [ ] `test_the_journey_skip_link_meets_the_target_floor_when_focused` — focused bounding box
      height at least 44, the floor `RRA-010:134` names and `test_rra_journey_browser.py:155`
      already enforces for other targets. The existing test's selector list excludes `.skip-link`;
      this closes that gap rather than editing that test.
- [ ] `test_the_journey_scroll_container_shows_focus` — `.table-region` is focusable and carries a
      non-`none` outline when focused.

## Task 3 — RED: the no-physical-directional-property pin

- [ ] Assert `journey.css` still declares no physical directional property, per the allocation
      plan's fourth RED shape and `RRA-010:133`.
- [ ] Check whether an existing test already asserts this for `journey.css`. **If one does, do not
      restate it** — cite it in the evidence file instead. A second copy drifts from the first.

## Task 4 — Mutation-test every guard

- [ ] Add a second `.skip-link`-like base selector to **`journey.css`**; confirm Task 1 **fails**.
- [ ] Add one to **`shell-components.css`**; confirm Task 1 still **passes** — the guard must not
      fire on the companion surface's file. This is the Decision 2 proof.
- [ ] Move the skip link below `.brand` in `base.html.j2`; confirm the tab-order test **fails**.
- [ ] Drop the skip link's padding to zero; confirm the target-floor test **fails**.
- [ ] Remove the `:focus-visible` outline rule; confirm the scroll-container test **fails**.
- [ ] Restore every mutant **by `git diff`/`git checkout`, never by `str.replace`** — see
      `khepri-restore-a-mutant-by-diff-not-by-replace`.

## Task 5 — Correct the allocation plan in place

- [ ] Rewrite §Slice 2's "Scope boundary" paragraph to state that the journey delivers one
      mechanism and that §73's consolidation clause has no subject, citing the binding evidence.
- [ ] Leave slice 2b's framing in the companion plan untouched — it is the shell's, and this plan
      may not correct the other's authority.

## Task 6 — Evidence file and gates

- [ ] Write `docs/superpowers/plans/2026-09-19-u1-rra-slice-2-evidence.md` with the Task 0 table,
      the mutation results, and the two recorded findings (the false premise, the focus-order trap).
- [ ] `uv run khepri-gov validate`, `uv run ruff check .`, `uv run pytest`.
- [ ] CodeScene: the new test module must score 10.00.
