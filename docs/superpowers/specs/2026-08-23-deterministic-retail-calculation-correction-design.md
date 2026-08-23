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

- a transaction date;
- an event kind of `sale` or `return`;
- a transaction status proving `posted` or a status that excludes the row as `void` or `cancelled`;
- a single ISO 4217 currency for every monetary measure in the package;
- additive row-level measures rather than averages, rates, unit costs, cumulative values, plans,
  forecasts, or repeated invoice totals.

Event kind, status, and currency may be supplied by a mapped source column or by an explicit
package-level declaration tied to a recorded source contract. A declaration may state that every
row is a sale only when the extract contract excludes returns; that every row is posted only when
the contract excludes void and cancelled transactions; and that every monetary value uses one
named currency. Khepri never derives those declarations from a generic header or observed values.

Event identity is proven in one of two ways:

- a stable source event or line key, including an admitted composite key, is unique within the
  package; or
- the source contract explicitly confirms unique line-grain rows and the package contains no
  repeated canonical row signature across all admitted identity, dimension, and measure fields.

A repeated event key, whether byte-identical or conflicting, refuses every additive or
distinct-transaction result that could include it. Without an event key, a repeated canonical row
signature also refuses those results because Khepri cannot distinguish a legitimate repeated line
from a duplicated extract. Repeated products and categories within one transaction remain valid
when their event identities are distinct.

An unknown or missing event kind, status, or required identity proof refuses every affected
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
this calculation-validation program. A second normalization shape requires a later owner-approved
specification, mapping version, formula version, and independent oracle; it is outside this gate.

### Discounts

`discount` is a positive additive informational amount attached to sale events. It includes line,
allocated invoice, promotion, loyalty, and markdown discounts only when the source has already
prevented overlap and allocated any invoice-level amount exactly once.

Discount never changes governed revenue because admitted revenue is already net. A bare discount,
rate, percentage, repeated invoice total, or overlapping component set refuses the discount metric.
Every posted sale row must carry a non-negative discount amount, including an explicit zero, or the
package must carry an admitted declaration that either no discounts occurred or discounts are not
captured. Proven absence states zero; not-captured coverage refuses discounts without refusing
independently proven net revenue.

### Returns

`returns` means the positive VAT-exclusive net sales-reversal magnitude derived from admitted
return-event revenue. For each posted return event, `return magnitude = -return revenue`; Khepri
does not admit a second independently mapped return-amount measure in this correction. A separate
gross merchandise value, tender refund, tax refund, fee, exchange value, or restocking charge is
outside this metric and cannot be substituted for it.

`returns` remains a published metric but is no longer an independent source semantic in
`rra003.mapping.v3`. Existing positive return-amount columns are not silently reinterpreted as
signed revenue; a source must instead supply the normalized negative revenue on return events or
wait for a separately governed future normalization shape outside this gate.

Full and partial returns use the return posting date. Khepri does not rewrite a previously
published sales period. A return posted without an event kind, revenue, or a sign consistent with
the contract refuses returns and the financial revenue population. Negative units are required only
for unit-dependent results: their absence refuses units but does not suppress independently proven
return revenue. If event-kind coverage proves that a package contains no return events, returns is
stated as zero; an absent event-kind mapping cannot establish that zero.

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

Gross profit is `sum(revenue) - sum(extended COGS)` over that population and may be negative. Gross
margin is `gross profit / sum(revenue)` and requires a strictly positive matched revenue
denominator. When that denominator is zero or negative, gross margin alone refuses; complete cost
and gross profit remain answerable. Missing cost never suppresses independently complete revenue.

### Units and bonus items

`units` means signed physical merchandise movement:

- ordinary and free/bonus sale units are positive;
- return units are negative;
- fractional quantities are refused by this specification and remain a future governed extension;
- zero units on a sale or return event refuses unit-dependent results.

Fractional quantities are never rounded to integers. They refuse only unit-dependent results;
independently proven monetary and dimension results survive. This is a deliberate private-beta
boundary for countable pharmacy/retail merchandise, not a claim that weighted retail never exists.

