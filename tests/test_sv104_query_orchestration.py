"""`SV1-04` — authorization, the uniform unavailable outcome, zero writes, no RRA import.

Authority: active `RCA-006` `FR-145`--`FR-150`.

Every case runs through the real isolation door and the W1 workspace stores, for
the reason `c106_support` gives: "A stub store would answer any key and miss the
point." An actor who may not act, a source in another scope and a revoked source
are all real here, not arranged.

The port is a fake, and that is not a gap. `SV1-04` ships the Protocol and the
orchestration; the composition root that binds a concrete `RRA-014`
implementation to it is **not authorized** -- `RCA-006` §Scope governs no runtime
wiring -- so no adapter exists to drive. What these tests prove is the RCA half:
who may ask, which rows they may see, that nothing is written, and that the
outcome comes back unchanged.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
from sqlalchemy import event

from khepri.rca.errors import ScopeAccessDenied
from khepri.rca.isolation import IsolationService
from khepri.rca.persistence import SqlAccountStore
from khepri.rca.semantic_queries import ports, queries
from khepri.rca.workspace.audit import OBJECT_VERSION
from khepri.rca.workspace.contracts import AnalysisRun
from khepri.rca.workspace.revocation import RevokedObject, SqlRevocationLedger
from tests.c106_support import completed_pair
from tests.w104_support import Member, member
from tests.w104b_support import Journey, journey

MISSING_ID = "no-such-source"

#: Statements that change rows. `FR-148` admits none of them on this path, and
#: `FR-149` no audit or telemetry row either -- which is the same INSERT seen from
#: the connection.
_WRITE_VERBS = ("insert", "update", "delete", "merge", "replace", "upsert")


class _FakePort:
    """A `SemanticViewPort` that records what it was handed and answers as told.

    Records rather than asserts, so a test can check *what reached RRA* -- the
    exact version, the scoped sources, their order -- rather than only what came
    back.
    """

    def __init__(self, outcome: ports.ViewOutcome | None) -> None:
        self.outcome = outcome
        self.calls: list[tuple[ports.SemanticViewRequest, tuple[object, ...]]] = []

    def project(
        self, request: ports.SemanticViewRequest, sources: tuple[object, ...]
    ) -> ports.ViewOutcome:
        self.calls.append((request, sources))
        return self.outcome  # type: ignore[return-value]


class _SpyReader:
    """The real store behind a recorder, so "never reached a store read" is checkable."""

    def __init__(self, store: object) -> None:
        self._store = store
        self.reads: list[tuple[str, str | None]] = []

    def get_analysis_run(self, run_id: str, owner_id: str | None = None) -> AnalysisRun | None:
        self.reads.append((run_id, owner_id))
        return self._store.get_analysis_run(run_id, owner_id)  # type: ignore[attr-defined]


def _actions(
    j: Journey, port: _FakePort, reader: object | None = None
) -> queries.SemanticQueryActions:
    return queries.SemanticQueryActions(
        isolation=IsolationService(j.w.organizations, SqlAccountStore(j.w.factory)),
        sources=reader or j.w.store,  # type: ignore[arg-type]
        port=port,
    )


def _view() -> ports.SemanticViewRequest:
    return ports.SemanticViewRequest(
        view_id="ExecutiveOverviewView", view_version="sv1.executive_overview.v1"
    )


def _request(who: Member, *source_ids: str) -> queries.SemanticQueryRequest:
    return queries.SemanticQueryRequest(
        actor=queries.SemanticQueryActor(account_id=who.account_id),
        organization_id=who.organization_id,
        view=_view(),
        source_ids=source_ids,
    )


def _admitted() -> ports.ViewOutcome:
    return ports.ViewOutcome(
        kind=ports.KIND_ADMITTED,
        projection=ports.ViewProjection(
            view_id="ExecutiveOverviewView", view_version="sv1.executive_overview.v1"
        ),
    )


def _revoke_version(j: Journey, version_id: str, owner_id: str) -> None:
    """End the version a run derives from, which is how a run stops being live."""
    SqlRevocationLedger(j.w.factory).revoke(
        RevokedObject(
            object_kind=OBJECT_VERSION,
            object_id=version_id,
            owner_id=owner_id,
            revoked_at=j.clock(),
        )
    )


def test_absent_deleted_cross_scope_and_unreadable_sources_are_one_outcome() -> None:
    """`FR-146` -- byte-identical, and compared against *each other*, not a literal.

    Four conditions the specification names as one answer. Asserting each equals
    `ViewOutcome(kind="unavailable")` would pass even if three of them had
    diverged from the fourth in some field a later slice adds; comparing them to
    one another cannot.
    """
    j = journey()
    owner = member(j.w)
    stranger = member(j.w, email="other@example.test", name="Other")
    mine = completed_pair(j, owner)
    theirs = completed_pair(j, stranger)
    port = _FakePort(_admitted())
    actions = _actions(j, port)

    absent = actions.request(_request(owner, MISSING_ID))
    cross_scope = actions.request(_request(owner, theirs.subject_run.run_id))
    _revoke_version(j, mine.subject.version_id, owner.owner_id)
    deleted = actions.request(_request(owner, mine.subject_run.run_id))
    unreadable = _actions(j, _FakePort(None)).request(_request(owner, mine.baseline_run.run_id))

    assert absent == cross_scope == deleted == unreadable
    assert absent.unavailable
    assert absent.projection is None and absent.refusal is None and absent.effective is None


def test_an_unreachable_source_never_reaches_the_port() -> None:
    """`FR-147` passes "only successfully scoped governed sources" -- so none is none."""
    j = journey()
    owner = member(j.w)
    completed_pair(j, owner)
    port = _FakePort(_admitted())

    assert _actions(j, port).request(_request(owner, MISSING_ID)).unavailable
    assert port.calls == []


def test_an_actor_outside_the_organization_never_reaches_a_store_read() -> None:
    """`FR-145` -- authorization resolves *before* a source read, driven end to end.

    Through `request`, not `resolve_scope`: calling the guard proves the guard
    works, not that the entry point calls it first. The spy proves the ordering.
    """
    j = journey()
    owner = member(j.w)
    stranger = member(j.w, email="other@example.test", name="Other")
    mine = completed_pair(j, owner)
    reader = _SpyReader(j.w.store)
    port = _FakePort(_admitted())
    actions = _actions(j, port, reader)

    foreign = queries.SemanticQueryRequest(
        actor=queries.SemanticQueryActor(account_id=stranger.account_id),
        organization_id=owner.organization_id,
        view=_view(),
        source_ids=(mine.subject_run.run_id,),
    )
    with pytest.raises(ScopeAccessDenied):
        actions.request(foreign)

    assert reader.reads == [], "a source was read before authorization resolved"
    assert port.calls == []


def test_an_unknown_account_never_reaches_a_store_read() -> None:
    """`FR-145` again, for an actor the account store does not know at all."""
    j = journey()
    owner = member(j.w)
    mine = completed_pair(j, owner)
    reader = _SpyReader(j.w.store)
    port = _FakePort(_admitted())

    unknown = queries.SemanticQueryRequest(
        actor=queries.SemanticQueryActor(account_id="no-such-account"),
        organization_id=owner.organization_id,
        view=_view(),
        source_ids=(mine.subject_run.run_id,),
    )
    with pytest.raises(ScopeAccessDenied):
        _actions(j, port, reader).request(unknown)

    assert reader.reads == []
    assert port.calls == []


def test_the_exact_requested_version_reaches_the_port_unchanged() -> None:
    """`FR-143`/`FR-147` -- no `latest`, no substitution, no relabelling in transit."""
    j = journey()
    owner = member(j.w)
    pair = completed_pair(j, owner)
    port = _FakePort(_admitted())

    _actions(j, port).request(_request(owner, pair.subject_run.run_id))

    assert len(port.calls) == 1
    request, _sources = port.calls[0]
    assert request == _view()


def test_every_scoped_source_reaches_the_port_in_the_order_named() -> None:
    """`FR-147` -- which source is subject and which is baseline is the caller's."""
    j = journey()
    owner = member(j.w)
    pair = completed_pair(j, owner)
    port = _FakePort(_admitted())

    _actions(j, port).request(_request(owner, pair.subject_run.run_id, pair.baseline_run.run_id))

    _request_seen, sources = port.calls[0]
    assert tuple(run.run_id for run in sources) == (  # type: ignore[attr-defined]
        pair.subject_run.run_id,
        pair.baseline_run.run_id,
    )


