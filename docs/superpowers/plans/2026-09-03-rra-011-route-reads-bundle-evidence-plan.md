# RRA-011 — the citation route reads the bundle's evidence

**Authority:** active `RRA-011` (`:169-170`: a catalog route *"MUST read the projection the report
surfaces already render from, never assemble a second one from the bundle directly"*). **Scope:**
`report_api.py`'s citation-evidence route and its tests. **Preconditions met:** `RRA-013`'s supply
(`#355`) put one evidence record per citation on the bundle and into the audit context under
`evidence`, so the projection the surfaces render from now *exists* for this route to read.

**Status:** bounded plan. Its RED tests land with it (`tests/test_rra011_route_reads_bundle_evidence.py`).
This slice reopens no roadmap program: `T1` stays `MERGED`, and this is the follow-on `RRA-013`'s
Scope note 2 named — a duplicate projection that `RRA-011` already forbade, now removable.

---

## Three checks against the tree, run before this plan was written

### 1. The route assembles a second projection today, and the spec already says it may not

`_evidence_response` (`report_api.py:985`) binds `build_context(...)["audit"]` — the test
`test_the_evidence_route_reads_the_shared_projection_and_no_other_key` proves it reads no other
context key — and then calls `_cited_figure(package, figures[0], language)` (`:1016`), which
resolves the fact through `_stored_fact` (`:822`) and re-derives definition, version, precision and
inputs on its own. That was the only way before `RRA-013`; it is now the second projection
`RRA-011`:169-170 refuses, byte-for-byte equal to `audit["evidence"][citation_id]`.

### 2. The audit entry carries everything `_cited_figure` produced except the business name

`CitedEvidence.as_entry` (`bundle.py`) yields `citation_id`, `metric`, `unit_kind`,
`formula_version`, `precision`, `inputs`, `definition`. `_cited_figure` additionally yields `name`
via `business_metric_name(metric, language)`, which is `RRA-009`'s and stays in the route. Nothing
else differs; the RED test asserts the route's response equals the entry field by field, for a
stored and a derived citation.

### 3. Coverage stays a package read

`_package_evidence(package)` reads coverage, filters and reconciliation from the package, which
`RRA-011` separately requires. `RRA-013` also put coverage on the identity and in
`audit["coverage"]`; the route keeps reading the package for its package-scope block, because the
route's response includes filters and reconciliation the bundle does not carry. Unchanged here.

---

## What is being built

- `_evidence_response` reads `audit["evidence"][citation_id]` for the per-figure block and
  `business_metric_name` for `name`. **`_cited_figure`, `_stored_fact` and `_by_citation` are
  deleted.** The response model does not change; what the route serves does not change (`RRA-013`
  excludes that, and this slice is under `RRA-011`, which governs the route and permits removing a
  duplicate).
- `test_a_derived_figure_omits_what_no_record_states_rather_than_recomputing` and
  `test_every_governed_record_shape_answers_its_evidence_link` keep passing unchanged: they assert the
  response, not the helper.

## RED tests — the deliverable

`tests/test_rra011_route_reads_bundle_evidence.py`, strict-xfail:

1. `test_the_route_answers_from_the_bundle_evidence_entry[stored, series, derived]` — response
   fields equal `audit["evidence"][citation]`'s, per record shape.
2. `test_the_second_projection_is_gone` — `report_api` has no `_cited_figure`, `_stored_fact`, or
   `_by_citation`. A retired helper that survives is a helper someone will call.
3. `test_the_route_still_reads_only_the_audit_key` — not RED; the existing spy discipline restated
   on this file's fixture so a rewrite that reaches for another context key fails here too.

## Out of scope, and why

- Any change to the response shape or to what any catalog route serves.
- The four registry routes, the quality route.
- `bundle.py`, `html.py` — `RRA-013`'s, already merged.
