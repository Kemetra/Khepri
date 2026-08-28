# CAL1-11 — final compatibility sweep ledger

**Baseline:** `origin/main` at `844d51b`, swept 2026-08-28 (UTC). Branch
`feat/cal1-11-compatibility-sweep`; its commits carry 2026-08-29 local (+0300) timestamps.
**Authority:** `RRA-003`, `RRA-004`, `RRA-008`, `RRA-009` (all ACTIVE).

`CAL1-11`'s acceptance is *"a catalogue-wide proof that every governed refusal and caveat already
shipped with its wording and surfaces; no surface recalculates; the successor facts reconcile in both
languages"* (roadmap §7 task table). Roadmap line 620 fixes its character: **a final sweep, not the
task where surfaces catch up.** A gap found here is filed against the owning family, not fixed here.

---

## 1. Obligation → existing proof mapping

The sweep is a *delta* exercise: most obligations were already discharged by the slices that
introduced each code. This section is the evidence that the sweep was catalogue-wide, and it is what
narrowed the work from "write a sweep" to "close two derivations".

### Obligation 1 — refusal reasons

| Leg | Covered by | Verdict |
|---|---|---|
| Section-tier universe pinned | `test_rra009_wording.py:268` (`len == 12`) | ✅ |
| Section-tier universe **derived from production** | `:72` — `frozenset(GOVERNED_SECTION_REASONS)`, itself derived from `SECTION_REASONS`, pinned by `test_rra006_bundle_sections.py:487` | ✅ closed chain |
| Section prose, both languages | `:297` cross-product | ✅ |
| Result-tier universe pinned | `:323` (`len == 12`) | ✅ |
| Result-tier universe derived | `:73` — **hand-listed** | ⚠️ F1b, filed |
| Result prose, both languages | `:362` cross-product | ✅ |
| Arabic prose pinned | `:369` | ✅ |
| Unknown code raises | `:314`, `:398` | ✅ |
| Guard-the-guard | `:483`–`:522` (5 tests, monkeypatched) | ✅ |
| Audit representation | `test_rra009_business_audit_split.py` | ✅ |

### Obligation 2 — caveats

| Leg | Covered by | Verdict |
|---|---|---|
| Caveat prose, both languages | `test_rra009_wording.py:387` | ✅ |
| Arabic caveat prose pinned | `:392` | ✅ |
| Caveat universe derived from production | `:89` — was hand-listed | ✅ F1a, closed here |
| Composite `result:reason` form | `:403`, `:412`, `:426` | ✅ |

### Obligation 3 — no surface recalculates

| Leg | Covered by | Verdict |
|---|---|---|
| Arabic render is transliteration, not recalculation | `test_rra006_bundle.py:308` | ✅ |
| Excel regroups, never recomputes | `excel_layout.py:10`, `excel.py:947` (prose); `test_rra006_excel_surface.py:606` | ✅ |
| Chart coordinates read off marks | `charts.py:380` | ✅ |
| Restriction selects from parent | `test_rra004_daily_bases.py:164` | ✅ |

### Obligation 4 — successor facts reconcile in both languages

| Surface | Covered by | Verdict |
|---|---|---|
| HTML | `test_rra006_html_sections.py:333` | ✅ |
| PDF | `test_rra006_pdf_sections.py:139` | ✅ |
| Excel | `test_rra006_excel_sections.py:245`, `test_rra006_excel_surface.py:606` | ✅ |
| Charts | `test_rra006_charts.py:412` | ✅ |
| Narrative | `test_rra005_narrative.py:318`, `test_rra005_narrative_units.py:140` | ✅ |
| Evidence page | `test_rra009_business_audit_split.py:278` | ✅ |
| Journey refusal | `test_rra003_journey_source_contract.py:540` | ✅ |

### Version compatibility (triple + families)

`test_rra004_version_compatibility.py` (12 tests) and `test_rra004_version_gate_wiring.py` (623
lines) close this: shipped triple admitted (`:37`), only landed families admitted (`:77`), moved
version refused (`:129`, `:142`, `:150`), tables non-empty (`:192`), family refusal carries bilingual
wording (`:203`), package refusal proven internal (`:225`). `.v99` sentinels already in place.

**No refusing family remains:** all four `rra008.*` families pair with `rra004.formula.v2`.

`test_only_the_families_that_have_landed_are_admitted` (`:77`) was written while families were still
landing one per commit, so it was checked for staleness rather than trusted. It is **not** stale and
**not** a tautology: deleting the `("rra004.formula.v2", "rra008.concentration.v2")` row from
`ADMITTED_FAMILY_PAIRS` fails it at `:105`. It compares the table against the family constants, so it
still discriminates now that the refusing set is empty.

