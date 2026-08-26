# Deterministic Retail Calculation Mission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Use
> `superpowers:test-driven-development` for every code correction. Steps use checkbox (`- [ ]`)
> syntax for tracking.

**Goal:** Replace Khepri's ambiguous and population-inconsistent deterministic retail calculations
with the complete governed successor contract, independently prove every changed result, and pass
the calculation validation and local pharmacy staging gates.

**Architecture:** Semantic admission proves what each normalized retail event means; population
eligibility proves which events and transactions each formula may combine; calculation applies one
pinned formula to one certified population. The remaining implementation lands in one later pull
request as seven ordered, independently verifiable publication commits, one governed successor
version per commit. Intermediate commits remain non-governing proposal history; only the complete
final head may merge, so no partial successor contract reaches `main` and no commit widens past the
specification that admits it.

**Tech Stack:** Python 3.13, Polars, `Decimal`, Pydantic/FastAPI, pytest, PostgreSQL, MinIO,
Docker Compose, uv, Ruff, Khepri governance validation, and CodeScene's server-side PR gate.

**Spec:** `docs/superpowers/specs/2026-08-23-deterministic-retail-calculation-correction-design.md`

## Current checkpoint

- Calculation audit: complete.
- Correction architecture: PR #262 merged at `18019b5`.
- Governed semantics: PR #264 merged at `f86507920155077fd3c87eb8878d29fb1624db69`.
- Active authorities: `RRA-003`, `RRA-004`, `RRA-008`, and `RRA-009` on `main`.
- Roadmap: `CAL1` is `IN_IMPLEMENTATION` (roadmap §16). The `CAL1-01` execution ledger exists at
  `docs/superpowers/plans/2026-08-26-cal1-01-v-mapping-execution-ledger.md`, and `#292`
  (`1813682`) and `#300` (`8acef78`) executed against it.
- Pre-publication implementation: `#292` landed manifest/source-contract API ingestion, gate
  wiring, and admission plumbing; `#300` landed the browser coverage-manifest attestation surface.
  What the publication commit still carries — the transaction-date refusal and the manifest
  exception fields — is recorded in the `CAL1-01` ledger.
- Publication state: all seven successor constants remain unpublished at their predecessor values.
- Next action: obtain the owner ruling on the delivery unit, then open one later implementation
  PR whose first ordered commit is the final `V-mapping` publication — the only one permitted to
  move `MAPPING_VERSION` to `rra003.mapping.v3`.

## Global constraints

- Read `AGENTS.md`, `governance/CONSTITUTION.md`, `governance/registry.yaml`, and active
  `RRA-003`, `RRA-004`, `RRA-008`, and `RRA-009` before changing product code.
- The registry is authoritative; do not change governance lifecycle state in the calculation PR.
- Publish exactly `rra003.mapping.v3`, `rra004.package.v3`, `rra004.formula.v2`,
  `rra008.comparison.v2`, `rra008.growth.v2`, `rra008.basket.v2`, and
  `rra008.concentration.v2`.
- Preserve the publication-commit order below; `V-mapping` precedes every other successor.
- Do not merge an intermediate publication commit to `main`; only the complete seven-commit head
  may merge.
- Every code change follows RED, verified intended failure, minimal GREEN, focused regression,
  self-review, and independent task review.
- Expected values are independently calculated literals; production helpers never generate their
  own oracle.
- Every new refusal or caveat ships with its governed code, audit representation, bundle/surface
  propagation, and complete accepted Arabic and English wording in the same commit group.
- Historical mapping-v2 and package-v2 artifacts remain immutable and are never reinterpreted.
- No currency conversion, fractional quantities, forecasting, customer formulas, crossed
  two-dimension analysis, new metric family, Seshat oracle, dependency addition, broad RRA
  refactor, or renderer-side calculation.
- Run `uv run khepri-gov validate`, `uv run ruff check .`, and `uv run pytest` before every handoff.
- CI must pass benchmark, image, and CodeScene gates; local evidence must not claim those checks.

---

## Delivery commits

The remaining CAL1 work ships in **one later implementation pull request**. Its seven ordered
publication commits are the small, independently verifiable slices required by Constitution
Article IV: every commit has its own RED, GREEN, reconciliation, and compatibility evidence while
publishing exactly one successor. A commit adds only the compatibility row owned by the successor
it publishes; `V-mapping` adds no row because no successor package triple is expressible until
`V-package`. Intermediate commits are reviewable proposal history, not governing artifacts. The
owner may merge only the complete final head.

**This delivery unit is proposed and needs an owner ruling before an implementation pull request
opens against it.** The superseded model required owner approval to co-land dependent successors
"because it changes the reviewable unit", and that requirement is not discharged by changing the
unit: moving from seven merged slices to seven commits in one pull request is itself a change to
the reviewable unit. The reasoning is recorded here and in the roadmap's release strategy so the
owner can rule on it, exactly as the residual placement was recorded and then confirmed in a dated
decision record. An implementer who finds the intermediate refusal states unacceptable must not
remove or widen the gate; that too is an owner ruling.

