# `G3-04` — The bounded implementation plan for the organization workspace

**Authority:** `RCA-005` (active), reading `KHEPRI-DEC-033` (active). Both merged 2026-09-03.
**Roadmap:** `G3-04`, the last governance task before `W1-01`. Closes `§17` item 16; opens item 17.
**Raised on:** `main` after the `G2-03`/`G3-03` activation.

This plan allocates `RCA-005`'s nineteen requirements to slices. It writes no code and decides
nothing the specification left open. Each slice below is one PR carrying a plan-and-RED commit then
an implementation commit, per the repository's standing rule.

---

## 1. The ordering constraint, stated once

`RCA-005` `FR-121` and `RCA-002` `FR-049` require that **a navigation link ships only in the slice
that ships its destination.** That single rule fixes the surface order: no Data link before the Data
surface exists, no Analyses link before the Analyses surface exists. Blueprint §19 gives the same
order for a different reason — a customer should meet the history spine before the passport that
hangs off it.

The persistence slices come first for a harder reason: `FR-112` makes dataset versions and runs
append-only, and an append-only table is expensive to reshape after rows exist. Contracts before
tables, tables before services, services before surfaces.

## 2. Slices

Eleven PRs across eight roadmap tasks, **numbered as the roadmap's `W1` task table numbers them** —
`W1-07` is lifecycle and `W1-08` is the version diff, not the reverse. `W1-05` is one roadmap task
delivering three surfaces, split into two PRs for reviewable size. `W1-04b` was added on 2026-09-05 after
review on `#373`: the seam between the services and the surfaces, which the first allocation left
unnamed.

**Build order is not numeric order.** `W1-08` (the Change Notice) is built before `W1-07` (deletion
and the sweep), because the Notice is a read over rows `W1-06` already retains, while `W1-07`
introduces the first destructive path and should land after every read surface it can affect exists.
The roadmap's dependency column permits both.

Each slice names its requirements, its acceptance, and the one thing most likely to go wrong.

### `W1-01` — Domain contracts and the source profile

- **Requirements:** `FR-109`, `FR-110`, `FR-115`.
- **Delivers:** `rca/workspace/contracts.py` — frozen dataclasses for dataset version, analysis run,
  artifact binding, source profile, tombstone. No persistence. The source-profile type carries only
  descriptive metadata, and its docstring states that it pre-fills a form and never a check.
- **Acceptance:** a test constructs each type and proves no field can hold a commercial identifier;
  a test proves the profile type has no field that could carry an admission outcome.
- **Risk:** modelling the profile as "a mapping you can apply" rather than "metadata you can read".
  `FR-115` is a *shape* constraint, not only a runtime one — if the type can carry a decision, a
  later slice will apply it.

### `W1-02` — Persistence and the one-head migration

- **Requirements:** `FR-109`, `FR-112`, `FR-113`.
- **Delivers:** tables for dataset versions, runs, artifact bindings, source profiles and
  tombstones, each keyed by the opaque scope; one Alembic revision; a repository with the append-only
  rule enforced at the write path, not by convention.
- **Acceptance:** `alembic heads` shows one head; an update to a content field after sealing raises;
  a scan proves no column holds an email, name or slug. Run real DDL against Postgres on
  `127.0.0.1:5432` — SQLite cannot express the constraints and will pass a migration Postgres
  refuses.
- **Risk:** enforcing append-only in the service layer only. Mutate the repository directly in a
  test; if the row changes, the guard is in the wrong place.

### `W1-03` — The tombstone allowlist

- **Requirements:** `FR-112`, and `KHEPRI-DEC-033` §3.
- **Delivers:** the tombstone projection for dataset version and analysis run, built from an explicit
  allowlist of field names rather than by removing fields from the live record.
- **Acceptance:** a test asserts each tombstone's field set **equals** its allowlist exactly — an
  equality assertion, not a subset one, so a field added to the live record cannot arrive in the
  tombstone by default. This is the test `KHEPRI-DEC-033` §3 promises.
- **Risk:** building the tombstone by deletion (`del d["filename"]`). A new sensitive field then
  passes straight through. Build it by construction from the allowlist.

### `W1-04` — Workspace services

- **Requirements:** `FR-110`, `FR-111`, `FR-114`, `FR-125`.
- **Delivers:** create-version, create-run and reuse-profile services, each calling the existing
  `RRA-003` admission and `RRA-004`/`RRA-006`/`RRA-008` pipeline. Every action emits one content-free
  audit event.
