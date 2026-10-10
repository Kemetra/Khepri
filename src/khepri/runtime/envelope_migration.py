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
scoped engine, one session at a time, with that session's `owner_id` set. The sweep engine is
built only once the catalogue says the policies exist, so a database before `20261002_0036`, which
has no sweep role, needs no sweep secret.

**It refuses, with no count, whatever the catalogue cannot vouch for (`FR-272`).**

- Whether the policies exist is read from the catalogue: row security enabled on
  `rra_report_artifacts`, `rra_uploads` or `rra_beta_sessions` (`pg_class.relrowsecurity`). It is
  not `row_security_active`, which answers false for a role that bypasses them. If any of the
  three is missing from `public`, the answer is unknown, and it refuses rather than guess "none".
- Where they exist, the lister must connect as the sweep role and the scoped engine as the
  application role, both to the same database: `FR-273`'s completeness argument holds within one.
- The lister must see every session: `rra_sweep_read` on `rra_beta_sessions`, permissive,
  `USING (true)`, for its role; no restrictive policy over it for its role or `PUBLIC`; and
  `SELECT` on `session_id` and `owner_id`.

A migration owner's or a superuser's connection is refused: a bypassing read proves nothing about
the policies. Without the policies (SQLite, or PostgreSQL before `20261002_0036`) it runs over the
stack's factory alone, and also counts every `v1` row in both tables, listed session or not, as a
backstop for a row the walk cannot reach.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
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

#: Builds the sweep role's session factory. Called only where the policies exist.
SweepSource = Callable[[], sessionmaker[Session]]


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

    Without a `sweep_factory`, which `run` allows only where no policy exists, the listing reads
    through the stack's factory and the global `v1` counts back the walk up.
    """
    return ArtifactEnvelopeMigration(
        factory=stack.factory,
        objects=stack.objects,
        lister=EnvelopeSessionLister(sweep_factory or stack.factory),
        backstop=sweep_factory is None,
    )


REFUSED_UNDER_POLICY = 2

#: The tables whose row security decides whether the policies exist.
GUARDED_TABLES = ("rra_beta_sessions", "rra_report_artifacts", "rra_uploads")
#: How many of them `public` holds, and whether any has row security enabled. Read from the
#: catalogue, so a bypassing connection gets the same answer as any other. The names are bound.
_CATALOGUE = text(
    "SELECT count(*), coalesce(bool_or(relrowsecurity), false) FROM pg_class "
    "WHERE relnamespace = 'public'::regnamespace AND relkind IN ('r', 'p') "
    "AND relname = ANY(:tables)"
).bindparams(tables=list(GUARDED_TABLES))
CURRENT_USER = text("SELECT current_user")
DATABASE_IDENTITY = text("SELECT current_database(), host(inet_server_addr()), inet_server_port()")
#: The lister's own sight: `rra_sweep_read` admits every session to its role, nothing restricts
#: it, and its role holds both listed columns.
LISTER_SIGHT = text(
    "SELECT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' "
    "AND tablename = 'rra_beta_sessions' AND policyname = 'rra_sweep_read' "
    "AND cmd = 'SELECT' AND permissive = 'PERMISSIVE' AND current_user = ANY(roles) "
    "AND qual = 'true') "
    "AND NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' "
    "AND tablename = 'rra_beta_sessions' AND permissive = 'RESTRICTIVE' "
    "AND cmd IN ('SELECT', 'ALL') AND (current_user = ANY(roles) OR 'public' = ANY(roles))) "
    "AND has_column_privilege('public.rra_beta_sessions', 'session_id', 'SELECT') "
    "AND has_column_privilege('public.rra_beta_sessions', 'owner_id', 'SELECT')"
)


class CatalogueUnreadable(RuntimeError):
    """A table the policy decision reads is missing, so the decision cannot be made."""


def _one(factory: sessionmaker[Session], statement: TextClause) -> tuple[Any, ...]:
    with factory() as database:
        return tuple(database.execute(statement).one())


def policies_exist(factory: sessionmaker[Session]) -> bool:
    """Whether the RRA policies exist in this database (`FR-272`). SQLite has none."""
    with factory() as database:
        if database.get_bind().dialect.name != "postgresql":
            return False
        found, secured = database.execute(_CATALOGUE).one()
    if found != len(GUARDED_TABLES):
        raise CatalogueUnreadable("A table the envelope migration's decision reads is missing.")
    return bool(secured)


def composition_refusal(scoped: sessionmaker[Session], lister: sessionmaker[Session]) -> str | None:
    """Why `FR-272` refuses this pairing where the policies exist, or `None`. First match wins."""
    checks: tuple[tuple[str, Callable[[], bool]], ...] = (
        ("lister_role", lambda: _one(lister, CURRENT_USER) == (DatabaseRole.SWEEP.value,)),
        ("scoped_role", lambda: _one(scoped, CURRENT_USER) == (DatabaseRole.APPLICATION.value,)),
        (
            "database_mismatch",
            lambda: _one(lister, DATABASE_IDENTITY) == _one(scoped, DATABASE_IDENTITY),
        ),
        ("lister_sight", lambda: _one(lister, LISTER_SIGHT) == (True,)),
    )
    return next((reason for reason, holds in checks if not holds()), None)


@dataclass(frozen=True, slots=True)
class _Composition:
    """The lister's factory (`None`: no policy, list through the scoped engine), or a refusal."""

    lister: sessionmaker[Session] | None = None
    refusal: str | None = None