| Commit | Publishes | Parts inside it | Follows |
|---|---|---|---|
| `V-mapping` | `rra003.mapping.v3` | Task 3, less its package-v3 structural fields, **plus the coverage manifest and its ingestion path** (`RRA-003` puts manifest confirmation in this version) **and the version compatibility gate below** | — |
| `V-package` | `rra004.package.v3` | Task 3's package-v3 structural fields; Task 4's coverage signatures, daily bases and projections; package population/basis/coverage fields only, with no residual field | `V-mapping` |
| `V-formula` | `rra004.formula.v2` | Task 8, **plus** the `RRA-004` core-formula rows inside Tasks 4, 6 and 7 — absolute and percentage delta, items per transaction, attach rate, concentration curve point, top decile and quartile share | `V-package` |
| `V-comparison` | `rra008.comparison.v2` | Task 4's comparison facts and refusals | `V-formula` |
| `V-growth` | `rra008.growth.v2` | Task 5's growth family, including all rounding-residual audit evidence | `V-comparison` |
| `V-basket` | `rra008.basket.v2` | Task 6's basket family | `V-growth` |
| `V-concentration` | `rra008.concentration.v2` | Task 7's concentration family, **plus Task 9's presentation sampling and its bilingual caveat** (`RRA-008` puts both in the concentration contract) | `V-comparison`, `V-growth`, **and** `V-basket`; it is last |

Five consequences the task order alone does not give:

- **`rra004.package.v3` spans Tasks 3 and 4 only.** `RRA-004` defines that one version to
  authorize readable population provenance, canonical transaction keys, retained
  reconciliation bases, coverage-manifest identity, coverage signatures, aligned daily
  bases, and currency. Task 5 contributes nothing to the persisted package. Growth rounding
  residuals are wholly `V-growth` audit evidence under `rra008.growth.v2`.
- **`rra004.formula.v2` precedes the four `RRA-008` families.**
  `RRA-008`'s exclusions name `rra004.formula.v2` as consumed there, and the formula
  rows for delta, attach, items-per-transaction and concentration shares live in
  `RRA-004`'s single core-formula table. Task 8 sitting last would leave Tasks 4, 6 and
  7 proving families against formulas that then change under them.
- **`V-mapping` carries every admission change `rra003.mapping.v3` governs**, including
  the normalized measures — revenue and returns, discounts, cost inputs, units — not
  only identity, currency and coverage confirmation.
- **`V-concentration` is last by designation, not by an `RRA-008` dependency.** `RRA-008`
  requires only growth after comparison, so basket and concentration carry no inter-family order of
  their own. A commit sequence is linear, so one of them must still be placed last, and the choice
  is load-bearing: whichever family is not last leaves the other still stamping `v1`, so the
  refusing set is not empty and Task 7's claim to close the window and restore the browser report
  would be false. Concentration is designated last, and basket therefore follows growth. The
  designation is what makes both claims determinate; it is recorded here so a later reader does not
  read it as an `RRA-008` requirement and reorder the two freely.
- **`V-concentration` carries presentation sampling, which Task 9 held.** `RRA-008` puts
  it inside the concentration contract — "The full curve remains authoritative.
  Presentation-only sampling keeps no more than 100 points, including the final 100%
  point, and carries a bilingual sampling caveat" — and names sampling in that
  specification's own Verification list. Shipping `rra008.concentration.v2` without it
  would publish the identity incomplete and let Task 9 change governed behaviour under an
  already-published version, which is the same defect the `V-package` bullet above
  refuses. The merged roadmap states the rule directly at §CAL1: a caveat and its wording
  "ship in **the same slice that introduces it**", and `CAL1-11` "is therefore a final
  sweep, not the task where surfaces catch up".

### The version compatibility gate, and why every publication commit proves it

PR #292 at `1813682` wired the fail-closed compatibility gate at package and family scope before
any successor constant moved. The later implementation PR must preserve those seams and prove
them at every publication commit.

Every intermediate commit in the proposal sequence creates a review state where a moved version
must refuse against consumers whose successors have not yet been committed:

- `V-mapping` alone makes the normalized-measure admission changes live — void-row
  exclusion, return derivation — while `rra004.package.v2` and `rra004.formula.v1` remain
  current, so results change under legacy package and formula identities.
- `V-formula` alone changes the delta, attach, items-per-transaction and
  concentration-share rows while all four families still stamp `v1`.

`RRA-004` forbids exactly this: "A new input, mapping, formula, population, interpretation,
correction, or serialized shape creates a new recorded version and stable identity."
Ordering does not fix it, because the defect is in the window rather than the order.

The gate is an **explicit table of admitted version pairs**, not a comparison: a
consumer publishes only when the pairing it is handed appears in the table, and refuses
otherwise.

A "newer than" predicate would be wrong, and the reason is worth recording so it is not
reintroduced. These identifiers are independent namespaces — `rra003.mapping.v3`,
`rra004.formula.v2` and `rra008.basket.v2` share a numbering convention and nothing else —
so their suffixes define no ordering to compare. A one-sided rule also guards one direction
only: once a family reached `v2`, "refuse when the formula is newer" would stamp a
successor family identity onto a package still carrying `rra004.formula.v1`. And an
unrecognised version's handling would be undefined, where a table refuses it by
construction. `RRA-008` frames the contract the same way: its `v2` families consume "the
exact `rra003.mapping.v3`, `rra004.package.v3`, and `rra004.formula.v2` changes".

Every refusal carries a governed reason code and complete accepted Arabic and English
wording, like every other refusal in this mission.