def test_one_missing_source_of_two_refuses_the_whole_request() -> None:
    """All-or-nothing: a partial tuple would project one population as the answer."""
    j = journey()
    owner = member(j.w)
    pair = completed_pair(j, owner)
    port = _FakePort(_admitted())

    outcome = _actions(j, port).request(_request(owner, pair.subject_run.run_id, MISSING_ID))

    assert outcome.unavailable
    assert port.calls == []


def test_the_port_outcome_is_returned_unchanged() -> None:
    """`FR-147` -- "without calculation, relabelling, filtering, or state suppression"."""
    j = journey()
    owner = member(j.w)
    pair = completed_pair(j, owner)
    for outcome in (
        _admitted(),
        ports.ViewOutcome(kind=ports.KIND_REFUSED, refusal=ports.ViewRefusal(cause="unknown view")),
    ):
        port = _FakePort(outcome)
        returned = _actions(j, port).request(_request(owner, pair.subject_run.run_id))
        assert returned is outcome


def test_a_request_writes_no_row_at_the_connection() -> None:
    """`FR-148` and `FR-149` -- asserted at the write path, never as a row-count delta.

    A before/after count is the pattern that let two sweeps both attest one purge
    on `#384`: it cannot see a write that was made and undone, or one to a table
    the count did not name. Listening on the cursor sees every statement the
    request issues, to any table.
    """
    j = journey()
    owner = member(j.w)
    pair = completed_pair(j, owner)
    port = _FakePort(_admitted())
    actions = _actions(j, port)

    statements: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany) -> None:  # noqa: ANN001
        statements.append(statement)

    engine = j.w.factory.kw["bind"]
    event.listen(engine, "before_cursor_execute", _record)
    try:
        actions.request(_request(owner, pair.subject_run.run_id))
        actions.request(_request(owner, MISSING_ID))
    finally:
        event.remove(engine, "before_cursor_execute", _record)

    assert statements, "the listener saw nothing, so it proves nothing"
    written = [s for s in statements if s.strip().split(" ")[0].lower() in _WRITE_VERBS]
    assert written == [], f"the path issued a write: {written}"


