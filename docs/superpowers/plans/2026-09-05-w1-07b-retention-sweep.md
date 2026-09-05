# `W1-07b` — Retention Sweep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a retention sweep with a caller present in the built wheel, and implement the two `KHEPRI-DEC-033` §2 horizons that have no implementation anywhere.

**Architecture:** The existing `LocalSweeper` composition moves from `khepri/local/sweeper.py` to `khepri/runtime/retention_sweep.py` and is renamed `RetentionSweeper`; `khepri.local` re-exports it so there is one definition. Two new twelve-month purges join `RetentionPasses` as optional fields — workspace audit events (RCA) and deletion evidence (RRA) — and the sweep records its own audit event per scope, which requires one `CHECK`-widening migration.

**Tech Stack:** Python 3.13, SQLAlchemy 2, Alembic, pytest, hatchling (wheel build), uv.

**Spec:** `docs/superpowers/specs/2026-09-05-w1-07b-retention-sweep-design.md`

## Global Constraints

- **`R7-01` §3**: `khepri.rca` and `khepri.rra` MUST NOT import each other. Composition happens in `khepri.runtime`.
- **Twelve months is `MEMBERSHIP_EVENT_RETENTION_MONTHS`** (`rca/lifecycle.py:54`), reused with `_months_before` — never a second literal. `KHEPRI-DEC-033` §2 says this horizon is "adopted rather than re-derived".
- **The migration head is pinned in three places**, all moving together: `RCA_REVISIONS` in `tests/test_rca001_migration.py` (middle field is the migration **file slug**, not a table), the `alembic heads` assertion in `tests/test_rca001_session_persistence.py:434`, and `Migration head` in `specs/001-rca-001-commercial-identity/STATUS.md:10`. Current head: `20260906_0027`.
- **Content-free**: every audit event and every evidence row carries opaque identifiers only (`KHEPRI-DEC-015` §7).
- **Do NOT amend `KHEPRI-DEC-033` §5.** It is the clause that gates this change; marking it discharged is the owner's edit.
- **Do NOT delete the `_EXPIRY_CLAIMS` copy guard** in `tests/test_w107_restore_and_copy.py`.
- Run tests with `./.venv/Scripts/python.exe -m pytest`. Do NOT run `ruff format` (no CI format gate); DO run `./.venv/Scripts/python.exe -m ruff check .`.
- Commit with `git commit -F -` (heredoc); rebase ignores `-c commit.gpgsign`.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/khepri/runtime/retention_sweep.py` | **Create.** The moved composition (`RetentionSweeper`, `RetentionPasses`, `RetentionCounts`, `SweepReport`, `REASON_EXPIRED`, `build_retention_sweeper`) plus `main()`, the console-script entry point. |
| `src/khepri/local/sweeper.py` | **Replace with a re-export.** Keeps `local/wiring.py` and `tests/test_local_sweeper.py` importing the same names from the same path. |
| `src/khepri/rca/workspace/audit.py` | **Modify.** Add `ACTION_RETENTION_SWEPT`, `ACTOR_RETENTION`; extend `AUDIT_ACTIONS`. |
| `src/khepri/rca/workspace/audit_persistence.py` | **Modify.** Add `purge_events_before(horizon)` and `scopes_with_events_before(horizon)`. |
| `src/khepri/rca/workspace/audit_retention.py` | **Create.** `WorkspaceAuditSweeper` — the RCA twelve-month pass. |
| `src/khepri/rra/evidence_retention.py` | **Create.** `DeletionEvidenceSweeper` — the RRA twelve-month pass. |
| `src/khepri/rra/persistence.py` | **Modify.** Add `purge_evidence_before(horizon)` to `SqlDeletionRepository`. |
| `migrations/versions/20260906_0028_rca_workspace_sweep_audit.py` | **Create.** Widen the action `CHECK` only. |
| `pyproject.toml` | **Modify.** Add the `khepri-retention-sweep` console script. |
| `tests/test_w107b_wheel_entry_point.py` | **Create.** §5's discharge: the entry point resolves inside the built wheel. |
| `tests/test_w107b_retention_horizons.py` | **Create.** One test per new horizon, plus the self-purge guard. |
| `tests/test_w107b_unenforced_flag.py` | **Create.** The scan replacing `INVITATION_HORIZON_IS_UNENFORCED`. |

---

## Task 1: Move the composition into the wheel-reachable package

**Files:**
- Create: `src/khepri/runtime/retention_sweep.py`
- Modify: `src/khepri/local/sweeper.py` (becomes a re-export)
- Test: `tests/test_w107b_wheel_entry_point.py` (created here, extended in Task 2)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `khepri.runtime.retention_sweep.RetentionSweeper`, `.RetentionPasses`, `.RetentionCounts`, `.SweepReport`, `.REASON_EXPIRED`, `.build_retention_sweeper(*, jobs, deletion, factory, retention=None) -> RetentionSweeper`. Task 3 and Task 4 add fields to `RetentionPasses`; Task 5 adds `main()` to this module.

- [ ] **Step 1: Write the failing test**

Create `tests/test_w107b_wheel_entry_point.py`:

```python
"""`W1-07b` -- the sweep must be reachable from the built wheel (`KHEPRI-DEC-033` §5).

§5's obligation is discharged by evidence against the **built artifact**, not the source tree: a
source-tree assertion passes today and proves nothing, since every sweeper already exists in source.
"""

from __future__ import annotations


def test_the_composition_has_exactly_one_definition() -> None:
    """`khepri.local` re-exports the runtime composition rather than keeping a copy.

    Two compositions is the "second deletion implementation to keep correct" `local/sweeper.py`'s
    own docstring warns against. Asserted by identity, so a copy-paste fails here.
    """
    from khepri.local import sweeper as local
    from khepri.runtime import retention_sweep as runtime

    assert local.RetentionSweeper is runtime.RetentionSweeper
    assert local.RetentionPasses is runtime.RetentionPasses
    assert local.build_retention_sweeper is runtime.build_retention_sweeper
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107b_wheel_entry_point.py -x -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'khepri.runtime.retention_sweep'`

- [ ] **Step 3: Move the module**

```bash
git mv src/khepri/local/sweeper.py src/khepri/runtime/retention_sweep.py
```

In `src/khepri/runtime/retention_sweep.py`, rename the class and factory, and replace the module docstring's first paragraph. Rename `LocalSweeper` → `RetentionSweeper` and `build_local_sweeper` → `build_retention_sweeper` throughout, and update `__all__`:

```python
__all__ = [
    "REASON_EXPIRED",
    "RetentionCounts",
    "RetentionPasses",
    "RetentionSweeper",
    "SweepReport",
    "build_retention_sweeper",
]
```

Replace the opening docstring paragraph with:

```python
"""The retention and recovery sweep, and the caller `KHEPRI-DEC-033` §5 requires.

**Why this module is in `khepri.runtime`.** The wheel excludes `src/khepri/local`, so a sweep
composed there is absent from the image that must run it -- which is what §5 measured and named as
the reason no retention horizon is enforced. `pyproject.toml:45` records the same reasoning for
`khepri-clerk-hard-stop`: a command in `khepri.local` "would be absent from the built artifact".

**Named `RetentionSweeper`, not `LocalSweeper`.** Once this ships in the wheel it is *the* sweeper.
A name saying "local" would misdescribe the deployed artifact to the next reader, which is how a
later slice comes to write a second one for "real" deployments.

**Nothing here is a scheduler.** It runs one pass when called. Choosing a cadence is an operational
decision, and a loop that invented one would be modelling a deployment nobody has authorized.
`KHEPRI-DEC-033` decides no cadence; §5 asks for *a caller present in the shipped image*, which a
console script in the wheel is.
"""
```

- [ ] **Step 4: Write the re-export**

Create `src/khepri/local/sweeper.py`:

```python
"""Re-export of the retention sweep, which now lives in `khepri.runtime`.

The composition moved to `khepri/runtime/retention_sweep.py` in `W1-07b` so it ships in the wheel
(`KHEPRI-DEC-033` §5). This module keeps `khepri.local`'s import path working and holds **no
second definition** -- `test_the_composition_has_exactly_one_definition` asserts identity, so a
copy here fails rather than drifting.
"""

