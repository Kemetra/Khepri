# `G4-01` — Comparison use cases and the supported period/dataset semantics

**Authority:** none of its own. This note is **product scope**, not a governed artifact. It reads
`RRA-008` (active), `RCA-005` (active), `KHEPRI-DEC-033` (active) and `KHEPRI-DEC-031` (active), and
decides nothing any of them left open.
**Roadmap:** `G4-01`, first incomplete item on the critical path (§17 item 19). Its `M3` dependency
was measured at `c98e946` (§17 item 18).
**Raised on:** `main` at `befd95a`, after `#393` closed the one finding the `M3` drive produced.
**Consumed by:** `G4-02` and `G4-03`, which are owner-authored and are where this scope acquires
authority — or is rejected. Nothing may be built from this note alone.

---

## 0. Why this is a note and not a decision

The roadmap says `G4-01` "may be drafted as a **proposed** artifact on the `KHEPRI-DEC-034`
precedent." **That sentence is wrong on three independent grounds**, and this note corrects it in
§7 rather than acting on it.

1. **There is no `proposed` state.** `ARTIFACT_STATES = {"active", "retired"}`
   (`src/khepri_gov/validator.py:15`), and the Constitution's Lifecycle section says drafts and
   proposals "live on branches and pull requests, **not in the authoritative lifecycle**." What
   `#386` actually did was register `KHEPRI-DEC-034` as `active` on a branch, where the *branch*
   made it a proposal and the *merge* made it approved. `#389` then existed only to delete the
   "not approved by its own existence" banner that its own merge had falsified.