The consequence is deliberate and must not be worked around: **each consumer refuses in an
intermediate proposal commit from the moment a version it consumes moves until its own successor
commit follows**, each publication commit adding only its owned compatibility row. The refusing
set is largest right after `V-formula` and
shrinks with each family slice — after `V-comparison` three families still refuse, after
`V-basket` one, and `V-concentration` empties it. That is a visible, reasoned refusal
rather than a plausible number under a stale identity, which is the trade this product
exists to make, and it gives every slice a precise definition of done.

These intermediate refusal states never reach `main`: only the complete final PR head may merge.
An implementer must not remove or widen the gate to make an intermediate commit publish.

### `V-growth` follows `V-comparison`, not merely `V-formula`

`RRA-008` is explicit: "Growth consumes the exact PoP window selected by period comparison
and may not select another", over "the structural coverage compatibility already accepted
by comparison" and "comparison's accepted aligned daily measure bases". A `V-growth` that
merged first would have to consume comparison `v1`'s window or reselect one itself, and the
specification forbids both.

Each family commit's definition of done includes **opening the gate for its own family**:
it publishes the family successor version and the compatibility check then passes for it.
A family commit that leaves its own gate closed is incomplete.

Each publication commit runs its own RED, verified failure, minimal GREEN, focused regression,
independent oracle, bilingual refusal wording, reconciliation, and the three required
gates. The validation gate in Task 10 runs against the assembled seven-commit PR head, which is
complete and still non-governing. Validating after merge would certify already-governing code and
put the gate on the wrong side of owner approval. No commit reaches a design partner before the
complete PR passes.

`docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md` §CAL1 carries the same slice map under
the identifiers `CAL1-03` … `CAL1-10`; where this plan and that roadmap disagree, the
active specification governs both and the disagreement is a defect in one of them.

---

### Task 1: Refresh the isolated execution branch

**Files:** No tracked files.

**Interfaces:**
- Consumes: merged governance commit `f865079` and the active specifications.
- Produces: clean branch `calculations-correction` in the existing `calculations` worktree.

- [ ] Verify `git status --short` is clean and stop for unexpected tracked changes.
- [ ] Fetch origin and verify PR #264's merge is reachable from `origin/main`.
- [ ] Create `calculations-correction` from fresh `origin/main`; do not rebase or reset a dirty
  worktree.
- [ ] Run the three required checks and record the baseline test count and environmental skips.
- [ ] Create the subagent-development ledger with the base SHA, task order, and this plan path.
- [x] Record the owner-confirmed growth rounding-residual placement. The ruling is formalized in
  `RRA-004`: the persisted package contains package population, basis, and coverage fields only,
  with no residual field. `V-growth` owns the residual evidence wholly under
  `rra008.growth.v2`, including its audit representation, reason code, and bilingual wording.

### Task 2: Add independent RED calculation proofs

**Files:**
- Modify: `tests/test_rra003_mapping.py`
- Modify: `tests/test_rra004_facts.py`
- Modify: `tests/test_rra004_retained_aggregates.py`
- Modify: `tests/test_rra008_comparison.py`
- Modify: `tests/test_rra008_growth.py`
- Modify: `tests/test_rra008_basket.py`
- Modify: `tests/test_rra008_concentration.py`

**Interfaces:**
- Consumes: current v2/v1 production behavior and the active governed successor requirements.
- Produces: independently derived failures that name the exact missing result or refusal behavior.

- [ ] Add a clean two-store/two-period dataset with distinct event keys, canonical transaction
  keys, repeated products on distinct lines, products/categories, revenue, units, COGS, and a
  complete coverage manifest.
- [ ] State literal expected revenue, units, distinct sales transactions, sale-only AOV and ASP,
  items per transaction, gross profit/margin, concentration, attach, PoP/YoY deltas, and growth
  effects. Do not call any production aggregation or analysis helper when constructing expected
  values.
- [ ] Add messy legitimate cases: partial nulls, posted returns, allocated discounts, duplicate
  signatures, negative signs, incomplete current period, and absent optional dimensions.
- [ ] Add adversarial cases: missing canonical transaction identity, zero/negative denominator,
  no exact prior period, disjoint revenue/units, partial cost, high monetary precision, sparse
  calendar coverage, store mismatch, and display truncation.
- [ ] Add exact regression proofs for:
  - missing manifest refusal and attested zero-activity acceptance;
  - partial current prefix against a manifest-proven projection from a complete prior month;
  - natural 28/29/30/31-day full-period compatibility;
  - missing product/category on a zero-revenue sale row;
  - repeated invoice IDs in different stores;
  - return-inclusive headlines beside sale-only AOV/ASP;
  - zero and negative gross-margin denominators;
  - half-even growth residual assignment;
  - one refused metric leaving independent metrics standing.
- [ ] Run every new focused test against current production code and record the intended numerical
  or refusal mismatch. Fix test setup errors until each case fails for its intended reason.
- [ ] Commit the verified RED tests locally. Do not push the branch while its head is RED.
- [ ] **Hold each slice's RED tests with that slice, not all of them here.** The required handoff
  runs the full `pytest`, and a branch carrying committed failures for `V-package` through
  `V-concentration` cannot produce a green gate while only `V-mapping` is implemented. This task
  derives and verifies every expected literal — that work is done once, outside production helpers —
  and each slice then adds its own verified-RED cases immediately before its GREEN. The oracle is
  shared; the failing tests are not.

