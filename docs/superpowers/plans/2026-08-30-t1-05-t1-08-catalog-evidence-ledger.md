# T1-05 / T1-08 — the catalog read surface and its evidence parity

**Slices:** `T1-05` (metric detail and evidence routes) and the `T1-08` remainder that could not
exist until it did. `T1-01` through `T1-04` merged at `#334`, `#338` and `#340`, building a registry
with **no production caller** — nothing in `src/` imported `definitions.py`. This slice is the one
that wires it, which is why every guard below drives the HTTP boundary or an external oracle rather
than calling the catalog functions directly.

**Run date:** 2026-08-30. **Tree:** `feat/t1-05-catalog-evidence-routes`, `main` (`46b2d56`) plus
seven commits.

**Authority:** `RRA-011`, active. Its Scope names three files —`definitions.py`, `report_api.py`,
`rendering/wording.py` — and excludes `src/khepri/rra/journey/` as `RRA-010`'s and the shell surface
set as `RCA-002`'s. No file under either is touched.

---

## T1-05 — the catalog read surface

Acceptance (roadmap:745): *"Definition, formula version, inputs, coverage, filters, citations,
reconciliation, and caveats."*

Six routes under `/api/v1/beta/catalog/`, declared in two halves because they answer at two scopes.

| Route | Scope | Reads |
|---|---|---|
| `GET /catalog/metrics/{code}/{language}` | catalog | `define_metric`, `describe_metric`, `not_meant`, `synonyms` |
| `GET /catalog/populations/{code}` | catalog | `define_population` |
| `GET /catalog/reasons/{code}/{scope}/{language}` | catalog | `define_reason`, `explain_reason` |
| `GET /catalog/caveats/{code}/{language}` | catalog | `define_caveat`, `explain_caveat` |
| `GET /catalog/quality/{language}` | package | `summarize(bundle)` |
| `GET /catalog/citations/{citation_id}/evidence/{language}` | package | the audit region + the package |

### Two corrections to the approved plan, both found by building rather than reading

**F1 — the route key is `citation_id`, not `fact_id`.** *(CLOSED — the plan was wrong, the code is
right)*

`_identity` (`facts.py:2211-2226`) returns `(f"fct_{digest[:24]}", f"cit_{digest[:12]}")`, so the two
are different strings derived from one digest. `FigureCell` (`html.py:228-250`) carries
`citation_id` and **deliberately drops** `fact_id`, so no fact identifier reaches the audit region at
all. A fact-keyed route could therefore answer only by reading `bundle.figures` itself — the second
projection `RRA-011` forbids in the same sentence that requires exactly one.

Measured while settling it: the shared fixture renders **49 figures over 22 citations**, because a
series has one citation and many cells. The response groups cells under a citation rather than
pairing them. `test_the_audit_region_names_no_fact_identifier` pins the reasoning so a later slice
cannot add the field back as a convenience.

**F2 — the routes are session scoped, not job scoped, and no governed record could make them
otherwise.** *(CLOSED for this slice; the underlying gap is filed as F6)*

The plan keyed these on `{job_id}` by analogy to `report_api.py`'s siblings and reconciled the
rebuilt package against `DeliveryRecord.package_version`. That check cannot discriminate: two
different packages in one session share `package_version` (`rra004.package.v3`) and differ only by
digest — measured, not assumed. It would have passed while serving evidence rebuilt from the wrong
data.

`RRA-011`'s Scope settles the shape: read routes expose *"the registry, the summary, and **a fact's
evidence**, session scoped exactly as their existing siblings are."* A fact's, not a report's — and
`summarize(bundle)` and `availability(mapping)` take no job either. The job-keyed siblings are job
keyed because they serve one delivered **artifact**. `GET /api/v1/beta/facts` (`api.py:381`) is the
session-keyed package route this follows.