- **Acceptance:** a run bound to fewer than every required surface is not presented as completed;
  Run Again with an incompatible source refuses at admission and creates no run; each service emits
  exactly one audit event, asserted by count.
- **Risk:** a second admission path. If this slice can create a dataset version without calling
  `RRA-003`, `FR-110` is violated however the code reads. Drive the test through the real admission
  entry point.

### `W1-05` — Overview and the Data surface

- **Requirements:** `FR-120`, `FR-121`, `FR-122`, plus `FR-117`'s row vocabulary where Data shows
  version state.
- **Delivers:** the Overview and Data surfaces, the Data navigation link, both languages, RTL.
- **Acceptance:** a scan proves no template computes, rounds or sums; Overview carries no KPI,
  chart or figure (`M3-U5`); the Data link is absent before this slice and present after.
- **Risk:** an Overview "summary number". `FR-120` forbids a business figure, and a count of
  analyses is a presentation of retained rows rather than a computed metric — state which side of
  that line each element sits on, in the slice's own plan, before building it.

### `W1-05` (continued) — The Analyses history spine

The roadmap's `W1-05` is one task delivering *Overview, Data and Analyses* into one four-item
navigation. It is split into two PRs here for reviewable size, not into two roadmap tasks.

- **Requirements:** `FR-117`, `FR-121`, `FR-122`.
- **Delivers:** the Analyses surface, newest first, each row carrying run time, dataset version,
  operational state, trust state through `RRA-012`'s components, artifact availability, retention
  state and next valid action. The Analyses navigation link.
- **Acceptance:** a tombstone row renders as a tombstone in both languages with no content action;
  no filter system, no Compare control, no fixed result count.
- **Risk:** reaching for a second trust vocabulary. Trust state must come through `RRA-012`'s
  components; a new badge here is a duplicate source of truth for the same concept.

### `W1-04b` — The pipeline records the workspace

*Added 2026-09-05, after review on `#373` found the seam this plan had not allocated.* `W1-04`
delivered the actions and `W1-05` the surfaces that read them, and nothing in the deployed
application called the actions: the shell's entry route (`R8-06`) opens a journey session and the
journey's own routes admit, derive and report, so a customer's real work would have left Overview
saying nothing had been submitted -- the fake capability `RCA-002` `FR-049` exists to prevent.
`#373` carried the question as an owner decision; it was merged with the empty states understood as
provisional, and this slice is the wiring that follows.

- **Requirements:** `FR-110`, `FR-111`, `FR-125`; `RCA-002` `FR-049`.
- **Delivers:** three decorators at the composition root and nothing inside `rra/`: the profile
  route records the admitted, attested source as a dataset version; the report request starts the
  run and binds it to the job that will settle it (`rca_workspace_run_reports`, one migration, one
  head); the worker completes the run from the delivery, every artifact by digest, or fails it when
  the queue dead-letters the job. Events name the pipeline as actor (`ACTOR_PIPELINE`) in the scope
  the session already carries. The scope-level recording is extracted from `WorkspaceActions` into
  `workspace_recording.py`, so the customer door and the pipeline door share one implementation.
- **Acceptance:** the journey's own HTTP routes and the real worker, over one engine, put the
  submission on Data, the run on Overview as processing, then as completed with seven bindings whose
  digests are the stored artifacts' own, and the version sealed; a dead-lettered job fails the run
  and Overview asks for attention; a re-posted profile and a re-requested report are one version and
  one run with `already_recorded` events; a session no organization owns records nothing and still
  gets its report; an unattested source records nothing and no event; `build_web_app` hands
  `create_app` the recording services and `build_worker_loop` the settling store.
- **Risk:** a run the worker cannot find. Two processes hold one run; the link table is how the
  second finds it, and the unique constraint on `job_id` is the arbiter between two requests that
  both found no link. A job identifier is written to a workspace row where a session identifier is
  not, because it confers nothing (`FR-023`) and is not bearer-adjacent; the column guard in
  `test_w104_audit_events.py` allows exactly that one column on exactly that table.
- **Carried, not closed:** an unattested source is not a dataset version (`W1-01` made the manifest
  part of one; `KHEPRI-DEC-033` §3 keeps its digest) while the journey's attestation is optional, so
  its analysis is not workspace history. Whether `RCA-005` should admit an unattested version, or the
  commercial journey should require attestation, is an owner reading this slice states rather than
  takes. And the journey's own `DELETE /api/v1/beta/content` dead-letters a session's jobs in SQL
  without passing the worker, so a run whose content was deleted that way stays `started`;
  `W1-07` owns deletion and reconciles it.

