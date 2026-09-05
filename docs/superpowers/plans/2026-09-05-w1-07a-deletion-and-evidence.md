# `W1-07a` — Deletion, evidence, and the restore guard: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a customer a way to delete a dataset version, evidenced and idempotent, that a backup restore cannot undo.

**Architecture:** The RCA cascade already exists — `store.set_retention_state` writes the version tombstone, cascades to run tombstones, and returns early on a repeat without moving the deletion clock. This slice composes it: a deletion service in `khepri.runtime` that calls the RCA store and the RRA deletion repository under one owner-only route, writes content-free evidence once, emits one audit event, and records the deleted identifier in a new workspace revocation ledger.

**Tech Stack:** Python 3.13, SQLAlchemy 2, Alembic, FastAPI, pytest. Run tests with `./.venv/Scripts/python.exe -m pytest`.

**Spec:** `docs/superpowers/specs/2026-09-05-w1-07-deletion-and-retention-design.md`

## Global Constraints

- **`R7-01` §3**: `khepri.rca` and `khepri.rra` MUST NOT import each other. Composition happens in `khepri.runtime`.
- **Owner-only** (`FR-123`): a member cannot delete. Refusal is the uniform content-free denial.
- **Content-free**: evidence and audit events carry opaque identifiers, timestamps, digests, outcome, retry state — never a column label, value, or filename.
- **No surface may state that content expires automatically** (`KHEPRI-DEC-033` §5) until `W1-07b` merges.
- **Migration head is `20260905_0025`.** A new migration's `down_revision` is that, and moving the head means updating three pins: `RCA_REVISIONS` in `tests/test_rca001_migration.py` (middle field is the revision **file slug**, not a table name), the `alembic heads` assertion in `tests/test_rca001_session_persistence.py`, and `Migration head` in `specs/001-rca-001-commercial-identity/STATUS.md`.
- **Line length 100.** Run `./.venv/Scripts/python.exe -m ruff check src/ tests/` before every commit. Do **not** run `ruff format`.
- **Commit without signing:** `git -c commit.gpgsign=false commit`.
- **CodeScene gates** cyclomatic complexity >9, module function mean >4, >4 arguments, low cohesion. Pre-flight with `analyze_change_set` against `origin/main` after fetching.

---

### Task 1: The deletion audit vocabulary and its migration

**Files:**
- Modify: `src/khepri/rca/workspace/audit.py`
- Create: `migrations/versions/20260906_0026_rca_workspace_deletion_audit.py`
- Modify: `tests/test_rca001_migration.py`, `tests/test_rca001_session_persistence.py`, `specs/001-rca-001-commercial-identity/STATUS.md`
- Test: `tests/test_w107_deletion_audit.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ACTION_VERSION_DELETED = "version_deleted"`, `OUTCOME_ALREADY_DELETED = "already_deleted"`, both added to `AUDIT_ACTIONS` / `AUDIT_OUTCOMES`; `WorkspaceAuditEvent.already_deleted(...)` with the same signature as the existing `already_recorded`.

Today `AUDIT_ACTIONS` is `(version_created, run_started, run_completed, run_failed, profile_remembered, profile_reused)` and `AUDIT_OUTCOMES` is `(completed, refused, already_recorded)`. Both are CHECK-constrained in `rca_workspace_audit_events`. `FR-123` names `already_deleted` literally, and `already_recorded` is a different contract — reusing it would make the idempotency contract unreadable to the evidence consumer.

- [ ] **Step 1: Write the failing test**

```python
def test_the_deletion_vocabulary_is_admitted_by_the_domain_and_the_table() -> None:
    """`FR-123` names `already_deleted` literally, and both vocabularies are CHECK-constrained,
    so admitting it in Python alone would fail at the driver rather than at the domain."""
    from khepri.rca.workspace.audit import (
        ACTION_VERSION_DELETED,
        AUDIT_ACTIONS,
        AUDIT_OUTCOMES,
        OUTCOME_ALREADY_DELETED,
    )

    assert ACTION_VERSION_DELETED in AUDIT_ACTIONS
    assert OUTCOME_ALREADY_DELETED in AUDIT_OUTCOMES
    # `already_recorded` is a different contract and stays.
    assert "already_recorded" in AUDIT_OUTCOMES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107_deletion_audit.py -v`