---

## 2. Findings

### F1a — The caveat registry was hand-listed, not derived *(CLOSED in this slice)*

`_GOVERNED_CAVEAT_CODES` (`test_rra009_wording.py:89`) enumerated imported constants by hand, and the
cross-product tests compare the wording tables *against that set*. So a new `CAVEAT_*` defined in
production and stated on a result left every existing test green while a customer read an
untranslated code.

The section tier never had this hazard: its chain from `SECTION_REASONS` → `GOVERNED_SECTION_REASONS`
→ `_SECTION_REFUSAL_CODES` → wording is derived end to end.

**Closed here** — a proof gap, not a surface gap, so it is in scope for a sweep.
`test_every_caveat_constant_defined_in_production_is_a_governed_caveat` derives the universe by
walking every module under `khepri.rra` and reading its own `CAVEAT_*` constants.

**Mutation evidence, two rounds — the first guard was defective and the record matters:**

| Mutant | v1 (four named modules) | v2 (walked package) | v3 (walk + root) |
|---|---|---|---|
| `CAVEAT_*` in `facts.py` | killed | killed | killed |
| `CAVEAT_*` in `analysis/basket.py` | **SURVIVED** | killed | killed |
| `CAVEAT_*` in `khepri/rra/__init__.py` | **SURVIVED** | **SURVIVED** | killed |

The first version named four source modules by hand — the very defect it was written to catch, one
level up. `basket.py` and `concentration.py` were unscanned, and `concentration.py` already imports
`CAVEAT_BUCKETS_TRUNCATED`, so a caveat appearing there is not hypothetical. `assert defined` catches
"the scan found nothing", never "the scan missed a module". The walk closes it; the emptiness
assertion on the module list guards the walk itself.

**The same defect recurred twice more, each one level up.** `pkgutil.walk_packages` yields
descendants and never the package root, so a caveat defined in `khepri/rra/__init__.py` sat outside
a walk that looked complete; the root is now included explicitly. And an earlier version swallowed
import errors, which would have let a module that defines an unregistered constant *and* raises on
import contribute nothing while the other modules kept the comparison non-empty. Three rounds, one
lesson: **a guard's own scope declaration is the weakest link, and no mutant placed inside that scope
can find it.**

Uses `vars(module)` rather than `dir(module)`: `dir()` includes imported names, which would attribute
a constant to every module that imports it.

### F1b — The result-tier registry is still hand-listed *(FILED — `RRA-009`)*

`_RESULT_REFUSAL_CODES` (`:73`) has the same shape as F1a and is **not** closed here.

It cannot be closed the same way. A result-tier reason is not identifiable by constant name: the
`REASON_*` constants in `bundle.py` (20) and `narrative.py` (21) are internal
`BundleRefused`/`NarrativeRefused` integrity codes that reach no customer, and
`facts.REASON_PACKAGE_VERSION_UNADMITTED` is deliberately internal
(`test_rra004_version_compatibility.py:225`). A `vars()` scan over-collects all of them.

Closing it needs raise-site analysis — which reasons actually reach a `RefusedResult` — not constant
introspection. That is a distinct piece of work under `RRA-009`, filed rather than improvised here.

### F2 — The two tiers overlap by design, and the overlap was unpinned *(CLOSED in this slice)*

`section` and `result` share exactly five codes — `coverage_structurally_incompatible`,
`family_version_pairing_unadmitted`, `incomplete_transaction_identifiers`, `repeated_row_signature`,
`required_input_unavailable`. `bundle.py` explains why: a family that refuses for one of these hands
its own code straight to the section rather than a section-flavoured synonym.

Nothing pinned that set, so a sixth shared code could arrive unnoticed.
`test_the_two_customer_tiers_are_the_only_ones_wording_states` now pins it.

**Mutation evidence, and an honest statement of what it does not prove.** Three mutants were run:

| Mutant | Result | Killed by |
|---|---|---|
| A code dropped from the pinned `_SHARED_TIER_CODES` set | killed at `:634` | **this test** |
| `"units_absent"` added to `_RESULT_REASON_CODES` | killed at import | production's wording guard |
| `"negative_base"` added to `SECTION_REASONS` | killed at import | production's wording guard |

Only the first is killed by this test. A production-side change to the intersection cannot reach the
assertion, because a code entering a tier needs prose in that tier and
`_assert_refusal_wording_complete` fires during import — verified by supplying the code and watching
the guard still refuse.

