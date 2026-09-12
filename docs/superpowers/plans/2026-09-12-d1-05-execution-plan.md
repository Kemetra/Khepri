# `D1-05` — The evidence drawer, its two authorities, and the absence that is not a refusal

**Slice:** `D1-05` under active `RCA-008`. **Requirements:** `FR-159`, `FR-161`, `FR-162`
(evidence action), `FR-164`.

**Blocked by:** `D1-04`, merged at `a65df40` (`#448`). Nothing else.

---

## What `D1-04` handed forward, verbatim

- **`evidence_absences` already reaches a read model.** `breakdowns.py:111` carries the field and
  `:158` copies it off the projection. This slice does not invent the channel; it renders it.
- **`REPORT_EVIDENCE` is already in the seam.** `seam.py:125` publishes the identity with
  `empty_rule=EMPTY_STATED_ABSENCE`, and the source-map test asserts `DECISION_VIEWS` equals what
  the registry publishes. A ninth view cannot be invented here.
- **`admitted_projection` has one definition**, in `seam.py`, imported by `overview.py` and
  `card.py`. The drawer's read uses it rather than repeating the fail-closed dispatch.
- **The route exists and the built image declares it.** `_shell_decisions` wires
  `ShellServices.decisions`, and `test_the_built_image_wires_every_optional_field` now derives its
  population from `dataclasses.fields(ShellServices)`. **If this slice needs a new optional
  collaborator, the fix is to wire it in `build_shell_services` — never to add a
  `deliberately_unwired` entry to make that test pass.**

---

## Five decisions, taken from precedent rather than assumed

**1. `required_evidence` stays `()`. This slice does not tighten it.**
Verified on `main`: all eight registry entries are `required_evidence=()`. `FR-141` makes a
required-but-absent evidence code a *refusal cause*, so populating that tuple would convert an
ordinary absence into a refused view. `D1-01` §4 already established the v1 emptiness is deliberate
and not an oversight for D1 to correct. **Absences arrive as `ViewProjection.evidence_absences` —
data on an admitted projection — and render as data.** A test asserts an absence does not produce a
`ViewRefusal`.

**2. The definition half comes from `khepri.rra.definitions`, read per code, never cached.**
`define_metric(code)` and `describe_metric(code, language)` are the accessors; `UnknownCode` is
raised rather than returning the code itself, which is the fail-closed behaviour `RRA-011` requires.
`FR-159` admits this because a definition is structure, not a figure. The drawer holds no copy of
the catalog: a second copy is the second-truth `FR-135` bars.

**3. The two halves arrive by different routes and are not merged into one record.**
The figure half is a `REPORT_EVIDENCE` projection through the seam; the definition half is a catalog
lookup. This is `limits.py`'s shape from `D1-04`, for its reason: a flattened record would have to
invent a field name for at least one half, and a reader could no longer tell which authority said
what. **The drawer's read model carries both, each named by its own source.**

**4. The drawer is never a page of its own (`FR-161`).**
It is reachable from every figure on S-1, S-3, S-4 and S-5 in one action, and has no route. This is
why the slice adds no route and no `ShellServices` field: it extends surfaces that already exist.

**5. An unknown metric code is a refusal, not a blank drawer.**
`UnknownCode` propagates as `FR-164`'s refusal path, worded from the governed catalog in the page
language. A drawer that opened empty on an unrecognized code would be indistinguishable from a
metric with no evidence — the `[[an-unevaluated-proof-reports-as-a-passed-one]]` shape.

---

## Files

```
src/khepri/rca/workspace/decision/
    evidence.py                              # NEW - the drawer's read model, both halves
src/khepri/runtime/
    shell_templates/decision_*.html.j2       # drawer markup, reachable from each figure
    shell_assets/workspace.css               # decision-surface drawer rules only
tests/
    test_d105_evidence_drawer.py             # NEW
```

No new route. No new `ShellServices` field. No persistence change.

---

## Steps

### RED

1. **An evidence absence renders as data, not as a refusal.** Project a `REPORT_EVIDENCE` outcome
   whose `evidence_absences` is non-empty; assert the drawer renders the absence and that the read
   model is an admitted projection, not a `ViewRefusal`. *This is the slice's central assertion.*
2. **The definition half comes from the catalog.** Assert the rendered label and formula version
   equal `define_metric(code)`'s, in both `en` and `ar`, rather than a string the drawer coins.
3. **An unknown code refuses.** `UnknownCode` reaches the surface as `FR-164`'s worded refusal in
   the page language, and the drawer does not render.
4. **The drawer is reachable from every figure on the surfaces that render**, asserted over the
   route rather than by a standalone render.

   **Corrected after implementation, and the correction is the point.** This step first said "S-1,
   S-3, S-4, S-5". Only **S-1 renders today**: `D1-04` shipped `breakdowns.py` and `limits.py` as
   read models, and `_respond` calls `read_cards` alone — no route renders S-3, S-4, S-5 or S-6, and
   no template for them exists. So there was exactly one include point to build, and the other three
   could only have been satisfied by *inventing* the surfaces, which would build what no slice
   authorized and pre-empt `D1-06`.

   `D1-05` therefore closes S-1's reachability and **hands S-3/S-4/S-5 forward to the slice that
   renders them**. That slice adds the include beside its own figures; the drawer, its copy and its
   stylesheet rules are already built and need no further authority.
5. **The drawer has no route.** Assert no path matching `.../evidence` is in the app's route table,
   which is `FR-161` from the deployment side.
6. **`required_evidence` is still `()` for all eight views.** An extent assertion over the registry,
   so a later slice cannot quietly populate it and convert absences into refusals.

### GREEN

Build `evidence.py`: a read model holding the figure half (a `REPORT_EVIDENCE` projection via
`admitted_projection`) and the definition half (catalog lookups), each named by its source. Wire the
drawer into the existing templates for the four surfaces. Add drawer rules to `workspace.css`.

### Gates

`ruff check src/ tests/`; full `pytest` (not targeted — `[[run-the-full-suite-before-believing-a-targeted-one]]`);
CodeScene pre-flight against a freshly fetched `origin/main`.

---

## Not in this slice

- **The `FR-170` unreachability assertion stays standing.** `D1-03` shipped it; only the slice that
  makes the Period Comparison source reachable removes it, and per the allocation plan that is none
  of `D1-05`…`D1-10`.
- **No chart grammar, navigation, or accessibility programme** — `U1-03`/`-05`/`-06`/`-07`'s, and
  they need their own authority.
- **No S-3/S-4/S-5 surface.** Those read models exist and nothing renders them; building a template
  to host a drawer would be building the surface. `D1-06` onward.
- **One evidence read per card, and it is named rather than hidden.** `FR-161` wants the evidence at
  each figure and `FR-168` bars the instruments that would fold the reads together. `D1-09` measures
  acquisition and may coalesce *within* a request — never between them. `drawers_for`'s docstring
  states the count so that slice finds it recorded.