### Task 3: Implement C0 normalized semantic admission

**Files:**
- Modify: `src/khepri/rra/mapping.py`
- Modify: `src/khepri/rra/admissibility.py`
- Modify: `src/khepri/rra/datasets.py`
- Modify: `src/khepri/rra/api.py`
- Modify: `src/khepri/rra/facts.py`
- Modify: `src/khepri/rra/packages.py`
- Test: RRA-003/RRA-004 files from Task 2.

**Interfaces:**
- Consumes: a profiled upload plus explicit normalized source contract.
- Produces: mapping v3, admitted normalized events, and readable population evidence — every
  admission change `rra003.mapping.v3` governs, normalized measures included.
- Commit: `V-mapping`, except the package-v3 structural fields it also produces, which are part of
  the later `V-package` commit.

- [ ] **Finish the browser journey.** `#292` added source-contract collection and API manifest
  ingestion; `#300` (`8acef78`) added the manifest controls, the `coverage_manifest` payload, the
  bilingual wording, and the journey regression coverage. **Still missing: the exception fields.**
  `CoverageManifestBody` carries `closed_days`, `extraction_gap_days` and
  `partial_terminal_boundary`; the journey sets none of them, so a known gap serializes as absent.
  (`store_roster` is excluded by design: `RRA-003` makes it and `aggregate_scope` alternatives.)
  Add those controls before `MAPPING_VERSION` moves.

  **What that coverage may assert is the governed refusal, not a report.** The gate is already
  wired, and after the `V-mapping` publication commit `mapping.v3` against
  `rra004.package.v2` is an unlisted pair, so
  `packages.py` refuses. `review.js:36-37` posts `/api/v1/beta/facts` and only then
  `/api/v1/beta/reports`, so the journey cannot reach a report while the window is open — an
  acceptance criterion demanding one would be unmeetable by construction, and the only ways to meet
  it are removing the gate or advancing to the later proposal commits. The criterion is therefore:
  **a normal browser upload reaches the governed bilingual
  refusal, stating which version pairing was refused, rather than a 422 or a stranded page.** That
  is what the client change buys during the window, and it is a real regression target — a 422 from
  a missing contract and a stated refusal from an unadmitted pairing are different outcomes and the
  journey must produce the second. `V-concentration` empties the refusing set, and the criterion
  returns to reaching a report there; the last slice carries that assertion.
- [x] Wire the fail-closed version compatibility gate at package and family scope. PR #292 merged
  that plumbing and its governed bilingual package-refusal path at `1813682` without moving a
  successor constant. The final `V-mapping` publication commit proves the gate with mapping v3
  and adds no compatibility row because no successor package triple is expressible yet.
- [ ] Add the RED proof that the gate fires at each seam: with one version moved and its consumer
  unmoved, the consumer refuses and states why, and no fact is published under the predecessor
  identity.
- [ ] **Refuse at the right scope for each seam; the gate straddles two.** Its table pairs package
  and formula against mapping *and* each `RRA-008` family against the formula, and those fire in
  different places.

  A **mapping/package/formula** mismatch is caught while the package is built, so it is a
  `PackageRefused`: `api.py:353` returns a 409 and `review.js` — which posts `/api/v1/beta/facts`
  before `/api/v1/beta/reports` — never creates a report, so there is no bundle to propagate into.
  The roadmap's §CAL1 rule scopes its bundle/narrative/chart/HTML/PDF/Excel clause to
  `RefusedResult` for that reason; a `PackageRefused` owes the rest of the rule in full instead —
  governed code, accepted Arabic and English prose in the response body, audit representation, and
  **rendering on the review page**, which
  `docs/superpowers/specs/2026-08-13-client-journey-ui-design.md` requires of a fact-package
  refusal: "Remain on review with governed reason."

  A **family-against-formula** mismatch must be a `RefusedResult` in `bundle._FAMILIES`, and owes
  the propagation rule in full — bundle, narrative, chart, HTML, PDF and Excel. `RRA-008` requires
  it: "A failure or missing optional input refuses only dependent results, leaving independently
  answerable facts and the rest of the report intact." So does the shrinking refusing set this plan
  describes, which is only meaningful if families refuse one at a time. Raising `PackageRefused`
  for a family pairing would suppress every independently answerable result until the last family
  merged — a blackout, not a shrinking set.

  **Build that path; do not assume it exists.** `PackageRefused` is still a bare `ValueError`
  subclass with no code and no audit hook, and three of the four raises in `packages.py` still pass
  plain English strings. **The client half is closed as of `#292` (`1813682`)**: `common.js`'s
  `ApiError` now carries the response body's `detail`, and `review.js`'s `refusal()` renders the
  stated reason rather than one fixed sentence. The rest is pre-existing debt against
  the same obligation, not a precedent to copy. This slice already carries client work for the
  source-contract surface, so the refusal rendering belongs beside it. Prove all four parts.
- [ ] Add the mutation evidence that the gate can fail: removing a seam's comparison kills a named
  mutant, so a green suite is not mistaken for a guard.
