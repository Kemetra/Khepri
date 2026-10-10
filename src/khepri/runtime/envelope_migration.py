"""`khepri-envelope-migrate`: the deployed caller of the report-artifact `v1` migration (#535).

**Why `khepri.runtime`.** The wheel excludes `src/khepri/local`, so a command there would be absent
from the image that holds the data, for the reason `pyproject.toml` gives for
`khepri-retention-sweep`.

**The exit status is the verification.** `KHEPRI-DEC-028` retires `v1` only once the migration has
"verified that none remains". The process exits non-zero while any `v1` row remains, and a row
whose rewrite faulted is one of them, so an operator or a script cannot read a partial pass as
done. The printed line repeats the counts and carries no identifier (`KHEPRI-DEC-015` §7).

**Nothing here schedules it**, as with the retention sweep. Running it is an operational act.

**Two engines, as `FR-271`'s sweep has (`RRA-017` `FR-273`).** The sweep role's engine goes to the
session lister and nothing else; every candidate read, re-seal and count runs on the stack's
scoped engine, one session at a time, with that session's `owner_id` set.

**It refuses any other composition under the policies (`FR-272`).** Whether the policies exist is
read from the catalogue (`pg_class.relrowsecurity` on either content table), not from
`row_security_active`, which answers false for a role that bypasses them. Where they exist, the
lister must connect as the sweep role and the scoped engine as the application role, and the lister
must see every session: `rra_sweep_read` on `rra_beta_sessions` for its role, and `SELECT` on
`session_id` and `owner_id`. Otherwise it prints one content-free refusal and exits non-zero, before
any count. A migration owner's or a superuser's connection is refused: a bypassing read proves
nothing about the policies. Without the policies (SQLite, or PostgreSQL before `20261002_0036`) it
runs over the stack's factory alone, as it did before.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import TextClause, text
from sqlalchemy.orm import Session, sessionmaker

from khepri.rra.envelope_migration import (
    ArtifactEnvelopeMigration,
    EnvelopeSessionLister,
    ResealingStore,
)
from khepri.runtime.db_roles import DatabaseRole


class MigrationStack(Protocol):
    """The three collaborators this reads off `RuntimeStack`, and nothing else."""

    @property
    def factory(self) -> sessionmaker[Session]: ...

    @property
    def objects(self) -> ResealingStore: ...

    @property
    def clock(self) -> Callable[[], datetime]: ...


def build_envelope_migration(
    stack: MigrationStack, *, sweep_factory: sessionmaker[Session] | None = None
) -> ArtifactEnvelopeMigration:
    """The scoped work over the stack's factory; the session listing over `sweep_factory`.

    Without a `sweep_factory` the listing reads through the stack's factory too, which `run`
    allows only where no policy exists.
    """
    return ArtifactEnvelopeMigration(
        factory=stack.factory,
        objects=stack.objects,
        lister=EnvelopeSessionLister(sweep_factory or stack.factory),
    )


REFUSED_UNDER_POLICY = 2

#: Whether either content table has row security enabled: read from the catalogue, so a bypassing
#: connection sees the same answer as any other. The names are bound, so the statement's text
#: names no content table.
_POLICIES_EXIST = text(
    "SELECT coalesce(bool_or(relrowsecurity), false) FROM pg_class "
    "WHERE relnamespace = 'public'::regnamespace AND relname = ANY(:tables)"
).bindparams(tables=["rra_report_artifacts", "rra_uploads"])
_CURRENT_USER = text("SELECT current_user")
#: The lister's own sight: its role holds `rra_sweep_read` and both listed columns.
_LISTER_SIGHT = text(
    "SELECT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' "
    "AND tablename = 'rra_beta_sessions' AND policyname = 'rra_sweep_read' "
    "AND cmd = 'SELECT' AND permissive = 'PERMISSIVE' AND current_user = ANY(roles)) "
    "AND has_column_privilege('public.rra_beta_sessions', 'session_id', 'SELECT') "
    "AND has_column_privilege('public.rra_beta_sessions', 'owner_id', 'SELECT')"
)


def _scalar(factory: sessionmaker[Session], statement: TextClause) -> Any:
    with factory() as database:
        return database.execute(statement).scalar()


def policies_exist(factory: sessionmaker[Session]) -> bool:
    """Whether the RRA policies exist in this database (`FR-272`). SQLite has none."""
    with factory() as database:
        if database.get_bind().dialect.name != "postgresql":
            return False
        return bool(database.execute(_POLICIES_EXIST).scalar())


def composition_refusal(
    scoped: sessionmaker[Session], sweep: sessionmaker[Session] | None
) -> str | None:
    """Why `FR-272` refuses this composition where the policies exist, or `None`."""
    if sweep is None:
        return "no_sweep_engine"
    if _scalar(sweep, _CURRENT_USER) != DatabaseRole.SWEEP.value:
        return "lister_role"
    if _scalar(scoped, _CURRENT_USER) != DatabaseRole.APPLICATION.value:
        return "scoped_role"
    if not _scalar(sweep, _LISTER_SIGHT):
        return "lister_sight"
    return None


def run(
    stack: MigrationStack,
    *,
    sweep_factory: sessionmaker[Session] | None = None,
    out: Callable[[str], None] = print,
) -> int:
    """One pass. Prints one line, counts or a refusal, and returns the process exit status."""
    now = stack.clock()
    policed = policies_exist(stack.factory)
    refusal = composition_refusal(stack.factory, sweep_factory) if policed else None
    if refusal is not None:
        out(json.dumps({"event": "envelope_migration", "refused": refusal}))
        return REFUSED_UNDER_POLICY
    lister = sweep_factory if policed else None
    report = build_envelope_migration(stack, sweep_factory=lister).migrate()
    out(
        json.dumps(
            {"event": "envelope_migration", "occurred_at": now.isoformat()} | report.as_counts(),
            sort_keys=True,
        )
    )
    return 0 if report.verified else 1


def main() -> None:
    from khepri.runtime.config import RuntimeSettings, role_database_url  # noqa: PLC0415
    from khepri.runtime.db_roles import engine_for  # noqa: PLC0415
    from khepri.runtime.wiring import build_stack  # noqa: PLC0415

    # `RRA-017` `FR-273`: the scoped work runs as the application role, and only the session
    # lister gets the sweep role's engine, built as `khepri-retention-sweep` builds it.
    stack = build_stack(RuntimeSettings.from_environment(role=DatabaseRole.APPLICATION))
    sweep_engine = engine_for(role_database_url(DatabaseRole.SWEEP), DatabaseRole.SWEEP)
    raise SystemExit(run(stack, sweep_factory=sessionmaker(bind=sweep_engine, future=True)))


__all__ = [
    "REFUSED_UNDER_POLICY",
    "MigrationStack",
    "build_envelope_migration",
    "composition_refusal",
    "main",
    "policies_exist",
    "run",
]
