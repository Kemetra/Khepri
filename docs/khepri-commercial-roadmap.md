# Khepri commercial roadmap: private beta to sellable analysis service

- Drafted at: 2026-08-04
- Base commit: `0b1ae35` on `main`
- Inputs: `docs/khepri-capability-audit.md`,
  `governance/decisions/KHEPRI-DEC-012-transformation-and-orchestration-boundary.md`
- Status: **advisory plan, not a governed artifact.** It approves nothing, records no approval,
  creates no authority, and authorizes no implementation. Every phase names the governance
  artifact that must be approved before its code may be written.

## Target

A service sold to **retail chains and mid-market operators** and to **agencies and
consultants**, whose differentiator is **auditable, defensible analysis**.

## The one-paragraph strategy

Khepri's moat is not the report; it is that every number on every surface is traceable to one
immutable versioned package, that no uncited claim survives validation, that the same input
reproduces the same bundle identity, and that a partial render is recorded as a refusal rather
than delivered as a report. That is built and tested today (1,273 tests) and it is invisible to
a buyer. The commercial task is to make it visible and to remove the two limits that stop a
paying customer from getting value — one dataset per session, and a seven-day expiry that
deletes the baseline any comparison needs. Neither limit is an orchestration problem, and
`KHEPRI-DEC-012` settles that no scheduler is coming to fix them.

## What "too traditional" actually costs, and what it does not

The pipeline is linear, and `KHEPRI-DEC-012` records why that is a safety property rather than
an unfinished design. Nothing in this roadmap proposes making it a graph.

What genuinely limits the product:

| Limit | Consequence for a paying buyer | Nature |
|---|---|---|
| One dataset per session, ever | A chain cannot ask "how did this month differ from last?" | Retention and tenancy |
| Seven-day expiry | The comparison baseline is deleted before it is needed | Retention |
| Pseudonymous single-use invitation | No durable customer, so nothing to bill | Identity |
| No portfolio or client switching | An agency cannot serve its own clients | Tenancy |
| Moat invisible in the product | The thing worth paying for is never seen | Presentation |

Every row is governance-gated before it is code-gated.

---

## Phase map

Phase 0A-gov and 0B are governance. **0A-spend is real money** and is separated for that reason.
Phase 0C is withdrawn (see below). Phase 1 is the first code a buyer would notice. Sequencing is chosen for earliest
revenue signal, not architectural completeness.

| Phase | Name | Gate artifact | Parallel with |
|---|---|---|---|
| **0A-gov** | Accept DEC-008, select the target | DEC-008 accepted + target-selection artifact | 0B |
| **0A-spend** | Provision and benchmark | Owner authorizes ~174-235 USD/month | 0B |
| **0B** | Charter the commercial family | New family + superseding decision | 0A |
| ~~**0C**~~ | ~~Test the thesis with a mock~~ — **WITHDRAWN 2026-08-06** | — | — |
| **1** | Business-first reporting layer + separated audit evidence | Design package approved, then spec under new family | — |
| **2** | Durable identity and workspaces | Specs; supersedes RRA-001 boundary | — |
| **3** | Multi-dataset accumulation | Spec; the actual product unlock | — |
| **4** | Commercial: pricing, billing, quotas | Spec | 5 (partly) |
| **5** | Public surface and onboarding | Spec | 4 (partly) |
| **6** | Agency tenancy | Spec | — |
| **7** | Recurring delivery | Spec; needs `scheduling` unblocked | — |

---

## Phase 0A — Unblock the runtime

**Why first.** Khepri has no approvable deployment path. `KHEPRI-DEC-005` is `accepted` and
names AWS `me-central-1`, which `KHEPRI-DEC-008` prices at ~675 USD/month and states the owner
cannot fund. `KHEPRI-DEC-008` replaces it with a provider-neutral capability contract but is
`proposed`. Its own fail-closed chain: no approved target-selection artifact → no deployment
definition → no environment → no benchmark evidence → no beta authorization. This blocks the
**beta**, before anything commercial. Nothing else in this roadmap can be demonstrated to a
customer until it clears.