- [ ] **Add the coverage-manifest document, its binding, and its production ingestion path here,
  not in `V-package`.** `RRA-003`'s stable contract states that `rra003.mapping.v3` governs
  "coverage-manifest confirmation", so a `V-mapping` that publishes the successor without the
  manifest publishes a mapping identity that cannot accept or confirm one — and `V-package` would
  then change behaviour governed by an already-published identity. Only the package coverage
  signatures, retained daily bases and structural projections wait for `V-package`.
- [ ] Record the manifest fields: version/evidence identity, input digest, **the source-contract or
  attestation identity and its evidence**, timezone, aggregate scope or full store roster, covered
  scope/date pairs, included event kinds/statuses, closures, extraction gaps, and partial terminal
  boundary. `RRA-003` names the source-contract binding separately from the input digest, and the
  reason is reuse: identical bytes re-uploaded under a corrected semantic contract would otherwise
  match an old manifest whose event-kind and status coverage was attested against different
  semantics, admitting comparison and growth without authoritative proof.
- [ ] Validate that binding on use, not only on write: a manifest whose source-contract identity
  differs from the contract the events were admitted under refuses the completeness-dependent
  results rather than being reused.
- [ ] Finish the ingestion path. **The API half landed in `#292` (`1813682`)**: the manifest is
  submitted on `POST /api/v1/beta/profile` as an optional `coverage_manifest`
  (`coverage_request.CoverageManifestBody`, `extra="forbid"`), bound to the input digest and the
  source contract, persisted into the digested profile document, and read back at use time through
  `GET /api/v1/beta/coverage/completeness`. It rides the profile request rather than its own POST
  because attaching a manifest to an existing profile would rewrite `profile_digest`, which every
  published package cites.
  **The browser surface landed in `#300` (`8acef78`)**: `upload.js` collects
  `[data-manifest-field]` controls and sends `coverage_manifest` only when the customer attests,
  and `upload.html.j2` carries the controls and their bilingual wording, so Task 11's staging
  journey can submit one and completeness-dependent comparisons no longer refuse from a real
  upload for want of an attestation. The end-to-end test **at the mapping boundary** — a submitted
  manifest accepted, bound, persisted, and confirmed by `rra003.mapping.v3` — still cannot close
  until the
  final PR moves the version constant.

  **The assertion that a manifest *admits a comparison* cannot be made here, and belongs to
  `V-comparison`.** The gate this slice introduces refuses `mapping.v3` against the still-current
  `rra004.package.v2` and `rra004.formula.v1`, so both uploads — with a manifest and without —
  stop at version skew before any comparison runs. Writing that test in this slice would prove
  only that the gate fires, under a name claiming it proved something about coverage.
- [ ] Extend `POST /api/v1/beta/profile` with a required `extra="forbid"` source-contract object
  containing contract/evidence identity, semantic column positions, event-kind column or sale-only
  declaration, status column or posted-only declaration, currency column or constant ISO code,
  event-key positions or unique-line-grain attestation, canonical transaction-key components and
  uniqueness scope, and exact revenue/units/cost/discount basis declarations.
- [ ] Persist the source contract and its digest inside the existing profile document JSON. Bind
  profile reuse/conflict checks to that digest; add no database migration.
- [ ] Make `build_mapping` deterministic from profile plus contract and set
  `MAPPING_VERSION = "rra003.mapping.v3"`.
- [ ] Refuse generic headers without explicit basis confirmation; never infer event kind, status,
  currency, net/gross, VAT, additivity, or allocation from observed values.
- [ ] Admit unique event keys or a unique-line-grain attestation with no repeated canonical
  signature. Refuse affected additive/distinct-transaction populations on collisions.
- [ ] Construct canonical transaction keys only from a package-unique source ID or the confirmed
  composite components. Never substitute row count or incomplete identifiers.
- [ ] Exclude proven void/cancelled events; refuse dependent populations for unknown event/status.
- [ ] Require one uppercase ISO 4217 currency for monetary facts and perform no conversion.
- [ ] Remove independently mapped returns; derive return magnitude later from admitted negative
  return-event revenue.
- [ ] Add package-v3 readable population/filter/currency/basis fields while preserving v2 artifact
  parsing as immutable history.
- [ ] Run the C0 focused RED set to GREEN, then RRA-003/RRA-004 regression tests, governance, Ruff,
  and full pytest. Commit C0 and obtain independent task review before C1.

### Task 4: Implement C1 coverage and period alignment

**Files:**
- Modify: `src/khepri/rra/facts.py`
- Modify: `src/khepri/rra/aggregates.py`
- Modify: `src/khepri/rra/analysis/windows.py`
- Modify: `src/khepri/rra/analysis/comparison.py`
- Modify: `src/khepri/rra/bundle.py`
- Modify: `src/khepri/rra/rendering/wording.py`
- Test: `tests/test_rra004_retained_aggregates.py`, `tests/test_rra008_comparison.py`, and surface
  parity tests.

**Interfaces:**
- Consumes: C0 normalized events and an input-bound coverage manifest.
- Produces: structural coverage signatures, aligned daily bases, accepted PoP/YoY windows, and
  `rra008.comparison.v2` facts/refusals.
- Slices: the manifest document, binding and ingestion are `V-mapping`; coverage signatures, daily
  bases and projections are `V-package`; the absolute and percentage delta formula rows are
  `V-formula`; the comparison family is `V-comparison`.

