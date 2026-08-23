# Deterministic Retail Calculation Correction — Design

Date: 2026-08-23

Authority: none. This document proposes amendments to active RRA specifications. It becomes neither
governing nor implementation authority by existing on a branch. Under the Khepri Constitution,
Ahmed Shaaban approves the proposal only by merging the corresponding governed changes to `main`.

## Outcome

Khepri states deterministic retail calculations only when the source proves one governed business
meaning and one compatible population. Ambiguous gross/net, VAT, return, cost, currency, void,
dimension, unit, or calendar coverage semantics refuse the affected result instead of producing a
plausible number.

The work proceeds through five reviewable phases and ends at a calculation validation gate:

1. governed semantics;
2. independently derived RED tests;
3. core population and window corrections;
4. policy-dependent formula corrections;
5. refusal, presentation, mutation, and pharmacy-fixture hardening.

No phase introduces forecasting, customer formulas, new analytical families, or generic metrics.

## Why the correction is architectural

The current arithmetic is exact on complete clean rows, but its meaning is partly inferred from
column names and its derived families do not all use compatible populations. Correcting that
changes the contracts shared by profiling, mapping, admissibility, fact-package shape, derived
facts, caveats, report surfaces, and formula identities. Treating the findings as four local
function fixes would leave the same ambiguity at a different layer.

The design therefore separates three responsibilities:

- **semantic admission** proves what a source value means;
- **population eligibility** proves which rows and transactions a formula may combine;
- **calculation** applies one pinned formula to an admitted population.

## Chosen approach

### Strict normalized-event contract

Khepri accepts normalized posted retail events for governed monetary calculations. It does not
guess whether a generic `sales`, `cost`, `discount`, or `return` column is gross, net, per-unit,
VAT-inclusive, repeated per invoice, or already reflected elsewhere.

This is preferred over two rejected alternatives:

- **Source-declared flexible formulas** would make two packages carrying the same metric name mean
  different things and would move customer-authored semantics into the deterministic engine.
- **Header/value heuristics** would preserve compatibility by guessing, contradicting the
  Constitution's fail-closed rule and the existing exclusion of opaque automatic guessing.

The compatibility cost is deliberate: inputs that cannot prove the normalized contract lose only
the affected result. A count or dimension survives only when its own event-kind, status, identity,
and population requirements remain independently proven.

## Governed source semantics

### Event population

Every row used by a governed calculation is one normalized retail event with:

- a stable source event or line identifier that is unique within the package;
- a transaction date;
- an event kind of `sale`, `return`, or `coverage`;
- a transaction status proving `posted` or a status that excludes the row as `void` or `cancelled`;
- a single ISO 4217 currency for every monetary measure in the package;
- additive row-level measures rather than averages, rates, unit costs, cumulative values, plans,
  forecasts, or repeated invoice totals.

`coverage` rows carry no business measures. They prove a store/calendar-day boundary and are never
counted as revenue, units, transactions, products, or rows in a published aggregate.

Repeated products and categories within one transaction are valid when their event identifiers are
distinct. A repeated event identifier, whether byte-identical or conflicting, refuses every
additive or distinct-transaction result that could include it; Khepri does not guess whether two
identical-looking rows are legitimate lines or a duplicated invoice extract.

An unknown or missing event kind, status, or required event identifier refuses every affected
population rather than silently excluding the row. Rows that are explicitly void or cancelled are
excluded from every population.

### Revenue and VAT

`revenue` means signed, VAT-exclusive, net realized sales at event posting date:

- sale revenue is non-negative and is after all line, invoice, promotion, loyalty, and markdown
  discounts;
- return revenue is non-positive and is recognized on the return posting date;
- VAT, sales tax, duties, tips, shipping, fees, commissions, and surcharges are excluded;
- void and cancelled events contribute nothing;
- Khepri performs no currency conversion.

A directly mapped revenue column must explicitly declare that basis. Generic `revenue`, `sales`,
`amount`, `total`, `grosssales`, VAT-inclusive, or tax-inclusive labels are ambiguous and cannot
become governed revenue by themselves.

Khepri does not reconstruct net revenue from gross sales, tax, discount, and return components in
the core correction slices. A later policy-dependent slice may admit a second normalized input
shape only if it produces the identical signed, VAT-exclusive row measure and proves that the
components are additive and non-overlapping.

### Discounts

`discount` is a positive additive informational amount attached to sale events. It includes line,
allocated invoice, promotion, loyalty, and markdown discounts only when the source has already
prevented overlap and allocated any invoice-level amount exactly once.

Discount never changes governed revenue because admitted revenue is already net. A bare discount,
rate, percentage, repeated invoice total, or overlapping component set refuses the discount metric.
Every posted sale row must carry a non-negative discount amount, including an explicit zero, or the
package must carry an admitted declaration that discounts are not captured. The former permits a
complete discount total; the latter refuses discounts without refusing independently proven net
revenue.