2. **There is no host specification.** A new `specification` row must "depend on exactly one family"
   (`validator.py:302-308`), so authoring comparison scope as a spec forces a choice between `RRA`
   and `RCA` — pre-empting the exact split `G4-02` and `G4-03` exist to make. And neither existing
   spec can host it: **`RCA-005` is the artifact that deferred comparison** ("Comparison is
   `G4/C1`'s", Exclusions), so appending comparison requirements there reopens its own exclusion;
   `RRA-008` is family-bound and scoped to "**one** compatible `RRA-004` population."
3. **Article IV governs product code, not scope definitions.** It admits code "linked to an active
   specification." A scope note that writes no code and grants no authority needs no row, and
   `G3-04` — the directly analogous deliverable — is a `docs/` note with an Authority header for
   precisely this reason.

**A fourth ground, recorded because it outlives this note.** Constitution v2.0.0 has Articles I–V.
**Article VII (Privacy and least data) and Article VIII (Delegation) were deleted by `#147`**, and
`Constitution VII` is still cited **16 times** in `governance/` (34 including `docs/`) — including
`KHEPRI-DEC-034` §3's load-bearing "Constitution VII's least-data default decides between them."
Article VIII was the article under which a human authority could delegate approval to a non-human
one. Under v2.0.0 that instrument is gone, and Article I says automation "does not approve changes
or act as a separate authority." **This is named as a finding, not worked around**: it is why this
note claims no authority, and it is §7's recorded item for the owner.

---

## 1. The one question `G4` exists to answer

`RRA-008` already ships period comparison. Its Outcome derives every fact "from **one** compatible
`RRA-004` population and retained basis," and it never mentions dataset versions. So the governed
comparison that exists today is **two periods inside one dataset version**.

`C1`'s comparison is **two dataset versions**. That is not a new calculation — it is a new
*admission*: a run whose input is more than one population. `RCA-005` names the term and reserves
it — "**Comparison run.** Reserved term. A run whose input is two or more dataset versions" — and
assigns it to `G4/C1` while authorizing none of it.

**The whole of `G4`'s scope question is therefore:** which pairs of dataset versions may be
admitted to one run, and what must be true of them before a figure is derived. Everything below is
an answer to that and nothing else.

---

## 2. The four use cases, in priority order

Each is stated as a customer sentence, then the pair it admits. **UC-1 and UC-2 are the scope this
note proposes for `C1`. UC-3 and UC-4 are named to be excluded**, because naming them is how a
later slice is prevented from assuming them.

| # | Customer sentence | Admitted pair | In `C1`? |
|---|---|---|---|
| **UC-1** | "The same report, one period later." | Two versions of **the same source lineage**, same mapping and formula versions, disjoint or adjacent periods | **Yes — primary** |
| **UC-2** | "This branch against that branch, same period." | Two versions, **same period**, differing only in a single governed dimension member | **Yes — secondary** |
| **UC-3** | "This year's file against last year's, after we changed the mapping." | Two versions with **differing `rra003.mapping` or `rra004.formula` versions** | **No — refused** |
| **UC-4** | "All twelve months at once." | Three or more versions | **No — deferred** |

**UC-1 is primary** because it is the one `M3` already leaves a customer wanting: an organization
retains multiple dataset versions (`M3` clause 1, PASS) and multiple analyses (clause 2, PASS), and
can read each one's Passport (clause 3a, PASS) — but nothing puts two of them side by side. The
capability gap is exactly one screen wide.

**UC-3 is refused, not deferred, and this is the load-bearing exclusion.** A mapping or formula
change means the two populations were *measured differently*; a delta across that boundary is a
number with no interpretation. `RRA-008` already refuses less than this — it refuses a comparison
whose counterpart period is merely incomplete — so admitting a cross-version-semantics delta would
make `C1` weaker than the spec it builds beside. `C1-02`'s "mapping drift and versions" detection
is therefore a **refusal path, not a reconciliation path**. See §4.

**UC-4 is deferred** because pairwise is a two-column table and N-way is a chart, which is
`RRA-012`'s presentation layer and a different design. Nothing in UC-1/UC-2 forecloses it.

---

## 3. Supported period semantics

**Inherited whole from `RRA-008`, not restated and not extended.** Its governed window is "one
period at the package's own day or month granularity," PoP uses "the immediately preceding calendar
period," YoY "the exact same calendar period one year earlier," and "nearest observed buckets never
substitute for missing exact counterparts."

`G4` adds **one** period rule, and it is a constraint rather than a capability:

> **P-1. The two versions' periods are compared as stated, never aligned.** If the periods differ in
> length, granularity, or retail-day boundary, the pair is refused. `G4` introduces no truncation,
> no rescaling, and no per-day normalization.

This is deliberately narrower than `RRA-008`, which does truncate two windows "to the same day
count." That truncation is safe *within* one population's retained daily bases; across two versions
it would require reconciling two coverage manifests, which no active artifact authorizes. **P-1 is
the least-data reading**, and it is the rule most likely to be relaxed later by an owner who decides
the truncation is worth its evidence burden.

---

## 4. Supported dataset semantics — the compatibility gate

Six predicates. **All six must hold** before any figure is derived; any failure refuses the pair
with a stated cause and derives nothing. This is `C1-02`'s "fail-closed compatibility contract,"
enumerated.

| # | Predicate | Cause when it fails | Why it cannot be relaxed |
|---|---|---|---|
| **D-1** | Both versions belong to **one organization scope** | cross-organization | `RCA-005`'s isolation invariant; not a comparison question at all |
| **D-2** | Identical `rra003.mapping` version | mapping drift | Different mapping = different measurement (UC-3) |
| **D-3** | Identical `rra004.formula` version | formula drift | Same, and `RRA-008` already hashes formula version into fact identity |
| **D-4** | Identical `rra004.package` shape version | package drift | A shape difference means the two fact packages are not addressable alike |
| **D-5** | Same **currency** and same governed **population** definition | incomparable basis | A delta across two currencies is not a number |
| **D-6** | Both versions' coverage is **complete** for their stated period, per the authoritative `RRA-003` manifest | incomplete coverage | `RRA-008`'s own rule; partial-prefix and sparse cases refuse there and must refuse here |

**D-2/D-3/D-4 together are the version triple** the `M3` ledger found pinned — `rra003.mapping.v3`,
`rra004.package.v3`, `rra004.formula.v2`. That is not a coincidence worth passing over: **the
single-triple image that made `M3` clause 3b unexercisable is the same condition that makes the
common case of `C1` admissible.** A deployment pinning one triple can always satisfy D-2..D-4, so
the refusal paths need fixtures rather than a second image — which is a testing note for `C1-08`,
and the reason this note does not touch the clause-3b question (§6).

---

## 5. What `G4` must *not* decide, and who decides it

| Question | Whose | Why not here |
|---|---|---|
| The comparison **fact** shape, identity, and provenance fields | `G4-02`, RRA specification | `Fact` is an `RRA-004` type; `comparison.py` already records that adding a field to it "is an `RRA-004` type this specification excludes changing" |
| The **orchestration** API, authorization, and run lifecycle | `G4-03`, RCA specification | A comparison run is a run; runs are `RCA-005`'s, and its authority stops at one population |
| **Frozen** input/output, filter, and evidence contracts | `G4-04` | Contracts freeze after both authorities exist, not before |
| Whether a **retained** comparison run is new retained content | Owner, against `KHEPRI-DEC-033` §2's matrix | A comparison run that persists is a new content class — check the matrix row, do not infer it |
| **Telemetry** of any kind | Nobody yet | `RCA-005` bars "any product-telemetry event" and `KHEPRI-DEC-015` §3 is unamended; `W1-11`, `R8-08` and `T1-07` all still wait |

**One obligation this note hands forward.** `comparison.py` records a deferred `RRA-008`
requirement: `COMPARISON_FORMULA_VERSION` "is hashed into every fact identity ... and hashing is not
recording," so "whichever slice first serializes these facts must record
`COMPARISON_FORMULA_VERSION` alongside them. Nothing does today." **`C1-03` is that slice** — it
"builds the immutable RRA comparison fact package," which is the first serialization. `G4-02` should
carry the field, or `C1-03` inherits a governed gap on its first commit.

---

## 6. What this note does not touch

- **`M3` clause 3b.** The `W1-08` Methodology Change Notice reading is open and is the owner's. The
  roadmap states `G4-01` "does not consume the open clause," and it does not: D-2/D-3 **refuse** a
  methodology difference rather than rendering one, so `C1` needs no diff surface and no reading of
  that clause either way.
- **`G4-02`/`G4-03` activation.** Owner-authored, and explicitly "not this queue's to schedule."
- **Any `C1-0n` slice.** All eight sit behind `G4-04`'s frozen contracts.
- **The `OPS1-02`..`OPS1-03` hosted environment**, still deferred by `KHEPRI-DEC-031` §4.

## 7. Two things for the owner

1. **Roadmap item 19 and the §16 status row say `G4-01` "may be drafted `proposed`."** Corrected in
   this PR to say what the Constitution and the validator actually permit — §0 gives the three
   grounds. No status changes: `G4/C1` stays `READY_FOR_PLAN`, and `G4-01`'s next step is still
   `G4-02`/`G4-03`.
2. **`Constitution VII` is cited 16 times in `governance/` — 34 including `docs/` — and does not exist**, and Article VIII (Delegation) is
   likewise deleted — both by `#147`. This is a governance-integrity finding, **not** fixed here:
   restoring an article, or rewriting those citations, is owner work and neither belongs in a scope
   note. `KHEPRI-DEC-034` §3 is the citation most worth checking first, because its least-data
   reasoning rests on the missing article.