- [ ] Retain structural coverage signatures containing only manifest/input binding, scope/store
  set, filters, completeness mode, and relative covered ordinals. Exclude absolute dates and all
  measure values.
- [ ] Retain daily revenue/unit bases separately, including attested zero-activity days.
- [ ] Permit a complete period to create a deterministic days-1..k structural projection bound to
  its parent signature and daily bases; never synthesize unproven coverage.
- [ ] Accept full calendar counterparts with identical scope/store/filter fields despite natural
  month-length differences. Accept partial current prefixes only against the identical proven
  prior prefix projection.
- [ ] Require exact previous calendar period for PoP and exact same period one year earlier for
  YoY; refuse nearest observed buckets, gaps, sparse prefixes, store/scope mismatch, filter
  mismatch, and leap day without counterpart.
- [ ] Publish absolute delta for any compatible base and refuse only percentage delta when prior
  is `<= 0`.
- [ ] Add the partial-window/refusal codes and accepted Arabic/English wording in the same commit;
  propagate them through bundle, audit evidence, web, PDF, and Excel without recomputation.
- [ ] **Make the manifest's comparison assertion here, deferred from `V-mapping`.** This is the
  first slice whose version pairing the gate admits, so it is the first place the end-to-end claim
  is testable: a submitted coverage manifest admits a comparison that the same upload refuses
  without one. `V-mapping` proves the manifest is accepted, bound, persisted and confirmed;
  proving what it *unlocks* waits for the slice that can run it.
- [ ] Run focused RED/GREEN tests, comparison and surface suites, the three required gates, commit,
  and obtain independent task review.

### Task 5: Implement C2 compatible growth populations

**Files:**
- Modify: `src/khepri/rra/analysis/growth.py`
- Modify: `src/khepri/rra/bundle.py`
- Modify: `src/khepri/rra/rendering/wording.py`
- Test: `tests/test_rra008_growth.py` and related bundle/surface tests.

**Interfaces:**
- Consumes: C1's accepted PoP window and matched return-free
  `sales_complete_revenue_units` daily bases.
- Produces: `rra008.growth.v2` revenue change, volume effect, realized price/mix effect, and
  rounding-residual evidence.
- Commit: `V-growth`, including the rounding-residual audit evidence wholly. It follows
  `V-comparison` because `RRA-008` requires growth to consume comparison's accepted window and
  daily bases rather than selecting its own. `V-package` contains no residual field.

- [ ] Refuse returns, missing paired rows, non-positive units, unproven/mixed currency, or C1
  structural incompatibility in either window.
- [ ] Calculate unrounded `volume = ASP_prior * (units_current - units_prior)` and
  `price = units_current * (ASP_current - ASP_prior)`.
- [ ] Publish half-even rounded revenue delta and volume effect; publish price as rounded delta
  minus rounded volume; record residual versus independently rounded unrounded price.
- [ ] Refuse reconciliation when residual magnitude exceeds one unit of the published last place.
- [ ] Label the business figure “realized price/mix effect” while retaining machine metric
  `price_effect`; add the equal Arabic/English not-pure-same-SKU caveat.
- [ ] Prove exact displayed additivity and reconciliation to the retained matched sale basis.
- [ ] Run focused RED/GREEN tests, growth/bundle/surface suites, required gates, commit, and review.

### Task 6: Implement C3 sale-only basket populations

**Files:**
- Modify: `src/khepri/rra/analysis/basket.py`
- Modify: `src/khepri/rra/facts.py`
- Modify: `src/khepri/rra/bundle.py`
- Modify: `src/khepri/rra/rendering/wording.py`
- Test: `tests/test_rra008_basket.py` and related package/surface tests.

**Interfaces:**
- Consumes: complete sale units, canonical sale-transaction sets, and dimension membership bases.
- Produces: `rra008.basket.v2` items-per-transaction and product/category attach families.
- Slices: the items-per-transaction and attach-rate formula rows are `V-formula`; the basket family
  is `V-basket`.

- [ ] Calculate items per transaction from positive posted-sale units, including free/bonus items,
  divided by distinct canonical posted-sale transactions over the identical complete population.
- [ ] Calculate attach as distinct eligible transactions containing a value divided by all
  distinct transactions in that dimension-complete population.
- [ ] Count repeated lines of the same value once per transaction.
- [ ] Refuse an attach dimension when any eligible sale row lacks its dimension or canonical key;
  keep the other dimension and items-per-transaction independently answerable.
- [ ] Prevent `other`, `unlabelled`, `redacted`, and display truncation from changing any attach
  numerator or denominator.
- [ ] Ship refusal/caveat codes, audit evidence, bilingual wording, and all surface propagation.
- [ ] Run focused RED/GREEN tests, basket/package/surface suites, required gates, commit, and review.

### Task 7: Implement C4 full-set concentration eligibility

**Files:**
- Modify: `src/khepri/rra/aggregates.py`
- Modify: `src/khepri/rra/analysis/concentration.py`
- Modify: `src/khepri/rra/bundle.py`
- Modify: `src/khepri/rra/rendering/wording.py`
- Test: `tests/test_rra004_aggregates.py`, `tests/test_rra008_concentration.py`, and surface tests.

