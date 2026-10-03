"""`khepri-envelope-migrate`: the deployed caller of the report-artifact `v1` migration (#535).

**Why `khepri.runtime`.** The wheel excludes `src/khepri/local`, so a command there would be absent
from the image that holds the data, for the reason `pyproject.toml` gives for
`khepri-retention-sweep`.

**The exit status is the verification.** `KHEPRI-DEC-028` retires `v1` only once the migration has
"verified that none remains". The process exits non-zero while any `v1` artifact row remains, and
a row whose rewrite faulted is one of them, so an operator or a script cannot read a partial pass
as done. The printed line
repeats the counts and carries no identifier (`KHEPRI-DEC-015` §7).

**Nothing here schedules it**, as with the retention sweep. Running it is an operational act.

**It refuses under the row-security policies (`RRA-017` `FR-272`).** Its reads span every scope.
Through a role the policies apply to, both come back empty, and an empty count is exactly what it
would report as "verified": the condition on which `KHEPRI-DEC-028` retires `v1`. Until Open item
7 admits a role for those reads, it asks PostgreSQL itself (`row_security_active`) and, if either
table is under a policy for this connection, prints one content-free refusal and exits non-zero.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from khepri.rra.envelope_migration import ArtifactEnvelopeMigration, ResealingStore


class MigrationStack(Protocol):
    """The three collaborators this reads off `RuntimeStack`, and nothing else."""

    @property
    def factory(self) -> sessionmaker[Session]: ...

    @property
    def objects(self) -> ResealingStore: ...

    @property
    def clock(self) -> Callable[[], datetime]: ...


def build_envelope_migration(stack: MigrationStack) -> ArtifactEnvelopeMigration:
    """Over the stack's own factory and object store: the ones the API reads through."""
    return ArtifactEnvelopeMigration(factory=stack.factory, objects=stack.objects)


_UNDER_POLICY = text(
    "SELECT row_security_active('public.rra_report_artifacts') "
    "OR row_security_active('public.rra_uploads')"
)
REFUSED_UNDER_POLICY = 2


def under_policy(factory: sessionmaker[Session]) -> bool:
    """Whether this connection is subject to the RRA policies (`FR-272`). SQLite has none."""
    with factory() as database:
        if database.get_bind().dialect.name != "postgresql":
            return False
        return bool(database.execute(_UNDER_POLICY).scalar())


def run(stack: MigrationStack, *, out: Callable[[str], None] = print) -> int:
    """One pass. Prints one counts line and returns the process exit status."""
    now = stack.clock()
    if under_policy(stack.factory):
        out(json.dumps({"event": "envelope_migration", "refused": "row_security_active"}))
        return REFUSED_UNDER_POLICY
    report = build_envelope_migration(stack).migrate()
    out(
        json.dumps(
            {"event": "envelope_migration", "occurred_at": now.isoformat()} | report.as_counts(),
            sort_keys=True,
        )
    )
    return 0 if report.verified else 1


def main() -> None:
    from khepri.runtime.config import RuntimeSettings  # noqa: PLC0415
    from khepri.runtime.db_roles import DatabaseRole  # noqa: PLC0415
    from khepri.runtime.wiring import build_stack  # noqa: PLC0415

    settings = RuntimeSettings.from_environment(role=DatabaseRole.APPLICATION)
    raise SystemExit(run(build_stack(settings)))


__all__ = ["MigrationStack", "build_envelope_migration", "main", "run"]