This **deleted** machinery rather than adding it: `reconcile_delivery`, `DeliveryWithheld`, the
`package_version` check, and the 503-versus-409 question all left the design.
`get_session_package` already refuses an expired session (`packages.py:474`), an unconsented one
(`:475`) and a superseded version (`:484`), and all four of its refusals were **already rows** in
`_REPORT_REFUSALS`. `_session_bundle` adds the digest self-check itself.

### The one projection

`RRA-011`: *"Expose exactly one evidence projection per fact. A catalog route MUST read the
projection the report surfaces already render from, never assemble a second one from the bundle
directly."*

The handler binds `build_context(bundle, language, cells)["audit"]` and reads no other key of that
context. `build_context` and `build_cells` are already public and already imported cross-module
(`pdf.py:213` does exactly this), and `context["audit"]` *is* the object handed to the
`evidence(audit, chrome, caveat_prose)` macro in `_evidence.html.j2`. Not a second assembly — the
same assembly, called. `rendering/html.py` is imported and never edited, which keeps the slice inside
its own Scope.

**F3 — an output comparison cannot prove single-sourcing, and the first guard did not.** *(CLOSED —
guard replaced, mutation-verified)*

The first version of `test_the_evidence_route_answers_from_the_projection_the_report_renders`
compared the response to `build_context(...)["audit"]` computed independently. It passed against a
mutant in which the handler assembled its own dict from `bundle.sections` and `bundle.caveats` —
because `_audit_region` copies those faithfully, so a hand-built dict is byte-identical. Every other
test in the module passed against that mutant too.

"Reads exactly one projection" is a claim about **where the answer came from**, not about what it
contains, so it is now asserted where it lives. `test_..._reads_the_shared_projection_and_no_other_key`
patches `report_api.build_context` with a spy returning a dict subclass that records every key read,
and asserts the call happened and `audit` was the only key taken. Its pair,
`test_..._reports_what_the_audit_region_holds`, empties the projection's sections so a handler
holding its own copy answers with five where the projection offers none. Neither alone is
sufficient: the first proves what was read, the second proves what was read is what was answered.

### Package scope, read from the package

`RRA-011` requires the evidence surface to carry coverage from `coverage_signatures` and
`coverage_manifest_identity`, the filters from `event_kind_filters` and `status_filters`, and each
`RetainedBasis` by `name`, `population`, `event_count`, `input_digest` and `precision`. None are in
the audit region. The same specification says a package-scoped attribute **must** be read from the
package that carries it, so `_package_evidence` does exactly that — the single-projection rule binds
the *evidence* projection, and package scope is separately required to come from the package.

Verified reproducible after `rebuild_fact_package`: all are serialized into `as_document()`
(`facts.py:480-487`). `CoverageSignature` is exposed by its governed `identity` rather than flattened
to a shape this surface would have invented.

**`population` appears on a basis and on no figure**, which is `RRA-011`'s per-figure prohibition
read from where the field actually lives: a `Fact` carries none, and a package retains several bases
with different ones.

### Two keys absent rather than empty

**F4 — a re-derived bundle cannot reproduce `bundle_id`, so `provenance` and `passages` are
omitted.** *(CLOSED — omission is the correct answer, and it is tested)*

`ReportBundle.bundle_id` (`bundle.py:858`) hashes `as_document()`, which includes
`"narrative": _narrative_document(self.narrative)` (`bundle.py:885`). The narrative comes from a
provider adapter (`narrative.py:617`) and **no `NarrativeDraft` is persisted** — verified by grep
across `src/khepri/`: it appears in seven modules, none of them a persistence module.

So `_audit_region`'s `provenance`, which sets `entries["bundle_id"] = bundle.bundle_id`
(`html.py:642`), would publish an identifier no delivered surface ever echoed; and `passages`
(`html.py:539`) would be empty on a report that has prose. Both are absent from
`FactEvidenceResponse` rather than emitted empty. The repository already draws this distinction in
its own words at `package_source.py:391-405`: "not counted" and "counted, and none" are different
findings.

### What the catalog still never serves