**Interfaces:**
- Consumes: complete non-null posted-sale dimension revenue bases.
- Produces: `rra008.concentration.v2` authoritative curves and top-decile/quartile shares.
- Slices: the curve-point and top decile/quartile formula rows are `V-formula`; the concentration
  family is `V-concentration`.

- [ ] Refuse a dimension when any eligible sale row lacks its value, including zero-revenue rows,
  or when the full set exceeds admissibility limits.
- [ ] Refuse negative ranked revenue and non-positive total ranked revenue.
- [ ] Keep zero-revenue values distinct, ranked last, and represented as a flat curve tail.
- [ ] Rank the full set before display truncation; retain distinct and ranked counts; carry shares
  only and no labels in the authoritative curve.
- [ ] Use `ceil(n / 10)` and `ceil(n / 4)` with at least one value; assign no fixed bands.
- [ ] Reconcile to retained sale-revenue basis and caveat the difference from return-inclusive
  headline revenue when returns exist.
- [ ] **Sample presentation curves here, not in Task 9.** No more than 100 measured points,
  always including the final 100%, without changing the authoritative curve, with the bilingual
  sampling caveat shipped alongside. `RRA-008` puts both in the concentration contract, so
  `rra008.concentration.v2` cannot publish without them.
- [ ] Ship all refusal/caveat evidence and bilingual surface wording.
- [ ] **Close the refusal window in the browser journey.** `V-concentration` is the last family to
  publish its successor, so the admitted-pair table now names every pairing the runtime combines
  and nothing refuses on version skew. The journey regression `V-mapping` left asserting a governed
  refusal is moved back to its real target here: a normal browser upload reaches a report. Leaving
  it asserting a refusal would pin the transitional behaviour as the permanent one.
- [ ] Run focused RED/GREEN tests, aggregate/concentration/surface suites, required gates, commit,
  and review.

### Task 8: Implement policy-dependent core formula v2

**Files:**
- Modify: `src/khepri/rra/facts.py`
- Modify: `src/khepri/rra/packages.py`
- Modify: `src/khepri/rra/bundle.py`
- Modify: `src/khepri/rra/rendering/wording.py`
- Test: RRA-004 fact/package tests and related bundle/surface tests.

**Interfaces:**
- Consumes: C0 admitted events and retained compatible bases.
- Produces: complete `rra004.formula.v2` headlines and ratios.
- Commit: `V-formula`, which is this task **plus** the `RRA-004` formula rows named in Tasks 4, 6
  and 7. It follows `V-package` and precedes the four `RRA-008` family commits, which consume it,
  and opens the formula seam of the compatibility gate already wired before publication.

- [ ] Add this slice's admitted pairs to the compatibility table, and no others: the four `RRA-008`
  families still stamp `v1` here, so every pairing of them with `rra004.formula.v2` refuses until
  that family's own successor commit follows.
- [ ] Revenue: sum complete signed net VAT-exclusive posted sale/return revenue.
- [ ] Units: sum complete signed integral posted physical movement.
- [ ] Transactions: distinct canonical posted-sale transaction keys only.
- [ ] AOV: complete non-negative sale revenue divided by complete sale transaction set.
- [ ] ASP: complete non-negative sale revenue divided by positive sale units, including bonus/free
  units; exclude returns from both sides.
- [ ] Cost: sum complete signed extended VAT-exclusive COGS over the financial population.
- [ ] Gross profit: matched financial revenue minus matched extended COGS.
- [ ] Gross margin: gross profit divided by strictly positive matched revenue; refuse margin alone
  for zero/negative denominator while cost and gross profit survive.
- [ ] Discounts: sum complete non-negative additive informational sale discounts; never subtract
  them again from already-net revenue.
- [ ] Returns: publish `-sum(non-positive admitted return revenue)` and state zero only when proven
  return-event absence exists.
- [ ] Refuse incomplete headline coverage rather than publishing partial totals; preserve every
  independently complete metric.
- [ ] Apply decimal round-half-even once: monetary 2–6 places from maximum admitted scale, integer
  counts zero places, dimensionless ratios four places.
- [ ] Add sale-only AOV/ASP return caveats and every new refusal/caveat's bilingual evidence and
  surface propagation.
- [ ] Run every Task 2 core RED case to GREEN, then complete package/bundle/surface suites and all
  required gates. Commit and independently review the entire formula-v2 group.

### Task 9: Harden evidence, mutations, and pharmacy oracles

**Files:**
- Modify: appropriate RRA-004/006/008/009 tests.
- Create only if existing fixture modules cannot carry the cases cleanly: one focused pharmacy
  golden-fixture module under `tests/`.

`src/khepri/rra/bundle.py` and `src/khepri/rra/rendering/wording.py` were listed here for the
presentation sampling that now belongs to `V-concentration`. **This task is test-only**, and
saying so is what makes "no slice" safe rather than a hole.

**Interfaces:**
- Consumes: the complete corrected successor package.
- Produces: calculation-validation evidence independent of production formulas.
- Commit: none, **because it changes no production behaviour**. Every task above names the version
  it feeds. A task that touched `src/` and named no slice would be worse than one in the wrong
  commit: its changes could not be on the final implementation PR head that Tasks 10 and 11
  validate, so the assembled gate would certify a tree that is not the one shipping. Anything this task
  *discovers* is a defect in the slice that introduced it and is fixed there, under that slice's
  version — never patched here.