The headline units total is net physical movement, including returns. ASP is sale-event net revenue
divided by positive sale units over a complete posted-sale population; return events never enter
either side. A non-positive denominator refuses. Free/bonus items therefore lower the realized ASP,
which is the intended commercial meaning of net sales revenue per physical sale unit supplied. If
the package contains returns, ASP carries a caveat that it is a sale-performance ratio and does not
reconcile to headline return-inclusive revenue or units.

Items per transaction uses only positive units from posted sale events, including free/bonus
items. Return events do not enter either its numerator or its sales-transaction denominator. Any
missing units on a sale row refuses items per transaction.

### Transactions and AOV

`transactions` counts distinct canonical transaction keys of posted sale events only. Return,
void, and cancelled events are not sales transactions.

Every sale row must carry a canonical transaction key. A source transaction identifier may be the
key only when its recorded source contract proves package-wide uniqueness. Otherwise the key is an
admitted composite of the source transaction identifier and every field needed for uniqueness,
normally store, business date, and terminal/register. Missing components or collisions refuse
transactions, AOV, basket size, and attach rate; no row count or partial identifier set substitutes
for the canonical key.

AOV is net sale-event revenue divided by distinct posted sale transactions. It excludes later
return events from both numerator and denominator, because the posting-period revenue impact of a
return cannot be assigned to an order in the current contract. AOV refuses if any sale row lacks
revenue. The report-level revenue total can consequently differ from AOV numerator when the period
contains returns; the metric's evidence records its `sale` population explicitly and every surface
carries a bilingual caveat that AOV is sale-only rather than return-inclusive headline revenue per
order.

### Currency

Every monetary package must prove exactly one normalized uppercase ISO 4217 code. Missing,
malformed, or mixed currency refuses all monetary facts and their derived results while count-only
facts may survive. Khepri performs no exchange-rate lookup or conversion.

## Population eligibility contract

Every fact records a population code in readable provenance; hashing it into an identity is not
sufficient. The initial governed populations are:

- `financial_posted`: posted sale and return events, excluding void and cancelled rows;
- `sales_posted`: posted sale events only;
- `sales_complete_revenue`: `sales_posted` with complete revenue;
- `sales_complete_units`: `sales_posted` with complete strictly positive units;
- `sales_complete_revenue_units`: `sales_posted` with complete revenue, strictly positive units,
  and no unmatched eligible row;
- `sales_complete_transactions`: `sales_posted` with complete canonical transaction keys;
- `sales_complete_revenue_transactions`: `sales_posted` with complete revenue and canonical
  transaction keys;
- `sales_complete_units_transactions`: `sales_posted` with complete strictly positive units and
  canonical transaction keys;
- `financial_complete_revenue_cost`: financial rows with complete revenue and extended cost;
- `dimension_complete_sales:<dimension>`: sale rows with complete canonical transaction keys and a
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

### Retained reconciliation bases

The package retains the following audit-evidence bases. They are not additional customer KPIs and
renderers never present or recalculate them:

- `financial_revenue_basis`: complete signed revenue over `financial_posted`;
- `financial_units_basis`: complete signed units over `financial_posted`;
- `sales_revenue_basis`: complete non-negative revenue over `sales_posted`;
- `sales_units_basis`: complete positive units over `sales_posted`;
- `sales_transaction_basis`: the complete canonical sale-transaction key set;
- `sales_revenue_units_basis`: paired sale revenue and units over one complete identical
  population;
- `sales_revenue_transaction_basis`: paired sale revenue and canonical transaction keys over one
  complete identical population;
- `sales_units_transaction_basis`: paired sale units and canonical transaction keys over one
  complete identical population;
- `financial_revenue_cost_basis`: paired revenue and extended COGS over the complete identical
  financial population;
- `dimension_sales_revenue_basis:<dimension>`: complete sale revenue by every admissible value;
- `dimension_transaction_basis:<dimension>`: the complete transaction-membership set for every
  admissible value;
- aligned daily revenue and unit bases bound to each accepted comparison window.

Every basis records its population code, event count, canonical transaction count where applicable,
input digest, mapping version, currency where applicable, precision, and stable basis identity.
Every derived fact cites exactly one compatible basis or a documented set of bases sharing the same
population identity. If a required basis cannot be retained completely, only its dependent facts
refuse. These bases provide the source aggregates required for RRA-008 reconciliation even when a
sale-only ratio intentionally differs from a return-inclusive headline.