The module docstring said responses carry *"not a figure, a caveat, a safe label"*. True of the
report routes, false of the catalog ones — they serve caveat codes and their bilingual wording
because that is what a catalog is for. Amended to say which half is which, and to state the line that
holds for both: **no figure, no value, no storage location, no Internal-tier field.**

That line is now a test. `_evidence_response` holds a list of `FigureCell` while it works and takes
only `figure_id` from them, and `test_no_catalog_response_carries_a_figure_value` is
mutation-verified against leaking `text`.

**Recorded because the first version of that test was wrong:** it searched the serialized body for
any rendered figure as a substring, and a rendered figure is sometimes `"2"`, which occurs inside a
digest. It failed against correct code. Fixed to compare field values. A test that fails on correct
code is as much a defect as one that passes on wrong code, and this one would have been "fixed" by
weakening the guard if the failure had been taken at face value.

---

## T1-08 — parity, fail-closed, and no duplicate truth over the evidence surface

Acceptance (roadmap:748): *"Unknown metric/reason/version refuses; every displayed figure has one
definition and evidence path."*

`tests/test_rra011_parity.py` (588 lines, merged at `#334`) already covers parity, fail-closed and
no-duplicate-truth over the metric, definition and quality **functions**. The genuinely new half is
the **evidence surface and the HTTP boundary**, across two modules — 28 tests, written deliberately
flat, no helper pyramid.

They began as one file and were split when CodeScene failed it on Low Cohesion, a critical rule:
LCOM4 measures whether a module's functions share data or call each other, and this one held two
groups that never touched. `tests/test_rra011_projection.py` (5 tests) characterizes
`build_context(...)["audit"]` using only the rendering path;
`tests/test_rra011_catalog_routes.py` (23 tests) drives the HTTP boundary through `_harness` and
`FakePackageReader`. The file already carried a `# --- the HTTP boundary ---` divider between them,
so the metric found a seam that had been drawn and then ignored. Both score 10.00.

| Property | Test |
|---|---|
| Every displayed figure's citation is listed | `test_every_cell_carries_a_citation_the_audit_region_lists` |
| One citation answers for many cells | `test_one_citation_answers_for_every_cell_that_quotes_it` |
| The route reads the shared projection, and only `audit` | `test_the_evidence_route_reads_the_shared_projection_and_no_other_key` |
| What it read is what it answered | `test_the_evidence_route_reports_what_the_audit_region_holds` |
| Unknown code refuses at every route | `test_an_unknown_code_refuses_at_every_catalog_route` |
| A reason refuses at a scope it is not stated at | `test_a_reason_refuses_at_a_scope_it_is_not_stated_at` |
| Every route requires a session, registry reads included | `test_every_catalog_route_requires_a_beta_session` |
| No reader configured → no route, not a refusing one | `test_the_catalog_routes_are_absent_without_a_package_reader` |
| No Internal-tier field on any response | `test_no_catalog_response_carries_an_internal_tier_field` |
| Absence, not emptiness | `test_the_evidence_response_omits_the_unreproducible_keys` |
| Populations only on a basis | `test_the_evidence_response_names_populations_only_on_a_basis` |
| No figure value | `test_no_catalog_response_carries_a_figure_value` |

**Fail-closed is asserted at the boundary, not only beneath it.** `UnknownCode` is now a row in
`_REPORT_REFUSALS` rather than a bespoke `except` in a helper beside that table — the module states
that policy directly, and a second `except` is how two statuses for one refusal come to disagree.
A code the catalog does not admit is **absent (404), not forbidden**, matching the module's existing
404-not-403 discipline.

**The reason scope is gated once.** The path constraint bounds the segment; `explain_reason` decides
admissibility. A `^(section|result)$` regex would have restated `wording.GOVERNED_REASON_SCOPES` as a
second truth for no gain — the 404 is identical either way.

### The duplicate-truth scan could not see a whole class of list

**F5 — `bundle.SECTION_REASONS` was invisible to the guard, not absent from the source.** *(CLOSED —
scan widened, list pinned with reasoning)*

