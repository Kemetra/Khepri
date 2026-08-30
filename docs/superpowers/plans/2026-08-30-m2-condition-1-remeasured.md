# M2 §7 condition 1, re-measured — and the four conditions now hold

**Slice:** none. This measures, it does not build.

**Run date:** 2026-08-30. **Tree:** `main` at `bc96a65`, which is `#343` merged.

`#342`'s ledger (`2026-08-29-m2-local-only-journey-evidence.md`) recorded three of `KHEPRI-DEC-031`
§7's four conditions holding and condition 1 failing, and named precisely what was missing:

> *"What remains is **two** read routes in `report_api.py`, both session-scoped like their siblings,
> because `RRA-011`:53-54 names three and only the evidence route is merged."*

`#343` merged both. This re-measures condition 1 on the tree where they exist, and re-runs
condition 4 against the surfaces that did not exist when it was last recorded.

**This document is evidence, not a declaration**, on the same footing `#342` set: producing the
evidence is one act and accepting it is another. §7 is an owner judgement and `AGENTS.md` makes the
merge of this assessment the approval.

---

## Condition 1 — catalog merged and `T1-08`'s proofs pass — **now holds**

> *"`RRA-011`'s catalog and evidence surfaces are merged to `main` and pass `T1-08`'s parity,
> fail-closed, and no-duplicate-truth tests."*

### The consumer gap is closed

`#342` verified the gap two ways, because an attribute-access grep alone would miss a bare
from-import. Both are re-run here, and both now find the consumer:

```
$ grep -rn "definitions\." src/khepri/ | grep -v src/khepri/rra/definitions.py | grep -v infra
src/khepri/rra/report_api.py:583:    (definitions.UnknownCode, 404, None),
src/khepri/rra/report_api.py:852:    definition = _defined(lambda: definitions.define_metric(code))
src/khepri/rra/report_api.py:857:        description=definitions.describe_metric(code, language),
...
$ grep -rn "definitions import\|import definitions" src/khepri/ | grep -v infra
src/khepri/rra/report_api.py:45:from khepri.rra import definitions
```

All three route groups `RRA-011`:53-54 names now exist, against the table `#342` left open:

| Route | Consumer it gives | `#342` state | Now |
|---|---|---|---|
| the registry | `define_metric`, `describe_metric`, `not_meant`, `synonyms` | absent | **merged** — four routes under `/api/v1/beta/catalog/` |
| the package summary | `summarize` | absent | **merged** — `/catalog/quality/{language}` |
| a fact's evidence | the rendered projection | merged | merged — `/catalog/citations/{citation_id}/evidence/{language}` |

`definitions.summarize` is called at `report_api.py:900`; `definitions.availability` remains without a
production consumer and is not required by condition 1, which names the catalog and evidence
surfaces.

### The gates on `bc96a65`

| Gate | Result |
|---|---|
| `uv run khepri-gov validate` | **Governance validation passed.** |
| `uv run ruff check .` | **All checks passed!** |
| `uv run pytest` | **3,910 passed**, 72 skipped, 1 xfailed |

`T1-08`'s three properties live in `tests/test_rra011_parity.py` (31 tests) and
`tests/test_rra011_evidence_parity.py` (28 tests), both in that suite. The second is new at `#343`
and carries the evidence half: one-projection, fail-closed at the HTTP boundary, tier absence,
absence-not-emptiness, session scoping, and no per-figure population.

**Skips are unchanged at 72** across `#342`'s measurement (3,797) and this one (3,910). A rise would
mean a test stopped running rather than started passing, which is the failure this number exists to
catch.

---

## Condition 4 — re-run against the surfaces that now exist

> *"The full journey passes end to end on the local stack against the merged catalog surfaces, in
> both languages."*

`#342` recorded this as holding, and its journey was correct — but it ran on `46b2d56`, where the
catalog had no reachable surface. "Against the merged catalog surfaces" is only fully answered on a
tree where those surfaces exist, so the journey was repeated on `bc96a65`.

Driven inside `khepri-staging-web` against the merged `docker-compose.staging.yml` stack — the built
image, TLS PostgreSQL and MinIO, the container's own interpreter and trust store. `CAL1-14`'s method
and `#342`'s. The oracle's `PHARMACY_ROWS` and `TEST_CONTRACT` were copied in at run time, so the
expectation is external to the product and the product is unmodified.

### Journey

| Stage | Evidence |
|---|---|
| Session | invitation issued, redeemed `201`, consent `204` |
| Upload | `201`, **623 bytes**, `text/csv` |
| Admission | profile `201`, `row_count: 7`, `rra003.profile.v2` / `rra003.mapping.v3` |
| Facts | `201` on **`rra003.mapping.v3` / `rra004.package.v3` / `rra004.formula.v2`**, `sale_units_total: 13`, `monetary_precision: 2` |

### The catalog surfaces, both languages