**The affordable number, which is the decision-relevant one.** 675 USD/month is the figure
`KHEPRI-DEC-008` exists to escape, not the figure this phase costs. The same decision
(`KHEPRI-DEC-008:16-18`) prices a cost-shaped AWS environment at roughly **178 USD/month** and a
DigitalOcean equivalent at **174 to 235 USD/month**, and states plainly that "the provider
question is not decided by the monthly figure. It is decided by the owner's judgment about the
commercial phase." Project memory records that provisioning was declined on cost at the 675
figure. Whether ~200 USD/month is fundable is a different question and is the owner's to answer —
this roadmap does not assume the answer, which is why 0A-spend is a separate gate.

**Verify before trusting the range.** Those figures were priced on 2026-08-02. Re-price before
authorizing spend; a published rate is a fact with an expiry date.

**Gate.** `KHEPRI-DEC-008` reaches `accepted`, then the target-selection artifact it mandates is
written and approved. DEC-008 fixes that artifact's required content: provider and region;
residency justification; the concrete product satisfying each capability with exact versions;
confirmation that the object store's expiry, deletion, and multipart-abort semantics satisfy
`RRA-002`; recorded RTO and RPO; and the sizing values DEC-008's rules require.

**Two different gates, easily conflated.** Accepting `KHEPRI-DEC-008` is **not** a spending
decision. The decision says so in its own words: "It does not select a provider, a region, or a
residency commitment. It does not authorize provisioning, deployment, or beta launch." It replaces
provider-specific products with a capability contract and authorizes the portability slices to be
written. What it costs is nothing.

Accepting it is gated by **authority** — Constitution II reserves approval of an architecture
decision to a named authority, and automation approves only as a named delegate within a recorded
delegation. Provisioning is gated by **money**. Keeping those separate matters, because conflating
them makes an approval look expensive when the expensive step is two artifacts later.

**Steps — 0A-gov (no spend).**

1. Owner reviews and accepts `KHEPRI-DEC-008`. Approval evidence is a GitHub issue comment, then
   a PR transcribing it; the approval package and the registry flip land in one commit.
   `KHEPRI-DEC-005` and `KHEPRI-DEC-007` move to `superseded`, retaining their approval evidence.
2. Write the target-selection artifact. Per project memory the practical target is DigitalOcean;
   DEC-008 deliberately declines to name it, so this artifact is where it is named and residency
   is justified.
3. Execute DEC-008's follow-on obligations, each an independently verifiable slice: replace the
   SQS adapter with PostgreSQL claim-and-redrive; replace the five provider-header proofs with
   envelope encryption and read-back digest verification; unlock `runtime/config.py` from
   `me-central-1`, the account identifier, and the KMS key ARN; re-issue
   `KHEPRI-BMK-001-sizing.yaml`; add `superseded_by` to the decisions registry and validator.

These are code slices, but they are *portability* slices against an approved decision. They need
no environment and cost nothing to run.

**Steps — 0A-spend (the first real money in this roadmap).**

4. Owner authorizes provisioning at the re-priced monthly figure. This is a decision, not a task.
5. Provision the selected target and run the DEC-006 benchmark on it: 40 datasets, ≥95% complete
   bundles within ten minutes, integer-exact threshold.

**Exit criterion.** A deployed environment exists, the benchmark passes on it, and beta
authorization is possible.

**Kill test — run it in step 5.** If the benchmark cannot hit 95%-within-ten-minutes on affordable
hardware, the unit economics of the whole service are wrong and every later phase is built on sand.
Chromium is the largest single memory consumer and does not shrink with dataset size (DEC-008
sizing rules). Run this before writing any commercial code.

**Note on ordering.** 0A-spend is the only phase whose gate is money rather than an artifact. If
the owner defers it, 0B still proceeds and Phase 1 can be specified — but nothing can be
*demonstrated*, so revenue stays blocked. Deferring it is a legitimate choice with a stated cost,
not a failure.

