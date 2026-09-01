# KHEPRI-DEC-032: A catalog route may construct a `ReportBundle`

## Context

`#345` (`d355d12`) merged to `main` as an open question and did not answer it. It asks whether
`RRA-011`:204's Exclusion —

> *"Any calculation, re-derivation, re-rounding, or re-formatting of a published figure. A catalog
> surface repeats a value; it never recomputes one."*

— prohibits a catalog route from constructing a `ReportBundle`.

**The mechanism is measured, not assumed.** Two of `#343`'s six catalog routes are affected. The four
registry reads (`metrics`, `populations`, `reasons`, `caveats`) construct no bundle and make zero
derivation calls. The two package-scoped reads — `/catalog/quality/{language}` and
`/catalog/citations/{citation_id}/evidence/{language}` — each make two, because `_session_bundle`
calls `ReportBundle.of(package)`, whose constructor calls `family.derive(package)` (`bundle.py:1638`)
and `concentration.curve_series(package)` (`bundle.py:1728`) as it assembles.

`#345` also replaced the guard that could not see this: a string search over `report_api.py` for
`family.derive` and `curve_series` passed against exactly the behaviour it was written to prevent,
because the call had moved into a collaborator. Its replacement counts the calls. That replacement is
not in question here and stands under either reading.

**This question gates `M2`.** `KHEPRI-DEC-031` §7 requires all four conditions. Condition 1 turns on
this reading. Condition 4 was re-measured on `d355d12` after `#343` changed `report_api.py` and both
wiring modules, and holds — see
`docs/superpowers/plans/2026-09-01-m2-condition-4-delivery-rerun-evidence.md`.

**Authorship.** The reading below was recommended by the implementing agent at the owner's explicit
direction, after the agent twice declined to choose and the owner twice reaffirmed. It is recorded as
a recommendation carrying its own counter-argument, not as an owner-authored ruling. `AGENTS.md`
makes a merge the approval, so merging this document is the decision; until then it stays on its
branch, per `governance/templates/decision.md`.

## Decision

**`RRA-011`:204's Exclusion does not prohibit a catalog route from constructing a `ReportBundle`.**
It prohibits a catalog surface from *publishing a figure it computed itself*. Reading B, in `#345`'s
terms.

Three things in `RRA-011` support this, and they are stated in the order of their weight.

**1. The Requirements presuppose the route holds a bundle.** `RRA-011`:169-170 requires a catalog
route to *"read the projection the report surfaces already render from, never assemble a second one
**from the bundle** directly."* A prohibition on assembling a *second* projection from a bundle
presupposes a route that has one. The specification's own Requirements assume what the Exclusion is
being read to forbid, and a reading that puts a document's Requirements in conflict with its
Exclusions should be preferred only when no consistent reading exists.

**2. The Exclusion's second sentence bounds its first.** *"A catalog surface repeats a value; it
never recomputes one."* The harm named is a catalog surface publishing a recomputed figure. Measured
on `d355d12` against live responses in both languages: no `value` field, no rendered text, and no
figure reaches any catalog response. `test_no_catalog_response_carries_a_figure_value` holds this
property in the suite. The harm the clause describes cannot occur on these routes.

**3. Under the contrary reading the specification is presently unsatisfiable.** The projection
`RRA-011`:169-170 mandates is `_audit_region`, whose only caller is `build_context(bundle, language,
cells)` (`html.py:591`). No store persists a `ReportBundle`: it appears in no persistence module, and
`ReportBundle.of` is called in exactly three places (`pipeline.py:352`, `benchmark_trial.py:127`,
`report_api.py:761`). There is no path to the mandated projection that does not take a bundle.

**The counter-argument, stated rather than omitted.** On a plain reading, "re-derivation" covers
executing the analysis families, whether or not the result is published. If the Exclusion exists to
protect *determinism* — that a governed figure is computed once, in one place, under one version
triple — rather than to protect *display*, then the contrary reading is the better one and these two
routes are outside the specification. That reading is coherent. It is not adopted because point 1
above makes it contradict `RRA-011`'s own Requirements, and because the third point shows it implies
work against the storage architecture rather than a defect in the merged routes.

**The implementing agent recommended this reading having also produced the work it preserves.** That
conflict is recorded here so a later reader weighs the argument on its own terms.

## Consequences

- **`#343`'s six catalog routes are admissible as merged.** The four registry routes were never in
  question; the two package-scoped routes are admitted by this reading.
- **`KHEPRI-DEC-031` §7 condition 1 holds.** With condition 4 re-measured on `d355d12`, and
  conditions 2 and 3 unchanged, all four hold and `M2` is reachable in its local-only form.
- **No work is implied against the storage architecture.** Retaining a `ReportBundle` or its
  projection is not required by this reading. Should a later decision adopt the contrary reading,
  that retention becomes an `RRA-004`/`RRA-006` change and these two routes change with it.
- **This decision authorizes no new surface, figure, or telemetry.** It reads an existing Exclusion
  against merged routes and nothing more. `T1-06` lineage and `T1-07` telemetry remain excluded from
  `RRA-011` and blocked as `KHEPRI-DEC-031` §5 records.
- **`RRA-011` is not amended.** This is a reading of the text as merged. If the owner prefers the
  contrary reading, this document is retired rather than the specification changed.

## Evidence

- `#345` (`d355d12`): the question, the measured per-route call counts, and the replaced guard.
- `#343` (`bc96a65`): the six catalog routes and the `T1-08` parity tests.
- `RRA-011`:169-170 (Requirements) and `RRA-011`:204 (Exclusions): the two clauses in tension.
- `bundle.py:1638`, `bundle.py:1728`: the two derivation call sites inside `ReportBundle.of`.
- `html.py:591`: the only caller of the mandated `_audit_region` projection.
- `docs/superpowers/plans/2026-09-01-m2-condition-4-delivery-rerun-evidence.md`: condition 4
  re-measured on `d355d12`, two runs, zero failures, both languages, figures equal to the
  independently derived oracle.
- `KHEPRI-DEC-031` §7: the four conditions this reading completes.
