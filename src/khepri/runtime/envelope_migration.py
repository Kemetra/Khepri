"""`khepri-envelope-migrate`: the deployed caller of the report-artifact `v1` migration (#535).

**Why `khepri.runtime`.** The wheel excludes `src/khepri/local`, so a command there would be absent
from the image that holds the data, for the reason `pyproject.toml` gives for
`khepri-retention-sweep`.

**The exit status is the verification.** `KHEPRI-DEC-028` retires `v1` only once the migration has
"verified that none remains". The process exits non-zero while any `v1` artifact row remains or
any row faulted, so an operator or a script cannot read a partial pass as done. The printed line
repeats the counts and carries no identifier (`KHEPRI-DEC-015` §7).

**Nothing here schedules it**, as with the retention sweep. Running it is an operational act.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Protocol

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


def run(stack: MigrationStack, *, out: Callable[[str], None] = print) -> int:
    """One pass. Prints one counts line and returns the process exit status."""
    now = stack.clock()
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
    from khepri.runtime.wiring import build_stack  # noqa: PLC0415

    raise SystemExit(run(build_stack(RuntimeSettings.from_environment())))


__all__ = ["MigrationStack", "build_envelope_migration", "main", "run"]
