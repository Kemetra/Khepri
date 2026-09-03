# KHEPRI-DEC-033: Durable retail-content retention for the organization workspace

## Context

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
- `KHEPRI-DEC-015` §8 fixes the backup invariants and left the backup horizon open as its own
  owner decision. **§4 of this decision closes it** at fourteen days. `KHEPRI-DEC-028` and
  `KHEPRI-DEC-030` select DigitalOcean FRA1; before this decision no artifact fixed the horizon, so
  every "bounded backups" cell in `KHEPRI-DEC-015` §2 was unbounded in practice.
- `KHEPRI-DEC-007`'s discipline: *no single retention horizon is quietly longer than another.*
- `RCA-001` `FR-031`–`FR-035`: an organization maps to one opaque isolation scope, stable for its
  lifetime; no commercial identifier may appear in or be derivable from that scope.
- `RRA-002` continues to govern the *mechanics* of intake, encryption, deletion and evidence. This
  decision changes **when** content ends, not **how** it is deleted.
- `KHEPRI-DEC-032`: no store retains a `ReportBundle`; catalog routes reconstruct one from the
  retained package. A durable workspace changes what is worth retaining (§2, row *Fact package*).

**Authorship.** The values in §2 and §4 were recommended by the implementing agent and approved by
the owner in session on 2026-09-03, after the agent presented all eight choices with their
alternatives and the cost of each. This is recorded as an owner-approved recommendation, not as
owner-authored prose. `AGENTS.md` makes a merge the approval, so merging this document is the
decision.

## Decision

**Retention follows the organization, not the session.** Today content belongs to a session and dies
with it. In the workspace, content belongs to the organization's isolation scope and lives while the
organization wants it, bounded by an explicit horizon per class and ended by an explicit trigger.
Every class still has a *bounded* active retention, an *end trigger*, a *post-trigger state* and a
*deletion rule*; "kept until deleted" is a lifecycle only when the deleting actor and the backup
horizon are both named. Both are named below.

### 1. The three kinds of ending

The matrix names which applies to every row:

- **Owner-requested deletion** — a customer action, immediate, idempotent, and **evidenced**
  (`RRA-002`'s content-free evidence). Nothing is deleted by inference from another action.
- **Named cascade** — a deletion that follows an owner-requested one because a row names its
  parent (a run follows its dataset version). Evidenced as part of the parent's deletion.
- **Retention-triggered purge** — the automatic ending of a class whose purpose has elapsed:
  sealing plus grace, an evidence horizon, backup expiry. Run by the retention sweep, recorded as a
  lifecycle audit event, and **not** presented to the customer as a deletion they performed.

**Derived content never outlives its input's *right to exist*.** A fact package or report may
outlive the raw upload it came from — the upload is the bulkiest and least useful class to keep —
but if the customer deletes the *dataset version*, every derivative of it goes too, because the
derivative is a transformation of content the customer withdrew.

### 2. Retention matrix

This matrix is authoritative. Every value is fixed; no cell defers to a later choice.

| Data class | Purpose | Active retention | End trigger | Post-trigger state | Deletion rule | Backup rule | Anchor |
|---|---|---|---|---|---|---|---|
| **Raw upload** (CSV/XLSX bytes) | Admission, profiling, and re-attestation of a source | **7 days** after its dataset version is *sealed* (facts derived and reconciled), then purged | Sealing plus seven days (purge); dataset-version deletion (cascade); organization closure | **Purged.** The *live* dataset version keeps the upload's digests, size and media type and its coverage manifest; the rows are gone | Immediate on trigger; idempotent | 14-day bounded horizon (§4) | `RRA-002`, `RRA-003` |
| **Normalized events** (materialized rows) | Fact derivation | Same as raw upload — a materialization is the upload in another shape | As raw upload | **Purged** | As raw upload | As raw upload | `RRA-002`, `RRA-004` |
| **Dataset version** (record: digests, mapping, manifest, admission outcome, versions) | The durable identity of one admitted source; what *Remember My Data* re-attests against | While the organization exists, or until the customer deletes it. **No inactivity expiry** (§4) | Customer deletion; organization closure | **Tombstone, by allowlist** (§3): opaque identifiers, timestamps, digests, version identifiers, admission outcome code. **Everything in the profile document is excluded** — column labels, min/max values, the manifest's text fields | Immediate, cascading to every derivative below; evidence recorded | 14-day bounded horizon; a restored deleted version must not become readable (revocation-ledger pattern, `KHEPRI-DEC-015` §8) | `RRA-003`, `KHEPRI-DEC-015` §6 |
| **Mapping and coverage manifest** | Provenance of admission; reuse as a *source profile* | With the dataset version they describe | As dataset version | Tombstoned with it | Cascade | As dataset version | `RRA-003` |
| **Fact package** (facts, series, comparisons, refusals, versions) | The analysis; the input every report and catalog read reconstructs from | With the analysis run that produced it, while the organization exists | Analysis-run deletion; dataset-version deletion (cascade); organization closure | **Tombstone**: opaque run identifier, timestamps, formula and package versions, package digest — no figure | Immediate, cascading to reports and evidence | As dataset version | `RRA-004`, `RRA-008`, `KHEPRI-DEC-032` |
| **Report bundle artifacts** (web, evidence, PDF, Excel) | The deliverable, reopened from Analysis detail | With their analysis run | As fact package | **Purged** — the run's tombstone is the only trace | Cascade from the run | As dataset version | `RRA-006` |
| **Narrative** (grounded commentary) | Part of the report bundle | As report artifacts | As report artifacts | Purged | Cascade | As dataset version | `RRA-007` |
| **Analysis run** (record: which dataset version, when, state, quality, versions) | The history spine — *"when it ran, which data entry it used, its state, whether the report is available, its retention state"* | While the organization exists, or until the customer deletes it. **No inactivity expiry** | Customer deletion; dataset-version deletion (cascade); organization closure | **Tombstone** as above; the row remains so history does not silently shorten | Immediate, cascading | As dataset version | `RRA-006`, blueprint §7.3 |
| **Provenance record** (`W1-06`: bindings between run, version, facts, artifacts, digests) | Reproducibility and the Analysis Passport | With the run; the tombstone keeps its digests | As run | Digests and version identifiers survive in the tombstone; nothing else | Cascade | As dataset version | `W1-06` |
| **Reusable source profile** (`W1-01`: descriptive metadata for *Remember My Data*) | Offer a prior mapping for re-attestation; never skip admission | While the organization exists, or until the customer deletes it | Customer deletion; organization closure | **Purged** | Immediate; deleting a profile deletes no dataset version | 14-day bounded horizon | `W1-01`, `RRA-003` |
| **Deletion evidence** | Prove that content ended, without saying what it was | **12 months** from the deletion event, matching `KHEPRI-DEC-015` §2a so no horizon is quietly longer | Elapse of twelve months | Purged | Purge on elapse | 14-day bounded horizon | `RRA-002`, `KHEPRI-DEC-015` §2a |
| **Retention/lifecycle audit event** (who deleted what, when; sweeps run) | Attribute deletion; investigate a dispute | **12 months** — the `KHEPRI-DEC-015` §2a horizon, adopted rather than re-derived | Elapse of twelve months | Content-free record | Purge on elapse | 14-day bounded horizon | `KHEPRI-DEC-015` §2a |
| **Retail content under a disabled organization** | Preserve a recoverable state without leaving content readable | **24 months** from disablement, matching `KHEPRI-DEC-015` §2b so content never outlives the accounts that could have claimed it | Owner-requested deletion; or elapse of twenty-four months from disablement | Frozen at disablement — nothing readable, nothing deleted; purged per class at the horizon | Purge on elapse, per the class rows above | 14-day bounded horizon | `KHEPRI-DEC-015` §2b, `FR-015` |
| **Repeat-use telemetry** (`W1-11`) | Product learning about second analysis, reopen, return, deletion completion | **Not authorized by this decision.** `KHEPRI-DEC-015` §3 forbids product-analytics use of identity data, and `RRA-010`, `RCA-003`, `RRA-011`, `RRA-012` and `RRA-013` each exclude new telemetry. `W1-11` needs its own amendment | — | — | — | — | `KHEPRI-DEC-015` §3 |
| **Backups** of any of the above | Operational recovery | **14 days** on the FRA1 target — the horizon `KHEPRI-DEC-015` §8 left open | Elapse of fourteen days | Destroyed by the runtime's lifecycle mechanism | — | Must not resurrect deleted content as readable | `KHEPRI-DEC-015` §8 |

### 3. The tombstone allowlist

A tombstone is defined by what it **may** contain, never by what was removed. `G2-01` F-2 is why:
the live profile document holds sanitized customer column headers and min/max values, and the
coverage manifest holds free text (`attested_by`, `aggregate_scope`, exception notes). None of it
survives.

| Tombstone | May contain | Never contains |
|---|---|---|
| Dataset version | opaque version id and organization scope; created, sealed and deleted instants; upload plaintext and ciphertext digests, size, media type; manifest **digest**; `rra003.mapping.*` version; admission outcome **code** | filename, any column label or digest of one, any value, any manifest text field, the mapping itself |
| Analysis run | opaque run id, version id and scope; started, completed and deleted instants; package digest; `rra004.*` and `rra008.*` versions; per-section state codes (answered, caveated, refused) | any figure, series, label, narrative, refusal prose, artifact bytes or key |
| Source profile | none — purged, not tombstoned | — |

A test asserts each tombstone's field set equals its allowlist exactly, so a field added to the live
record cannot leak into the tombstone by default.

**Clock cardinality: one clock per class, anchored to that class's own trigger.** A dataset version's
clock does not start a run's clock; a run's tombstone clock is the deletion instant. Nothing here
retains by "last activity" — see the inactivity row in §4.

### 4. The eight choices, as decided

Recorded so a later reader sees what was chosen against what, rather than only the result. The
reference labels are the choice sheet's, preserved so the drafting record stays traceable.

| Ref | Question | Decided |
|---|---|---|
| `OD-1` | Raw upload and normalized events, after sealing | **Seven days, then purge.** The version keeps digests and manifest, so re-attestation and provenance survive; the bulkiest content does not. Rejected: keeping them with the dataset version, which puts raw retail rows in every backup for the organization's lifetime; and purging at sealing, which leaves a disputed seal with no input to recheck |
| `OD-2` | Deletion-evidence horizon | **Twelve months**, on `KHEPRI-DEC-015` §2a's discipline that no horizon is quietly longer than another. Rejected: indefinite, by Constitution VII's least-data default |
| `OD-3` | Inactivity expiry for dataset versions and runs | **None.** Content lives while the organization exists or until deleted. History that silently shortens is the failure the blueprint §7.3 forbids, and an inactivity sweep would need a notification capability no active artifact grants |
| `OD-4` | Organization closure | **Disablement freezes; content is deleted on owner request, or at twenty-four months after disablement**, matching `KHEPRI-DEC-015` §2b. Rejected: deletion on disablement, which takes irreversible action on a state `KHEPRI-DEC-015` treats as recoverable. Organization *deletion* stays excluded by `RCA-001` and `KHEPRI-DEC-015` §6; this row governs content under a disabled organization, not the organization record |
| `OD-5` | Backup purge horizon | **Fourteen days** on the FRA1 target, fixed here rather than deferred to a runtime successor. This closes `KHEPRI-DEC-015` §8's own open item. Rejected: seven days, whose `KHEPRI-DEC-007` anchor was a matched S3 expiry that no longer applies; and thirty days, which keeps deleted retail content restorable for a month and grows the revocation ledger and evidence margin with it |
| `OD-6` | Who may delete | **Organization owners only** (`RCA-001` owner and member roles; the blueprint's `M3-U7` owner-only control). Members may see retention state and request deletion; they cannot perform it. Rejected: any member, which widens the blast radius of one compromised member account |
| `OD-7` | Export of retained content | **None beyond the governed bundle's own artifacts** (web, evidence, PDF, Excel), reached from Analysis detail. Raw-row export stays excluded by `RRA-002` |
| `OD-8` | Legal and operational ownership | **The organization is the data controller of its retail content; Khepri is the processor; the organization owner is the actor who exercises deletion.** A statement of roles only — contract terms are outside every artifact in this repository |

### 5. These horizons are unenforced until a sweep ships with a caller

**Stated in the decision, not only in its evidence, because this is the kind of gap that hides.**
`G2-01` measured it on `main` at `457f276`: no retention sweeper has a caller in the shipped image.
Every sweeper's only caller is `khepri.local.cli`, which `pyproject.toml` excludes from the wheel,
and `rca/invitation_retention.py:40` already records `INVITATION_HORIZON_IS_UNENFORCED = True`
against the same gap. The worker's per-claim sweep is *lease* recovery, not retention.

Consequently every horizon in §2 states what the product **must** do, and none of them describes
what the deployed image **does**. The obligation is discharged by `W1-07`, which must ship a
retention sweep with a caller present in the shipped image, and evidence that each horizon in §2 is
honoured. Until that merges:

- No surface may tell a customer that content expires automatically.
- The beta's seven-day expiry stays what `G2-01` found it to be — a cookie and an API refusal, not a
  fact about the store.
- A later reader must not infer from this decision's activation that any purge runs.

`G2-01` also records F-2: on-demand deletion **is** complete — `SqlDeletionRepository.complete`
deletes the profile, fact-package, artifact and upload rows — but `rra_dataset_profiles.document`
and `rra_fact_packages.document` hold customer-derived labels and values as plaintext JSON,
unencrypted at rest, unlike the objects. Whether they should be envelope-encrypted is an `RRA-002`
reading and is not decided here.

## Consequences

- `G2-03` is complete on this document's merge; `G3-02` and `G3-03` may proceed.
- `RCA-005` may activate, granting the durable workspace its specification.
- `W1` implementation is unblocked in authority. `W1-07` carries the §5 obligation and is not
  optional to it: a workspace that retains without a working sweep implements only half of this.
- `KHEPRI-DEC-015` §8's open backup horizon is closed at fourteen days. Its §2 "bounded backups"
  cells are bounded by that number from this decision's merge.
- Nothing here authorizes telemetry, organization deletion, raw-row export, or member-performed
  deletion.

## Explicit non-authorizations

- No product-analytics or repeat-use telemetry. `KHEPRI-DEC-015` §3 stands; `W1-11` needs its own
  amendment.
- No deletion of an organization record. `RCA-001` and `KHEPRI-DEC-015` §6 continue to exclude it.
- No change to `RRA-002`'s deletion mechanics, encryption, or evidence shape.
- No raw-row export, and no re-download of a purged upload.
- No claim, on any surface, that a retention horizon is enforced before `W1-07` ships.