Expected: FAIL with `ImportError: cannot import name 'ACTION_VERSION_DELETED'`

- [ ] **Step 3: Write minimal implementation**

In `src/khepri/rca/workspace/audit.py`, beside the existing constants:

```python
#: `W1-07a`. A customer ending a dataset version (`FR-123`). The cascade to its runs is part of
#: this action, not a second one -- `KHEPRI-DEC-033` §1 calls a named cascade part of the parent's
#: deletion, so a cascaded run does not emit an event of its own.
ACTION_VERSION_DELETED = "version_deleted"

#: `FR-123`'s idempotent repeat. **Not** `already_recorded`, which says a *write* was a duplicate;
#: this says the object was already ended, and the two reach different consumers.
OUTCOME_ALREADY_DELETED = "already_deleted"
```

Add `ACTION_VERSION_DELETED` to `AUDIT_ACTIONS` and `OUTCOME_ALREADY_DELETED` to `AUDIT_OUTCOMES`,
and add the named constructor beside `already_recorded`:

```python
    @classmethod
    def already_deleted(
        cls, event_id: str, entry: AuditEntry, *, occurred_at: datetime
    ) -> WorkspaceAuditEvent:
        """`FR-123`'s repeat: the object had already ended, and no new evidence was written."""
        return cls._record(event_id, entry, OUTCOME_ALREADY_DELETED, occurred_at=occurred_at)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107_deletion_audit.py -v`
Expected: PASS

- [ ] **Step 5: Write the migration**

Create `migrations/versions/20260906_0026_rca_workspace_deletion_audit.py`, `down_revision = "20260905_0025"`. Both CHECKs are recreated with the widened vocabulary; use `op.batch_alter_table` and drop/recreate each constraint, matching how `20260905_0022` spells its `_states_check` values literally. Then update the three head pins named in Global Constraints.

- [ ] **Step 6: Run the migration and pin tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca001_migration.py tests/test_rca001_session_persistence.py tests/test_rca001_status_consistency.py -q`
Expected: PASS. If `test_migration_columns_match_the_declared_models` fails, the literal spelling in the migration disagrees with `audit.py` — fix the migration, not the test.

- [ ] **Step 7: Commit**

```bash
git add -A
git -c commit.gpgsign=false commit -m "feat(w1-07a): admit the deletion action and the already_deleted outcome"
```

---

### Task 2: The workspace revocation ledger

**Files:**
- Create: `src/khepri/rca/workspace/revocation.py`
- Modify: `src/khepri/rca/workspace/schema.py`
- Create: `migrations/versions/20260906_0027_rca_workspace_revocations.py`
- Test: `tests/test_w107_revocation_ledger.py`

**Interfaces:**
- Consumes: Task 1's migration head (`20260906_0026`).
- Produces: `RevokedObject(object_kind: str, object_id: str, owner_id: str, revoked_at: datetime)`; `SqlRevocationLedger(factory)` with `revoke(revoked: RevokedObject) -> None` and `is_revoked(object_kind: str, object_id: str, owner_id: str) -> bool`.

No revocation ledger exists anywhere in the tree. `KHEPRI-DEC-015` §8 item 6 bounds its content: **opaque identifiers, revocation timestamps and status only** — no email, no verifier, no role history, no retail content. Workspace-scoped, per the spec §3.5.

- [ ] **Step 1: Write the failing test**

```python
def test_a_revoked_object_is_refused_even_when_its_row_is_readable() -> None:
    """`FR-126`. A restore puts the row back; the ledger is what keeps it unreadable, so the test
    asserts the ledger's answer for an object whose record still exists."""
    j = journey()
    who = member(j.w)
    ledger = SqlRevocationLedger(j.w.factory)
    ledger.revoke(
        RevokedObject(
            object_kind=OBJECT_VERSION, object_id="dsv-1", owner_id=who.owner_id, revoked_at=NOW
        )
    )

    assert ledger.is_revoked(OBJECT_VERSION, "dsv-1", who.owner_id) is True
    assert ledger.is_revoked(OBJECT_VERSION, "dsv-2", who.owner_id) is False


