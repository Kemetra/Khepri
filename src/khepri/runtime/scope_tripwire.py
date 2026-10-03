"""A forgotten scope fails loudly, not silently (`RRA-017` `FR-233`, `FR-238`).

Under the policies a transaction with no scope reads nothing and writes nothing. That is closed,
but it is also silent: an empty page, or a session that quietly looks like "not a workspace". This
tripwire makes it loud. Before each statement on an application or worker connection it derives
the tables the statement touches from the compiled construct, never from SQL text, and raises
`ScopeRequired` if one is covered while the transaction has set no scope.

`khepri.rra.scope.mark` records the scope on the connection when a transaction sets it (or binds it
deliberately unresolved); a `begin` listener clears that record, so every transaction starts
unscoped. SQLite engines carry no tripwire, which keeps the application-isolation suite exactly as
it runs without row security (Verification 8).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, Table, event
from sqlalchemy.sql import visitors

from khepri.rra.scope import SCOPE_MARK, ScopeRequired

#: `FR-230`'s eight tables with `owner_id`, and `FR-269`'s four walled through their parents.
COVERED_TABLES = frozenset(
    {
        "rra_beta_sessions",
        "rra_dataset_profiles",
        "rra_deletion_jobs",
        "rra_fact_packages",
        "rra_report_artifacts",
        "rra_report_deliveries",
        "rra_report_jobs",
        "rra_uploads",
        "rra_report_job_attempts",
        "rra_operational_events",
        "rra_report_delivery_surfaces",
        "rra_deletion_evidence",
    }
)


def attach_tripwire(engine: Engine) -> None:
    """Refuse any statement on a covered table in a transaction that set no scope."""
    event.listen(engine, "begin", _clear)
    event.listen(engine, "before_cursor_execute", _check)


def _clear(connection) -> None:
    connection.info.pop(SCOPE_MARK, None)


def _check(connection, *event: Any) -> None:
    """`before_cursor_execute`; `event` is cursor, statement, parameters, context, executemany."""
    if SCOPE_MARK in connection.info:
        return
    context = event[3]
    touched = covered_tables(getattr(context, "compiled", None))
    if touched:
        raise ScopeRequired(f"A statement reached {sorted(touched)} with no scope set.")


def covered_tables(compiled: Any) -> frozenset[str]:
    """The covered tables a compiled statement names, from the construct, not its SQL text."""
    statement = getattr(compiled, "statement", None)
    if statement is None:
        return frozenset()
    names = {
        element.name for element in visitors.iterate(statement) if isinstance(element, Table)
    }
    return frozenset(names & COVERED_TABLES)


__all__ = ["COVERED_TABLES", "attach_tripwire", "covered_tables"]