**What could kill the business.** An affordable target that cannot meet the latency objective
forces either a price the target buyers will not pay or a weakened objective, and DEC-003
forbids weakening controls to improve latency.

---

## Phase 0B — Charter the commercial family

**Why separate from 0A.** It shares no files and no evidence with 0A and can proceed in
parallel. It is the gate for every phase from 1 onward.

**The blocking fact.** `governance/families/RRA.md` excludes commercial authentication, user
profiles, persistent customer workspaces, organizations, membership roles, billing,
subscriptions, scheduling, public signup, agency portfolios, client switching, delegated access,
work queues, and white labeling. **Every capability both target buyers need is on that list.**
`AGENTS.md` forbids implementing ahead of an approved specification, so no billing or signup
slice can be authorized today. Two reference reviews already surveyed this ground and deferred
it — `BATCH-04` (commercial identity, persistent workspaces, report history) and `BATCH-09`
(agency portfolios, delegation, work queues, white labeling) — as technical evidence carrying no
approval.

**Recommended shape: a new family, plus a minimal re-scope of RRA.md.** Deleting `RRA.md`'s
exclusions and putting commercial capabilities there would leave one family document asserting both
"invite-only pseudonymous beta" and "commercial multi-tenant service," which is the drift
Constitution I forbids. A new family — call it **RCA, Retail Commercial Analysis** — depending on
`RRA` and `FND` keeps lineage clean and matches how `FND.md` and `RRA.md` already carve
responsibility.

But `RRA.md` cannot be left entirely untouched, and claiming otherwise would reintroduce the same
drift by a different route. Its exclusions are written as flat prohibitions — "billing,
subscriptions, scheduling, and public signup" are *excluded*, full stop. Once RCA is active and owns
billing, "billing is excluded" is ambiguous between excluded-from-RRA and excluded-from-Khepri, and
Constitution I requires one authoritative representation per governed fact. Note that `FND.md`
already solves this correctly: it excludes "responsibilities of future product families" and says
those boundaries "require separately approved families." `RRA.md` should adopt the same phrasing.

**Steps.**

1. Draft a decision superseding `KHEPRI-DEC-003`'s beta boundary, stating what commercialization
   authorizes and what it still refuses. It must not silently relax RRA-001/002 privacy
   controls — say explicitly which survive unchanged (encryption, isolation, deletion-on-demand,
   content-free evidence) and which are replaced (pseudonymity, seven-day expiry, single-use
   invitation).
2. Draft `governance/families/RCA.md` with Owns and Excludes, following the `RRA.md` and `FND.md`
   pattern. Its Excludes should still hold a line: forecasting, customer-authored formulas, and
   generic non-retail analysis stay out.