### Returns

`returns` is a positive additive informational magnitude attached to return events. The same event
carries negative revenue and negative units; the informational return amount is not subtracted a
second time.

Full and partial returns use the return posting date. Khepri does not rewrite a previously
published sales period. A return posted without an event kind, or with signs inconsistent with the
contract, refuses return-dependent results.

For each return event, return amount must equal the absolute value of its VAT-exclusive negative
revenue at admitted input precision. A mismatch refuses both the return total and the financial
revenue population because it proves incompatible semantics. If event-kind coverage proves that a
package contains no return events, returns is stated as zero; an absent event-kind mapping cannot
establish that zero.

Revenue comparisons include posted returns. Growth decomposition refuses a compared window that
contains return events: the current two-term price/volume identity has no governed interpretation
for merchandise returned in a later period at an earlier selling price.

### Cost and gross profit

`cost` means signed, extended row-level cost of goods sold, VAT-exclusive and in the package
currency:

- sale cost is non-negative;
- return cost is non-positive when inventory value is restored;
- zero cost is valid for a proven zero-cost item;
- unit cost, average cost, standard cost, list cost, and a bare ambiguous `cost` label are not
  additive COGS and are refused.

Gross profit and gross margin require complete revenue and cost coverage over the identical
financial population. They refuse when either measure is missing on any eligible row. Standalone
cost also refuses incomplete population coverage; it is not published as a partial headline total.

### Units and bonus items

`units` means signed physical merchandise movement:

- ordinary and free/bonus sale units are positive;
- return units are negative;
- fractional quantities are refused by this specification and remain a future governed extension;
- zero units on a sale or return event refuses unit-dependent results.

The headline units total is net physical movement. ASP is net realized revenue divided by signed
units over rows carrying both measures; zero denominator refuses. Free/bonus items therefore lower
the realized ASP, which is the intended commercial meaning of revenue per physical unit supplied.

Items per transaction uses only positive units from posted sale events, including free/bonus
items. Return events do not enter either its numerator or its sales-transaction denominator. Any
missing units on a sale row refuses items per transaction.

### Transactions and AOV

`transactions` counts distinct identifiers of posted sale events only. Return, void, cancelled,
and coverage events are not sales transactions.

Every sale row must carry a transaction identifier. A missing identifier refuses transactions,
AOV, basket size, and attach rate; no row count or partial identifier set substitutes for it.

AOV is net sale-event revenue divided by distinct posted sale transactions. It excludes later
return events from both numerator and denominator, because the posting-period revenue impact of a
return cannot be assigned to an order in the current contract. AOV refuses if any sale row lacks
revenue. The report-level revenue total can consequently differ from AOV numerator when the period
contains returns; the metric's evidence records its `sale` population explicitly.

### Currency

Every monetary package must prove exactly one normalized uppercase ISO 4217 code. Missing,
malformed, or mixed currency refuses all monetary facts and their derived results while count-only
facts may survive. Khepri performs no exchange-rate lookup or conversion.

## Population eligibility contract

Every fact records a population code in readable provenance; hashing it into an identity is not
sufficient. The initial governed populations are:

- `financial_posted`: posted sale and return events, excluding void, cancelled, and coverage rows;
- `sales_posted`: posted sale events only;
- `sales_complete_revenue`: `sales_posted` with complete revenue and identifiers;
- `sales_complete_units`: `sales_posted` with complete units and identifiers;
- `financial_complete_revenue_units`: financial rows carrying both revenue and units, with no
  unmatched eligible row in a compared window;
- `financial_complete_revenue_cost`: financial rows with complete revenue and extended cost;
- `dimension_complete_sales:<dimension>`: sale rows with complete transaction identifiers and a
  non-null governed dimension value on every row.

Single-input totals may exclude null cells only when the resulting metric is explicitly a partial
coverage fact. The current package has no partial-coverage headline vocabulary, so revenue, cost,
units, discounts, and returns refuse when a required admitted column has gaps. Optional columns
that are absent altogether refuse only their metric.

An admitted explicit zero is different from a missing value. An empty eligible population states
zero only when the event-kind and status mappings prove that the relevant event class is absent;
otherwise the metric refuses as unproven rather than treating missing coverage as zero.

Derived metrics never combine two whole-package facts merely because both exist. They consume one
population-certified aggregate or refuse.

## Metric population assignments

