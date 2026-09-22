"""`T-01` (#521): the deployed sweep must construct and run every retention pass.

`build_retention_sweep` is what `khepri-retention-sweep` calls (`KHEPRI-DEC-033` §5). Every
`RetentionPasses` field defaults to `None`, so a pass deleted from the composition is not an error
anywhere: the sweep simply stops enforcing that horizon. The previous guard grepped the function's
source for seven class names while the composition had eight passes, so deleting the raw-upload
pass left CI green.

These cases build the real runtime stack (over SQLite rather than PostgreSQL, since the sweep's
collaborators take whatever session factory the stack carries) and assert behaviour rather than
source text:

* the composed `RetentionPasses` has every field set, to the expected class, checked against the
  *emitted* field set so a new field without a composition entry fails here; and
* one sweep invokes each pass exactly once. The count is taken by wrapping each pass class's
  `sweep`, so the assertion does not depend on how `RetentionPasses.run` handles a failing pass.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from datetime import UTC, datetime

import pytest
from sqlalchemy import URL, create_engine

from khepri.rca.invitation_retention import InvitationRetentionSweeper
from khepri.rca.lifecycle import AccountRetentionSweeper, MembershipEventSweeper
from khepri.rca.persistence import Base as RcaBase
from khepri.rca.recovery_security import RecoverySecurityEventSweeper
from khepri.rca.session_retention import SessionRetentionSweeper
from khepri.rca.workspace.audit_retention import WorkspaceAuditSweeper
from khepri.rra.envelope import MasterKey
from khepri.rra.evidence_retention import DeletionEvidenceSweeper
from khepri.rra.persistence import Base as RraBase
from khepri.runtime.config import RuntimeSettings
from khepri.runtime.retention_sweep import RetentionPasses, RetentionSweeper
from khepri.runtime.wiring import RuntimeClients, RuntimeStack, build_retention_sweep, build_stack
from khepri.runtime.workspace_retention import RawUploadRetentionSweeper

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)

#: The class each `RetentionPasses` field must hold in the deployed composition. Its keys are
#: asserted equal to the dataclass's own field set, so this map cannot silently fall behind.
EXPECTED_PASS = {
    "accounts": AccountRetentionSweeper,
    "events": MembershipEventSweeper,
    "sessions": SessionRetentionSweeper,
    "invitations": InvitationRetentionSweeper,
    "recovery_events": RecoverySecurityEventSweeper,
    "workspace_audit": WorkspaceAuditSweeper,
    "evidence": DeletionEvidenceSweeper,
    "raw_uploads": RawUploadRetentionSweeper,
}


class S3ClientStub:
    """No object exists in an empty database, so the sweep never reaches the store."""


def _stack(tmp_path) -> RuntimeStack:
    database_url = URL.create("sqlite+pysqlite", database=str(tmp_path / "sweep.db"))
    engine = create_engine(database_url)
    RraBase.metadata.create_all(engine)
    RcaBase.metadata.create_all(engine)
    engine.dispose()
    settings = RuntimeSettings(
        database_url=database_url,
        storage_endpoint="https://fra1.spaces.example",
        storage_region="fra1",
        bucket="test",
        master_key=MasterKey(material=b"k" * 32),
        clerk=None,
    )
    return build_stack(settings, clients=RuntimeClients(s3=S3ClientStub()), clock=lambda: NOW)


def _passes(sweeper: RetentionSweeper) -> RetentionPasses:
    passes = sweeper._retention
    assert isinstance(passes, RetentionPasses), "the deployed sweep carries no retention passes"
    return passes


def test_the_expected_pass_map_covers_every_retention_field() -> None:
    """A new `RetentionPasses` field must be added here, and so to the checks below."""
    assert set(EXPECTED_PASS) == {field.name for field in dataclasses.fields(RetentionPasses)}


def test_the_deployed_sweep_composes_every_retention_pass(tmp_path) -> None:
    passes = _passes(build_retention_sweep(_stack(tmp_path)))

    missing = [
        field.name
        for field in dataclasses.fields(RetentionPasses)
        if getattr(passes, field.name) is None
    ]
    assert not missing, f"the deployed sweep composes no pass for: {missing}"
    for field in dataclasses.fields(RetentionPasses):
        composed = getattr(passes, field.name)
        assert type(composed) is EXPECTED_PASS[field.name], (
            f"{field.name} holds {type(composed).__name__}, "
            f"expected {EXPECTED_PASS[field.name].__name__}"
        )


def test_one_deployed_sweep_runs_every_retention_pass_once(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sweeper = build_retention_sweep(_stack(tmp_path))
    passes = _passes(sweeper)
    calls: Counter[str] = Counter()

    for field in dataclasses.fields(RetentionPasses):
        composed = getattr(passes, field.name)
        if composed is None:
            # Left uncounted so the assertion below names the missing pass.
            continue
        pass_class = type(composed)
        real_sweep = pass_class.sweep

        def counted(self, *, now: datetime, _name: str = field.name, _real=real_sweep):
            calls[_name] += 1
            return _real(self, now=now)

        monkeypatch.setattr(pass_class, "sweep", counted)

    sweeper.sweep(now=NOW)

    assert calls == Counter({field.name: 1 for field in dataclasses.fields(RetentionPasses)})