`_HAND_LISTED` matched a flat set literal. `SECTION_REASONS` (`bundle.py:285`) is a dict whose
*values* are frozensets, so its body lines read `SECTION_COMPARISON: frozenset(` and the colon broke
the alternation. It had never been reported. A second pattern now matches the nested shape, and
`test_the_catalog_adds_no_hand_maintained_code_list` pins three names where it pinned two.

It is **pinned rather than removed**, and the distinction is the one the specification draws.
`REASON_CODES` states which reasons exist; `SECTION_REASONS` states which of them each analysis may
refuse with — a per-section scoping no governed module derives. Deriving it here would invent that
relationship, which is the second truth the test exists to prevent; narrowing it to the catalog's
flat set would lose a real constraint. Reducing it is an `RRA-009` change to what a section may say.

The scan was also rooted at `pathlib.Path("src/khepri/rra")` **relative to the working directory**,
so running pytest from elsewhere scanned a path that did not exist. Now rooted at the test file, with
`test_the_hand_listed_scan_reaches_the_product_source` asserting it finds something.

---

### F7 — a derived figure's precision and inputs are unobtainable without re-derivation

*(CLOSED by omission; the underlying gap is filed below)*

`RRA-008`'s analysis facts — comparison, growth, basket, concentration — are computed by
`family.derive(package)` while `ReportBundle.of` assembles, and no governed record retains them. Only
`CitedFigure` survives, carrying `unit_kind` but not `precision` or `inputs`.

**An earlier revision of this slice resolved those citations by calling `family.derive(package)`
during the read, and that was outside the specification.** `RRA-011`'s Exclusions forbid *"any
calculation, re-derivation, re-rounding, or re-formatting of a published figure. A catalog surface
repeats a value; it never recomputes one."* The commit that introduced it argued determinism made it
safe — that re-deriving "reads the same truth the bundle read rather than inventing a second one."
That reasoning is wrong against the text: the Exclusion names re-derivation itself, not
non-determinism, and no exemption for deterministic recomputation is offered. Recorded as a reversal
rather than only as a final state, because the argument was plausible and a later slice may reach for
it again.

The surface therefore serves derived citations from what the bundle and its audit region already
hold, and **omits `precision` and `inputs` for them** — absent, not empty and not recomputed, the
same rule F4 applies to `provenance` and `passages`. Every one of the 22 displayed citations still
resolves, so `T1-08`'s evidence path holds; only the two fields no readable record states are gone.
`test_no_catalog_route_recomputes_a_published_figure` asserted the absence of `family.derive` in the
module.

**That guard was later found worthless and is gone.** `ReportBundle.of` calls `family.derive` and
`concentration.curve_series` itself, so the two package-scoped routes still reach derivation one
frame deeper, and a string search over one file could not see it. Whether *that* is permitted is the
open question `F8` puts to the owner — see
`docs/superpowers/plans/2026-08-30-rra011-exclusion-reading.md`. What this slice fixed is narrower
than the paragraph above claimed: the route no longer calls `family.derive` directly, and the two
fields no readable record states are still omitted rather than recomputed.

**The gap this leaves is real and filed as P2.** Roadmap:745 names "inputs" in `T1-05`'s acceptance.
It is met for stored facts and structurally unmeetable for derived ones under `RRA-011`'s own
Exclusions — the two clauses cannot both be satisfied for a derived figure without retaining those
facts on the package or in the shared projection, which is an `RRA-004`/`RRA-008` change and not this
specification's to make. `P2` on the same reasoning as F6: no wrong figure is published, and the
omission is visible in the response rather than papered over with an empty list.

## Findings

| Finding | Kind | Severity | State |
|---|---|---|---|
| F1 | Plan error — route key | — | Closed; code correct, plan corrected |
| F2 | Plan error — route scope | — | Closed; deleted machinery |
| F3 | Weak guard — output equality | P1 | Closed, mutation-verified |
| F4 | Unreproducible `bundle_id` | — | Closed by omission |
| F5 | Invisible hand-maintained list | P1 | Closed, mutation-verified |
| F6 | No report-to-package link exists | **P2** | **Filed, open** |
| F7 | Derived figures: precision and inputs unobtainable without re-derivation | **P2** | **Filed, open** |

