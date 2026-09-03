# `[RCA-WORKSPACE]` — Organization Workspace, Dataset Versions, Analysis History, and Deletion

**DRAFT. Not a governed artifact. Allocates no identifier.** Intended target:
`governance/specifications/RCA-<next>.md`, registered `active` with
`depends_on: [RCA, RCA-001, RCA-002, RRA-002, RRA-003, RRA-004, RRA-006, [DEC-RETENTION]]`. It
cannot be activated before `[DEC-RETENTION]` is, because every lifecycle clause below reads that
decision's matrix rather than restating it. Roadmap tasks: `G3-01` (this draft), `G3-02` (the
semantics in §3, to be confirmed as a clarification record), `G3-03` (the rules in §5). `G3-04`
produces the plan and registry proposal after `G2-03`.

**Raised on:** `main` at `457f276`, 2026-09-03. Numbering continues from `RRA-013` (`FR-108`).

---

## Outcome

An organization's members can return to Khepri and find their work: the dataset versions they
admitted, the analyses run over them, and each analysis's report, evidence, PDF and Excel — reopened
from the analysis that produced them, with the analysis's operational state, trust state, retention
state, and provenance visible. An owner can delete a dataset version or an analysis and see content-free
evidence that it ended. Nothing is computed on any workspace surface; nothing crosses an organization's
opaque isolation scope; and every retained object has the lifecycle `[DEC-RETENTION]` fixes for its class.

**Three boundaries are stated here rather than discovered by an implementer.**

- **The one-time beta journey is unchanged.** `/beta` keeps `RRA-001`'s seven-day session and
  `RRA-002`'s deletion. The workspace is a second entry to the same admission, derivation and
  rendering path, reached from the commercial shell, and it retains under a different decision. Two
  lifecycles coexist until the beta is retired by its own artifact.
- **Nothing here recalculates.** Workspace surfaces select and present retained facts and artifacts.
  Run Again / Run New Period *start a new admission and derivation*; they never re-render an old
  package as a new result, and they never copy a figure forward.
- **Compare is not here.** Cross-dataset comparison is `G4/C1`'s. This specification lets two
  analyses exist side by side and shows whether their governed versions differ (`W1-08`); it does
  not put their figures in one table.

## Scope

- `src/khepri/rca/workspace/` (new) — domain contracts, persistence and services for the
  organization workspace: dataset versions, analysis runs, artifact bindings, source profiles,
  provenance, deletion, retention sweep.
- `src/khepri/runtime/shell_api.py` and `shell_templates/` — the Overview, Data and Analyses surfaces
  and the four-item navigation, under `RCA-002`'s frame (`FR-041`–`FR-049`); the shipped Team
  destination is not rebuilt.
- `migrations/` — one-head Alembic revisions for the new tables.
- Object-store namespaces for retained artifacts, as `RRA-002` already encrypts them, keyed by the
  organization's opaque scope.
- `tests/` — lifecycle, isolation, authorization, provenance and surface tests.