## Metric population assignments

| Metric | Population |
|---|---|
| Revenue, period revenue, revenue comparison | `financial_posted` with complete revenue |
| Units | `financial_posted` with complete units |
| Transactions | `sales_complete_transactions` |
| AOV | `sales_complete_revenue_transactions` |
| ASP | `sales_complete_revenue_units` |
| Cost, gross profit, gross margin | `financial_complete_revenue_cost` |
| Discounts | posted sales with complete additive discount coverage |
| Returns | negative posted return revenue, published as its positive magnitude |
| Growth decomposition | return-free compared windows over `sales_complete_revenue_units` |
| Items per transaction | `sales_complete_units_transactions` |
| Attach rate | `dimension_complete_sales:<product|category>` |
| Concentration | complete non-null product/category values over revenue-complete posted sales |

These assignments eliminate the current cross-headline claim that matched gross profit can be
read as total revenue minus a differently covered cost total.

## Exact formula and refusal contract

All sums use admitted unrounded decimals. `count_distinct` operates on canonical keys, never rows.

| Metric | Exact formula | Required refusal |
|---|---|---|
| Revenue | `sum(financial signed revenue)` | Missing revenue or monetary semantics |
| Units | `sum(financial signed units)` | Missing/non-integral units; caveat a non-positive net total |
| Transactions | `count_distinct(sale transaction key)` | Any eligible sale row lacks a complete canonical key |
| AOV | `sales revenue / distinct sale transactions` | Incomplete sale revenue/key population or transaction denominator `<= 0` |
| ASP | `sales revenue / positive sale units` | Incomplete sale revenue/unit population or unit denominator `<= 0` |
| Cost | `sum(financial signed extended COGS)` | Any eligible financial row lacks admitted extended COGS |
| Gross profit | `matched revenue - matched extended COGS` | Revenue/cost population mismatch |
| Gross margin | `gross profit / matched revenue` | Gross profit refused or matched revenue denominator `<= 0` |
| Discounts | `sum(non-negative sale discount)` | Not captured, partial, overlapping, or non-additive |
| Returns | `-sum(non-positive return revenue)` | Return-event or revenue semantics are incomplete |
| Absolute delta | `current - prior` | Exact governed counterpart or compatible population is absent |
| Percentage delta | `(current - prior) / prior` | Absolute delta refused or prior denominator `<= 0` |
| Items per transaction | `sum(sale units) / distinct sale transactions` | Incomplete units/keys or denominator `<= 0` |
| Attach rate for value | `distinct containing keys / all eligible keys` | Incomplete dimension/keys or denominator `<= 0` |
| Concentration curve point | `cumulative revenue / total ranked revenue` | Incomplete inputs, negative value, or total `<= 0` |
| Top decile share | Curve share after `ceil(distinct values / 10)` ranked values | Concentration curve refused |
| Top quartile share | Curve share after `ceil(distinct values / 4)` ranked values | Concentration curve refused |

Period and growth formulas use the aligned bases and additional rules below. A missing optional
input refuses only formulas that require it.

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

Product and category attach families are emitted independently when both dimensions are admissible.
Neither dimension suppresses the other.

## Price/volume growth contract

Growth uses the exact aligned, return-free posted-sale population carrying complete revenue and
strictly positive units in both windows. It refuses if either window has a missing row, a return,
a non-positive unit denominator, a different coverage signature, or an unproven currency.

For current sale revenue `R_c`, prior sale revenue `R_p`, current sale units `U_c`, prior sale
units `U_p`, and `ASP = R / U` calculated without intermediate rounding:

```
volume effect = ASP_p * (U_c - U_p)
price effect  = U_c * (ASP_c - ASP_p)
revenue delta = R_c - R_p = volume effect + price effect
```

This convention assigns the entire price-volume interaction term to price. Because aggregate ASP
also changes when the product mix changes, the machine metric remains `price_effect` but its
business label is **realized price/mix effect**. Every surface carries a bilingual caveat that it is
not a pure same-SKU price-change measure. The reconciliation is an algebraic invariant, but the
allocation is a governed commercial convention rather than the only mathematically possible
decomposition.