| Metric | Population |
|---|---|
| Revenue, period revenue, revenue comparison | `financial_posted` with complete revenue |
| Units | `financial_posted` with complete units |
| Transactions | `sales_posted` with complete identifiers |
| AOV | `sales_complete_revenue` |
| ASP | `financial_complete_revenue_units` |
| Cost, gross profit, gross margin | `financial_complete_revenue_cost` |
| Discounts | posted sales with complete additive discount coverage |
| Returns | posted returns with complete return magnitude coverage |
| Growth decomposition | return-free compared windows over `financial_complete_revenue_units` |
| Items per transaction | `sales_complete_units` |
| Attach rate | `dimension_complete_sales:<product|category>` |
| Concentration | complete non-null product/category values over revenue-bearing posted sales |

These assignments eliminate the current cross-headline claim that matched gross profit can be
read as total revenue minus a differently covered cost total.

## Attach eligibility

Attach rate means:

```
distinct posted sale transactions containing value
--------------------------------------------------
all distinct posted sale transactions in the same dimension-complete population
```

Multiple lines of the same product or category in one transaction count once. It is never line,
unit, revenue, or displayed-bucket share.

Every sale row must carry the governed product or category value. If any is missing, that
dimension's attach family refuses; an unknown product transaction is not silently added only to
the denominator. `other`, `unlabelled`, and `redacted` synthetic display buckets never receive an
attach rate. Display truncation cannot change any numerator or denominator, although only named
published values are shown.

Product remains preferred over category when both are admissible.

## Price/volume growth contract

Growth uses the exact aligned, return-free posted-sale population carrying complete revenue and
strictly positive units in both windows. It refuses if either window has a missing row, a return,
a non-positive unit denominator, a different coverage signature, or an unproven currency.

For current revenue `R_c`, prior revenue `R_p`, current units `U_c`, prior units `U_p`, and
`ASP = R / U` calculated without intermediate rounding:

```
volume effect = ASP_p * (U_c - U_p)
price effect  = U_c * (ASP_c - ASP_p)
revenue delta = R_c - R_p = volume effect + price effect
```

This convention assigns the entire price-volume interaction term to price. The reconciliation is
an algebraic invariant, but the allocation is a governed commercial convention rather than the
only mathematically possible decomposition. Effects round only at their published boundary and
must still reconcile at that boundary under the family formula version.

## Concentration eligibility

Concentration uses posted sale revenue over the full, non-null, admissible product or category set
before display truncation. A missing value on any revenue-bearing sale row refuses that dimension;
`None` and the synthetic `unlabelled` bucket are never ranked as products.

The curve refuses when total ranked revenue is non-positive or any ranked value has negative
revenue. Zero-revenue values remain distinct and rank last, producing a flat tail. The top decile
and quartile contain `ceil(n/10)` and `ceil(n/4)` ranked values respectively, with at least one
value. Ceiling is used because a discrete ranked set must include at least the requested fraction
of products; floor would publish an empty top decile for fewer than ten values. Shares retain four
decimal places and the ceiling convention is part of the concentration formula version.

The full curve remains authoritative. Sampling is presentation-only, must keep no more than 100
points including the final 100% point, and must carry a bilingual sampling caveat.

## Period alignment contract

### Calendar windows

The comparison window remains one period at the package's own day/month granularity.

- PoP uses the immediately preceding calendar period.
- YoY uses the same calendar period one year earlier.
- Missing exact counterparts refuse; nearest observed buckets never substitute.
- Percentage delta requires a strictly positive prior base; absolute delta survives a zero or
  negative base.

### Coverage proof

A day-count total is insufficient to align a prior period. The package retains a deterministic
coverage signature and daily subaggregates for every monthly revenue and unit bucket:

- ordered calendar-day ordinals covered;
- when store is mapped, the set of covered `(store, day ordinal)` pairs;
- daily revenue and units totals for each covered day;
- whether coverage is a contiguous prefix beginning on the first calendar day.

Coverage rows may prove a zero-sale store/day. Without a coverage row, absence of transactions is
not interpreted as zero activity.

A full monthly window requires a contiguous complete calendar signature for every admitted store.
An incomplete current month may compare days 1 through its last proven contiguous day against the
same calendar-day prefix in the prior period. Both windows must have identical store coverage. The
facts carry the aligned start/end dates and bilingual partial-window caveat.

If no store dimension is mapped, the source must explicitly declare that the package represents
one store or one already-governed aggregate scope. Otherwise period comparisons refuse because
different store participation cannot be ruled out.

A sparse, non-contiguous, count-equal, or store-mismatched signature refuses the affected
comparison. Equal counts alone never prove equal windows.

Day-granularity comparisons require exact date counterparts and complete admitted-store coverage
for each day. Leap-day YoY continues to refuse when the prior calendar has no counterpart.

Growth consumes the exact PoP window selected by comparison and may not choose its own.

## Fact-package and version contract

The corrected package must disclose, for every fact or derived series:

- formula version;
- mapping version;
- population code;
- event-kind filters;
- status filters;
- currency code for monetary facts;
- aligned calendar window when applicable;
- precision, rounding mode, inputs, caveats, fact identity, and citation identity.

The rounding mode is decimal round-half-even. Monetary precision remains the largest admitted input
scale, minimum two and maximum six; ratios remain four decimal places. Rounding occurs once at the
published fact boundary unless an intermediate published structure, such as the concentration
curve, is itself the authoritative value.

Any changed number, refusal, population, or interpretation receives a new family formula version.
Any changed serialized package shape receives a new package version. Mapping confirmation changes
receive a new mapping version. Existing packages remain immutable historical artifacts and are not
silently reinterpreted.

## Governance amendments

Phase 1 proposes coordinated amendments rather than hiding policy in code:

- `RRA-003` adds source-event identity, currency, event-kind, status, normalized revenue, extended
  cost, and coverage confirmation semantics and removes its stale draft/non-authorization sentence;
- `RRA-004` defines the normalized measures, population provenance, coverage signature, daily
  subaggregates, rounding mode, and refusal rules, and removes its stale sentence;
- `RRA-008` defines corrected population assignments, concentration eligibility, attach
  eligibility, and calendar alignment, lifts its old exclusion only for the mapping changes
  explicitly governed here, and removes its stale sentence;
- `RRA-009` remains presentation-only; later caveat/refusal additions extend its complete bilingual
  catalog without changing its calculation boundary;
- `governance/registry.yaml` remains authoritative and needs no lifecycle change unless the owner
  chooses a new superseding specification instead of in-place amendments.

The governance amendment is one proposal. Formula code begins only after the owner approves and
merges the active semantic contract, or explicitly approves an atomic branch sequence whose code
remains blocked behind the amended specification.

## Delivery phases

### Phase 1 — Governed semantics

Deliver only the specification amendments above, validation evidence, and no formula code.

### Phase 2 — Independent RED tests

Add manually calculated tests for:

- partial and sparse calendar periods;
- disjoint revenue and unit rows;
- partial sale-unit coverage;
- missing product/category values;
- cross-headline revenue/cost population mismatch.

Each test must fail against the present implementation for the intended numerical or refusal
reason. Expected values may not call production calculation helpers.

### Phase 3 — Core corrections

- **C1:** package coverage signatures and period alignment;
- **C2:** population-certified growth inputs;
- **C3:** sale-only, complete-coverage basket inputs;
- **C4:** non-null full-set concentration eligibility.

Each correction is a separate formula-versioned slice with its own RED/GREEN/reconciliation gate.

### Phase 4 — Policy-dependent corrections

- AOV complete sale population;
- complete financial cost/gross-profit population;
- attach denominator and dimension-complete refusal;
- strict normalized revenue, discount, return, currency, event-kind, status, and cost admission.

### Phase 5 — Hardening

- accurate per-result refusal reasons;
- concentration-curve sampling bound and caveat;
- metric- and population-specific bilingual caveats;
- deliberate mutation evidence for load-bearing formulas and refusals;
- clean, messy, and adversarial pharmacy golden fixtures.

## Verification and validation gate

The final gate requires all of the following:

- governance validation, Ruff, and the complete pytest suite pass in the required service
  environment;
- every governed metric has an independent clean, messy, and adversarial oracle;
- every ratio proves compatible numerator and denominator populations;
- every comparison proves exact calendar and store coverage;
- headline revenue, cost, gross profit, and margin reconcile or refuse together;
- every refusal leaves independently answerable metrics standing;
- every new or changed formula carries a new readable version and stable identity;
- every caveat/refusal has equal accepted Arabic and English wording;
- named mutants are killed for period equality, matched populations, distinct transaction sets,
  full-set concentration, and formula additivity;
- no renderer recalculates a business figure;
- CodeScene's server-side Code Health gate passes with 10.00 for every new file and no hotspot
  decline.

Only after this gate may the engine return to local staging validation for a design-partner
dataset.

## Out of scope

- Currency conversion or exchange-rate data.
- Fractional quantities.
- Forecasting, price optimization, demand planning, cohorts, retention, or new analytical
  families.
- Customer-defined formulas or per-customer metric meanings.
- Rewriting historical packages in place.
- Crossed two-dimension business breakdowns.
- Seshat as a deterministic-calculation oracle.

## Compatibility consequences

The strict contract is intentionally breaking for ambiguous exports and existing fixtures whose
headers merely say `revenue`, `cost`, or omit currency/status/event kind. They will refuse affected
facts until represented as normalized events. This is preferable to preserving green tests that
certify an unknown business meaning.

The implementation plan must stage fixture migration after the RED proofs and must never weaken a
semantic guard merely to preserve old fixture output. Historical serialized packages remain valid
under their recorded versions; corrected packages receive new identifiers.