### `W1-06` — Analysis detail, provenance, and the Analysis Passport

- **Requirements:** `FR-118`, `FR-119`.
- **Delivers:** Analysis detail, immutable provenance and fact/artifact bindings, the Analysis
  Passport, and artifact links.
- **Acceptance:** artifacts are reachable from nowhere else — a scan proves no second index; the
  Passport leads with period, data reference, coverage, timestamp and methodology, with digests
  behind contextual audit detail.
- **Risk:** the Passport leading with digests. `FR-119` puts machine identifiers behind contextual
  detail; a passport that opens with a hash reads as provenance for auditors, not for the customer.

### `W1-08` — The Methodology Change Notice

- **Requirements:** `FR-116`.
- **Delivers:** the version and availability diff between two analyses, presented as a Methodology
  Change Notice where governed mapping, formula or family versions differ.
- **Acceptance:** the Notice presents the differing identifiers and reaches them; it presents no
  delta, percentage or "up from", and no figure from either run beside the other.
- **Risk:** the Notice implying comparability. `FR-116` says it presents the *difference* between
  versions and computes nothing. This is also the boundary with `G4/C1`: showing that two runs
  differ is here; putting their figures in one table is not.

### `W1-07` — Deletion, evidence, and the retention sweep

- **Requirements:** `FR-123`, `FR-124`, `FR-126`, and `KHEPRI-DEC-033` §5.
- **Delivers:** owner-only deletion with cascade, first-deletion evidence, the `already_deleted`
  idempotent path, the revocation-ledger guard against a backup restore, and **the retention sweep
  with a caller present in the shipped image.**
- **Acceptance:** a cascade test per `KHEPRI-DEC-033` §2 row that names one; a repeated deletion
  returns the same response, writes no second evidence record and emits one audit event with outcome
  `already_deleted`; a member cannot delete; a restored deleted object is not readable. **And the
  §5 obligation: a test proves the sweep's caller exists in the built wheel, not only in
  `khepri.local.cli`.**
- **Risk:** this slice carries `KHEPRI-DEC-033` §5 and is the only one that can discharge it.
  Shipping deletion without the sweep leaves every horizon in the decision unenforced while the
  product looks finished. `pyproject.toml` excludes `khepri/local` from the wheel — verify against
  the built artifact, not the source tree.

### `W1-10` — Isolation and failure hardening

- **Requirements:** `FR-127`, and re-verification of `FR-109`.
- **Delivers:** the cross-organization, expired, deleted, partial, corrupt, restore and concurrent
  lifecycle tests.
- **Acceptance:** each isolation test drives real requests across two organizations and asserts the
  uniform content-free denial byte-for-byte; each failure mode fails closed.
- **Risk:** testing the guard rather than the caller. A test that calls the isolation check directly
  survives deletion of its call site — drive the real route.

## 3. What this plan does not allocate

- **`W1-11` repeat-use telemetry.** Excluded by `RCA-005` and by `KHEPRI-DEC-015` §3. It needs an
  owner-authored amendment, exactly as `R8-08` does, and no slice above may emit a product metric.
- **Comparison.** `G4/C1`'s. `W1-07`'s Change Notice shows that versions differ; it never puts two
  runs' figures together.
- **Inactivity expiry.** `KHEPRI-DEC-033` §4 decided against it.
- **Anything on `/beta`.** `RRA-010` governs the journey and `RCA-005` excludes changing it.

## 4. Preconditions, as measured

| # | Precondition | State |
|---|---|---|
| 1 | `KHEPRI-DEC-033` active | **Met** on merge |
| 2 | `RCA-005` active | **Met** on merge |
| 3 | This plan exists | **Met** by this document |
| 4 | `resolve_scope` refuses a disabled account | **Met** — `rca/isolation.py:32` refuses on `not account.can_act`; covered by `tests/test_rca001_authorization_resolution.py`. Re-measured rather than inherited |

`W1-01` may begin.

## 5. One standing caution for every slice

`KHEPRI-DEC-033` §5: no retention horizon is enforced until `W1-07` ships the sweep with a deployed
caller. Until that merges, **no surface built above may tell a customer that content expires
automatically** — not in copy, not in a retention-state label, not in a tooltip. A surface that says
"expires in 7 days" before the sweep runs is stating something the image does not do.