Published rounding is deterministic and preserves the exact displayed reconciliation:

```
published revenue delta = round(R_c - R_p)
published volume effect = round(unrounded volume effect)
published price effect  = published revenue delta - published volume effect
rounding residual       = published price effect - round(unrounded price effect)
```

The rounding residual is recorded in audit evidence, is bounded to one unit of the published last
place, and is assigned to price consistently with the interaction convention. A larger residual is
a reconciliation failure. This rule prevents independent half-even rounding of two effects from
disagreeing with the published revenue delta.

## Concentration eligibility

Concentration uses posted sale revenue over the full, non-null, admissible product or category set
before display truncation. Its business name is **sales revenue concentration**. When a package
contains returns, every surface states that the result reconciles to the retained sale-revenue
basis, not return-inclusive headline revenue. A missing value on any revenue-bearing sale row
refuses that dimension; `None` and the synthetic `unlabelled` bucket are never ranked as products.

The curve refuses when total ranked revenue is non-positive or any ranked value has negative
revenue. Zero-revenue values remain distinct and rank last, producing a flat tail. The top decile
and quartile contain `ceil(n/10)` and `ceil(n/4)` ranked values respectively, with at least one
value. Ceiling is used because a discrete ranked set must include at least the requested fraction
of products; floor would publish an empty top decile for fewer than ten values. Shares retain four
decimal places and the ceiling convention is part of the concentration formula version.

Zero-revenue values remain in `n` because active RRA-004 defines the population as the full
admissible distinct-value set, not only positive-revenue values. They change the discrete cutoff
count but contribute no cumulative revenue. The audit evidence and business caveat disclose their
count. Excluding them would be a different concentration formula version and is not part of this
correction.

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

A day-count total and the observed event rows are insufficient to prove an extract complete. A
separate, source-provided or explicitly operator-attested coverage manifest is the only authority
for a zero-activity store/day or a complete calendar boundary. The manifest is versioned and bound
to the input digest, and records:

- the covered start and end dates and reporting timezone;
- the complete store roster, or the identity of one governed aggregate scope;
- every covered `(store or aggregate scope, calendar date)` pair;
- the included event kinds and statuses;
- the source contract or attestation identity and its evidence;
- every known extraction gap, store closure, and partial terminal boundary.

An attested store closure is complete coverage with zero activity. An extraction gap is not. Khepri
must not synthesize proof from a date spine, minimum/maximum observed dates, equal row counts, or
the absence of events. Without a valid manifest, observed trends may survive, but completeness-
dependent period comparisons and growth refuse.

Using the manifest and admitted events, the package retains a deterministic coverage signature and
daily subaggregates for every monthly revenue and unit bucket:

- ordered calendar-day ordinals covered;
- the set of covered `(store or aggregate scope, day ordinal)` pairs;
- daily revenue and units totals, including attested zero-activity days;
- whether coverage is a contiguous prefix beginning on the first calendar day.

A full monthly window requires a contiguous complete calendar signature for every admitted store.
An incomplete current month may compare days 1 through its last proven contiguous day against the
same calendar-day prefix in the prior period. Both windows must have identical store coverage. The
facts carry the aligned start/end dates and bilingual partial-window caveat.

If no store dimension is mapped, the coverage manifest must explicitly declare that the package
represents one store or one already-governed aggregate scope. Otherwise period comparisons refuse
because different store participation cannot be ruled out.

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

The rounding mode is decimal round-half-even. Revenue, cost, profit, discounts, returns, AOV, ASP,
absolute deltas, and growth effects use the largest admitted monetary input scale, minimum two and
maximum six. Integral units and transaction counts use zero decimal places. Dimensionless ratios,
percentage deltas, items per transaction, attach rates, and concentration shares use four decimal
places. Rounding occurs once at the published fact boundary unless an intermediate published
structure, such as the concentration curve, is itself the authoritative value.

Any changed number, refusal, population, or interpretation receives a new family formula version.
Any changed serialized package shape receives a new package version. Mapping confirmation changes
receive a new mapping version. Existing packages remain immutable historical artifacts and are not
silently reinterpreted.

Phase 1 must name and authorize these exact successors in the active specifications:

- `rra003.mapping.v3`, succeeding `rra003.mapping.v2`;
- `rra004.package.v3`, succeeding `rra004.package.v2`;
- `rra004.formula.v2`, succeeding `rra004.formula.v1`;
- `rra008.comparison.v2`, succeeding `rra008.comparison.v1`;
- `rra008.growth.v2`, succeeding `rra008.growth.v1`;
- `rra008.basket.v2`, succeeding `rra008.basket.v1`;
- `rra008.concentration.v2`, succeeding `rra008.concentration.v1`.

The package v3 authorization covers readable population provenance, canonical transaction keys,
retained reconciliation bases, coverage-manifest identity, coverage signatures, aligned daily
bases, currency, and growth rounding residual evidence. An implementation may not substitute an
unnamed version bump.

## Governance amendments

Phase 1 proposes coordinated amendments rather than hiding policy in code:

- `RRA-003` adds source-event identity, canonical transaction identity, explicit semantic
  declarations, currency, event-kind, status, normalized revenue, extended cost, and coverage-
  manifest confirmation semantics and removes its stale draft/non-authorization sentence;
- `RRA-004` defines the normalized measures, population provenance, coverage signature, daily
  subaggregates, rounding mode, and refusal rules, and removes its stale sentence;
- `RRA-008` defines corrected population assignments, concentration eligibility, attach
  eligibility, and calendar alignment, lifts its old exclusion only for the mapping changes
  explicitly governed here, and removes its stale sentence;
- `RRA-009` remains presentation-only; later caveat/refusal additions extend its complete bilingual
  catalog without changing its calculation boundary;
- `governance/registry.yaml` remains authoritative and needs no lifecycle change unless the owner
  chooses a new superseding specification instead of in-place amendments.

The governance amendment is one proposal. The owner must merge Phase 1 to `main` before any RED
test or product-code slice begins. The calculation worktree then refreshes from that governing
commit. Owner intent expressed in chat, a branch, or an atomic same-branch sequence does not replace
the Constitution's merge-as-approval rule.

## Delivery phases

### Phase 1 — Governed semantics

Deliver only the specification amendments above, validation evidence, and no formula code.

### Phase 2 — Independent RED tests

Add manually calculated tests for:

- partial and sparse calendar periods;
- refusal without an authoritative coverage manifest and acceptance of an attested zero-sales day;
- disjoint revenue and unit rows;
- partial sale-unit coverage;
- missing product/category values;
- cross-headline revenue/cost population mismatch;
- repeated transaction identifiers in different stores;
- return-containing periods proving sale-only ASP and return-inclusive headlines;
- zero and negative gross-margin denominators;
- the half-even growth case where independently rounded effects do not reconcile;
- sale-only derived facts reconciling to retained sale bases rather than headline net revenue.

Each test must fail against the present implementation for the intended numerical or refusal
reason. Expected values may not call production calculation helpers.

### Phase 3 — Core corrections

- **C1:** package coverage signatures and period alignment;
- **C2:** retained reconciliation bases, population-certified growth inputs, and deterministic
  growth residual assignment;
- **C3:** sale-only, complete-coverage basket inputs;
- **C4:** non-null full-set concentration eligibility.

Each correction is a separate formula-versioned slice with its own RED/GREEN/reconciliation gate.

### Phase 4 — Policy-dependent corrections

- AOV complete sale population;
- sale-only ASP population;
- complete financial cost/gross-profit population;
- attach denominator and dimension-complete refusal;
- canonical event/transaction identity;
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
- revenue reconciles independently; when cost is admitted, cost and gross profit reconcile to the
  matched financial basis, gross margin uses that same basis, and missing cost never suppresses
  complete revenue;
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
headers merely say `revenue` or `cost`, or that cannot supply or explicitly declare currency,
status, event kind, event-identity proof, canonical transaction scope, and calendar coverage. They
will refuse only the dependent facts until represented as normalized events and, for comparisons,
bound to a valid coverage manifest. This is preferable to preserving green tests that certify an
unknown business meaning.

The implementation plan must stage fixture migration after the RED proofs and must never weaken a
semantic guard merely to preserve old fixture output. Historical serialized packages remain valid
under their recorded versions; corrected packages receive new identifiers.