from __future__ import annotations

from khepri.runtime.retention_sweep import (
    REASON_EXPIRED,
    RetentionCounts,
    RetentionPasses,
    RetentionSweeper,
    SweepReport,
    build_retention_sweeper,
)

__all__ = [
    "REASON_EXPIRED",
    "RetentionCounts",
    "RetentionPasses",
    "RetentionSweeper",
    "SweepReport",
    "build_retention_sweeper",
]
```

- [ ] **Step 5: Repoint the two existing callers**

In `src/khepri/local/wiring.py:32`, change the import:

```python
from khepri.local.sweeper import RetentionPasses, RetentionSweeper, build_retention_sweeper
```

Then update `:134` (`sweeper: LocalSweeper` → `sweeper: RetentionSweeper`) and the
`build_local_sweeper(` call site to `build_retention_sweeper(`.

In `tests/test_local_sweeper.py:16`, change to:

```python
from khepri.local.sweeper import REASON_EXPIRED, RetentionPasses, RetentionSweeper
```

and `:50` `class StubSweeper(LocalSweeper):` → `class StubSweeper(RetentionSweeper):`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107b_wheel_entry_point.py tests/test_local_sweeper.py -q`
Expected: PASS. `test_local_sweeper.py` must pass **unchanged in behaviour** — it is the existing evidence that the composition works, and this task must not weaken it while relocating it.

- [ ] **Step 7: Run the full suite**

Run: `./.venv/Scripts/python.exe -m pytest -q --basetemp=.pytest-tmp-w107b`
Expected: PASS. Five test files import this module; a move is exactly the change that breaks suites you never opened.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -F - <<'MSGEOF'
refactor(w1-07b): move the sweep composition into the wheel-reachable package

`KHEPRI-DEC-033` §5 records that no retention horizon is enforced because every
sweeper's only caller is `khepri.local.cli`, which the wheel excludes. This moves the
composition to `khepri.runtime`, where `khepri-clerk-hard-stop` already lives for the
same reason.

Renamed `RetentionSweeper`: once it ships in the wheel it is *the* sweeper, and a name
saying "local" is how a later slice comes to write a second one for "real" deployments.

`khepri.local.sweeper` becomes a re-export holding no second definition, asserted by
identity so a copy fails rather than drifting.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSGEOF
```

---

## Task 2: The wheel entry point, and the test that can actually fail

**Files:**
- Modify: `src/khepri/runtime/retention_sweep.py` (add `main()`)
- Modify: `pyproject.toml` (add the console script)
- Test: `tests/test_w107b_wheel_entry_point.py`

**Interfaces:**
- Consumes: `khepri.runtime.retention_sweep.build_retention_sweeper` from Task 1.
- Produces: the console script `khepri-retention-sweep = "khepri.runtime.retention_sweep:main"`.

**Why the obvious test is worthless — read before writing it.** This was measured, not assumed. A wheel built from a `pyproject.toml` carrying `khepri-phantom = "khepri.local.cli:main"`, with `exclude = ["src/khepri/local"]` unchanged, produced:

```
[console_scripts]
khepri-phantom = khepri.local.cli:main      <- declared
khepri/local packaged: False                 <- absent
```

`entry_points.txt` comes from `[project.scripts]` metadata; `exclude` governs packaged files. They are independent. A test reading the manifest passes over a command that crashes on invocation.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_w107b_wheel_entry_point.py`:

```python
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ENTRY_POINT = "khepri-retention-sweep"


@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The actual wheel, built the way the image is built."""
    out = tmp_path_factory.mktemp("wheel")
    built = subprocess.run(
        ["uv", "build", "--wheel", "-o", str(out)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    if built.returncode != 0:
        pytest.skip(f"uv build unavailable: {built.stderr[-300:]}")
    return next(out.glob("*.whl"))


def _declared_target(wheel: Path, name: str) -> str:
    """The `module:function` the wheel declares for one console script."""
    archive = zipfile.ZipFile(wheel)
    for entry in archive.namelist():
        if entry.endswith("entry_points.txt"):
            for line in archive.read(entry).decode().splitlines():
                if line.startswith(f"{name} ="):
                    return line.split("=", 1)[1].strip()
    raise AssertionError(f"{name} is not declared in the wheel")


def test_the_sweep_entry_point_resolves_inside_the_built_wheel(built_wheel: Path) -> None:
    """`KHEPRI-DEC-033` §5: a caller **present in the shipped image**.

    Resolved against the wheel's **contents**, never against `entry_points.txt` alone. Measured
    while designing this slice: a wheel will happily declare `khepri-phantom = khepri.local.cli:main`
    while `khepri/local` is absent from that same wheel, because entry points come from project
    metadata and `exclude` governs packaged files. A manifest test therefore passes over a command
    that crashes on invocation -- reproducing, inside the test meant to prove §5 closed, exactly the
    unreachable-procedure shape §5 exists to close.
    """
    target = _declared_target(built_wheel, ENTRY_POINT)
    module, _, function = target.partition(":")
    assert function == "main", target

    packaged = set(zipfile.ZipFile(built_wheel).namelist())
    assert f"{module.replace('.', '/')}.py" in packaged, (
        f"{ENTRY_POINT} targets {module}, which the wheel does not package"
    )


def test_the_sweep_module_imports_with_no_excluded_package(built_wheel: Path) -> None:
    """The command must *run*, not merely be declared.

    A module that ships but reaches into the excluded `khepri.local` package puts the command in
    the image and crashes it at import. This installs the wheel into a throwaway environment --
    where `src/` is not importable -- and imports the target there, so a transitive leak fails.
    """
    target = _declared_target(built_wheel, ENTRY_POINT)
    module, _, _ = target.partition(":")

    venv = built_wheel.parent / "probe"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, capture_output=True)
    python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    install = subprocess.run(
        [str(python), "-m", "pip", "install", "--quiet", str(built_wheel)],
        capture_output=True,
        text=True,
    )
    if install.returncode != 0:
        pytest.skip(f"cannot install the wheel: {install.stderr[-300:]}")

    imported = subprocess.run(
        [str(python), "-c", f"import {module}"], capture_output=True, text=True
    )
    assert imported.returncode == 0, imported.stderr[-500:]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107b_wheel_entry_point.py -x -q`
Expected: FAIL with `AssertionError: khepri-retention-sweep is not declared in the wheel`

- [ ] **Step 3: Add `main()`**

Append to `src/khepri/runtime/retention_sweep.py`, following `runtime/clerk_hard_stop.py`'s shape:

```python
def main() -> None:
    """One retention pass over the configured database (`KHEPRI-DEC-033` §5).

    Prints one content-free JSON line of counts -- no identifier is echoed, per
    `KHEPRI-DEC-015` §7 -- so an operator or a scheduled invocation has a record of what a pass
    did without the pass becoming a channel for customer data.
    """
    import json
    from datetime import UTC, datetime

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from khepri.runtime.config import RuntimeSettings
    from khepri.runtime.wiring import build_retention_sweep

    now = datetime.now(UTC)
    stack = build_stack(RuntimeSettings.from_environment())
    try:
        report = build_retention_sweep(stack).sweep(now=now)
    finally:
        stack.engine.dispose()
    print(json.dumps({"event": "retention_sweep", "occurred_at": now.isoformat()}
                     | report.as_counts(), sort_keys=True))
```

with the imports at the top of `main()` being:

```python
    from khepri.runtime.config import RuntimeSettings
    from khepri.runtime.wiring import build_retention_sweep, build_stack
```

**Reuse `build_stack`, do not build a second stack.** `build_stack(settings)` (`wiring.py:160`)
already constructs the engine, the session factory and the `S3EncryptedObjectStore` from settings
alone — and `DeletionService` needs that object store, so a bespoke construction here would be a
second wiring of the same collaborators, which is the defect Task 1 exists to avoid one level down.

If `RuntimeStack` exposes no `engine` attribute, dispose through whatever it does expose, or drop
the `try/finally` — a one-shot process exiting is not a leak. Read the dataclass before writing
this rather than guessing at the attribute.

Add `as_counts()` to `SweepReport`:

```python
    def as_counts(self) -> dict[str, int]:
        """Every count by name, for the entry point's one JSON line."""
        return {field: getattr(self, field) for field in self.__dataclass_fields__}
```

- [ ] **Step 4: Add the wiring factory**

Append to `src/khepri/runtime/wiring.py`:

```python
def build_retention_sweep(stack: RuntimeStack) -> RetentionSweeper:
    """The sweep `khepri-retention-sweep` runs (`KHEPRI-DEC-033` §5).

    Takes the stack rather than settings so the object store, the session factory and the
    `DeletionService` are the **same ones** the API and the worker use. `DeletionService` needs the
    `S3EncryptedObjectStore` that `build_stack` already constructs; building a second one here
    would be a second wiring of the same collaborators, and `local/sweeper.py` records why that is
    the thing to avoid: *"an expiry route that deleted differently from the on-demand route would
    be a second deletion implementation to keep correct."*
    """
    from khepri.rca.invitation_retention import InvitationRetentionSweeper
    from khepri.rca.lifecycle import AccountRetentionSweeper, MembershipEventSweeper
    from khepri.rca.recovery_security import RecoverySecurityEventSweeper
    from khepri.rca.session_retention import SessionRetentionSweeper
    from khepri.rca.workspace.audit_persistence import SqlWorkspaceAuditStore
    from khepri.rca.workspace.audit_retention import WorkspaceAuditSweeper
    from khepri.rra.evidence_retention import DeletionEvidenceSweeper
    from khepri.rra.persistence import SqlDeletionRepository
    from khepri.runtime.retention_sweep import RetentionPasses, build_retention_sweeper

    factory = stack.factory
    deletions = SqlDeletionRepository(factory)
    return build_retention_sweeper(
        jobs=stack.reports.jobs,
        deletion=stack.services.deletion,
        factory=factory,
        retention=RetentionPasses(
            accounts=AccountRetentionSweeper(SqlAccountStore(factory)),
            events=MembershipEventSweeper(SqlMembershipEventStore(factory)),
            sessions=SessionRetentionSweeper(SqlSessionStore(factory)),
            invitations=InvitationRetentionSweeper(SqlInvitationStore(factory)),
            recovery_events=RecoverySecurityEventSweeper(SqlRecoverySecurityEventStore(factory)),
            # `W1-07b`'s two additions, wired here in Task 5.
            workspace_audit=WorkspaceAuditSweeper(SqlWorkspaceAuditStore(factory)),
            evidence=DeletionEvidenceSweeper(deletions),
        ),
    )
```

**Read `local/wiring.py:316` before writing this** and use the same store classes it uses — the two
compositions must construct identical collaborators, or the local sweep and the deployed sweep
diverge. `stack.reports.jobs` and `stack.services.deletion` already exist on `RuntimeStack`
(`wiring.py:207`, `:214`); confirm the attribute names rather than assuming them.

The `workspace_audit` and `evidence` fields do not exist until Task 5 — write this function without
them in Task 2 and add those two lines in Task 5 Step 6.

- [ ] **Step 5: Declare the console script**

In `pyproject.toml`, under `[project.scripts]`, after `khepri-clerk-hard-stop`:

```toml
# `KHEPRI-DEC-033` §5. Every retention horizon in §2 was unenforced because every sweeper's only
# caller was `khepri.local.cli`, which the wheel excludes. `khepri.runtime` for the reason stated
# above for the hard stop: a command in `khepri.local` would be absent from the built artifact.
# This declares the caller; choosing a cadence is operational and `KHEPRI-DEC-033` decides none.
khepri-retention-sweep = "khepri.runtime.retention_sweep:main"
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107b_wheel_entry_point.py -q`
Expected: PASS (3 tests)

- [ ] **Step 7: Mutation-test both failure modes**

Both mutants must kill the tests. Run each, confirm the failure, then revert with `git stash && git stash drop`.

Mutant A — point the script at an excluded module. In `pyproject.toml` change the target to `"khepri.local.cli:main"`.
Expected: `test_the_sweep_entry_point_resolves_inside_the_built_wheel` FAILS with "which the wheel does not package".

Mutant B — the transitive leak. Add to the top of `src/khepri/runtime/retention_sweep.py`:

```python
import khepri.local.cli  # noqa: F401
```

Expected: `test_the_sweep_module_imports_with_no_excluded_package` FAILS with `ModuleNotFoundError`.

**Mutant B is the one that matters.** It is the difference between "the command is declared" and "the command runs". If it does not fail, the test is reading the manifest and the task is not done.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -F - <<'MSGEOF'
feat(w1-07b): the sweep's console script, and a wheel test that can fail

`KHEPRI-DEC-033` §5 asks for a caller present in the shipped image. This declares
`khepri-retention-sweep` against `khepri.runtime`, following `khepri-clerk-hard-stop`.

**The obvious test is worthless, and this was measured rather than assumed.** A wheel
built declaring `khepri-phantom = khepri.local.cli:main` with `exclude` unchanged listed
the command in `entry_points.txt` while `khepri/local` was absent from the same wheel:
entry points come from project metadata, exclusion governs packaged files, and the two are
independent. So the test resolves the declared target against the wheel's contents, and a
second test installs the wheel into a throwaway environment and imports the target there --
which is what catches a transitive `khepri.local` import that would ship the command and
crash it at invocation.

Both mutants verified: retargeting the script and adding a transitive import each fail.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSGEOF
```

---

## Task 3: The workspace audit-event horizon (RCA, twelve months)

**Files:**
- Modify: `src/khepri/rca/workspace/audit_persistence.py`
- Create: `src/khepri/rca/workspace/audit_retention.py`
- Test: `tests/test_w107b_retention_horizons.py`

**Interfaces:**
- Consumes: `MEMBERSHIP_EVENT_RETENTION_MONTHS`, `_months_before` from `khepri.rca.lifecycle`.
- Produces: `WorkspaceAuditSweeper(audit, *, retention_months=MEMBERSHIP_EVENT_RETENTION_MONTHS)` with `.sweep(*, now) -> WorkspaceAuditSweepReport(purged_events: int)`; `SqlWorkspaceAuditStore.purge_events_before(horizon: datetime) -> int`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_w107b_retention_horizons.py`:

```python
"""`W1-07b` -- the two `KHEPRI-DEC-033` §2 horizons that had no implementation anywhere.

Both are twelve months, and both take that number from `MEMBERSHIP_EVENT_RETENTION_MONTHS` rather
than a literal: §2 says the horizon is "adopted rather than re-derived", and two literals for one
decided number is how they come to disagree.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from khepri.rca.workspace.audit import ACTION_VERSION_CREATED, AuditActor, AuditSubject
from khepri.rca.workspace.audit import WorkspaceAuditEvent
from khepri.rca.workspace.audit_persistence import SqlWorkspaceAuditStore
from khepri.rca.workspace.audit_retention import WorkspaceAuditSweeper
from tests.w104_support import member
from tests.w107_support import journey

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
THIRTEEN_MONTHS_AGO = NOW - timedelta(days=396)
ELEVEN_MONTHS_AGO = NOW - timedelta(days=334)


def _event(store: SqlWorkspaceAuditStore, owner_id: str, account_id: str, when: datetime) -> None:
    store.record(
        WorkspaceAuditEvent.completed(
            AuditActor(owner_id=owner_id, actor_account_id=account_id),
            ACTION_VERSION_CREATED,
            AuditSubject("version", "dsv_example"),
            now=when,
        )
    )


def test_an_audit_event_past_twelve_months_is_purged() -> None:
    """`KHEPRI-DEC-033` §2: the retention/lifecycle audit event is purged on elapse of twelve
    months, the `KHEPRI-DEC-015` §2a horizon."""
    j = journey()
    who = member(j.w)
    audit = SqlWorkspaceAuditStore(j.w.factory)
    _event(audit, who.owner_id, who.account_id, THIRTEEN_MONTHS_AGO)

    report = WorkspaceAuditSweeper(audit).sweep(now=NOW)

    assert report.purged_events == 1
    assert audit.events_for_scope(who.owner_id) == ()


def test_an_audit_event_inside_twelve_months_survives() -> None:
    """The horizon is a boundary, not a purge-everything. A sweeper that removed live evidence
    would destroy the attribution `FR-125` exists to keep."""
    j = journey()
    who = member(j.w)
    audit = SqlWorkspaceAuditStore(j.w.factory)
    _event(audit, who.owner_id, who.account_id, ELEVEN_MONTHS_AGO)

    report = WorkspaceAuditSweeper(audit).sweep(now=NOW)

    assert report.purged_events == 0
    assert len(audit.events_for_scope(who.owner_id)) == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107b_retention_horizons.py -x -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'khepri.rca.workspace.audit_retention'`

- [ ] **Step 3: Add the store verb**

Append to `src/khepri/rca/workspace/audit_persistence.py`:

```python
    def purge_events_before(self, horizon: datetime) -> int:
        """Remove every event that occurred before `horizon`, returning how many.

        Across scopes, because the horizon is a property of the *event* and not of any
        organization: `KHEPRI-DEC-015` §2a fixes one twelve-month audit horizon, and a per-scope
        sweep would leave a closed organization's events indefinitely -- which are precisely the
        rows nobody will read again and the horizon exists to bound.
        """
        from sqlalchemy import delete

        with writing(self._factory) as database:
            return database.execute(
                delete(WorkspaceAuditEventRow).where(
                    WorkspaceAuditEventRow.occurred_at < horizon
                )
            ).rowcount
```

Add `writing` to the module's existing `unit_of_work` import.

- [ ] **Step 4: Write the sweeper**

Create `src/khepri/rca/workspace/audit_retention.py`:

```python
"""The workspace audit horizon (`W1-07b`; `KHEPRI-DEC-033` §2; `RCA-005` `FR-125`).

§2 gives the retention/lifecycle audit event twelve months, "the `KHEPRI-DEC-015` §2a horizon,
adopted rather than re-derived" -- so this takes `MEMBERSHIP_EVENT_RETENTION_MONTHS` and
`_months_before` from `rca/lifecycle.py` rather than spelling twelve again. Two literals for one
decided number is how they come to disagree when one moves.

Nothing called this before `W1-07b`: `KHEPRI-DEC-033` §5 records that no retention horizon had a
caller in the shipped image, and the workspace audit horizon had no implementation at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from khepri.rca.lifecycle import MEMBERSHIP_EVENT_RETENTION_MONTHS, _months_before
from khepri.rca.workspace.audit_persistence import SqlWorkspaceAuditStore


@dataclass(frozen=True, slots=True)
class WorkspaceAuditSweepReport:
    """What one pass purged, in counts only. No identifier is echoed."""

    purged_events: int


class WorkspaceAuditSweeper:
    """Purges workspace audit events past `KHEPRI-DEC-015` §2a's twelve-month horizon."""

    def __init__(
        self,
        audit: SqlWorkspaceAuditStore,
        *,
        retention_months: int = MEMBERSHIP_EVENT_RETENTION_MONTHS,
    ) -> None:
        self._audit = audit
        self._retention_months = retention_months

    def sweep(self, *, now: datetime) -> WorkspaceAuditSweepReport:
        """One pass. Measured from the event's own instant, which is when the action happened."""
        horizon = _months_before(now, self._retention_months)
        return WorkspaceAuditSweepReport(
            purged_events=self._audit.purge_events_before(horizon)
        )


__all__ = ["WorkspaceAuditSweepReport", "WorkspaceAuditSweeper"]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107b_retention_horizons.py -q`
Expected: PASS (2 tests)

- [ ] **Step 6: Mutation-test the boundary**

Change `_months_before(now, self._retention_months)` to `_months_before(now, 0)`.
Expected: `test_an_audit_event_inside_twelve_months_survives` FAILS.
Revert with `git stash && git stash drop`.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -F - <<'MSGEOF'
feat(w1-07b): the workspace audit event's twelve-month horizon

`KHEPRI-DEC-033` §2 gives the retention/lifecycle audit event twelve months and nothing
implemented it -- one of the two §2 horizons with no code anywhere, not merely no caller.

Takes `MEMBERSHIP_EVENT_RETENTION_MONTHS` and `_months_before` rather than spelling twelve
again: §2 says the horizon is "adopted rather than re-derived".

Purges across scopes, because the horizon belongs to the event and not to an organization:
a per-scope sweep would leave a closed organization's events indefinitely, which are
exactly the rows the horizon exists to bound.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSGEOF
```

---

## Task 4: The deletion-evidence horizon (RRA, twelve months)

**Files:**
- Modify: `src/khepri/rra/persistence.py`
- Create: `src/khepri/rra/evidence_retention.py`
- Test: `tests/test_w107b_retention_horizons.py`

**Interfaces:**
- Consumes: nothing from Task 3 (a different package; `R7-01` §3 forbids the import).
- Produces: `DeletionEvidenceSweeper(deletions, *, retention_months=12)` with `.sweep(*, now) -> EvidenceSweepReport(purged_evidence: int)`; `SqlDeletionRepository.purge_evidence_before(horizon: datetime) -> int`.

**Note on the constant.** `R7-01` §3 forbids `khepri.rra` importing `khepri.rca`, so this cannot reuse `MEMBERSHIP_EVENT_RETENTION_MONTHS`. Define `EVIDENCE_RETENTION_MONTHS = 12` in this module with a comment naming `KHEPRI-DEC-033` `OD-2` as its authority and stating why it is a second constant rather than a second *derivation*.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_w107b_retention_horizons.py`:

```python
def test_deletion_evidence_past_twelve_months_is_purged() -> None:
    """`KHEPRI-DEC-033` `OD-2`: twelve months, "on `KHEPRI-DEC-015` §2a's discipline that no
    horizon is quietly longer than another". Rejected there: indefinite retention."""
    from khepri.rra.evidence_retention import DeletionEvidenceSweeper
    from khepri.rra.persistence import SqlDeletionRepository

    j = journey()
    who = member(j.w)
    deletions = SqlDeletionRepository(j.w.factory)
    _evidence_row(j, who, attempted_at=THIRTEEN_MONTHS_AGO)

    report = DeletionEvidenceSweeper(deletions).sweep(now=NOW)

    assert report.purged_evidence == 1


def test_deletion_evidence_inside_twelve_months_survives() -> None:
    """Evidence proves content ended. Purging it early destroys the proof `FR-124` requires."""
    from khepri.rra.evidence_retention import DeletionEvidenceSweeper
    from khepri.rra.persistence import SqlDeletionRepository

    j = journey()
    who = member(j.w)
    deletions = SqlDeletionRepository(j.w.factory)
    _evidence_row(j, who, attempted_at=ELEVEN_MONTHS_AGO)

    report = DeletionEvidenceSweeper(deletions).sweep(now=NOW)

    assert report.purged_evidence == 0
```

Write `_evidence_row(j, who, *, attempted_at)` as a module-level helper that produces one real `rra_deletion_evidence` row through the production path: drive `tests/w107_support.deletion_service(j).delete_version(...)` over a `sealed_version`, then update that row's `attempted_at` to the test instant with `sqlalchemy.text`. Do **not** insert the row directly — raw setup exempts the transition it skips, and a mutant of the bypassed verb survives every test built on it.

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107b_retention_horizons.py -x -q -k evidence`
Expected: FAIL with `ModuleNotFoundError: No module named 'khepri.rra.evidence_retention'`

- [ ] **Step 3: Add the repository verb**

Add to `SqlDeletionRepository` in `src/khepri/rra/persistence.py`, beside `list_evidence`:

```python
    def purge_evidence_before(self, horizon: datetime) -> int:
        """Remove evidence attempted before `horizon`, returning how many rows went.

        Keyed on `attempted_at` rather than the parent job's completion: `KHEPRI-DEC-033` §2
        anchors the evidence horizon to the deletion event, and a job that retried for a week
        would otherwise hold its first attempt's evidence a week longer than the decision allows.
        """
        with self._factory.begin() as database:
            return database.execute(
                delete(DeletionEvidenceRow).where(DeletionEvidenceRow.attempted_at < horizon)
            ).rowcount
```

Add `delete` to the module's `sqlalchemy` imports if absent.

- [ ] **Step 4: Write the sweeper**

Create `src/khepri/rra/evidence_retention.py`:

```python
"""The deletion-evidence horizon (`W1-07b`; `KHEPRI-DEC-033` §2, `OD-2`; `RRA-002` `FR-124`).

`OD-2` decided twelve months, "on `KHEPRI-DEC-015` §2a's discipline that no horizon is quietly
longer than another", rejecting indefinite retention by Constitution VII's least-data default.

**Why the number is repeated here rather than imported.** `R7-01` §3 forbids `khepri.rra`
importing `khepri.rca`, and twelve months lives in `rca/lifecycle.py`. This is a second *constant*
for one decided number, which the boundary requires; it is not a second *derivation* -- both cite
`KHEPRI-DEC-033` §2 as the authority, and a test asserts the two agree, so a horizon that moves in
one package fails rather than drifting.

Nothing implemented this horizon before `W1-07b`.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime

#: `KHEPRI-DEC-033` `OD-2`. Kept equal to `khepri.rca.lifecycle.MEMBERSHIP_EVENT_RETENTION_MONTHS`
#: by `test_the_two_twelve_month_horizons_agree`, which is what makes this a restatement of one
#: decision rather than a second policy.
EVIDENCE_RETENTION_MONTHS = 12


@dataclass(frozen=True, slots=True)
class EvidenceSweepReport:
    """What one pass purged, in counts only."""

    purged_evidence: int


class DeletionEvidenceSweeper:
    """Purges deletion evidence past `KHEPRI-DEC-033` §2's twelve-month horizon."""

    def __init__(self, deletions, *, retention_months: int = EVIDENCE_RETENTION_MONTHS) -> None:
        self._deletions = deletions
        self._retention_months = retention_months

    def sweep(self, *, now: datetime) -> EvidenceSweepReport:
        horizon = _months_before(now, self._retention_months)
        return EvidenceSweepReport(
            purged_evidence=self._deletions.purge_evidence_before(horizon)
        )


def _months_before(moment: datetime, months: int) -> datetime:
    """`moment` shifted back by whole calendar months, clamping a short target month.

    The same arithmetic as `rca/lifecycle._months_before`, restated for the reason
    `EVIDENCE_RETENTION_MONTHS` is: `R7-01` §3 forbids `khepri.rra` importing `khepri.rca`.
    `timedelta` has no month unit and a fixed day count drifts across leap years, so the horizon is
    computed on the calendar; a day-of-month absent from the target month (31 March going back to
    February) clamps to that month's last day, which keeps the horizon monotonic.
    """
    month_index = moment.month - 1 - months
    year = moment.year + month_index // 12
    month = month_index % 12 + 1
    day = min(moment.day, monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


__all__ = ["EVIDENCE_RETENTION_MONTHS", "DeletionEvidenceSweeper", "EvidenceSweepReport"]
```

**`dateutil` is deliberately not used — it is not a dependency of this project** (checked against
`pyproject.toml`), and adding one for month arithmetic the repository already implements would be
a dependency bought for nine lines.

- [ ] **Step 5: Write the agreement test**

Append to `tests/test_w107b_retention_horizons.py`:

```python
def test_the_two_twelve_month_horizons_agree() -> None:
    """One decision, restated across a package boundary `R7-01` §3 forbids crossing.

    `KHEPRI-DEC-033` §2 gives audit events and deletion evidence the same twelve months. The
    number therefore appears in both packages, and this is what keeps that a restatement rather
    than two policies: move one and this fails.
    """
    from khepri.rca.lifecycle import MEMBERSHIP_EVENT_RETENTION_MONTHS
    from khepri.rra.evidence_retention import EVIDENCE_RETENTION_MONTHS

    assert EVIDENCE_RETENTION_MONTHS == MEMBERSHIP_EVENT_RETENTION_MONTHS
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107b_retention_horizons.py -q`
Expected: PASS (5 tests)

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -F - <<'MSGEOF'
feat(w1-07b): the deletion-evidence twelve-month horizon

`KHEPRI-DEC-033` `OD-2` decided twelve months and nothing implemented it -- the second of
the two §2 horizons with no code anywhere.

Keyed on `attempted_at` rather than the parent job's completion: §2 anchors the horizon to
the deletion event, so a job that retried for a week would otherwise hold its first
attempt's evidence a week longer than the decision allows.

The number is restated rather than imported, because `R7-01` §3 forbids `khepri.rra`
importing `khepri.rca`. `test_the_two_twelve_month_horizons_agree` is what keeps that a
restatement of one decision rather than a second policy.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSGEOF
```

---

## Task 5: The sweep records itself — vocabulary, migration, and the self-purge guard

**Files:**
- Modify: `src/khepri/rca/workspace/audit.py`
- Create: `migrations/versions/20260906_0028_rca_workspace_sweep_audit.py`
- Modify: `tests/test_rca001_migration.py`, `tests/test_rca001_session_persistence.py`, `specs/001-rca-001-commercial-identity/STATUS.md`
- Modify: `src/khepri/runtime/retention_sweep.py`
- Test: `tests/test_w107b_retention_horizons.py`

**Interfaces:**
- Consumes: `WorkspaceAuditSweeper` (Task 3), `DeletionEvidenceSweeper` (Task 4).
- Produces: `ACTION_RETENTION_SWEPT = "retention_swept"`, `ACTOR_RETENTION = "system:retention"` in `khepri.rca.workspace.audit`; `RetentionPasses.workspace_audit` and `.evidence` fields; `RetentionCounts.purged_audit_events` and `.purged_evidence`.

**Why an event at all.** `FR-125` names `sweep` literally among the workspace actions that MUST emit one audit event, and `KHEPRI-DEC-033` §2's audit row states the ending is "Run by the retention sweep, **recorded as a** [content-free record]". `FR-124` covers "every retention-triggered purge" for evidence.

**The subject is `None`, and the type already allows it.** `AuditEntry.subject` is `AuditSubject | None`, every constructor takes `subject: AuditSubject | None`, and `WorkspaceAuditEvent` documents the pairing as "`None` together, for a refusal that produced no object", pinned by `ck_rca_workspace_audit_subject_pair`. A sweep acts on a class over a horizon. So the migration widens **only** the action `CHECK` — `AUDIT_OBJECTS` and `AUDIT_OUTCOMES` are untouched.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_w107b_retention_horizons.py`:

```python
def test_the_sweep_records_one_audit_event_per_scope_it_purged() -> None:
    """`FR-125` names `sweep` among the actions that MUST emit an audit event, and
    `KHEPRI-DEC-033` §2 says the audit class's ending is "run by the retention sweep, recorded as
    a" content-free record.

    Per scope, because `rca_workspace_audit_events.owner_id` is `nullable=False`: a cross-scope
    pass cannot write one global event, and a customer's audit trail should show the sweeps that
    touched *their* rows rather than a counter for everyone's.
    """
    from khepri.rca.workspace.audit import ACTION_RETENTION_SWEPT

    j = journey()
    who = member(j.w)
    audit = SqlWorkspaceAuditStore(j.w.factory)
    _event(audit, who.owner_id, who.account_id, THIRTEEN_MONTHS_AGO)

    WorkspaceAuditSweeper(audit).sweep(now=NOW)

    events = audit.events_for_scope(who.owner_id)
    assert [e.action for e in events] == [ACTION_RETENTION_SWEPT]
    assert events[0].object_kind is None and events[0].object_id is None


def test_the_sweep_does_not_purge_its_own_evidence() -> None:
    """The sweep's event is itself subject to the horizon the sweep enforces.

    It is written at `now` and the horizon is twelve months before `now`, so no correctly ordered
    pass can reach it -- but that is a property to assert, not to assume: it becomes false the day
    a later slice moves the horizon or reorders the pass, and nothing else would notice.
    """
    from khepri.rca.workspace.audit import ACTION_RETENTION_SWEPT

    j = journey()
    who = member(j.w)
    audit = SqlWorkspaceAuditStore(j.w.factory)
    _event(audit, who.owner_id, who.account_id, THIRTEEN_MONTHS_AGO)
    sweeper = WorkspaceAuditSweeper(audit)

    sweeper.sweep(now=NOW)
    second = sweeper.sweep(now=NOW)

    assert second.purged_events == 0
    assert [e.action for e in audit.events_for_scope(who.owner_id)] == [
        ACTION_RETENTION_SWEPT,
        ACTION_RETENTION_SWEPT,
    ]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107b_retention_horizons.py -x -q -k sweep_records`
Expected: FAIL with `ImportError: cannot import name 'ACTION_RETENTION_SWEPT'`

- [ ] **Step 3: Add the vocabulary**

In `src/khepri/rca/workspace/audit.py`, after `ACTION_VERSION_DELETED`:

```python
#: `W1-07b`. One retention pass over one scope (`FR-125`, which names `sweep` literally, and
#: `KHEPRI-DEC-033` §2, whose audit row is "run by the retention sweep, recorded as a" record).
#: Its subject is `None`: a sweep acts on a *class* over a horizon, not on an object, and naming
#: one would make an evidence consumer read a class-level purge as an act on that object.
ACTION_RETENTION_SWEPT = "retention_swept"
```

Add it to `AUDIT_ACTIONS` (last), and replace the tuple's preceding comment — which currently says `W1-07b` will add this — with a note that it did.

After `ACTOR_PIPELINE`:

```python
#: `W1-07b`'s retention sweep, in the shape `ACTOR_PIPELINE` prescribes: the pass is performed by
#: no account, and `system:` keeps it from reading as one.
ACTOR_RETENTION = "system:retention"
```

- [ ] **Step 4: Write the migration**

Create `migrations/versions/20260906_0028_rca_workspace_sweep_audit.py`, following `20260906_0026` exactly:

```python
"""Admit the retention sweep's audit action (`W1-07b`, `RCA-005` `FR-125`).

`FR-125` names `sweep` among the workspace actions that MUST emit one audit event, and
`KHEPRI-DEC-033` §2's audit row states the class's ending is "run by the retention sweep, recorded
as a" content-free record. `20260906_0026` did not admit it -- `W1-07a` left the note in
`audit.py`: "`W1-07b` adds the sweep when it writes it, and the migration literal moves in the
same commit."

**Only the action constraint moves.** A sweep's subject is `None`, which
`ck_rca_workspace_audit_subject_pair` already admits, so `AUDIT_OBJECTS` needs nothing; the
outcome is `completed`, already admitted.

**Rebuilt, not altered.** SQLite cannot `ALTER` a `CHECK`, so `batch_alter_table` recreates the
table, and `test_migration_columns_match_the_declared_models` compares the literals here against
`audit.py`'s tuples.

**`down_revision` is `20260906_0027`**, `W1-07a`'s revocation ledger, the head this slice inherits.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260906_0028"
down_revision: str | None = "20260906_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIONS_BEFORE = "('version_created', 'run_started', 'run_completed', 'run_failed', 'profile_remembered', 'profile_reused', 'version_deleted')"  # noqa: E501
_ACTIONS_AFTER = "('version_created', 'run_started', 'run_completed', 'run_failed', 'profile_remembered', 'profile_reused', 'version_deleted', 'retention_swept')"  # noqa: E501


def _rewrite(actions: str) -> None:
    with op.batch_alter_table("rca_workspace_audit_events") as batch:
        batch.drop_constraint("ck_rca_workspace_audit_action", type_="check")
        batch.create_check_constraint("ck_rca_workspace_audit_action", f"action IN {actions}")


def upgrade() -> None:
    _rewrite(_ACTIONS_AFTER)


def downgrade() -> None:
    # A row carrying the new action cannot satisfy the narrower constraint; the downgrade refuses
    # rather than deleting a customer's audit history to fit an older shape.
    _rewrite(_ACTIONS_BEFORE)
```

- [ ] **Step 5: Move all three head pins**

1. `tests/test_rca001_migration.py` — append to `RCA_REVISIONS`. **The middle field is the migration file's slug, not a table name:**

```python
    # `W1-07b`'s sweep action: a `CHECK` rewrite on `20260905_0022`'s table, so the slug names
    # this migration's own file rather than the table it widens.
    ("20260906_0028", "rca_workspace_sweep_audit", "20260906_0027"),
```

`RCA_TABLES` gains nothing — this migration creates no table, and `test_every_rca_table_in_the_models_is_named_here` will hold unchanged, which is the check that this claim is true.

2. `tests/test_rca001_session_persistence.py:434` — change `assert "20260906_0027" in result.stdout` to `20260906_0028`, and extend the docstring above it naming this revision.

3. `specs/001-rca-001-commercial-identity/STATUS.md:10` — `Migration head `20260906_0027`` → `20260906_0028`.

- [ ] **Step 6: Write the event, and wire both passes**

In `src/khepri/rca/workspace/audit_retention.py`, `WorkspaceAuditSweeper.sweep` records one event per scope it purged from. Add `scopes_with_events_before(horizon) -> tuple[str, ...]` to `SqlWorkspaceAuditStore` (a `select(distinct(owner_id)).where(occurred_at < horizon)`), read the scopes **before** deleting, then after the delete record for each:

```python
        for owner_id in scopes:
            self._audit.record(
                WorkspaceAuditEvent.completed(
                    AuditActor(owner_id=owner_id, actor_account_id=ACTOR_RETENTION),
                    ACTION_RETENTION_SWEPT,
                    None,
                    now=now,
                )
            )
```

In `src/khepri/runtime/retention_sweep.py`, add two fields to `RetentionPasses`:

```python
    #: `KHEPRI-DEC-033` §2's twelve-month workspace audit horizon (`W1-07b`).
    workspace_audit: WorkspaceAuditSweeper | None = None
    #: `KHEPRI-DEC-033` `OD-2`'s twelve-month deletion-evidence horizon (`W1-07b`).
    evidence: DeletionEvidenceSweeper | None = None
```

Extend `RetentionCounts` with `purged_audit_events: int = 0` and `purged_evidence: int = 0`, run both in `RetentionPasses.run`, and add both to `SweepReport`. Then add both to `build_retention_sweep` in `wiring.py` (Task 2) and to `local/wiring.py:316`, so the two compositions stay identical.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107b_retention_horizons.py tests/test_rca001_migration.py tests/test_rca001_session_persistence.py -q`
Expected: PASS

- [ ] **Step 8: Verify the migration against real PostgreSQL**

`alembic heads` executes nothing and SQLite cannot `ALTER` constraints, so the `CHECK` rewrite needs a real engine:

```bash
KHEPRI_DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres \
  ./.venv/Scripts/python.exe -m pytest tests/test_rca001_migration.py -q
```

If the stack is not running, start it from WSL. Note the recorded trap: compose binds `127.0.0.1` *inside WSL2*.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -F - <<'MSGEOF'
feat(w1-07b): the sweep records itself, and the migration that admits it

`FR-125` names `sweep` literally among the workspace actions that MUST emit an audit
event, and `KHEPRI-DEC-033` §2's audit row says the class's ending is "run by the retention
sweep, recorded as a" content-free record. `W1-07a` left the note in `audit.py` that the
migration literal moves in the same commit as the write.

**Only the action `CHECK` widens.** A sweep's subject is `None`, which
`ck_rca_workspace_audit_subject_pair` already admits and every constructor already takes,
so no new object kind is needed -- and naming one would make an evidence consumer read a
class-level purge as an act on one customer's object.

One event per scope purged from, because `owner_id` is `nullable=False`: a cross-scope pass
cannot write one global event, and a customer's trail should show the sweeps that touched
their rows.

The pass does not purge its own evidence. It cannot today -- the event is written at `now`
and the horizon is twelve months earlier -- but that is asserted rather than assumed,
because it becomes false the day a later slice moves the horizon or reorders the pass.

Head moved to `20260906_0028` in all three places: `RCA_REVISIONS` (middle field is the
file slug), the `alembic heads` assertion, and `STATUS.md`.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSGEOF
```

---

## Task 6: Delete the unenforced flag, with a guard that replaces it

**Files:**
- Modify: `src/khepri/rca/invitation_retention.py`, `src/khepri/rca/session_retention.py`
- Modify: `tests/test_rca001_invitation_retention.py`
- Create: `tests/test_w107b_unenforced_flag.py`

**Interfaces:**
- Consumes: `build_retention_sweep` (Task 2), `RetentionPasses` (Task 5).
- Produces: nothing later tasks use.

**Why a replacement guard.** `KHEPRI-DEC-033` §5 says the flag's deletion "is part of the evidence". But it is defined at `invitation_retention.py:40`, exported in `__all__` at `:103`, and asserted `is True` at `tests/test_rca001_invitation_retention.py:179`. Deleting constant, export and assertion together leaves **nothing that can fail if the flag returns**.

- [ ] **Step 1: Write the failing test**

Create `tests/test_w107b_unenforced_flag.py`:

```python
"""`W1-07b` -- the evidence that replaces `INVITATION_HORIZON_IS_UNENFORCED`.

`KHEPRI-DEC-033` §5 says deleting that flag "is part of the evidence". Deleting the constant, its
export and its assertion together would leave nothing that can fail if the flag returns -- so the
evidence needs a shape, and this is it.

Written as a scan over a *pattern* rather than a check on one name, because the defect it guards is
**a horizon documented as unenforced**, not that particular constant.
"""

from __future__ import annotations

import re
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / "src" / "khepri"
UNENFORCED = re.compile(r"^[A-Z0-9_]*_IS_UNENFORCED\s*=", re.MULTILINE)


def test_no_horizon_is_declared_unenforced() -> None:
    """`KHEPRI-DEC-033` §5 is discharged by a sweep with a caller in the shipped image. A constant
    still announcing a horizon as unenforced would contradict the artifact that ships."""
    modules = sorted(SOURCE.rglob("*.py"))
    # The scan's own input, asserted non-empty: a scan that can silently cover nothing passes
    # vacuously, which is how `#240`'s table stayed invisible to a guard written to catch it.
    assert len(modules) > 100, f"the scan found only {len(modules)} modules; its root is wrong"

    declared = [
        module.relative_to(SOURCE).as_posix()
        for module in modules
        if UNENFORCED.search(module.read_text(encoding="utf-8"))
    ]

    assert not declared, f"a horizon is still declared unenforced in: {declared}"


def test_the_deployed_composition_reaches_the_invitation_pass() -> None:
    """Deleting a flag that says "unenforced" while the pass stays unreached would be worse than
    the flag. This asserts the sweep the console script builds actually carries it."""
    import inspect

    from khepri.runtime.wiring import build_retention_sweep

    source = inspect.getsource(build_retention_sweep)
    for pass_name in (
        "InvitationRetentionSweeper",
        "AccountRetentionSweeper",
        "MembershipEventSweeper",
        "SessionRetentionSweeper",
        "RecoverySecurityEventSweeper",
        "WorkspaceAuditSweeper",
        "DeletionEvidenceSweeper",
    ):
        assert pass_name in source, f"the deployed sweep does not reach {pass_name}"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107b_unenforced_flag.py -x -q`
Expected: FAIL with "a horizon is still declared unenforced in: ['rca/invitation_retention.py']"

- [ ] **Step 3: Delete the flag and correct the stale comments**

In `src/khepri/rca/invitation_retention.py`: delete `INVITATION_HORIZON_IS_UNENFORCED = True` (`:40`) and its `__all__` entry (`:103`). Replace the note at `:30` — which says `RetentionPasses` "is invoked only by the manual `sweep` subcommand (`khepri.local.cli`), and no scheduler exists" — with:

```python
#: Reached from `khepri-retention-sweep`, the console script `W1-07b` added to the wheel
#: (`KHEPRI-DEC-033` §5). Until that slice this horizon was documented as unenforced, because the
#: only caller was `khepri.local.cli` and the wheel excludes it. Choosing a cadence remains an
#: operational decision this repository does not make.
```

Apply the same correction to `src/khepri/rca/session_retention.py:14`.

In `tests/test_rca001_invitation_retention.py`: delete the import at `:26` and the assertion at `:179`, and replace that test's body with a pointer to `tests/test_w107b_unenforced_flag.py` — or delete the test if its only assertion was the flag. Read it before deciding.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107b_unenforced_flag.py tests/test_rca001_invitation_retention.py -q`
Expected: PASS

- [ ] **Step 5: Mutation-test the scan outside its own scope**

Add to a module the scan does **not** already name — `src/khepri/rra/intake.py`:

```python
SOME_OTHER_HORIZON_IS_UNENFORCED = True
```

Expected: `test_no_horizon_is_declared_unenforced` FAILS naming `rra/intake.py`.

**Mutating outside the scope is the point.** A scan that only catches the file it was written for reproduces the drift it exists to catch. Revert with `git stash && git stash drop`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -F - <<'MSGEOF'
feat(w1-07b): delete the unenforced flag, and guard what replaces it

`KHEPRI-DEC-033` §5 says deleting `INVITATION_HORIZON_IS_UNENFORCED` "is part of the
evidence". Deleting the constant, its export and its `is True` assertion together would
leave nothing that can fail if the flag returns -- so the evidence gets a shape.

A scan over the `*_IS_UNENFORCED` pattern, not a check on one name: the defect is a horizon
documented as unenforced, not that particular constant. Mutation-tested by declaring one in
`rra/intake.py`, outside the scan's own scope -- a scan that only catches the file it was
written for reproduces the drift it exists to catch. It also asserts its own input is
non-empty, so it cannot pass vacuously.

Plus a test that the deployed composition reaches all seven passes: deleting a flag saying
"unenforced" while the pass stays unreached would be worse than the flag.

Two comments claiming `RetentionPasses` is reached only from `khepri.local.cli` are now
false and corrected.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSGEOF
```

---

## Task 7: Full verification and the pull request

**Files:** none changed unless verification finds something.

- [ ] **Step 1: Lint**

Run: `./.venv/Scripts/python.exe -m ruff check .`
Expected: `All checks passed!` Do **not** run `ruff format`.

- [ ] **Step 2: Run the full suite**

Run: `./.venv/Scripts/python.exe -m pytest -q --basetemp=.pytest-tmp-w107b-final`
Expected: PASS, with the count at or above `4668` plus this slice's new tests.

Use an explicit writable `--basetemp` — an unset `$TMPDIR` in Git Bash expands to `/kh-full`, which becomes `C:\Program Files\Git\kh-full` and fails with `PermissionError` on every test.

- [ ] **Step 3: CodeScene pre-flight**

```bash
git fetch origin
```

Then run `analyze_change_set` against `origin/main`. A stale `origin/main` returns empty results and a meaningless "passed". Gates: cyclomatic >9, module function mean >4, >4 arguments, low cohesion. `RetentionPasses` gaining two fields keeps `RetentionSweeper.__init__` at four arguments — verify rather than assume.

- [ ] **Step 4: Push and open the PR**

```bash
git push -u origin feat/w1-07b-retention-sweep
```

PR body must state:
- What `KHEPRI-DEC-033` §5 asked for, and which half each change discharges
- **The measured wheel finding** (a wheel declares an entry point for an excluded module) and both mutants that prove the test sees it
- That eight §2 rows need no sweeper *by decision* (`OD-3`), with the row-by-row table from spec §1.1
- The two non-goals with their reasons: the disabled-organization 24-month purge, and the revocation ledger's horizon (`#383`)
- **That §5 is NOT amended** — it gates this change, so marking it discharged is the owner's edit
- That the horizons are enforced when the command exists *and* something invokes it; this ships the command, and no cadence is decided here

---

## Self-Review

**Spec coverage.** §1.1's row table → Task 3, Task 4 (the two missing horizons) and Task 2 (the caller for the rest). §2.1 the move → Task 1. §2.2 the console-script argument → Task 2 Step 5's comment and the PR body. §3 the wheel test with both mutants → Task 2 Steps 1 and 7. §4 the two purges → Tasks 3 and 4. §4.1 the sweep writing what it purges, the migration, the three head pins, the self-purge guard → Task 5. §4.2 ordering → Task 5 Step 6. §5 the flag and its replacement → Task 6. §6 non-goals → asserted by absence, and restated in the PR body. §7 testing → distributed across every task's mutation step. §8 risks → each mitigated by a named test.

**Type consistency.** `RetentionSweeper` / `build_retention_sweeper` used identically in Tasks 1, 2, 5, 6. `RetentionPasses` fields `workspace_audit` and `evidence` defined in Task 5 Step 6 and referenced in Task 6's reachability test by *class name*, which is what that test asserts. `WorkspaceAuditSweeper.sweep` returns `WorkspaceAuditSweepReport(purged_events=...)` in Task 3 and is read as `.purged_events` in Task 5. `DeletionEvidenceSweeper.sweep` returns `EvidenceSweepReport(purged_evidence=...)` in Task 4, read as `.purged_evidence` in Task 5.

**Two corrections made while self-reviewing, both of which would have stalled an implementer.**

1. **`dateutil` is not a dependency.** Task 4's first draft imported `relativedelta`; the module now
   restates `_months_before`'s calendar arithmetic instead, for the same `R7-01` §3 reason the
   twelve-month constant is restated. Checked against `pyproject.toml`, not assumed.
2. **`DeletionService` needs the object store.** An earlier draft built the sweep from
   `(settings, factory)` and left a `_deletion_service` helper undefined. `build_stack`
   (`wiring.py:160`) already constructs the engine, factory and `S3EncryptedObjectStore` from
   settings alone, so `build_retention_sweep` takes the **stack** — reusing the same
   `DeletionService` the API and worker use, rather than wiring a second one.

**Verify before writing, do not assume.** Two attribute names in Task 2 Step 4 were read from
`wiring.py:207` and `:214` but should be re-confirmed at implementation time: `stack.reports.jobs`
and `stack.services.deletion`. Likewise `RuntimeStack`'s engine attribute in `main()` — the plan
says to read the dataclass rather than guess.