- [ ] Enumerate the complete refusal and caveat catalogues and prove Arabic/English, audit, bundle,
  web, PDF, and Excel coverage equality.
- [ ] Add named mutation proofs that fail if code substitutes observed-day counts for calendar
  compatibility, whole-package totals for matched populations, rows for distinct transactions,
  displayed buckets for full-set concentration, or independently rounded growth effects for the
  governed residual rule.
- [ ] Add three independently calculated pharmacy fixtures:
  - clean: multi-invoice, repeated product lines with distinct event keys, two stores, two periods;
  - messy: partial optional coverage, discounts, returns, duplicate evidence, incomplete period,
    missing optional dimensions;
  - adversarial: missing IDs, zero/negative bases, no prior period, disjoint populations,
    high precision, and many distinct products.
- [ ] Store expected literal values and refusal/caveat outcomes beside each fixture; production
  helpers may process the input but never generate the expected answer.
- [ ] Prove every renderer uses bundle strings and performs no business arithmetic.
- [ ] Run focused mutation/golden/surface suites and the three required gates. Commit and review.

### Task 10: Pass the calculation gate across the assembled contract

**Where this runs.** Tasks 10 and 11 run on the one implementation PR's complete seven-commit
head. Every publication commit has already passed its own focused RED/GREEN/reconciliation gate,
but the branch remains a proposal and none of its intermediate commits governs. Nothing treats
the proposal as approved before Task 12's owner merge.

**Files:** No additional behavior unless a RED test exposes a defect; any fix repeats TDD and task
review before this gate.

**Interfaces:**
- Consumes: the complete seven-commit implementation PR head, with every publication commit having
  passed its own RED/GREEN/reconciliation gate.
- Produces: the assembled successor contract, validated as one analytical system before approval.

- [ ] Run `uv run khepri-gov validate`, `uv run ruff check .`, and `uv run pytest` at exact head.
- [ ] Verify every metric has clean, messy, and adversarial independent-oracle evidence.
- [ ] Verify every ratio uses compatible populations and every accepted comparison proves calendar
  and store/scope coverage.
- [ ] Verify revenue, cost, profit, margin, sale-only ratios, returns, basket, concentration, and
  growth reconcile to their retained bases.
- [ ] Verify one refused result never suppresses independently answerable results.
- [ ] Verify every changed fact/refusal carries the named successor version and stable identity.
- [ ] Obtain broad external calculation/code review; fix all Critical/Important findings and
  re-review the fix diff.
- [ ] In the one later PR, document each ordered commit's RED command/failure, GREEN
  command/result, independent oracle, the single governed version it publishes, owned
  compatibility-row change, and exclusions.
- [ ] Run this gate against the assembled contract on the complete PR head, not against any single
  commit in isolation: a commit can be internally green while the system it joins is not. It runs
  **before** the owner merges the PR, because a gate that ran afterwards would validate something
  already governing.
- [ ] Require CI governance, Ruff, pytest, benchmark, image, and CodeScene gates before owner merge.

### Task 11: Run full PostgreSQL/MinIO local pharmacy staging

**Files:** No tracked change unless staging discovers a defect, which returns to the responsible
task's RED/GREEN loop.

**Interfaces:**
- Consumes: the same complete PR head Task 10 validated, with the calculation gate green.
- Produces: design-partner-equivalent end-to-end staging evidence.

- [ ] Start `docker compose -f docker-compose.local.yml up -d`; use current PostgreSQL and MinIO,
  not LocalStack.
- [ ] Apply current migrations and start the web and worker processes using README commands.
- [ ] Create a fresh invitation/session, upload the normalized pharmacy fixture, submit its source
  contract and coverage manifest, and request a report.
- [ ] Compare package values/refusals/bases against independent expected literals.
- [ ] Inspect Arabic and English web, PDF, and Excel outputs for identical figures, caveats,
  refusals, citations, and separated audit evidence.
- [ ] Exercise clean, return, bonus-item, multi-store, partial-window, missing-optional-input, and
  refusal journeys.
- [ ] Record input, contract, manifest, package and bundle digests, exact versions, commands,
  outcomes, and environmental skips in the PR evidence.

### Task 12: Complete owner cutover and merged-main validation

**Files:** No tracked change.

**Interfaces:**
- Consumes: the validated complete PR head, server-side gates, and staging evidence.
- Produces: validated successor calculation contract on `main`.

- [ ] Owner merges the one complete seven-commit implementation PR; automation never merges or
  treats checks as approval. No intermediate publication commit is merged separately.
- [ ] Fetch fresh `origin/main`, verify the merge SHA, and update the calculations worktree without
  destructive reset.
- [ ] Rerun governance validation, Ruff, and full pytest on merged `main`.
- [ ] Re-run the normalized pharmacy golden journey and compare its package/bundle digests and
  figures with the reviewed PR evidence.
- [ ] Declare the calculation validation gate complete only when merged-main, independent oracle,
  CI, and local staging evidence all agree.

## Completion definition

The mission is complete only when the owner has merged the complete implementation PR and
merged-main
evidence proves the complete normalized-event, population, formula, reconciliation, bilingual,
mutation, pharmacy-oracle, and local-staging contract. A green unit suite alone is insufficient.