| Surface | Evidence |
|---|---|
| `catalog/quality/en` | `200`, **3,598 bytes**, `answered: 3`, `refused: 2` |
| `catalog/quality/ar` | `200`, **4,692 bytes**, same counts |
| `catalog/metrics/revenue/en` | `200`, name **`Revenue`**, no Arabic script |
| `catalog/metrics/revenue/ar` | `200`, name **`الإيرادات`**, Arabic present |
| `catalog/populations/sales_complete_revenue` | `200` |
| `catalog/reasons/zero_denominator/result/en` | `200` |
| `catalog/caveats/returns_not_netted/ar` | `200`, Arabic present |
| `catalog/metrics/revenues/en` (unknown code) | **`404`** — fails closed |
| `catalog/citations/{id}/evidence/en` | **30 of 30 displayed citations resolve** |
| `catalog/citations/{id}/evidence/ar` | `200`, Arabic present, reconciliation present, **no `value` field** |

**The two quality bodies differ by 1,094 bytes at identical counts.** That is the bilingual property
stated as a measurement rather than a claim: before `#343`'s review round the route accepted a
language it never used and both bodies were byte-identical, which made the path segment a promise the
response did not keep.

**30 of 30, not 22.** The `PHARMACY_ROWS` fixture publishes more figures than the unit fixture, so
this exercised the derived-analysis path — comparison, growth, basket, concentration — more broadly
than the test suite does. Every one resolved without the module recomputing anything, which is
`RRA-011`'s Exclusion holding under a live load.

`no value field` is the tier boundary confirmed outside the test harness: the catalog says what a
figure is made of and never what it measured.

---

## Conditions 2 and 3 — unchanged by `#343`

**Condition 2** (`CAL1` complete, two carried `P2`s non-blocking): `#343` touched neither
`rendering/excel.py`'s container assembly nor `RRA-003` admission, so the two carried findings —
`CAVEAT_CURRENCY_NOT_DECLARED` unreachable, and the Excel container not byte-identical across
regenerations — are as `#342` recorded them. The journey above re-derived the governed version triple
on the same 623-byte input, which is positive evidence the calculation contract still holds after
`#343`.

**Condition 3** (nothing widened `RRA-010` or `RCA-002`): `#343` added no file under
`src/khepri/rra/journey/` and no member of the shell's closed surface set. `RRA-011`'s Scope excludes
both by name and the slice stayed inside it; the catalog routes sit in `report_api.py`, which
`RRA-011`:53 names. `tests/test_r801_shell_tokens.py` passes in the suite above.

---

## Standing

| Condition | `#342` | Now |
|---|---|---|
| 1 — catalog merged, `T1-08` proofs pass | Does not hold | **Holds** |
| 2 — `CAL1` complete, two `P2`s non-blocking | Unchanged | **Holds** |
| 3 — no widening of `RRA-010` / `RCA-002` | Holds | **Holds** |
| 4 — full journey, both languages | Holds | **Holds**, now against surfaces that exist |

**All four §7 conditions hold on `bc96a65`.** `KHEPRI-DEC-031` §6 adds a fifth requirement — closure
of `CAL1-11`'s finding `F5` under `RRA-009` — which was met at `#334`: all five wording tables `F5`
named carry import-time completeness guards (`_assert_label_wording_complete` `wording.py:95`,
`_assert_derived_metric_wording_complete` `:304`, `_assert_kind_qualifiers_complete` `:390`,
`_assert_chart_descriptions_complete` `:1171`, `SECTION_HEADINGS` `:1150`, `bundle._DISCLOSURE`
`bundle.py:500`), plus a sixth found while closing them.

### What this does not say

`M2`'s two unmet clauses are **unmet, not met** — recorded rather than waived, which is the whole
point of `KHEPRI-DEC-031`:

- **Activation telemetry** is blocked by active `KHEPRI-DEC-015`, and needs an owner-authored
  amendment rather than an implementation slice. `R8-08` and `T1-07` wait on the same amendment.
- **The hosted environment** is deferred; `KHEPRI-DEC-030`'s provisioning authority stays active and
  unexercised.

So this records `M2` reached **in its local-only form**: an internal rehearsal, no external
participant. §2's bound is absolute — no one outside the project may receive access, a report, an
artifact, or a link — and nothing here authorizes external alpha, which needs both the hosted
environment and that amendment.

**The catalog is reachable but unrendered.** No journey or shell surface reads it; the UX blueprint
records that as `IMPLEMENTATION-BLOCKED`, and rendering it is an `RRA-010` slice. `R8-10` is the
slice after that, not a defect here.

### Carried findings, unchanged and non-blocking

| # | Finding | Severity |
|---|---|---|
| `CAL1-12` F1 | `CAVEAT_CURRENCY_NOT_DECLARED` unreachable | P2 |
| `CAL1-14` F3 | Excel container not byte-identical across regenerations | P2 |
| `#343` F6 | No governed record ties a delivered report to its package | P2 |
| `#343` F7 | Derived figures: `precision`/`inputs` unobtainable without re-derivation | P2 |

None publishes a wrong figure. F6 and F7 are `RRA-004`/`RRA-006`/`RRA-008` changes, outside
`RRA-011`'s authority to make.

Whether this assessment is accepted is the owner's call, and merging it is that decision.