So the honest scope is narrower than "a sixth shared code cannot arrive": production's own guard
already refuses one that arrives without prose. What this test adds is a **pinned record of the
intersection** — a reviewer adding a sixth code with complete prose in both tiers must edit
`_SHARED_TIER_CODES` deliberately, which makes the widening visible in the diff rather than silent.
That is a real but modest property, and it is stated here rather than overclaimed.

### F3 — `JOURNEY_COPY` is not linked to `admissibility.REASON_*` *(FILED — `RRA-003`)*

All six admissibility reasons **do** have bilingual prose and a rendered surface
(`journey/templates/review.html.j2:21-26`, EN `journey/copy.py:70,73`, AR `:241,244`). An earlier
report that four were unworded was wrong.

The defect is structural: one code carries three spellings — constant `REASON_NO_TIME_FIELD`, value
`no_admissible_time_field`, attribute `data-no-admissible-time-field`, copy key `reason_no_time_field`
— and **nothing asserts the correspondence.** Renaming a code silently breaks the surface.

Not closed here: the fix is a new guard over a `RRA-003` surface, which is a family change.

### F4 — No cross-surface reason-set equivalence test *(FILED — `RRA-006`)*

Each surface is proven bilingual in isolation. Nothing asserts web/PDF/Excel state the *same* reason
set for one bundle. `pdf.py` imports no projection directly — it inherits transitively from
`html.py:51` — so a PDF-layer divergence is untested.

### F5 — Tables without a completeness guard *(FILED — `RRA-009`)*

`SECTION_HEADINGS`, `CHART_DESCRIPTIONS`, `KIND_QUALIFIERS`, `DERIVED_METRIC_WORDING`,
`bundle._DISCLOSURE` have no import-time parity assertion, unlike `REFUSAL_WORDING`, `CAVEAT_WORDING`,
and `METRIC_WORDING`.

### F6 — Ten version constants are unpaired *(FILED — owner-decided out of scope)*

`versions.py` governs only `(mapping, package, formula)` and `(formula, family)`. Unpaired:
`BUNDLE_VERSION`, `NARRATIVE_VERSION`, `ADAPTER_VERSION`, `PIPELINE_VERSION`, `PROFILE_VERSION`,
`COVERAGE_MANIFEST_VERSION`, `SOURCE_CONTRACT_VERSION`, `HTML_SURFACE_VERSION`,
`EXCEL_SURFACE_VERSION`, `PDF_SURFACE_VERSION`.

Owner decision 2026-08-28: prove the triple only; building new pairing tables is
catalogue-construction, which line 620 excludes from a sweep.

### F7 — Stale prose at `versions.py:66-68` *(FILED — docs)*

Describes a blackout window as current: *"The refusing set is largest at this commit and
`V-concentration` empties it."* At `844d51b` the set is already empty.

### F8 — Stale test name *(FILED — naming, not an obligation gap)*

`test_section_refusal_universe_is_eleven_codes` (`test_rra009_wording.py:268`) asserts `== 12`. Its
docstring enumerates the twelfth. **Not counted as an obligation gap.**

---

## 3. Disposition

| Finding | Kind | Disposition |
|---|---|---|
| F1a | Proof gap (caveats) | Closed in this slice, mutation-verified over two rounds |
| F1b | Proof gap (result tier) | Filed — needs raise-site analysis, not introspection |
| F2 | Proof gap | Closed in this slice, mutation-verified |
| F3 | Surface guard, `RRA-003` | Filed — separate slice |
| F4 | Surface guard, `RRA-006` | Filed — separate slice |
| F5 | Wording guard, `RRA-009` | Filed — separate slice |
| F6 | Version pairing | Filed — owner-decided out of scope |
| F7 | Stale prose | Filed — docs |
| F8 | Stale name | Filed — naming, not a gap |

**No deferred refusal reason, caveat, bilingual wording, or surface representation was found.** Every
governed code reaching a customer carries prose in both languages and a rendered surface. The
findings closed here are gaps in the *proof*, not in the shipped contract — consistent with line
620's rule that a slice leaving its refusal unsurfaced for `CAL1-11` had already broken the rule.

**CodeScene pre-flight was not run:** the CodeScene MCP server failed to connect this session. The
change is 83 lines into an existing test module with no new source file, which is the shape that gate
is least likely to flag, but the server-side gate remains the authority.

Version compatibility across the assembled contract is closed for the governed triple and all four
families.
