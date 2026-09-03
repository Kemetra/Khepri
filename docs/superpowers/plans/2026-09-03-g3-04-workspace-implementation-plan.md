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

Nine slices. Each names its requirements, its acceptance, and the one thing most likely to go wrong.

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

### `W1-06` — The Analyses history spine

- **Requirements:** `FR-117`, `FR-121`, `FR-122`.
- **Delivers:** the Analyses surface, newest first, each row carrying run time, dataset version,
  operational state, trust state through `RRA-012`'s components, artifact availability, retention
  state and next valid action. The Analyses navigation link.
- **Acceptance:** a tombstone row renders as a tombstone in both languages with no content action;
  no filter system, no Compare control, no fixed result count.
- **Risk:** reaching for a second trust vocabulary. Trust state must come through `RRA-012`'s
  components; a new badge here is a duplicate source of truth for the same concept.

### `W1-07` — Analysis detail, the Passport, and artifact access

- **Requirements:** `FR-118`, `FR-119`, `FR-116`.
- **Delivers:** Analysis detail, the Analysis Passport, artifact links, and the Methodology Change
  Notice where governed versions differ.
- **Acceptance:** artifacts are reachable from nowhere else — a scan proves no second index; the
  Passport leads with period, data reference, coverage, timestamp and methodology, with digests
  behind contextual detail; the Change Notice presents differing identifiers and no comparison of
  figures.
- **Risk:** the Change Notice implying comparability. `FR-116` says it presents the *difference*
  between versions and computes nothing — no delta, no percentage, no "up from".

### `W1-08` — Deletion, evidence, and the retention sweep

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

### `W1-09` — Isolation and failure hardening

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

`KHEPRI-DEC-033` §5: no retention horizon is enforced until `W1-08` ships the sweep with a deployed
caller. Until that merges, **no surface built above may tell a customer that content expires
automatically** — not in copy, not in a retention-state label, not in a tooltip. A surface that says
"expires in 7 days" before the sweep runs is stating something the image does not do.