def _names_rra(name: str | None) -> bool:
    """Whether an import names the package `RCA-006` bars this one from reaching."""
    return (name or "").startswith("khepri.rra")


def _from_import(node: ast.AST) -> list[str]:
    """`from khepri.rra... import ...`, if that is what this node is."""
    if not isinstance(node, ast.ImportFrom):
        return []
    if not _names_rra(node.module):
        return []
    return [f"{node.lineno}: from {node.module}"]


def _plain_import(node: ast.AST) -> list[str]:
    """`import khepri.rra...`, for every alias on the node that names it."""
    if not isinstance(node, ast.Import):
        return []
    return [f"{node.lineno}: import {alias.name}" for alias in node.names if _names_rra(alias.name)]


def _rra_imports(source: str) -> list[str]:
    """Every reach into `khepri.rra` one module makes, whichever form it takes.

    Split across three small readers rather than one loop with a compound
    condition: CodeScene reads `isinstance(...) and startswith(...)` as a complex
    conditional, and its threshold here is two branches. Suppressing the finding
    was the offered alternative and is not one -- a gate waived for the test that
    guards `FR-150`'s import boundary is the boundary unguarded.
    """
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        found += _from_import(node)
        found += _plain_import(node)
    return found


def test_the_package_imports_no_concrete_rra_implementation() -> None:
    """`FR-150` -- a static scan, so the boundary holds without the module running.

    `RCA-006` requires the RCA half call "an injected protocol" and not import a
    concrete RRA implementation. An import added in a branch that no test happens
    to execute would pass a runtime check and fail this one.
    """
    package = pathlib.Path(queries.__file__).parent
    offenders = [
        f"{path.name}:{hit}"
        for path in sorted(package.glob("*.py"))
        for hit in _rra_imports(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"khepri.rca.semantic_queries imports khepri.rra: {offenders}"


def test_the_port_is_a_protocol_the_package_only_declares() -> None:
    """The consumer owns the seam; the composition root binds it, and is not here."""
    assert getattr(ports.SemanticViewPort, "_is_protocol", False)
    package = pathlib.Path(queries.__file__).parent
    assert not (package / "adapter.py").exists()
    assert not (package.parent.parent / "runtime" / "semantic_view_adapter.py").exists()