def test_the_ledger_holds_nothing_but_identifiers_timestamps_and_status() -> None:
    """`KHEPRI-DEC-015` §8 item 6: minimal and purpose-bound. An extent assertion, so a column
    added later fails here rather than quietly turning the ledger into a second content store."""
    from khepri.rca.workspace.schema import WorkspaceRevocationRow

    assert {c.name for c in WorkspaceRevocationRow.__table__.columns} == {
        "object_kind",
        "object_id",
        "owner_id",
        "revoked_at",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107_revocation_ledger.py -v`
Expected: FAIL with `ImportError` — `SqlRevocationLedger` does not exist.

- [ ] **Step 3: Write minimal implementation**

Add `WorkspaceRevocationRow` to `schema.py` with exactly those four columns, primary key `(object_kind, object_id, owner_id)`, `object_kind` CHECKed against `AUDIT_OBJECTS`, and `owner_id` indexed. Write `revocation.py` with the value and the store; `revoke` is idempotent (a second call for the same object is not an error and does not move `revoked_at`, for `set_retention_state`'s recorded reason).

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107_revocation_ledger.py -v`
Expected: PASS

- [ ] **Step 5: Write the migration and move the pins**

`down_revision = "20260906_0026"`. Update the same three pins.

- [ ] **Step 6: Commit**

```bash
git add -A
git -c commit.gpgsign=false commit -m "feat(w1-07a): the workspace revocation ledger, minimal and purpose-bound"
```

---

### Task 3: The deletion service

**Files:**
- Create: `src/khepri/runtime/workspace_deletion.py`
- Test: `tests/test_w107_deletion_service.py`

**Interfaces:**
- Consumes: Task 1's `ACTION_VERSION_DELETED` / `OUTCOME_ALREADY_DELETED`; Task 2's `SqlRevocationLedger`; the existing `store.tombstone_dataset_version(version_id, *, now, owner_id=None, sections_of=_no_sections)`.
- Produces: `DeletionOutcome(deleted: bool, version_id: str)`; `WorkspaceDeletion.delete_version(owner_id: str, version_id: str, *, actor_account_id: str, now: datetime) -> DeletionOutcome`.

**The cascade already exists.** `set_retention_state` locks the row, writes the version tombstone, cascades to run tombstones, and returns early on a repeat without moving `retention_changed_at`. This service composes it — it does not reimplement the walk. `deleted=False` is the already-deleted repeat.

- [ ] **Step 1: Write the failing test**

```python
def test_a_repeated_deletion_returns_the_same_answer_and_writes_no_second_evidence() -> None:
    """`FR-123`'s three separate claims, asserted separately: same response, no second evidence,
    one audit event with `already_deleted`. One outcome assertion would pass with two of the three
    broken."""
    j = journey()
    who = member(j.w)
    version = a_sealed_version(j, who)
    service = deletion_service(j)

    first = service.delete_version(who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW)
    second = service.delete_version(who.owner_id, version.version_id, actor_account_id=who.account_id, now=LATER)

    assert first.deleted is True and second.deleted is False
    assert first.version_id == second.version_id
    assert len(evidence_for(j, version.version_id)) == 1
    outcomes = [e.outcome for e in audit_events_for(j, who.owner_id) if e.action == ACTION_VERSION_DELETED]
    assert outcomes == [OUTCOME_COMPLETED, OUTCOME_ALREADY_DELETED]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107_deletion_service.py -v`
Expected: FAIL — `workspace_deletion` does not exist.

- [ ] **Step 3: Write minimal implementation**

`WorkspaceDeletion` takes the RCA store, the RRA deletion repository, the ledger and the audit recorder by constructor injection (`R7-01` §3: this is the composition seam). `delete_version` reads the version's retention state first; if already tombstoned it emits one `already_deleted` event and returns `deleted=False` without writing evidence or touching the ledger. Otherwise it calls `tombstone_dataset_version`, ends the RRA content through the deletion repository, writes one `DeletionEvidence`, revokes the identifier, and emits one `completed` event.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107_deletion_service.py -v`
Expected: PASS

- [ ] **Step 5: Mutation-test each of the three claims**

Break each separately and confirm a *different* assertion fails each time: (a) return `deleted=True` on the repeat, (b) write evidence on the repeat, (c) emit `OUTCOME_COMPLETED` on the repeat. Restore with `git stash` / `git stash pop` — **never `git checkout --`**, which discards uncommitted work.

- [ ] **Step 6: Commit**

```bash
git add -A
git -c commit.gpgsign=false commit -m "feat(w1-07a): the workspace deletion service, evidenced and idempotent"
```

---

### Task 4: The cascade table and its extent assertion

**Files:**
- Create: `src/khepri/rca/workspace/deletion_matrix.py`
- Test: `tests/test_w107_cascade_matrix.py`

**Interfaces:**
- Consumes: Task 3's service.
- Produces: `ENDINGS: Mapping[str, str]` — one entry per workspace table, valued `"tombstone"`, `"purge"` or `"cascade"`; `ENDING_TOMBSTONE`, `ENDING_PURGE`, `ENDING_CASCADE`.

`KHEPRI-DEC-033` §2 assigns every class an ending. The table asserts that matrix; it does not re-implement the walk `store.py` performs.

- [ ] **Step 1: Write the failing test**

```python
def test_every_workspace_table_has_exactly_one_ending() -> None:
    """The extent assertion. A table added without a rule fails here rather than surviving
    deletion silently -- the failure `#365` and `KHEPRI-DEC-033` §2 both turn on."""
    from khepri.rca.workspace.deletion_matrix import ENDINGS
    from khepri.rca.workspace.schema import Base

    workspace_tables = {
        t for t in Base.metadata.tables if t.startswith("rca_workspace_")
    }
    assert set(ENDINGS) == workspace_tables, (
        f"unruled: {workspace_tables - set(ENDINGS)}; unknown: {set(ENDINGS) - workspace_tables}"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107_cascade_matrix.py -v`
Expected: FAIL — `deletion_matrix` does not exist.

- [ ] **Step 3: Write minimal implementation**

One entry per `rca_workspace_*` table, each citing the `KHEPRI-DEC-033` §2 row it comes from in a comment. The audit-event and tombstone tables are **not** ended by a customer deletion (they are what survives it) — give them their own ending value rather than omitting them, so the extent assertion stays total.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107_cascade_matrix.py -v`
Expected: PASS

- [ ] **Step 5: Mutation-test the extent assertion**

Add a throwaway `rca_workspace_probe` table to `schema.py` **without** a rule; confirm the test fails. Remove it.

- [ ] **Step 6: Commit**

```bash
git add -A
git -c commit.gpgsign=false commit -m "feat(w1-07a): the ending matrix, with an extent assertion over every workspace table"
```

---

### Task 5: The route, owner-only

**Files:**
- Modify: `src/khepri/runtime/shell_api.py`, `src/khepri/runtime/wiring.py`
- Test: `tests/test_w107_deletion_route.py`

**Interfaces:**
- Consumes: Task 3's `WorkspaceDeletion.delete_version`.
- Produces: a `POST` at `{SHELL_PREFIX}/{language}/{organization}/data/{version_id}/delete`.

- [ ] **Step 1: Write the failing test**

```python
def test_a_member_cannot_delete_and_the_version_survives() -> None:
    """Driven through the real route, and asserting the *effect*: a test that calls the guard
    directly survives deletion of its call site, and a test asserting only the status code passes
    while the row is gone."""
    j = journey()
    owner = member(j.w)
    plain = member(j.w, email="member@example.test", name="Member", role="member")
    version = a_sealed_version(j, owner)

    response = client_for(j, plain).post(delete_address(owner, version.version_id))

    assert response.status_code in (403, 404)
    assert j.w.store.get_dataset_version(version.version_id, owner.owner_id) is not None
    assert j.w.store.tombstones_for_scope(owner.owner_id) == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107_deletion_route.py -v`
Expected: FAIL — the address is unknown, or the version is gone.

- [ ] **Step 3: Write minimal implementation**

Dispatch inside `_scoped_response`, following how `W1-06` reaches Analysis detail. Owner check through the resolver's `require_owner`; the refusal is the uniform `unavailable`.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107_deletion_route.py -v`
Expected: PASS

- [ ] **Step 5: Mutation-test the owner check**

Delete the `require_owner` call; confirm the test fails on the *effect* assertion (the version is gone), not only on the status code.

- [ ] **Step 6: Commit**

```bash
git add -A
git -c commit.gpgsign=false commit -m "feat(w1-07a): the owner-only deletion route"
```

---

### Task 6: The restore guard, and the copy check

**Files:**
- Modify: `src/khepri/runtime/shell_workspace.py` (or the read path the Data surface uses)
- Test: `tests/test_w107_restore_and_copy.py`

**Interfaces:**
- Consumes: Task 2's `SqlRevocationLedger.is_revoked`; Task 5's route.

- [ ] **Step 1: Write the failing test**

```python
def test_a_restored_deleted_version_is_not_readable() -> None:
    """`FR-126`. The restore is simulated the only honest way at this layer: the row is put back
    exactly as a backup would, and the ledger is what must still refuse it."""
    j = journey()
    who = member(j.w)
    version = a_sealed_version(j, who)
    delete_through_the_route(j, who, version)
    restore_the_row(j, version)  # the row is readable again, as after a restore

    assert reader_for(j).dataset_version(who.owner_id, version.version_id) is None


def test_no_surface_says_content_expires_automatically() -> None:
    """`KHEPRI-DEC-033` §5: until `W1-07b` ships a sweep with a caller, no surface may tell a
    customer that content expires by itself.

    **This guard passes over an empty set today** -- no `SHELL_COPY` string contains the word --
    so it was proven by the inverse mutant instead: adding a violating string makes it fail, and
    removing it makes it pass again. Recorded here because a guard nobody has watched fail is not
    evidence of anything (`W1-07a` review).
    """
    for language in ("en", "ar"):
        for key, text in SHELL_COPY[language].items():
            assert "automatic" not in str(text).lower(), key
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107_restore_and_copy.py -v`
Expected: FAIL — the restored row reads back.

- [ ] **Step 3: Write minimal implementation**

The workspace read path consults the ledger before returning a version. Keep the check in one place so a second read path cannot bypass it.

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107_restore_and_copy.py -v`
Expected: PASS

- [ ] **Step 5: Prove the copy check can fail**

Add a violating string to `SHELL_COPY["en"]` (e.g. `"probe": "Content is deleted automatically."`),
run the test and confirm it FAILS naming that key, then remove the string and confirm it passes.
A guard that has never been watched fail is not evidence.

- [ ] **Step 6: Full verification**

```bash
./.venv/Scripts/python.exe -m ruff check src/ tests/
./.venv/Scripts/python.exe -m pytest -p no:randomly -q
git fetch origin
```
Then CodeScene `analyze_change_set` against `origin/main`. Expected: `4612+` passed, ruff clean, quality gates passed.

- [ ] **Step 7: Commit and open the PR**

```bash
git add -A
git -c commit.gpgsign=false commit -m "feat(w1-07a): the restore guard, and the copy check DEC-033 §5 requires"
git push -u origin feat/w1-07a-deletion-and-evidence
```

---

## Self-Review

**Spec coverage:** `FR-123` → Tasks 1, 3, 5. `FR-124` → Task 3. `FR-126` → Tasks 2, 6. Cascade table → Task 4. Copy check (spec §2) → Task 6. Migration pins → Tasks 1, 2. Non-goals carry no task, by design.

**Known gaps for the executor to close, not silently invent:**
- Tasks 3, 5 and 6 name helpers (`a_sealed_version`, `deletion_service`, `evidence_for`, `audit_events_for`, `delete_address`, `client_for`, `restore_the_row`, `reader_for`) that do not exist yet. Build them in `tests/w107_support.py` following `tests/w106_support.py`'s shape, and use **production verbs** for setup — raw-SQL setup exempts the transition and lets a mutant of the bypassed verb survive.
- Task 6's copy check asserts on the English word "automatic"; when the Arabic copy is written, assert the Arabic term too rather than only the English.
- `DeletionEvidence` is at `src/khepri/rra/deletion.py:44` and its fields are `evidence_id`, `deletion_id`, `target_kind`, `target_id`, `location_digest`, `content_digest`, `attempted_at`, `attempt_number`, `outcome`, `error_code`. Note it is keyed **per target**, not per object: `FR-124` says evidence is written "once per object per ending", so Task 3's `len(evidence_for(...)) == 1` must count *endings of this version*, not rows. Decide which the helper counts before writing it, and say so in its docstring — counting rows would make the assertion pass or fail for the wrong reason once a version has several targets.