### F6 — no governed record ties a delivered report to the package it was built from

`DeliveryRecord` (`pipeline.py:146-151`) carries `bundle_id` — derived over the unpersisted narrative
(F4) — and `package_version`, which a session's several packages share.
`get_package_for_session` (`persistence.py:640-661`) is explicitly *"latest first"*. `ReportJob`
(`jobs.py:97-111`) carries no package identifier. The worker path avoids the problem by loading at
build time; a route reading later cannot.

**A report-keyed evidence route is therefore not currently buildable**, and supplying that link is an
`RRA-004`/`RRA-006` change to what a delivery record carries — which `RRA-011` says in its own
Requirements is not its to make.

**P2 rather than P1, and the reason decides whether this slice is complete.** It publishes no wrong
figure and no wrong attribution: the catalog answers about the session's *current admitted data* and
says so, rather than claiming to describe a particular past report. A caller who has published once
— the whole of the `M2` journey — sees evidence for exactly the package their report was built from.
The gap bites only where a session republishes, and there the honest answer is the current package,
which is what is served. The existing job-keyed HTML evidence surfaces are untouched and continue to
serve the delivered artifact.

---

## Gate

| Check | Result |
|---|---|
| `uv run khepri-gov validate` | **Governance validation passed.** |
| `uv run ruff check .` | **All checks passed!** |
| `uv run pytest` | **3813 passed, 72 skipped, 1 xfailed** |

The baseline on `main` at `46b2d56` is **3797 passed, 72 skipped, 1 xfailed**, measured this session
rather than quoted: `CAL1-13`'s recorded 3,631 predates `#334`, `#338` and `#340`. The delta is
16 — 15 in the new evidence module and one new scan-reach test — and **skips are unchanged at 72**,
which is the half that matters, since a rise would mean a test stopped running rather than started
passing.

**CodeScene**, run locally through the MCP server before handoff:

| File | Score |
|---|---|
| `tests/test_rra011_projection.py` (new) | **10.00** |
| `tests/test_rra011_catalog_routes.py` (new) | **10.00** |
| `src/khepri/rra/report_api.py` (modified) | **9.37**, its baseline unchanged |

**The server gate caught a file the local pre-flight had not scored.** `test_rra011_parity.py` fell
10.00 → 9.39 on "Deep, Nested Complexity": widening the scan put a second pattern loop inside the
file loop, taking `_hand_listed_sets` to nesting depth 4, one past Python's threshold. The local
check had scored `report_api.py` and the new test module — the two files the slice was *about* — and
not the third file the same commit edited. Fixed by splitting `_listed_in` from the walk, which is
the honest decomposition anyway: one function asks what a module declares, the other which modules
exist. Back to 10.00, and the nested-list mutant is still killed after the split. Recorded because
the lesson is about *what was measured* rather than about the metric: the gate scores every changed
file, and all seven are now scored — `api.py` 7.52 and unchanged (two lines, neither adding a
branch), `reports.py` and both `wiring.py` at 10.00.

The first draft of the routes scored **8.64** — a decline, which the gate forbids. Two findings were
mine and both were fixed by splits the design already wanted: `_package_evidence` separates
package-scope reads from the audit region, and `_add_registry_routes` / `_add_package_routes`
separate the two scopes the group answers at. The remaining finding is the pre-existing 113-line
`add_report_routes`, which this slice does not touch — restoring the baseline is compliance, and
refactoring a method belonging to another slice would be scope creep.

## Standing

| Slice | State |
|---|---|
| `T1-05` | Complete |
| `T1-08` | Complete for the surfaces `M2` ships |

`KHEPRI-DEC-031` §7.1 requires these merged to `main` before `M2` can be recorded. That record is
deliberately **not** in this PR: at the moment it would be written, these commits are not merged, and
a milestone gating external customer contact is the wrong place to assert a condition that is not yet
true. It follows in its own PR.
