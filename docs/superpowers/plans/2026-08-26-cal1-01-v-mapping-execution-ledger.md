# `CAL1-01` execution ledger — the `V-mapping` slice

> **Task:** `CAL1-01`, the ledger the merged roadmap requires before any `CAL1` slice opens.
> **Mission:** `docs/superpowers/plans/2026-08-24-deterministic-retail-calculation-mission.md`.
> **Spec:** `docs/superpowers/specs/2026-08-23-deterministic-retail-calculation-correction-design.md`.
> **Authorities:** `RRA-003`, `RRA-004`, `RRA-008`, `RRA-009`.
> **Base SHA:** `739d474` (`origin/main`, PR #283).
> **Branch:** `calc2`, worktree `.claude/worktrees/calc2`.
> **Baseline:** `uv run pytest` → 3250 passed, 72 skipped, 1 xfailed.

The roadmap gives this task one job: **own the exact slice boundaries.** The mission plan's
slice table fixes which governed version each slice publishes and which tasks sit inside it;
this ledger fixes the file-level split and proves that no task contributing to
`rra003.mapping.v3` sits outside `V-mapping`. A boundary that would publish a version twice,
publish it incomplete, or make a later family consume an unlanded version is a stop condition
here, not a judgement call.

---

## 1. Stop conditions, discharged

`CAL1-01` may not open a slice while either of the mission plan's Task 1 blockers stands.
Both are discharged, and the evidence is recorded here rather than re-derived per slice.

### 1.1 The growth rounding-residual placement

**Discharged.** `docs/superpowers/decisions/2026-08-25-growth-rounding-residual-placement.md`
carries the owner's confirmation on `main`: the residual is growth-family evidence published
under `rra008.growth.v2`, carried on the growth facts and surfaced through the bundle's audit
representation. No field is added to the persisted package document and `rra004.package.v3` is
not widened. `RRA-004` is satisfied as written through its "when applicable" clause; no
amendment is required.

**This ledger does not restate the reasoning and does not reopen the option space.** Option (a),
moving growth derivation into `build_fact_package`, was rejected on four pieces of code
evidence before the ruling and is not available to any slice.

Two consequences bind the slice map, and they are the decision doc's, not this ledger's:

- **`V-package` no longer spans three tasks.** It is Task 3's package-v3 structural fields plus
  Task 4's coverage signatures, daily bases and projections. Task 5 contributes nothing to it.
- **`V-growth` owns the residual whole**, with its reason code, audit representation and
  bilingual wording in the same slice, per the same-slice rule.

### 1.2 Task 2's independent oracle

**Discharged.** PR #282 landed `tests/rra_calculation_oracle.py` at `f68a7ce` — "the independent
calculation oracle the seven CAL1 slices prove against" — with `tests/test_rra_calculation_oracle.py`
proving its internal consistency. It supplies the clean two-store/two-period dataset, the messy
legitimate cases, the adversarial cases, the regression proofs with no production counterpart,
and the growth/residual cases, as hand-derived literals that call no production aggregation or
analysis helper.

**The shared oracle is done once; the failing tests are not.** Per the mission plan's Task 2
closing rule, each slice adds its own verified-RED cases immediately before its GREEN, drawing
expected values from this module. `V-mapping` therefore adds only `V-mapping`'s RED cases. A
branch carrying committed failures for `V-package` through `V-concentration` could not produce
the green gate the handoff requires.

---

## 2. What is already on `main`, and what it means for this slice

Read from `739d474`, not assumed. This is what stops `V-mapping` from re-doing landed work.

| Artifact | State on `main` | Consequence for `V-mapping` |
|---|---|---|
| `src/khepri/rra/versions.py` | The gate exists: `ADMITTED_PACKAGE_PAIRS`, `ADMITTED_FAMILY_PAIRS`, `admits_package`, `admits_family`, and both reason codes | The gate is **not** built in this slice, and this slice **adds no row** (§4.1). It proves the gate now refuses |
| `facts.py:351` | Calls `admits_package`; refuses at package scope | Seam wired. This slice fixes *which* mapping version it reads -- see below |
| `bundle.py:1564` | Calls `admits_family`; refuses one family, leaving others standing | Seam wired at the correct scope per `RRA-008` |
| `src/khepri/rra/source_contract.py` | The governed vocabulary and contract model exist | Not consumed anywhere. This slice **wires it into the profile route and `build_mapping`** |
| `src/khepri/rra/coverage.py` | Manifest model, binding, and `source_contract_digest` validation exist | No route, no storage, no ingestion. This slice **builds the ingestion path** |
| `mapping.py:21` | `MAPPING_VERSION = "rra003.mapping.v2"` | This slice moves it to `v3` |
| `facts.py:60-61` | `rra004.package.v2`, `rra004.formula.v1` | **Unchanged by this slice.** They are `V-package` and `V-formula` |
| `analysis/*.py` | All four families at `rra008.*.v1` | **Unchanged by this slice** |

**One defect fixed in the gate, and it is not a widening.** `facts._build` received a
`RetailMapping` carrying its own `mapping_version` and then asked the table about the
`MAPPING_VERSION` module constant. `versions.py` says the gate enforces "that the versions a
result actually **combines** were authorized to appear together", and the mapping actually
combined is the object's -- so a package built from a `v2` mapping object was being checked as
though it were `v3`. `_build` now reads `mapping.mapping_version`; the module import it no longer
needs is dropped. **No row is added and no pairing is admitted that was not admitted before**, and
the full suite is unchanged at the 3250-passing baseline, which is the claim the fix makes.

It also creates the seam §4.2 assumes: a test moves one version by restamping the mapping it
hands the builder, rather than by patching a module global. `test_rra004_version_gate_wiring`'s
assertions are replaced on that seam, not relaxed -- the refusal proved is the same one, now
reached the way production reaches it.

**The mission plan's Task 3 bullet "add the fail-closed version compatibility gate, whole, in
this slice" is satisfied by construction, not skipped.** The gate landed early, in PR #273, at
both seams with fail-closed membership semantics. What that bullet still requires of `V-mapping`
is the part that cannot land before the version moves: **the RED proof that the gate fires at
each seam, and the mutation evidence that it can fail.** The table's `v3` rows are *not* this
slice's -- each belongs to the slice that publishes the version naming it (§4.1).

---

## 3. Slice boundary — the `V-mapping` contents

`V-mapping` publishes exactly `rra003.mapping.v3`, complete. It publishes no other governed
version.

### In scope

1. **Every admission change `rra003.mapping.v3` governs.** `RRA-003` states the version governs
   "the semantic declarations, event and canonical transaction identities, **normalized
   measures**, currency, and coverage-manifest confirmation in this specification". So:
   - semantic declarations and the source contract as the basis of admission;
   - event identity and canonical transaction key construction;
   - **normalized measures** — revenue and returns, discounts, cost and gross-profit inputs,
     units;
   - one uppercase ISO 4217 currency for monetary facts, with no conversion;
   - proven void/cancelled exclusion, and refusal of dependent populations on unknown
     event/status;
   - coverage-manifest confirmation.
2. **The source contract on `POST /api/v1/beta/profile`** — a required `extra="forbid"` object,
   persisted with its digest inside the existing profile document JSON, bound to the profile.
3. **`build_mapping` deterministic from profile plus contract**, stamping `rra003.mapping.v3`.
4. **The coverage-manifest document, its binding, and its production ingestion path** — route,
   schema, storage — because `RRA-003` puts manifest confirmation in this version. Validated on
   *use*, not only on write.
5. **The version-gate proof that the pairing is now refused**, at both seams, with mutation
   evidence. **`V-mapping` adds no row to `ADMITTED_PACKAGE_PAIRS`** — see §4.1.
6. **The browser journey**, carried with the contract in this slice.
7. **Governed reason codes with complete accepted Arabic and English wording**, audit
   representation, and surface propagation at the scope each refusal actually reaches (§6.2).

### Out of scope — and where each piece goes instead

- Package-v3 structural fields → `V-package`. Task 3 produces them; they merge with `V-package`
  so `rra004.package.v3` publishes once, complete.
- Core formula rows → `V-formula`. `rra004.formula.v2` is one version over `RRA-004`'s single
  core-formula table and lands as one slice.
- All four `RRA-008` families → their own slices, after `V-formula`.
- The growth residual → `V-growth`, per §1.1.

### Where each admission rule actually lives

`RRA-003` assigns these rules to `rra003.mapping.v3` **semantically**. Their **runtime**
locations are not all in `mapping.py`, and the difference decides which files this slice must
touch. Read from `739d474`:

| Rule | Runtime location today | Why not `mapping.py` |
|---|---|---|
| Column → semantic resolution | `mapping.py` `build_mapping` | This is what mapping does |
| Declared column overrides inference | `mapping.py` `_declared_over_inferred` | Same |
| Event kind, status, currency **semantics** | **nowhere** — `mapping.py` has no such semantic | `SEMANTIC_*` covers date, revenue, units, transaction id, product, category, store, channel, cost, discount, returns. There is no event-kind, status, or currency semantic to resolve |
| Void/cancelled row **exclusion** | **nowhere** | Mapping resolves columns to semantics; it never filters rows. Exclusion must happen where the frame is read |
| One ISO 4217 currency for monetary facts | **nowhere** | Same: a per-row check over the frame |
| Reading the rows | `facts.py` `_measures` | Reads columns straight off the mapping |

Verified by search: `status`, `void`, `cancel`, and `currency` appear nowhere in
`aggregates.py` or `admissibility.py`, and no such semantic exists in `mapping.py`.

**So `_declared_over_inferred` is a stub, not most of the way there.** It re-points
`transaction_id` and nothing else, because `transaction_id` is the only one of these rules that
already had a semantic to re-point.

**Consequence for the module boundary.** Row admission does not belong in `mapping.py`, and not
only for tidiness: CodeScene already reports that module at mean cyclomatic complexity **4.50
against a threshold of 4**. Adding event-kind, status, currency and basis admission there earns a
`degraded` verdict and a refactor mid-slice. The admission rules land in their own module
consuming profile plus contract, with `mapping.py` keeping column resolution and `facts.py`
consuming the admitted result.

**Boundary proof.** `rra003.mapping.v3` is published by exactly one slice — this one — and every
task contributing to it is inside this slice, including the rules above whose runtime home is not
`mapping.py`. No admission rule the version governs is deferred: the normalized measures are here
rather than split into `V-formula`, because `RRA-003` names them as admission and only the
`RRA-004` formula *rows* are `V-formula`. Splitting a measure's admission out of `V-mapping`
would publish `mapping.v3` incomplete.

### Outstanding inside `V-mapping`

Recorded here rather than left as a placeholder in code, so the slice cannot reach its final PR
believing these are done:

- **The transaction-date requirement has no refusal.** `RRA-003` lists a transaction date first
  among the fields a normalized event carries, and `admission.py` does not refuse a row lacking
  one. The date is resolved as a mapped semantic and read by the comparison windows downstream,
  so the refusal belongs where those windows are selected rather than duplicated at admission.
  `AdmittedEvent` therefore carries no `day` field: one that always held `None` would read as
  done while lying to its first caller.
- **The coverage-manifest ingestion path** — route, schema, storage — is still absent. `RRA-003`
  puts manifest confirmation inside `rra003.mapping.v3`, so it cannot be deferred past this
  slice.
- **The browser journey and the bilingual wording** for every refusal this slice introduces.

### The slice is one publication, not one pull request

**`V-mapping` lands as a sequence of PRs, of which only the last moves the version.** The
one-version-per-slice rule constrains *publication*: `rra003.mapping.v3` must be published once,
complete, by this slice. It says nothing about how many pull requests contribute the plumbing
that precedes the publication, and `governance/CONSTITUTION.md` Article IV — product code admitted
"only in small, independently verifiable slices" — actively favours the split over one PR
carrying admission, ingestion, journey and wording together.

What makes this safe is §4.2's ordering: **the version constant moves in the final PR.** Until it
does, no intermediate PR publishes a governed version, so none can publish `mapping.v3` early,
twice, or incomplete — the three failures the rule exists to prevent. Each PR is independently
verifiable on its own terms: the suite stays green at its baseline, and the behaviour it adds is
proven by its own tests.

The stop condition is unchanged and worth restating: **no PR in this sequence may move
`MAPPING_VERSION` before the slice is complete**, and the PR that does move it carries every
admission rule the version governs.

---

## 4. Two facts that size this slice

### 4.1 `V-mapping` adds **zero** rows to `ADMITTED_PACKAGE_PAIRS`

The one-version-per-slice rule decides row ownership, and it is worth stating because "add the
gate's `v3` rows" reads like this slice's job and is not.

A row in `ADMITTED_PACKAGE_PAIRS` is a `(mapping, package, formula)` **triple**, so the row that
admits `rra003.mapping.v3` is `(mapping.v3, package.v3, formula.v1)` — a row naming a package
version that does not exist until `V-package`. `V-mapping` cannot add it without publishing
`package.v3`'s identity early, which is the defect the whole slice map exists to prevent.

So each slice adds the row that its own published version makes expressible:

| Slice | Row it adds |
|---|---|
| `V-mapping` | **none** |
| `V-package` | `(mapping.v3, package.v3, formula.v1)` |
| `V-formula` | `(mapping.v3, package.v3, formula.v2)` |
| each `RRA-008` family | its own `(formula.v2, family.v2)` pair |

`V-mapping`'s gate work is therefore entirely **proof**: that moving the mapping makes the
pairing unlisted, that both seams refuse at the right scope, that no fact publishes under the
predecessor identity, and that the comparison can fail (mutation evidence). It also **does not
touch** the existing `("rra003.mapping.v2", "rra004.package.v2", "rra004.formula.v1")` row —
that row names a combination already published under a stable identity and is immutable, per
`versions.py`'s own rule that a slice "never edits a row another slice put here".

This is what makes the refusal window in §6.1 a *consequence of correctness* rather than an
oversight: the window is open for exactly as long as it takes the consumer slices to land their
own rows, and `V-concentration` closes it.

### 4.2 The refusal window's blast radius is the slice's dominant test effect

Measured on `739d474`, not estimated:

- **68** test files build packages or drive `/api/v1/beta/facts` / `/api/v1/beta/reports`.
- **27** of them call `build_fact_package` directly.
- Only **5** name a version identifier at all; `test_rra004_version_compatibility.py` is the
  only one carrying the `rra003.mapping.v2` literal.

`facts._build` calls `assert_versions_admitted(mapping_version=MAPPING_VERSION, ...)` reading the
**module constant**. So moving that constant to `v3` does not require touching 68 files to
propagate a value — every one of them picks it up automatically — but it does mean **every
package build in the suite begins refusing** the moment the constant moves, until `V-package`
lands its row.

**That is the real cost of this slice, and it is a test-expectation migration, not a code
migration.** Each affected test either asserts the governed refusal or pins its versions
explicitly to the immutable v2 triple to keep proving the behaviour it was written for. M8
demands a green full `pytest` against the 3250-passing baseline, so this work is inside
`V-mapping` and is scheduled as its own step (M7a) rather than discovered during M2.

**It does not split the slice.** `rra003.mapping.v3` still publishes exactly once, from one PR;
the migration is that publication's blast radius, not a second governed version. A slice that
deferred it would hand `V-package` a red suite it did not cause.

## 5. Task order

RED before GREEN throughout, per `superpowers:test-driven-development`. Expected values come from
`tests/rra_calculation_oracle.py`; production helpers never generate their own oracle.

| # | Step | Gate |
|---|---|---|
| M1 | Source-contract wire-up: required object on the profile route, persisted with digest, bound to the profile | RED: request without contract refuses; contract mismatch on read refuses |
| M2 | `build_mapping(profile, contract)` deterministic; `MAPPING_VERSION` → `rra003.mapping.v3` | RED: mapping stamps v3 and derives from the contract, not inference |
| M3 | Normalized measures: revenue/returns, discounts, cost inputs, units; currency; void/cancelled exclusion; canonical transaction keys; unique-key or line-grain attestation | RED per rule, literals from the oracle |
| M4 | Coverage-manifest ingestion path: route, schema, storage, binding validated on use | RED: missing manifest refuses; attested zero-activity accepted; wrong contract identity refuses |
| M5 | Version-gate proof at both seams + mutation evidence. **No row added** (§4.1) | RED: gate fires with the mapping moved; mutation kills a named comparison |
| M6 | Journey: collection surface, `upload.js` both call sites, `ApiError` body preserved, `review.js` renders the governed reason | RED: normal upload reaches the **governed bilingual refusal naming the pairing**, not a 422 and not a stranded page |
| M7 | Bilingual wording, audit representation, surface propagation for every code introduced | RED: wording parity; audit carries each code |
| M7a | Refusal-window test migration across the 27 package-building files (§4.2) | Each asserts the governed refusal, or pins the immutable v2 triple to keep proving its original behaviour |
| M8 | Full regression + `uv run khepri-gov validate` + `uv run ruff check .` + `uv run pytest` | All green before handoff |

**`tests/test_rra004_version_gate_wiring.py` must go red at M5, by design.** It asserts today's
gate behaviour, including that the v2 triple is the only admitted pairing. When the mapping
moves, its expectations change. **Replace the assertion; never relax it** — and specifically
never widen `ADMITTED_PACKAGE_PAIRS` to make a red test pass, which would silently grant the
pairing this slice is proving must be refused. A red test here is confirmation the gate works;
rewrite it to assert the new governed behaviour and keep the mutation evidence that it can fail.

---

## 6. Two rules this slice must not get wrong

### 6.1 The refusal window is expected, and its acceptance criterion is the refusal

After M5, `rra003.mapping.v3` against `rra004.package.v2` is an **unlisted pair**, so
`packages.py` refuses. `journey/assets/review.js` posts `/api/v1/beta/facts` before
`/api/v1/beta/reports`, so **the journey cannot reach a report while the window is open.** An
acceptance criterion demanding one would be unmeetable by construction, and the only ways to
meet it — removing the gate, or co-landing the consumer successors — are both ruled out.

So the criterion for M6 is: **a normal browser upload reaches the governed bilingual refusal
stating which version pairing was refused** — not a 422, not a stranded page. A 422 from a
missing contract and a stated refusal from an unadmitted pairing are different outcomes, and the
journey must produce the second. `V-concentration` empties the refusing set and restores the
report criterion; the last slice carries that assertion.

### 6.2 Which refusal owes what

The gate straddles two seams and they fire in different places, so they owe different things.

- **Mapping/package/formula** → caught while the package is built → `PackageRefused`. Owes a
  structured bilingual refusal in the response, an **audit record**, and a client that
  **preserves and renders it** on review. It does *not* owe bundle/narrative/chart/HTML/PDF/Excel
  propagation, because no package and no report exist to propagate into.
- **Family against formula** → must be a `RefusedResult` in `bundle.py` → owes the propagation
  rule **in full**: bundle, narrative, chart, HTML, PDF, Excel. `RRA-008` requires that a failure
  refuse "only dependent results, leaving independently answerable facts and the rest of the
  report intact", and the shrinking refusing set is only meaningful if families refuse one at a
  time.

**The roadmap's account of the package-level debt is out of date, and the difference matters
because it changes what this slice still owes.** The roadmap (line 512) records that "the four
raises in `packages.py` pass plain English strings into a bare `ValueError` subclass with no code
and no audit hook". Read at `739d474`, that is no longer true of the seam this slice depends on:

- `assert_versions_admitted` raises `PackageRefused` carrying the governed reason code
  `REASON_PACKAGE_VERSION_UNADMITTED` and all three version identifiers, and
  `packages.package_refused_detail` matches **on the reason code, not on prose**, replacing it
  with `PACKAGE_UNAVAILABLE` at the `409` boundary so an Internal-tier string cannot leak.
- The other three raises still carry fixed customer-safe prose with no governed code.

So the version-gate refusal already has its code and its wording seam. **What is still missing,
and is therefore `V-mapping`'s to add:** the *bilingual* customer wording under `RRA-009` (the
current path yields one English sentence), the **audit representation** of the refusal, and a
client that **preserves and renders** it — `common.js`'s `ApiError` keeps only the HTTP status
and discards the body (verified at `common.js:2-13`), and `review.js` prints one fixed sentence,
so the governed reason cannot reach the review page today.

That client gap is exactly what M6's criterion (§6.1) fails on if left alone: the journey would
show a generic sentence rather than a refusal *stating which pairing was refused*. Carrying
`ApiError`'s body and rendering it is in scope here, not deferred to `CAL1-11`.

The remaining debt is **pre-existing, not a blessed precedent** — this slice may not cite it to
excuse its own codes.

---

## 7. Handoff

- `uv run khepri-gov validate`, `uv run ruff check .`, `uv run pytest` all green, from this
  worktree, with output read rather than assumed.
- No governance lifecycle state changed in this PR; the registry is authoritative.
- Local evidence claims nothing about the benchmark, image, or CodeScene gates — those are CI's.
- Historical mapping-v2 and package-v2 artifacts remain immutable and are not reinterpreted.
- One PR against fresh `origin/main`, publishing `rra003.mapping.v3` and no other version.
