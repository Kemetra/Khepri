# RRA-013 — the catalog evidence supply

**Authority:** active `RRA-013` (`5170145`, `#353`). **Scope:** the `U1-04` supply slice only — the
bundle carries the evidence, the audit context carries it to the templates, the print surface says
it wants the drawer open. **Not in this plan:** placing the drawer (`RRA-012`), the citation route's
adoption of the bundle's evidence (`RRA-011`).

**Status:** bounded plan. Its RED tests land with it (`tests/test_rra013_evidence_supply.py`), which
is what §15 requires before `U1`'s row moves to `READY_FOR_IMPLEMENTATION`.

---

## Three checks against the tree, run before this plan was written

### 1. Every figure's citation resolves to exactly one of three shapes, and the bundle already knows which

`_figures(package)` (`bundle.py:1805`) builds stored figures from `package.facts`, `package.series`,
and `package.comparisons`; `_analysed(package)` (`bundle.py:1617`) builds derived figures per
`_FAMILIES` section, and `_curve` adds the concentration curve under `SECTION_CONCENTRATION`. So for a
distinct `citation_id` among `bundle.figures`:

| Citation resolves to | `precision` | `inputs` | `formula_version` |
|---|---|---|---|
| a `Fact` (`facts.py:249`) | the record's | the record's | the record's |
| a `FactSeries` / `FactComparison` (`:284`, `:310`) | the record's | `None` — no such field | the record's |
| no retained record (derived, incl. the curve) | `None` | `None` | `_FAMILIES[figure.section].version()` |

The third column is where `RRA-013` FR-102 bites: `package.formula_version` is `rra004.formula.v2`
and a comparison figure's is `rra008.comparison.v2` (`comparison.py:135`). A RED test asserts the
family constant, not the package's.

### 2. Coverage is two package fields and one identity method

`FactPackage.coverage_manifest_identity: str | None` and `coverage_signatures:
tuple[CoverageSignature, ...]` (`facts.py:405-407`); `CoverageSignature.identity` is what
`_package_evidence` (`report_api.py:1082`) already serves. `BundleIdentity` (`bundle.py:541`) carries
neither. **Both enter `BundleIdentity`** as `coverage_manifest_identity` and `coverage_signatures`
(the identity strings), and `as_document()` gains both keys — which is why `BUNDLE_VERSION` moves
`v7` → `v8`. The pin test at `test_rra006_bundle_sections.py:677` gains its `v8` paragraph in the
implementation PR, in the same voice as `v6` and `v7`.

`FactPackage` is a frozen dataclass, so `dataclasses.replace(package, coverage_manifest_identity=…)`
gives a RED test two packages identical but for coverage without touching any figure.

### 3. `evidence_open` needs a default, or every template guards it

`StrictUndefined` (`html.py:374`) fails a template that reads a key the context lacks. FR-107 says the
web surface "MUST NOT set it"; read literally, the placement template would need
`{% if evidence_open is defined and evidence_open %}` on every use. **Resolution: `build_context`
carries `evidence_open: False`, and `pdf.py:219`'s `_context` overrides it to `True`** beside
`print_stylesheet_name`, the key it already adds. "Set" in FR-107 means *set true*; the web contexts
carry the key and it is false, and a RED test asserts exactly that on both surfaces.

---

## What is being built

**`bundle.py`**

- `CitedEvidence` — frozen, slotted: `citation_id`, `metric`, `unit_kind`, `formula_version`,
  `precision: int | None`, `inputs: tuple[str, ...] | None`. No coverage field (FR-104).
- `ReportBundle.evidence: tuple[CitedEvidence, ...] = ()` — a default, so the tests that build a
  `ReportBundle` by hand keep constructing. Assembled in `ReportBundle.of` from `figures`, one entry per
  distinct citation in figure order, by the table in check 1. **Excluded from `as_document()`.**
- `BundleIdentity.coverage_manifest_identity` and `.coverage_signatures`, filled by
  `BundleIdentity.of(package)`, **included in `as_document()`**. `BUNDLE_VERSION = "rra006.bundle.v8"`.

**`html.py`** — `_audit_region` gains two keys. `evidence`: `{citation_id: {…record fields…,
"definition": metric_description(metric, language)}}`. `coverage`: `{"manifest_identity": …,
"signatures": [...]}` once. `build_context` gains `evidence_open: False`. **Scope (b) — binding
`METRIC_DESCRIPTIONS` into `_CHROME` — is not exercised**: the projection already carries the resolved
definition, and a chrome table no template reads is the defined-but-never-attached defect this
repository has met before. Recorded here so a reviewer does not read its absence as an omission.

**`pdf.py`** — `_context` sets `context["evidence_open"] = True`.

**Provenance note.** `_provenance` stringifies every identity field, so the two new identity fields
appear in the audit provenance table as strings — the signatures as the string form of a list. Tier A,
correct, and unlovely; the drawer's `coverage` key is the reader's channel, and this plan does not
touch `_provenance`.

## RED tests — the deliverable

`tests/test_rra013_evidence_supply.py`, strict-xfail, driven by a package built under the published
triple so the comparison section publishes and all three record shapes are present.

1. `test_every_cited_figure_has_exactly_one_evidence_record` — FR-102, the extent assertion.
2. `test_a_retained_fact_supplies_its_precision_inputs_and_version` — FR-102 row 1.
3. `test_a_retained_series_has_no_inputs_and_its_own_version` — FR-102 row 2.
4. `test_a_derived_figure_carries_its_family_version_and_absent_records` — FR-102 row 3; asserts
   `comparison.COMPARISON_FORMULA_VERSION` and that it differs from `package.formula_version`.
5. `test_no_evidence_value_is_a_figure_value` — FR-103/FR-106.
6. `test_coverage_lives_in_the_identity_once_and_on_no_record` — FR-104/FR-105.
7. `test_a_coverage_only_difference_changes_the_bundle_id` — FR-105.
8. `test_the_bundle_version_advanced_with_the_identity_shape` — FR-105: `v8`, and `as_document()`
   carries both coverage keys.
9. `test_the_audit_context_carries_evidence_and_coverage_in_both_languages` — FR-106, with Arabic
   definition text in the Arabic context.
10. `test_the_business_context_carries_neither_key` — FR-106's tier boundary.
11. `test_evidence_carries_no_value_and_no_internal_field` — FR-106.
12. `test_the_print_context_opens_the_drawer_and_the_web_does_not` — FR-107.

Plus one non-RED guard: `test_the_renderer_contract_and_pipeline_call_are_unchanged` (FR-108) reads
`MaterializedRenderer.render_materialized`'s signature and `pipeline.py`'s call rather than asserting a
constant.

## Sequence

1. Land this plan and its RED tests. `U1`'s §16 row moves to `READY_FOR_IMPLEMENTATION`.
2. Implement per "What is being built"; remove the markers; add the `v8` paragraph to the pin test.
3. `RRA-012` placement slice: the drawer beside each evidence figure, `coverage` passed as its own
   argument, `open=evidence_open`, and the placement guard deleted.
4. `RRA-011` slice: the citation route reads `bundle.evidence`; `_cited_figure`/`_stored_fact` retire.

## Out of scope, and why

- Template, stylesheet, or macro changes — `RRA-012`'s.
- `report_api.py` — `RRA-011`'s.
- The renderer contract, `pipeline.py`, `excel.py`, the wirings — FR-108 forbids it.
- `_provenance`'s rendering of the new identity fields — a presentation question for `RRA-012`.
