# `[DEC-RETENTION]` — Durable retail-content retention for the organization workspace

**DRAFT. Not a governed artifact. Allocates no identifier.** Intended target:
`governance/decisions/<derived-id>-durable-retail-content-retention.md`, registered `active` with
`depends_on: [KHEPRI-DEC-014, KHEPRI-DEC-015, RRA-002]` once the owner has made the choices in §4.
Roadmap tasks: `G2-02` (the choices) and `G2-03` (the activation). Inventory: `G2-01`, in
`docs/superpowers/specs/2026-09-03-g2-01-retained-data-inventory.md`.

**Raised on:** `main` at `457f276`, 2026-09-03.

---

## 1. Context

Every retail byte Khepri holds today is bounded by one rule: `RRA-001` sets the content expiry
instant to seven days after session creation, and `RRA-002` deletes input, materializations, facts,
narrative, exports and orphans at that instant or on demand, keeping content-free evidence. The
`RCA` family charter reserves *"persistent customer workspaces: durable storage of inputs and reports
beyond the beta's seven-day expiry, **under an explicit approved retention decision**"*, and
`KHEPRI-DEC-015` §Explicit non-authorizations says it grants no *"retention of retail uploads,
derived facts, narratives, or report bundles beyond `RRA-002`"* and no *"persistent workspaces,
report history, multi-dataset storage, or long-lived retail content."* `RCA-002` excludes *"a
dashboard, a report history, or a reports index"* for the same reason: *"a product with durable
retention, which no active decision grants."*

This is that decision. M3 — *"durable trust workspace beta"* — cannot start without it, because every
`W1` task depends on active `G3`, and `G3-04` depends on `G2-03`.

**What already constrains it, and is not reopened here:**

- `KHEPRI-DEC-015` §2 fixes the lifecycle of every *identity* class and is the pattern this decision
  follows: one authoritative matrix, one row per class, purpose, active retention, end trigger,
  post-trigger state, deletion rule, backup rule, anchor.
- `KHEPRI-DEC-015` §6 binds any later deletion rule: immediate and idempotent on demand; deleting a
  commercial identity must not orphan retail content; deletion reaches backups through the bounded
  horizon; the final-owner protection cannot be circumvented by deletion.
- `KHEPRI-DEC-015` §8 fixes the backup invariants and leaves the backup horizon as `OD-3`, an input
  to the runtime decision. `KHEPRI-DEC-028`/`030` select DigitalOcean FRA1; the horizon is still not
  fixed by any artifact.
- `KHEPRI-DEC-007`'s discipline: *no single retention horizon is quietly longer than another.*
- `RCA-001` `FR-031`–`FR-035`: an organization maps to one opaque isolation scope, stable for its
  lifetime; no commercial identifier may appear in or be derivable from that scope.
- `RRA-002` continues to govern the *mechanics* of intake, encryption, deletion and evidence. This
  decision changes **when** content ends, not **how** it is deleted.
- `KHEPRI-DEC-032`: no store retains a `ReportBundle`; catalog routes reconstruct one from the
  retained package. A durable workspace changes what is worth retaining (§3, row *Fact package*).
- `G2-01` F-1 and F-2: no retention sweeper runs on the deployed path, and the profile and
  fact-package documents end only by on-demand deletion. Every horizon below is a statement of
  intent until `W1-07` ships a sweep *with a caller in the shipped image*.

## 2. The governing principle

**Retention follows the organization, not the session.** Today content belongs to a session and dies
with it. In the workspace, content belongs to the organization's isolation scope and lives while the
organization wants it, bounded by an explicit horizon per class and ended by an explicit trigger.
Every class still has a *bounded* active retention, an *end trigger*, a *post-trigger state* and a
*deletion rule*; "kept until deleted" is a lifecycle only when the deleting actor and the backup
horizon are both named.

Three kinds of ending, and the matrix names which applies to every row:

- **Owner-requested deletion** — a customer action, immediate, idempotent, and **evidenced**
  (`RRA-002`'s content-free evidence). Nothing is deleted by inference from another action.
- **Named cascade** — a deletion that follows an owner-requested one because a row names its
  parent (a run follows its dataset version). Evidenced as part of the parent's deletion.
- **Retention-triggered purge** — the automatic ending of a class whose purpose has elapsed:
  sealing plus grace, an evidence horizon, backup expiry, an inactivity horizon if OD-3 chooses one.
  Run by the retention sweep, recorded as a lifecycle audit event, and **not** presented to the
  customer as a deletion they performed.
- **Derived content never outlives its input's *right to exist*.** A fact package or report may
  outlive the raw upload it came from (the upload is the bulkiest and least useful class to keep),
  but if the customer deletes the *dataset version*, every derivative of it goes too, because the
  derivative is a transformation of content the customer withdrew.

## 3. Retention matrix — proposed

Values marked **OD-n** are the owner's; a recommended value is given and the alternatives are in §4.
Everything else follows from an active artifact named in the anchor column.

| Data class | Purpose | Active retention | End trigger | Post-trigger state | Deletion rule | Backup rule | Anchor |
|---|---|---|---|---|---|---|---|
| **Raw upload** (CSV/XLSX bytes) | Admission, profiling, and re-attestation of a source | **OD-1**: until its dataset version is *sealed* (facts derived and reconciled), plus a short grace — recommended **7 days** after sealing | Sealing + grace (purge); dataset-version deletion (cascade); organization closure | **Purged.** The *live* dataset version keeps the upload's digests, size and media type and its coverage manifest; the rows are gone | Immediate on trigger; idempotent | Bounded horizon **OD-5** | `RRA-002`, `RRA-003` |
| **Normalized events** (materialized rows) | Fact derivation | Same as raw upload — a materialization is the upload in another shape | As raw upload | **Purged** | As raw upload | As raw upload | `RRA-002`, `RRA-004` |
| **Dataset version** (record: digests, mapping, manifest, admission outcome, versions) | The durable identity of one admitted source; what *Remember My Data* re-attests against | While the organization exists, or until the customer deletes it | Customer deletion; organization closure | **Tombstone, by allowlist** (§3a): opaque identifiers, timestamps, digests, version identifiers, admission outcome code. **Everything in the profile document is excluded** — column labels, min/max values, the manifest's text fields | Immediate, cascading to every derivative below; evidence recorded | Bounded horizon **OD-5**; a restored deleted version must not become readable (revocation-ledger pattern, `DEC-015` §8) | `RRA-003`, `KHEPRI-DEC-015` §6 |
| **Mapping and coverage manifest** | Provenance of admission; reuse as a *source profile* | With the dataset version they describe | As dataset version | Tombstoned with it | Cascade | As dataset version | `RRA-003` |
| **Fact package** (facts, series, comparisons, refusals, versions) | The analysis; the input every report and catalog read reconstructs from | With the analysis run that produced it, while the organization exists | Analysis-run deletion; dataset-version deletion (cascade); organization closure | **Tombstone**: opaque run identifier, timestamps, formula and package versions, package digest — no figure | Immediate, cascading to reports and evidence | As dataset version | `RRA-004`, `RRA-008`, `KHEPRI-DEC-032` |
| **Report bundle artifacts** (web, evidence, PDF, Excel) | The deliverable, reopened from Analysis detail | With their analysis run | As fact package | **Purged** — the run's tombstone is the only trace | Cascade from the run | As dataset version | `RRA-006` |
| **Narrative** (grounded commentary) | Part of the report bundle | As report artifacts | As report artifacts | Purged | Cascade | As dataset version | `RRA-007` |
| **Analysis run** (record: which dataset version, when, state, quality, versions) | The history spine — *"when it ran, which data entry it used, its state, whether the report is available, its retention state"* | While the organization exists, or until the customer deletes it | Customer deletion; dataset-version deletion (cascade); organization closure | **Tombstone** as above; the row remains so history does not silently shorten | Immediate, cascading | As dataset version | `RRA-006`, blueprint §7.3 |
| **Provenance record** (`W1-06`: bindings between run, version, facts, artifacts, digests) | Reproducibility and the Analysis Passport | With the run; the tombstone keeps its digests | As run | Digests and version identifiers survive in the tombstone; nothing else | Cascade | As dataset version | `W1-06` |
| **Reusable source profile** (`W1-01`: descriptive metadata for *Remember My Data*) | Offer a prior mapping for re-attestation; never skip admission | While the organization exists, or until the customer deletes it | Customer deletion; organization closure | **Purged** | Immediate; deleting a profile deletes no dataset version | Bounded horizon **OD-5** | `W1-01`, `RRA-003` |
| **Deletion evidence** | Prove that content ended, without saying what it was | **OD-2**: recommended **12 months** from the deletion event, matching `DEC-015` §2a so no horizon is quietly longer | Elapse | Purged | Purge on elapse | Bounded backups | `RRA-002`, `KHEPRI-DEC-015` §2a |
| **Retention/lifecycle audit event** (who deleted what, when; sweeps run) | Attribute deletion; investigate a dispute | **12 months** — the `DEC-015` §2a horizon, adopted rather than re-derived | Elapse | Content-free record | Purge on elapse | Bounded backups | `KHEPRI-DEC-015` §2a |
| **Repeat-use telemetry** (`W1-11`) | Product learning about second analysis, reopen, return, deletion completion | **Not authorized by this decision.** `KHEPRI-DEC-015` §3 forbids product-analytics use of identity data and `RRA-010`/`RCA-003`/`RRA-011`/`RRA-012`/`RRA-013` each exclude new telemetry. `W1-11` needs its own amendment | — | — | — | — | `KHEPRI-DEC-015` §3 |
| **Backups** of any of the above | Operational recovery | **OD-5**: the bounded purge horizon `DEC-015` left open as `OD-3` | Elapse | Destroyed by the runtime's lifecycle mechanism | — | Must not resurrect deleted content as readable | `KHEPRI-DEC-015` §8 |

### 3a. The tombstone allowlist

A tombstone is defined by what it **may** contain, never by what was removed. `G2-01` F-2 is why:
the live profile document holds sanitized customer column headers and min/max values, and the
coverage manifest holds free text (`attested_by`, `aggregate_scope`, exception notes). None of it
survives.

| Tombstone | May contain | Never contains |
|---|---|---|
| Dataset version | opaque version id and organization scope; created, sealed and deleted instants; upload plaintext and ciphertext digests, size, media type; manifest **digest**; `rra003.mapping.*` version; admission outcome **code** | filename, any column label or digest of one, any value, any manifest text field, the mapping itself |
| Analysis run | opaque run id, version id and scope; started, completed and deleted instants; package digest; `rra004.*`/`rra008.*` versions; per-section state codes (answered / caveated / refused) | any figure, series, label, narrative, refusal prose, artifact bytes or key |
| Source profile | none — purged, not tombstoned | — |

A test asserts each tombstone's field set equals its allowlist exactly, so a field added to the live
record cannot leak into the tombstone by default.

**Clock cardinality (blueprint `M3-U6` names this as `G2`'s to decide): one clock per class, anchored
to that class's own trigger.** A dataset version's clock does not start a run's clock; a run's
tombstone clock is the deletion instant. Nothing here retains by "last activity" — an inactivity
sweep is a separate choice, **OD-3**, and the recommendation is *no inactivity expiry* in M3.

## 4. Owner decisions — the choice sheet (`G2-02`)

Each block is one choice. A recommended value is first. Pick, strike, or write a fourth.

```text
OD-1  Raw upload and normalized events: how long after the dataset version is sealed?
      Recommended:  7 days after sealing, then purge. The version keeps digests + manifest, so
                    re-attestation and provenance survive; the bulkiest content does not.
      Alternative:  keep with the dataset version (re-download / re-profile possible; largest
                    footprint; every backup carries raw retail rows for the whole org lifetime).
      Alternative:  purge at sealing (no grace; a failed or disputed seal has no input to recheck).
      Risk if shorter: a defect found within days of sealing cannot be replayed against the input.
      Risk if longer:  raw rows in every backup for as long as the organization exists.

OD-2  Deletion evidence horizon.
      Recommended:  12 months (DEC-015 §2a discipline: no horizon quietly longer than another).
      Alternative:  the backup horizon plus a margin (evidence lives only as long as a restore could
                    contradict it).
      Alternative:  indefinite (rejected by Constitution VII's least-data default).

OD-3  Inactivity expiry for dataset versions and runs.
      Recommended:  none in M3. Content lives while the organization exists or until deleted.
                    History that silently shortens is the failure blueprint §7.3 forbids.
      Alternative:  N months of organization inactivity, with a notice period; needs a
                    notification capability no active artifact grants.

OD-4  Organization closure: what happens to retail content when an organization is disabled?
      Recommended:  disablement freezes (nothing readable, nothing deleted); content is deleted
                    when the owner of the organization requests deletion, or at a fixed horizon
                    after disablement — recommended 24 months, matching DEC-015 §2b so the content
                    never outlives the accounts that could have claimed it.
      Alternative:  delete on disablement (irreversible on a reversible state; DEC-015 treats
                    disablement as recoverable).
      Alternative:  keep until an explicit deletion only (indefinite by omission — rejected).
      Note: organization DELETION stays excluded by RCA-001 and DEC-015 §6; this row governs
            content under a disabled organization, not the organization record.

OD-5  Backup purge horizon (DEC-015's OD-3, still open).
      Recommended:  14 days on the FRA1 target, fixed as a number here or in KHEPRI-DEC-028's
                    successor — but fixed. Every "bounded backups" cell above is unbounded until it is.
      Alternative:  7 days (KHEPRI-DEC-007's beta anchor; matched S3 expiry that no longer applies).
      Alternative:  30 days (longer restore window; deleted retail content restorable for a month;
                    revocation ledger and deletion-evidence margin grow with it).

OD-6  Who may delete.
      Recommended:  organization owners only (RCA-001 owner/member roles; M3-U7 "owner-only
                    control"). Members may see retention state and request; they cannot delete.
      Alternative:  any member (widens the blast radius of a compromised member account).

OD-7  Export of retained content.
      Recommended:  none beyond the governed bundle's own artifacts (web, evidence, PDF, Excel),
                    reached from Analysis detail. Raw-row export stays excluded (RRA-002).
      Alternative:  raw upload re-download while it exists (conflicts with OD-1 recommended).

OD-8  Legal and operational ownership.
      Recommended:  the organization is the data controller of its retail content; Khepri is the
                    processor; the organization owner is the actor who exercises deletion.
                    Recorded as a statement of roles, not a contract — contract terms are outside
                    every artifact in this repository.
```

## 5. Decision — as it would read once the choices are made

Khepri retains an organization's retail content in that organization's opaque isolation scope
according to the matrix in §3, with the values the owner fixed in §4. Every class has a bounded active
retention, a named end trigger, a defined post-trigger state and a deletion rule. Deletion is
immediate, idempotent, cascading as the matrix states, owner-invoked, and evidenced content-free.
Nothing is retained by inactivity, nothing is retained indefinitely, and no backup makes deleted
content readable again.

## 6. Consequences

- `RRA-002`'s *"retention beyond the beta session"* exclusion is **superseded for organization
  scopes only**; the invitation-based beta journey keeps its seven-day rule unchanged until it is
  retired. Two lifecycles will coexist for a while and the inventory must say which applies to a row.
- `RCA-002`'s exclusion of *"a dashboard, a report history, or a reports index"* is unblocked in
  principle; `W1-05` still builds under `G3`, not here.
- `KHEPRI-DEC-032` stands: bundles are reconstructed from the retained package, so the *fact package*
  row is the one that makes reopening a report possible.
- `KHEPRI-DEC-015` is not amended. Its matrix keeps identity; this one keeps content; both cite §6
  and §8 of the former.
- **Not authorized here:** telemetry (`W1-11`), organization deletion, cross-organization sharing,
  external connectors, recurring refresh, raw export, any change to `RRA-001`/`RRA-002` mechanics.

## 7. Verification, once active

- A test per matrix row proves the end trigger purges or tombstones exactly what the row says, and
  nothing in a sibling row.
- A cascade test proves dataset-version deletion removes every derivative and leaves only tombstones.
- A restore test proves a backup taken before a deletion cannot make the deleted content readable.
- A sweep test proves no inactivity expiry exists (OD-3 as recommended).
- `khepri-gov validate` passes with the registry row; `ruff`, `pytest` green.

## 8. What this draft is not

It is not an implementation plan (`G3-04`), not a schema (`W1-02`), and not the workspace
specification (`[RCA-WORKSPACE]`, drafted beside it). It takes no decision: every `OD-n` is the
owner's, and the recommendations are recommendations.