**Not in scope:** `src/khepri/rra/journey/` (`RRA-010`'s), `rra/rendering/` (`RRA-006`/`009`/`012`),
`rra/bundle.py` and the calculation families (`RRA-004`/`008`/`013`), the catalog routes
(`RRA-011`), and the shell's identity, membership and session code (`RCA-001`/`RCA-003`/`RCA-004`).

## Semantics (`G3-02`)

Seven terms, each with what it is, what it is not, and what makes it immutable.

| Term | Is | Is not | Immutable once |
|---|---|---|---|
| **Workspace** | The organization's opaque isolation scope (`RCA-001` `FR-031`–`FR-035`) seen as a container of dataset versions and runs. Exactly one per organization. | A customer-facing noun (blueprint §8: "Workspace" stays internal); a second scope; a folder hierarchy | Created with the organization's scope mapping |
| **Dataset version** | One admitted source: upload digest, size, media type, coverage manifest, confirmed mapping, admission outcome, `RRA-003` mapping version. | The raw bytes (those have their own row in the retention matrix); a "dataset" that changes in place — a new file is a new version, always | Sealed: facts derived and reconciled. After sealing only its *retention state* changes |
| **Analysis run** | One derivation over one dataset version at one instant: package and formula versions, quality (answered / caveated / refused per section), operational state, artifact bindings. | A re-render; a comparison; a schedule | Completed or failed. A run is never edited; Run Again creates a new run |
| **Comparison run** | Reserved term. A run whose input is two or more dataset versions. | Anything this specification builds — `G4/C1` | — |
| **Retained artifact** | One published surface of one run's bundle (web, evidence, PDF, Excel), bound to the run by digest. | Generated on demand (`RRA-006`: the bundle publishes together or not at all) | Published |
| **Source profile** | Descriptive metadata from a prior dataset version — column labels, confirmed mapping, manifest fields — offered for **re-attestation** on a new upload. | A shortcut past admission. Reuse re-runs `RRA-003` admission against the new source and refuses where it fails (Constitution V) | Never; it is metadata, deletable independently |
| **Tombstone** | What `[DEC-RETENTION]` says remains after deletion: opaque identifiers, timestamps, digests, versions. Rendered as a history row with no content action. | A soft-delete that can be undone; a place where a filename or figure survives | On deletion |

**Visibility.** Every member of the organization sees every dataset version, run, artifact and
tombstone in its workspace (`RCA-001` roles are owner and member; there is no per-object ACL and
none is introduced). A member of two organizations sees two workspaces and switches with the shipped
active-organization mechanism (`RCA-001` `FR-035`, `RCA-002`). Nothing is visible across scopes,
and a cross-scope request fails closed with the uniform content-free denial (`FR-034`, `FR-052`).

**Deletion semantics.** Deletion is by dataset version or by analysis run, owner-invoked, immediate,
idempotent, cascading exactly as `[DEC-RETENTION]` §3 states, and evidenced. Deleting a source profile
deletes no version. Deleting the last run of a version does not delete the version. There is no
"delete workspace": organization deletion stays excluded (`RCA-001`, `KHEPRI-DEC-015` §6), and content
under a disabled organization follows `[DEC-RETENTION]` OD-4.

## Requirements

### Domain and persistence

- **FR-109**: Every workspace object MUST be keyed by the organization's opaque isolation scope and
  MUST carry no commercial identifier (`RCA-001` `FR-032`, `FR-033`). A test proves no email,
  organization name, slug or human-readable identifier appears in any workspace table or object key.
- **FR-110**: A dataset version MUST be created only by the existing `RRA-003` admission path, and MUST
  record the admission outcome and mapping version it was admitted under. There is no second
  admission.
- **FR-111**: An analysis run MUST be produced only by the existing `RRA-004`/`RRA-006`/`RRA-008`
  pipeline, and MUST bind its retained artifacts by digest. A run naming fewer than every required
  surface is incomplete and MUST NOT be presented as completed (`RRA-006`).
- **FR-112**: Dataset versions and runs are append-only. A change to any content field after sealing
  or completion is refused. Only retention state and tombstoning may change a row.
- **FR-113**: Migrations MUST keep one Alembic head. A test asserts it.

### Reuse without recalculation

- **FR-114**: Run Again and Run New Period MUST start a new admission and derivation. Before
  confirming, the surface MUST show which prior configuration is proposed for reuse (mapping,
  manifest fields) and MUST refuse reuse where `RRA-003` admission against the new source fails.
  Nothing from the prior run's package is copied into the new one.
- **FR-115**: A source profile MUST be descriptive only. Presenting one MUST NOT skip, shorten or
  pre-fill past any `RRA-003` check; it pre-fills the *form*, and the check runs on what is submitted.
- **FR-116**: Where a later run's governed versions (`rra003.mapping.*`, `rra004.*`, `rra008.*`) differ
  from an earlier run's over the same or a related dataset version, the surface MUST show a
  Methodology Change Notice with the differing identifiers reachable, and MUST NOT present figures
  from the two runs as numerically comparable. It presents the *difference*; it computes nothing.

### Surfaces

- **FR-117**: Analyses is the single history spine (blueprint §7.3): newest first; each row states
  when it ran, which dataset version, operational state, trust state (through `RRA-012`'s components
  where a bundle state is shown), whether artifacts are available, retention state, and the next valid
  action. No filter system, no Compare, no fixed result count.
- **FR-118**: Artifacts are reached only from Analysis detail (blueprint §7.4). There is no reports
  index and no second list of the same objects.
- **FR-119**: The Analysis Passport on Analysis detail shows period, data reference, scope coverage,
  run timestamp and methodology/version context from the provenance record; digests and machine
  identifiers sit behind contextual audit detail, never leading.
- **FR-120**: Overview shows latest work, data state and items needing attention, drawn from rows
  this specification retains. No KPI, chart or business figure appears on Overview (`M3-U5`).
- **FR-121**: Navigation is Overview · Data · Analyses · Team, and a destination's link ships only in
  the slice that ships its surface (`RCA-002` `FR-049`; blueprint §19 ordering).
- **FR-122**: Every surface renders in both languages with right-to-left parity, meets the 44px target
  floor, uses logical properties only, and presents no state through colour alone, under `RCA-002`'s
  and `RRA-012`'s existing rules. A tombstone row reads as a tombstone in both languages.

### Lifecycle and evidence (`G3-03`)

- **FR-123**: Deletion MUST be owner-only, immediate, idempotent and cascading exactly as
  `[DEC-RETENTION]` §3 states. A second deletion of the same object succeeds and records nothing new.
- **FR-124**: Every deletion and every retention sweep MUST record content-free evidence: opaque
  identifiers, timestamps, digests, locations attempted, outcome, retry state (`RRA-002`), retained
  for `[DEC-RETENTION]` OD-2.
- **FR-125**: Every workspace action — create version, run, delete, sweep, profile reuse — MUST emit
  one content-free audit event carrying opaque actor, opaque organization, object identifiers, action,
  outcome and timestamp, under `KHEPRI-DEC-015` §7's logging rule and its twelve-month horizon.
- **FR-126**: A restore from backup MUST NOT make a deleted or tombstoned object readable. The
  mechanism is `KHEPRI-DEC-015` §8's revocation-ledger pattern applied to deleted object identifiers,
  bounded by the backup horizon plus a margin.
- **FR-127**: Cross-organization, expired, deleted, partial, corrupt, restore and concurrent
  lifecycle cases (`W1-10`) each have a test, and each failure mode fails closed with the uniform
  denial.

## Exclusions

This specification authorizes none of the following, and a slice claiming it is outside its
specification within the meaning of Constitution IV:

- Any calculation, comparison, aggregation or re-rendering of figures on a workspace surface.
  Comparison is `G4/C1`'s; figures are `RRA-004`/`RRA-008`'s; presentation components are `RRA-012`'s.
- Any change to admission, derivation, bundle assembly, rendering or the catalog routes.
- Any change to the `/beta` journey or its retention.
- Organization deletion, account deletion, cross-organization sharing or transfer, secure share links,
  scheduled or recurring runs, external connectors, raw-row export or preview, file preview.
- Per-object permissions, a third role, or any membership semantics (`RCA-001`).
- **Any telemetry event, of any kind.** `W1-11` waits for an owner-authored amendment to
  `KHEPRI-DEC-015` §3, exactly as `R8-08` does.
- Any retention horizon, trigger or post-trigger state not in `[DEC-RETENTION]`'s matrix. This
  specification reads that decision; it does not extend it.
- Inactivity expiry, unless `[DEC-RETENTION]` OD-3 chooses it.

## Invariants

- The opaque-scope boundary (`RCA-001` `FR-031`–`FR-035`) is unchanged and is the only isolation key.
- `RRA-002`'s encryption, evidence and deletion mechanics apply to every retained object unchanged.
- No customer content in logs, audit events, tombstones or evidence.
- Bilingual parity, RTL, target size, no colour alone, no inline script or style, CSP unweakened.
- One Alembic head; no downgrade that cannot run.

## Verification

- A test per FR above, with the isolation tests (`FR-109`, `FR-127`) driving real requests across two
  organizations and asserting the uniform denial byte-for-byte.
- A cascade test per `[DEC-RETENTION]` matrix row that names a cascade.
- A test that Run Again with an incompatible source refuses at admission and creates no run.
- A test that no workspace template, SQL read model or script computes, rounds or sums a figure.
- `khepri-gov validate`, `ruff check`, `pytest` green; CodeScene at the repository threshold.

## Implementation preconditions

1. `[DEC-RETENTION]` is `active`, with every `OD-n` fixed.
2. This specification is `active`.
3. `G3-04` has produced the bounded plan, in slices ordered as blueprint §19: contracts and
   persistence (`W1-01`–`W1-03`), services (`W1-04`), then surfaces in `FR-049` order
   (`M3-U1`…`M3-U5`), lifecycle (`W1-07`, `M3-U6`, `M3-U7`), hardening (`W1-10`, `M3-U8`).
4. `RCA-001`'s known carried risk — `resolve_scope` does not refuse a disabled account — is closed
   before any workspace consumer exists, because every workspace read resolves a scope.

## What this draft is not

It is not the retention decision (drafted beside it), not the plan (`G3-04`), not a schema. Its
`FR` numbers are provisional until promotion. It takes no owner decision; §3's semantics are proposed
for confirmation as `G3-02`'s clarification record.