3. Re-scope `RRA.md`'s Excludes from flat prohibitions into family boundaries, following `FND.md`'s
   existing phrasing ("responsibilities of future product families... require separately approved
   families"). This is an edit to an approved family document and belongs in the same approval
   package as the RCA charter, so that no moment exists where both documents claim the same
   capability.
4. Add both to the registries with `depends_on: [FND, RRA]` and no approval evidence.
5. Owner approves via the DEC-004 atomic approval package mechanism. Per project memory, evidence
   is a GitHub comment first — bare issue URLs are rejected — then a PR transcribing it, with the
   package and registry flip in one commit.

**Exit criterion.** `RCA` is `active` in `families.yaml` with approval evidence, and the
superseding decision is `accepted`.

**Kill test.** Write the pricing page copy before writing the family charter. If you cannot
state in three sentences why a chain pays monthly for this, the charter is premature.

---

## Phase 0C — WITHDRAWN by owner election, 2026-08-06

**The owner has elected not to conduct prospect interviews, and this phase is withdrawn rather
than deferred.** Recorded as the withdrawal of **G5** in
[`platform/cross-repository-pr-sequence.md`](platform/cross-repository-pr-sequence.md) §0, which
stays the single statement of gate status. It is written down rather than deleted because the same
document records why: a gate removed without a record is later indistinguishable from a gate that
never existed.

**This is a legitimate election, and it was always available.** Phase 0C was *ungated* — nothing
ever blocked it, and it needed no code, charter, environment, or approval. It gated `[SPEC-REPORT]`
and nothing else. Withdrawing it therefore costs no schedule and blocks nothing.

### What the withdrawal costs, stated plainly

The sequencing argument in this roadmap rested on auditability being what a buyer pays for. **No
prospect in either named segment has been spoken to, and none now will be.** That premise is
therefore permanently an assumption rather than a finding, and every phase from 1 onward is
sequenced around a differentiator that has not been tested against a buyer.

The specific exposure, which is worth carrying explicitly:

- If auditability is a **hygiene factor** rather than a purchase driver, phases 1 through 7 are
  ordered around the wrong thing, and the product competes on report quality alone — where a
  generic pipeline plus a good prompt is a real competitor.
- The failure would surface at **first paid sale attempt** instead of after a few conversations.
- What prospects would have reacted to *instead* of auditability is now unknown, and that list was
  the roadmap's most valuable missing input.

**No re-sequencing is implied.** The roadmap's order stands as written; it simply stands on
judgment rather than evidence. That is the owner's call to make, and it is recorded here so a
later reader does not mistake an untested premise for a validated one.

### What survives the withdrawal

- **The static golden sample exists** — `docs/reporting/golden-sample/` holds HTML, PDF, and XLSX
  on a fictional dataset, plus `verify_separation.py`. It was never gated and is not withdrawn.
- **G4 — golden-sample approval, including the Arabic copy review — is unaffected.** It is a
  review of an artifact that already exists, not an interview, and it still gates `[SPEC-REPORT]`.
  It is now the **only** thing between the owner and the report layer.
- **The kill tests in later phases stand**, minus their references to prospect conversations.

**Exit criterion.** None. The phase is withdrawn, not pending.

**If the owner later wants the evidence**, nothing prevents it: the phase was ungated and the
sample still exists. Reviving it needs no approval, only a decision.

---

## Phase 1 — Create a business-first reporting layer with separately accessible governed audit evidence

**Why before tenancy.** It is the cheapest *code* phase, needs no schema change, and it builds the
artifact the golden sample already mocks. Doing it before tenancy means the deliverable is sellable
before the expensive retention and identity work is committed.

**Phase 0C is withdrawn, so nothing tests the hypothesis before this phase ships.** This phase now
proceeds on the untested premise that auditability is what a buyer pays for. Its only remaining
gate is G4, the golden-sample approval.

**The problem — restated 2026-08-04 after owner review of the generated outputs.** The earlier
framing of this phase was "make the moat visible," on the assumption that the provenance data
existed but was not surfaced. That was wrong in an important way: **the provenance is already
surfaced, and it is surfaced in the wrong place.** The HTML, PDF, and Excel outputs are
structurally technical audit ledgers. The primary customer report exposes figure identifiers,
citation identifiers, raw metric codes, raw unit-kind codes, section states, refusal codes,
caveat codes, and full bundle provenance — in the report body, styled as machine identifiers.

So the defect is not missing visibility. It is **missing separation**. A report ordered by
computation mechanism, addressed to a reader who wants findings, does not become a business report
by translating its identifiers into prose — it becomes a translated technical report.

**Not "surface refusals." Not "fill the wording table."** Both were considered and both are too
narrow. Filling `rendering/wording.py` addresses the vocabulary and leaves the information
architecture untouched.

**The design package, approved before implementation.** Three documents plus a golden sample:

| Document | Contents |
|---|---|
| `docs/reporting/presentation-visibility-matrix.md` | Every rendered field classified Business / Audit / Internal |
| `docs/reporting/business-report-information-architecture.md` | Customer-facing structure for HTML, PDF, Excel |
| `docs/reporting/refusal-presentation.md` | The five-part customer refusal contract; the 13-code catalog |
| `docs/reporting/golden-sample/` | HTML, PDF, XLSX mocks on one fictional dataset |

**Steps.**

1. **Split the presentation into two layers.** A business report that leads with findings, and a
   governed audit-evidence layer carrying every identifier. Separate page in HTML, appendix after
   a page break in PDF, final two worksheets in Excel. The audit layer is **generated with every
   report** and is the differentiator, not a debug view; whether the customer's copy *includes*
   it is a render variant of each surface. It is never a delivery-time filter —
   `delivery_persistence.py:346-350` raises `DeliveryCorrupted` on a delivery that does not name
   every required surface. See `docs/reporting/business-report-information-architecture.md` §B.1.
2. **Reorder the business report by decision relevance** — what happened, why, which products or
   branches or periods drove it, the implication, the limitations. Not by bundle section order.
3. **Add the business-name table for governed metrics.** `label` already has a translation path
   (`GOVERNED_FIGURE_LABELS` → `_row_label`); `metric` has none and reaches the page raw. This is
   new work, not a fill-in.
4. **Implement the five-part refusal contract** (`refusal-presentation.md` §D) for all 13
   customer-facing reason codes — 8 section reasons plus 5 result reasons — in Arabic and English.
   Every refusal states whether the rest of the report remains valid.
5. **Word every caveat.** `bundle.py:1324` requires the claimed caveat set to *equal* the bundle's,
   so an unworded caveat is a reconcile failure rather than a cosmetic gap. No opt-out, no subset.
6. **Keep the reproduction receipt** — input digest, package version, bundle identity, and the
   statement that re-running the same input reproduces the same bundle identity. This is what a
   customer forwards to their auditor, and it belongs in the audit layer.
7. **Keep the governed-fact catalog** as an internal product and specification asset. It is not
   the customer report.

**Verified implementation facts** (from `docs/reporting/` §B.6):

- `reconcile` (`bundle.py:1271-1314`) validates the `SurfaceContent` *claim* and never parses the
  rendered document. Relocating a field changes no claim, so **the separation is a pure
  presentation change** and needs no change to the reconcile contract.
- **Deletion is not relocation.** The caveat set, the figure set, and the disclosure
  (`bundle.py:1319-1323`, compared in full) must all survive.
- PDF does not fork: `pdf.py:193` renders through the shared `build_context` and the print
  template *extends* the web template. The appendix is a template block.

**Exit criterion.** A report a retail owner reads for the finding and forwards to their auditor for
the evidence — with no identifier on any page the owner reads, and no figure missing from the page
the auditor reads.

**Kill test.** Phase 0C is withdrawn, so no prospect has seen the mock and there is no baseline to
re-show against. The nearest available substitute is the golden-sample review (G4) against the
*built* surfaces rather than the mock — a real surface carries caveats and refusals a mock can
omit, and that difference is now unobserved by anyone outside the project.

**What could kill the business.** If auditability is a hygiene factor rather than a purchase
driver, the moat does not convert and the product competes on report quality alone — where a
generic pipeline plus a good LLM prompt is a real competitor. Note the sharper risk this
restatement exposes: for the whole of the beta so far the *only* output was the technical ledger,
so any prospect shown it was shown the least sellable form of the product.

---

## Phase 2 — Durable identity and workspaces

**Why here.** Phases 3 through 7 all require a customer that persists. This is the largest
single boundary change in the roadmap.

**What must not weaken.** `RRA-001` and `RRA-002` controls are the substrate of the moat: opaque
identifiers, cross-session isolation failing closed, encryption in transit and at rest, isolated
object namespaces, immediate idempotent deletion, content-free logging. Replacing pseudonymity
with real accounts must preserve every one of them. State that as a specification requirement,
with tests, not as an intention.

**Steps.**

1. Specify commercial identity: accounts, credentials, sessions, recovery. The opaque owner ID
   should survive as the internal boundary key so `assert_same_scope` and every isolation test
   keep working — the new identity maps *to* it rather than replacing it.
2. Specify organizations and membership roles.
3. Specify persistent workspaces: durable storage of inputs and reports beyond seven days, with
   an explicit retention decision per Constitution VII (purpose, owner, boundary, retention,
   approval). This is the clause that makes retention a governance act rather than a config
   change.
4. Specify deletion and export under the new model. Immediate deletion must still work, and
   "delete my account" is now a real operation with a real blast radius.
5. Migration: sibling Alembic migrations become siblings off one parent, so the second to merge
   re-points its `down_revision`. Squash-merging a base branch detaches anything stacked on it —
   replay with `git rebase --onto origin/main <old-base>` rather than merging. State both in the
   PR before they happen.

**Exit criterion.** A customer logs in, sees their own history, and cannot see anyone else's —
with cross-tenant isolation tests as the evidence.

**Kill test.** Before building, write the retention decision. If you cannot state a lawful,
owner-approved purpose and boundary for holding customer retail data indefinitely, the
persistent-workspace phase stops here and the product stays ephemeral.

**What could kill the business.** A cross-tenant leak. It is fatal for a product sold on
defensibility, and agencies multiply the blast radius because one leak exposes their clients.

---

## Phase 3 — Multi-dataset accumulation

**Why this is the actual product unlock.** This is the phase that removes the limit the audit
identified as commercially binding. A chain uploads monthly; the previous period becomes the
comparison baseline instead of being deleted. `RRA-008` already implements period-over-period and
year-over-year comparison — it currently has to find both periods inside one uploaded file.
Accumulation is what makes those analyses ordinary rather than dependent on how the customer
happened to export.

**Steps.**

1. Specify a dataset collection per workspace: multiple inputs, each with its own profile,
   mapping, and provenance, related by a governed time dimension.
2. Specify cross-dataset fact packages, preserving immutability and content addressing. A package
   spanning two inputs must digest both.
3. Specify schema-drift handling — the customer's export format will change, and a silent
   remap is a correctness failure on a defensibility product. Refuse, explain, and offer remap.
4. Extend `RRA-008` comparison to cross-dataset periods.
5. **Add comparable-store ("like-for-like") sales.** Recorded here 2026-08-04 after checking the
   report design against retail reporting practice. This is the metric mid-market retail buyers and
   their lenders read *first*, and Khepri does not compute it. Total revenue growth conflates a
   concept getting stronger with a chain getting bigger: a retailer can post 24% total growth while
   comparable sales fall 3%. It is a **new governed analysis**, not a presentation change, so it
   needs an `RRA-008` family amendment rather than a wording table.

   **Why it lands in this phase rather than Phase 1.** It requires branch-level revenue across two
   comparable periods, restricted to the branches present in *both*. That is exactly the data
   accumulation makes ordinary and that a single upload currently refuses with
   `prior_window_absent`. Building it before accumulation would ship an analysis that refuses for
   most real customers.

   **A refusal it needs.** A chain that opened or closed branches between the two periods has a
   comparable set smaller than its full estate, and a like-for-like figure computed over a
   silently-shrunken set is the exact misstatement this product exists to refuse. Expect a new
   governed reason — provisionally `comparable_set_insufficient` — plus a caveat naming how many
   branches were excluded and why.

**Exit criterion.** A customer uploads a second month and receives a comparison neither upload
could have produced alone.

**Kill test.** Ask two mid-market prospects for two consecutive monthly exports before building.
If the formats differ in ways that break mapping, drift handling is the phase, not a sub-step.

**Where `KHEPRI-DEC-012` gets revisited.** This phase creates the durable multi-dataset store
that gives dbt something to model. DEC-012 names the trigger as a precondition, not a date: when
a family owning cross-session accumulation is `active` and a specification under it requires a
persistent multi-dataset store, re-open the question. That condition is satisfied by this phase.
Re-open it then, with evidence, and only if in-process Polars is actually failing — note that
moving governed arithmetic into warehouse SQL would substitute engine numeric semantics for the
`Decimal` contract `facts.py` enforces, which DEC-012 records as a downgrade for this product.

---

## Phase 4 — Commercial: pricing, billing, quotas

**Steps.** Specify plans and entitlements; subscription lifecycle including failed payment and
cancellation; quota enforcement (datasets, reports, storage, seats) with fail-closed behaviour;
invoicing and tax as appropriate to jurisdiction; and a payment provider selection as a separate
decision with its own data-handling gates, following the pattern DEC-005/008 set for the
narrative provider.

**Exit criterion.** A customer pays, and non-payment degrades access predictably.

**Kill test.** Manual invoicing for the first ten customers. Do not build billing to discover
the price is wrong. This phase can start with a spreadsheet.

**What could kill the business.** Price discovered after the architecture is committed to it.
Per-report pricing and per-seat pricing imply different tenancy models.

---

## Phase 5 — Public surface and onboarding

**Steps.** Specify public signup with abuse controls; the marketing surface stating what the
product refuses as well as what it does; self-serve upload and mapping confirmation (the current
mapping flow assumes a cooperative beta participant); and a bilingual first-run experience —
`RRA-005` parity is a market advantage that should be visible before purchase.

**Exit criterion.** A stranger signs up and gets a report without operator involvement.

**Kill test.** Watch five unassisted strangers attempt upload-to-report. Admissibility rejection
without a clear remedy is the likely failure, and it is a Phase 1 presentation problem surfacing
late.

**Partial parallelism with Phase 4.** The signup and onboarding surfaces do not depend on billing
internals; only the plan-selection step does. Sequence that step last.

---

## Phase 6 — Agency tenancy

**Why after mid-market.** Agencies need everything mid-market needs plus delegation, and they are
a smaller number of larger contracts. Serving mid-market first proves the core; agency features
are additive rather than a different product. `BATCH-09` already surveyed this shape.

**Steps.** Specify portfolios and client switching; delegated access with an explicit
authority model (the Constitution's delegation discipline is a useful precedent, not a
reusable implementation); white labeling bounded so that provenance and refusal disclosures
cannot be re-branded away — the moat must survive being resold; and per-client isolation within
one agency account, which is a second isolation boundary inside the first.

**Exit criterion.** An agency serves three of its own clients from one account without those
clients being visible to each other.

**Kill test.** Confirm with two agencies that white labeling that *cannot* hide the provenance
disclosure is still saleable. If they need to hide it, the moat and the segment conflict — and
that is worth knowing before building.

---

## Phase 7 — Recurring delivery

**Steps.** Specify scheduled recurring reports, delivery channels, and failure notification.
`scheduling` is currently excluded by `RRA.md` and must be inside the RCA charter for this phase
to exist.

**Exit criterion.** A customer receives a monthly report without logging in.

**Note.** This is the one phase where an orchestration question could legitimately re-open — and
even here, a schedule that enqueues an existing job is a row in a table and a sweep, not a DAG
engine. `KHEPRI-DEC-012` should be superseded rather than ignored if that changes.

---

## Authorized now — no new governance required

These were gated by nothing. Each was a defect against an already-approved artifact, and each was
an independently verifiable slice. They were listed here so they would not be mistaken for roadmap
work waiting on a charter.

> **All three landed in `5117fa3` (#94) on 2026-08-04 — the day this document was drafted — and
> this section described the state immediately before that commit.** Nothing here is available
> work. The items are retained rather than deleted because a list of "available slices" that
> silently shrinks gives a later reader no way to tell a completed item from one that was dropped;
> each is marked with where its fix now lives, so the claim can be checked rather than trusted.

1. ~~**Cite `RRA-005` in the code that implements it.**~~ **Done.** `specifications.yaml` records
   RRA-005 as `approved`, and `src/khepri/rra/narrative.py:3` now opens "This module implements
   RRA-005." `grep -rn "RRA-005" src/` returns that line; the observation that it returned nothing
   was true only before `5117fa3`.
2. ~~**Declare `pydantic` and `botocore` in `pyproject.toml`.**~~ **Done.** Both are declared at
   `pyproject.toml:20,27` (`botocore>=1.43.58,<2`, `pydantic>=2.11,<3`), above a comment naming
   the direct import sites and stating the reasoning this item asked for — that a transitive
   resolution through FastAPI and boto3 is not a pin, and `KHEPRI-DEC-008` names Pydantic as the
   application-boundary schema library.
3. ~~**Name `fastexcel` where it is used.**~~ **Done.** The `materialize` docstring at
   `src/khepri/rra/profiling.py:282-291` now states that the `engine="calamine"` call is the only
   thing making the dependency required, that it is imported nowhere in the repository, and that
   `KHEPRI-DEC-008` names the fastexcel/calamine engine as the approved XLSX reader — so removing
   it would break the line rather than tidy a manifest.

**Not authorized now, and worth knowing why.** `KHEPRI-DEC-005`'s stale closing sentence — "This
decision remains proposed until its registry entry contains explicit approval evidence," against a
registry recording `state: accepted` — **cannot** be fixed as a housekeeping edit. `APP-013.yaml`
binds `document_sha256: sha256:2214cd12...` to that document, and `khepri-gov validate` fails
closed on any edit with `approval-packages:APP-013: governed document for KHEPRI-DEC-005 changed
without renewal`. This was confirmed empirically: the edit was attempted, validation rejected it,
and it was reverted.

Correcting it requires a **renewal approval package** approved by a named authority. It is governed
work, not a typo fix, and it belongs in Phase 0A-gov alongside the DEC-008 acceptance — where a
renewal is being written anyway. Recorded here because "it's just a stale sentence" is exactly the
reasoning the digest binding exists to stop.

## Invariants — verified after every phase

1. `uv run khepri-gov validate`, `uv run ruff check .`, `uv run pytest` all pass.
2. CodeScene Code Health 10.00 on every new file; no tracked hotspot declines. CI is the only
   authority — local tooling does not reproduce server thresholds. Keep constructors at two or
   three arguments rather than sitting at a limit.
3. Cross-tenant isolation tests pass. This invariant strengthens at Phase 2 and again at Phase 6.
4. Operational evidence stays content-free. `RRA-007` and DEC-008 both require it; every new
   surface is a new opportunity to leak a label into a log.
5. Every governed figure traces to one immutable package version.
6. No slice implements ahead of an approved specification, and no slice widens beyond its stated
   boundary.

## Known collisions when phases run in parallel

- Two slices each adding an Alembic migration become siblings off one parent; the second to
  merge re-points its `down_revision`.
- Squash-merging a base branch detaches anything stacked on it; replay with
  `git rebase --onto origin/main <old-base>` instead of merging.
- State both in the pull request before they happen.

## What this roadmap deliberately omits

- **Product code.** Nothing here authorizes implementation.
- **Specifications.** Phases name where specifications are needed; drafting them is the owner's
  call, and each requires approval before its slices exist.
- **Registry edits.** No registry is touched by this document.
- **Forecasting, customer-authored formulas, generic non-retail analysis.** Excluded by `RRA.md`
  and recommended to stay excluded in the RCA charter. They are where a defensibility product
  goes to die.
- **A date.** Every phase is gated on an approval this document cannot grant.

## The three sentences that matter

The moat is already built and nobody can see it, and Phase 0C — which would have tested that whole
thesis with a mock before any charter or schema existed — is withdrawn by owner election, so the
thesis now rests on judgment rather than evidence. Everything expensive is gated behind two
governance approvals and one spending decision, none of which code can substitute for. The binding limits are retention
and tenancy — one dataset per session, and a seven-day expiry that deletes the comparison baseline
— and `KHEPRI-DEC-012` records that no orchestrator is coming to fix either.