def _compose(stack: MigrationStack, sweep: SweepSource | None) -> _Composition:
    try:
        policed = policies_exist(stack.factory)
    except CatalogueUnreadable:
        return _Composition(refusal="catalogue_unreadable")
    if not policed:
        return _Composition()
    if sweep is None:
        return _Composition(refusal="no_sweep_engine")
    lister = sweep()
    return _Composition(lister, composition_refusal(stack.factory, lister))


def run(
    stack: MigrationStack,
    *,
    sweep: SweepSource | None = None,
    out: Callable[[str], None] = print,
) -> int:
    """One pass. Prints one line, counts or a refusal, and returns the process exit status."""
    now = stack.clock()
    composed = _compose(stack, sweep)
    if composed.refusal is not None:
        out(json.dumps({"event": "envelope_migration", "refused": composed.refusal}))
        return REFUSED_UNDER_POLICY
    report = build_envelope_migration(stack, sweep_factory=composed.lister).migrate()
    out(
        json.dumps(
            {"event": "envelope_migration", "occurred_at": now.isoformat()} | report.as_counts(),
            sort_keys=True,
        )
    )
    return 0 if report.verified else 1


def _sweep_factory() -> sessionmaker[Session]:
    """The sweep role's factory, built as `khepri-retention-sweep` builds it (`FR-271`)."""
    from khepri.runtime.config import role_database_url  # noqa: PLC0415
    from khepri.runtime.db_roles import engine_for  # noqa: PLC0415

    engine = engine_for(role_database_url(DatabaseRole.SWEEP), DatabaseRole.SWEEP)
    return sessionmaker(bind=engine, future=True)


def main() -> None:
    from khepri.runtime.config import RuntimeSettings  # noqa: PLC0415
    from khepri.runtime.wiring import build_stack  # noqa: PLC0415

    # `RRA-017` `FR-273`: the scoped work runs as the application role, and only the session
    # lister gets the sweep role's engine, built only where the policies exist.
    stack = build_stack(RuntimeSettings.from_environment(role=DatabaseRole.APPLICATION))
    raise SystemExit(run(stack, sweep=_sweep_factory))


__all__ = [
    "CURRENT_USER",
    "DATABASE_IDENTITY",
    "GUARDED_TABLES",
    "LISTER_SIGHT",
    "REFUSED_UNDER_POLICY",
    "CatalogueUnreadable",
    "MigrationStack",
    "SweepSource",
    "build_envelope_migration",
    "composition_refusal",
    "main",
    "policies_exist",
    "run",
]
