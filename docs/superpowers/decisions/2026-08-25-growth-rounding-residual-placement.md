# Growth rounding-residual placement

**Status:** **Confirmed by the owner on 2026-08-25 and formalized in `RRA-004`.** The residual is
growth-family evidence under `rra008.growth.v2`; `rra004.package.v3` is not widened and contains
no residual field. This unblocks `V-package` and `V-growth`. The earlier interpretive ambiguity is
preserved below as historical context; the current specification now states the placement
directly.
**Mission:** `docs/superpowers/plans/2026-08-24-deterministic-retail-calculation-mission.md`, Task 1.
**Governing text:** `RRA-004` "Fact-package provenance" and "Stable contract and versions";
`RRA-008` "Growth decomposition".
**Base:** `main` at `b19f365`.

## Historical question the plan left open

Before the owner ruling was formalized, the mission plan recorded the residual as "the one piece
no task on this map can write", because the then-current `RRA-004` prose listed growth
rounding-residual evidence among package provenance while the runtime derives growth in the
bundle, after the package is persisted. Task 1 required that historical ambiguity to be settled
before `V-package` was drafted. It is now settled and does not block a CAL1 publication commit.

## What the code actually establishes

Four facts, each read from `main` at `b19f365` rather than assumed:

1. **`bundle._FAMILIES` is the only call site for `growth.derive`.** Searching `src/` for
   `growth.derive` outside `bundle.py` returns nothing. The same holds for `comparison.derive`,
   `basket.derive`, and `concentration.derive`. No family derives inside the package builder.
2. **The package builds ten metrics, none of them a family fact.** `facts.py` defines
   `revenue`, `units`, `transactions`, `average_order_value`, `average_selling_price`, `cost`,
   `gross_profit`, `gross_margin`, `discount`, `returns`. `growth_price_effect` is not among them
   and is not reachable from `build_fact_package`.
3. **The package digest covers `as_document()`.** `FactPackage.digest` is
   `sha256(canonical_json(self.as_document()))`. Any field added to that document changes the
   package identity for every package, including those with no growth at all.
4. **`rebuild_fact_package` enumerates fields and refuses surprises**, and `package_source`
   raises `PackageCorrupted` when the rebuilt digest differs from the stored one. A residual
   written into the document after persistence would fail that check by construction.

Together these close the question: the residual **cannot** be a package-document field, because
the number does not exist when the document is digested and persisted.

## Options considered

- **(a) Move growth derivation into `build_fact_package`.** Rejected. It changes what
  `rra004.package.v3` *is*, pulls one of four families out of `bundle._FAMILIES` while the other
  three stay, and re-digests every package for a field most packages cannot populate. `RRA-004`
  names the successor's authorized scope and moving a family into the builder is not in it.
- **(b) Carry the residual as growth-family audit evidence under `rra008.growth.v2`.** Chosen.
- **(c) Amend `RRA-004` to relocate the clause.** Not chosen in the original ruling; the later
  governance reconciliation formalizes the ruling directly without changing its runtime outcome.

## Decision

**The residual is growth-family evidence published under `rra008.growth.v2`, carried on the
growth facts themselves, and surfaced through the bundle's audit representation. No field is
added to the persisted package document, and `rra004.package.v3` is not widened to hold one.**

`RRA-004` now formalizes the ruling directly: package v3 authorizes package population, basis,
coverage, and currency evidence only; growth-family audit evidence is not a persisted
`FactPackage` field and does not widen that document. The residual therefore belongs wholly to
`rra008.growth.v2`. This specification reconciliation removes the former need to interpret "when
applicable" as a package-shape rule.

## Consequences for the slice map

- **`V-package` does not include Task 5.** Historical mission text said `rra004.package.v3`
  spanned Tasks 3, 4 and 5 because Task 5 contributed the residual. It does not. `V-package` is
  Task 3's structural fields plus Task 4's coverage
  signatures, daily bases and projections. Task 5 contributes nothing to it.
- **`V-growth` owns the residual whole**, alongside the rest of `rra008.growth.v2`, satisfying
  the same-slice rule for its reason code, audit representation, and bilingual wording.
- **`RRA-008`'s reconciliation-failure bound is a growth-family refusal**, raised where the
  decomposition is computed, not a package-build refusal.

## What `V-growth` must therefore ship

Per `RRA-008`:

```
published revenue delta = round(R_c - R_p)
published volume effect = round(unrounded volume effect)
published price effect  = published revenue delta - published volume effect
rounding residual       = published price effect - round(unrounded price effect)
```

- the residual recorded in audit evidence and assigned to price;
- refusal when the residual magnitude exceeds one unit of the published last place;
- the `rra008.growth.v2` pin;
- the realized price/mix business label and its bilingual caveat.

Note this **replaces** today's behaviour at `growth.py:238`, which rounds both effects
independently and refuses the whole section with `decomposition_not_additive` when they disagree.
Measured on `main` at `b19f365` through the real `derive()` pipeline, 74 of 2304 ordinary
four-day amount/unit fixtures hit that refusal, always off by exactly one unit of the last place.
