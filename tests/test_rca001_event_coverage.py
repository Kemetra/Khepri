"""`R2-07` -- every membership write emits its `FR-014` event, and none can be added without one.

**This slice adds no emission code, because there is none left to add.** `R2-02` emitted the
creation event, `R2-04` the promotion, `R2-05` the revocation, and `R2-06` the demotion. The
roadmap's stated output for `R2-07` is "FR-014 event coverage", and coverage that already exists
is proven rather than rewritten.

What was missing is the *guarantee*. Each of those slices asserted its own event, so four tests
each prove one path -- and none of them fails if a fifth write path lands emitting nothing at all,
which is exactly the omission `R2-09` is asked to hunt for. These tests close that: they enumerate
the write paths from the source, pair each against the emission, and assert the counts agree
across a whole membership lifecycle.
"""

from __future__ import annotations

import ast
import inspect as inspect_module
import pathlib
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.organizations import MEMBER_ROLE, OWNER_ROLE, OrganizationService
from khepri.rca.persistence import Base, MembershipRow, SqlAccountStore, SqlOrganizationStore

NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 8, 14, 13, 0, tzinfo=UTC)
CREDENTIAL = "correct horse battery staple"


@pytest.fixture(name="factory")
def _factory(tmp_path) -> sessionmaker:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'coverage.db').as_posix()}")
    Base.metadata.create_all(engine)
    return sessionmaker(engine)


def _events(factory: sessionmaker) -> list[tuple]:
    with factory() as database:
        return [
            tuple(row)
            for row in database.execute(
                text(
                    "SELECT account_id, prior_role, next_role, actor_account_id "
                    "FROM rca_membership_events ORDER BY occurred_at, event_id"
                )
            ).fetchall()
        ]


def test_every_membership_write_path_emits_exactly_one_event(factory: sessionmaker) -> None:
    """Drive all four write paths in sequence and count.

    Four writes, four events, in order. Counting across a whole lifecycle rather than
    per-operation is what catches an operation that emits *twice* as well as one that emits none.
    A duplicate is as much an FR-014 defect as an omission, because a reader cannot tell which of
    two records of one change is the real one.
    """
    accounts = SqlAccountStore(factory)
    store = SqlOrganizationStore(factory)
    service = OrganizationService(store)
    owner = AccountService(accounts).create_account("owner@example.test", CREDENTIAL)
    second = AccountService(accounts).create_account("second@example.test", CREDENTIAL)
    joiner = AccountService(accounts).create_account("joiner@example.test", CREDENTIAL)

    # 1. create -- the owner membership, emitted inside the atomic write
    organization = service.create_organization("Acme", owner.account_id, now=NOW)
    with factory.begin() as database:
        for account in (second, joiner):
            database.add(
                MembershipRow(
                    organization_id=organization.organization_id,
                    account_id=account.account_id,
                    role=MEMBER_ROLE,
                )
            )

    # 2. promote  3. demote  4. revoke
    service.promote_to_owner(
        organization.organization_id,
        second.account_id,
        actor_account_id=owner.account_id,
        now=LATER,
    )
    service.demote_to_member(
        organization.organization_id,
        second.account_id,
        actor_account_id=owner.account_id,
        now=LATER,
    )
    service.revoke_membership(
        organization.organization_id,
        joiner.account_id,
        actor_account_id=owner.account_id,
        now=LATER,
    )

    events = _events(factory)

    assert len(events) == 4, f"four writes must produce four events, got {events}"

    # Compared as a multiset, not a sequence. Three of the four operations share one timestamp
    # here, and `event_id` is a CSPRNG token, so no total order over these rows exists to assert
    # -- an ordered comparison would pass or fail on which identifiers happened to sort first.
    # `occurred_at` is the only ordering FR-014 gives, and it is asserted where it is meaningful:
    # `test_the_event_table_is_append_only_across_every_operation` observes the count after each
    # operation, which pins the sequence without depending on tie-breaks.
    kinds = sorted(
        (prior or "", nxt or "") for _account, prior, nxt, _actor in events
    )
    assert kinds == sorted(
        [
            ("", OWNER_ROLE),
            (MEMBER_ROLE, OWNER_ROLE),
            (OWNER_ROLE, MEMBER_ROLE),
            (MEMBER_ROLE, ""),
        ]
    ), "create, promote, demote, revoke -- each distinguishable from the role pair alone"
    assert all(actor == owner.account_id for _a, _p, _n, actor in events), (
        "FR-014: every event names the account that made the change"
    )


#: How a method's source betrays that it writes `rca_memberships`: inserting a row, reassigning a
#: role, or deleting the row the shared guard located.
_MUTATION_MARKERS = ("MembershipRow(", ".role = ", "database.delete(row)")

#: How it betrays that the write is attributed: emitting the event itself, or delegating to the
#: shared guard that does. Delegation counts -- that indirection is what makes revoke and demote
#: share one final-owner guard.
_EMISSION_MARKERS = ("_event_row(", "_apply_membership_change(")


def test_no_membership_write_path_exists_without_an_event() -> None:
    """The guarantee the four per-slice tests do not give.

    Each earlier slice asserted its own event, so a *fifth* write path could land emitting
    nothing and every one of those tests would still pass. This enumerates the writes from
    `SqlOrganizationStore`'s own source and requires each to sit in a method that also emits.

    Read as: every method whose source mutates `rca_memberships` must also reach an
    `FR-014` emission -- either by writing the event itself, or by delegating to the shared guard
    that does.

    `revoke_membership` and `demote_membership` mutate inside a nested callback and hand it to
    `_apply_membership_change`, which is where their `_event_row` call lives. That indirection is
    deliberate -- it is what makes the two share one final-owner guard -- so delegation counts as
    emission here. What does *not* count is a method that mutates and neither emits nor delegates,
    which is the omission this test exists to catch.

    The `writes` set is stated rather than derived so that *moving* a write is visible too: a path
    that appears, disappears, or relocates fails this test and has to be acknowledged.
    """
    # `_apply_membership_change` is absent deliberately: it holds the guard and the emission, but
    # the mutation itself lives in the callbacks its two callers pass in, so their source carries
    # the write and its does not.
    writes = {
        "create_organization",
        "promote_membership",
        "revoke_membership",
        "demote_membership",
    }
    emits = set()
    mutates = set()

    for name, method in inspect_module.getmembers(
        SqlOrganizationStore, predicate=inspect_module.isfunction
    ):
        source = inspect_module.getsource(method)
        if any(marker in source for marker in _MUTATION_MARKERS):
            mutates.add(name)
        if any(marker in source for marker in _EMISSION_MARKERS):
            emits.add(name)

    assert mutates == writes, (
        f"a membership write path appeared or moved: {sorted(mutates)} vs known {sorted(writes)}. "
        "A new operation needs an FR-014 event and a line in this set."
    )
    assert mutates <= emits, (
        f"these write a membership without emitting or delegating an event: "
        f"{sorted(mutates - emits)}"
    )


def test_the_event_table_is_append_only_across_every_operation(factory: sessionmaker) -> None:
    """No operation deletes or rewrites an event, including the one that deletes its subject.

    `KHEPRI-DEC-015` retains the membership "only as the subject of the FR-014 audit event", so
    revocation removing the row must leave the event -- and no path may quietly tidy up after
    itself. Only the twelve-month sweeper (`R2-08`) may remove an event, and it does not exist
    yet, so the count must never decrease here.
    """
    accounts = SqlAccountStore(factory)
    store = SqlOrganizationStore(factory)
    service = OrganizationService(store)
    owner = AccountService(accounts).create_account("owner@example.test", CREDENTIAL)
    target = AccountService(accounts).create_account("target@example.test", CREDENTIAL)
    organization = service.create_organization("Acme", owner.account_id, now=NOW)
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization.organization_id,
                account_id=target.account_id,
                role=MEMBER_ROLE,
            )
        )

    counts = [len(_events(factory))]
    operations = (
        lambda: service.promote_to_owner(
            organization.organization_id,
            target.account_id,
            actor_account_id=owner.account_id,
            now=LATER,
        ),
        lambda: service.demote_to_member(
            organization.organization_id,
            target.account_id,
            actor_account_id=owner.account_id,
            now=LATER,
        ),
        lambda: service.revoke_membership(
            organization.organization_id,
            target.account_id,
            actor_account_id=owner.account_id,
            now=LATER,
        ),
    )
    for operation in operations:
        operation()
        counts.append(len(_events(factory)))

    assert counts == sorted(counts), f"the event count decreased: {counts}"
    assert counts == [1, 2, 3, 4], f"one event per operation, none removed: {counts}"

    assert store.get_membership(organization.organization_id, target.account_id) is None
    revocations = [event for event in _events(factory) if event[2] is None]
    assert len(revocations) == 1, "the revocation event outlived the row it describes"


#: Functions allowed to remove an `FR-014` record, by name. `R2-08`'s twelve-month sweep is the one
#: legitimate deleter, and it must be named here when it lands rather than the test below being
#: relaxed -- failing closed is the point.
_PERMITTED_DELETERS = frozenset({"sweep", "_purge_expired_events"})


def _deletes_an_event(function: ast.FunctionDef) -> bool:
    """Whether this function removes a membership event.

    Two rejected approaches are worth recording, because both looked adequate.

    A *line-scoped* text check requiring `delete(` and `MembershipEventRow` on one line missed the
    ordinary two-line form -- `for stale in ...select(MembershipEventRow)...:` then
    `database.delete(stale)` -- and reported green against a deleter. Found by mutation-testing
    this test.

    Widening it to the whole function then flagged `revoke_membership`, correctly by the letter and
    wrongly by intent: it deletes a *membership* row and merely mentions `MembershipEventRow` in
    prose. Text cannot tell a subject from a docstring.

    So the judgement is on the AST. A deletion counts when what is handed to `.delete()`, or named
    in a `delete()` construct, traces back to `MembershipEventRow` -- either directly or through a
    local bound from a query naming it. Prose is invisible to this, and the two-line form is not.
    """
    event_bound_names = _names_bound_from_event_queries(function)
    deleted = (
        ast.unparse(argument)
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and _is_delete_call(node)
        for argument in node.args
    )
    return any(
        "MembershipEventRow" in rendered or rendered in event_bound_names
        for rendered in deleted
    )


def _is_delete_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr == "delete"
    return isinstance(node.func, ast.Name) and node.func.id == "delete"


def _names_bound_from_event_queries(function: ast.FunctionDef) -> set[str]:
    """Locals bound from something that queries `MembershipEventRow`.

    Covers the two-line deletion: the loop variable of `for x in ...MembershipEventRow...` and the
    target of `x = ...MembershipEventRow...`, so `delete(x)` is recognised without needing the
    table name on the deleting line.
    """
    nodes = list(ast.walk(function))
    loops = (
        node.target
        for node in nodes
        if isinstance(node, ast.For) and "MembershipEventRow" in ast.unparse(node.iter)
    )
    assignments = (
        target
        for node in nodes
        if isinstance(node, ast.Assign) and "MembershipEventRow" in ast.unparse(node.value)
        for target in node.targets
    )
    return {
        name for target in (*loops, *assignments) for name in _target_names(target)
    }


def _target_names(target: ast.expr) -> set[str]:
    return {node.id for node in ast.walk(target) if isinstance(node, ast.Name)}


def _event_deleting_functions(source: str, name: str) -> list[str]:
    tree = ast.parse(source)
    return [
        f"{name}:{node.name}"
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name not in _PERMITTED_DELETERS
        and _deletes_an_event(node)
    ]


def test_no_production_code_deletes_a_membership_event() -> None:
    """Append-only, asserted against the source rather than only by observation.

    A path that deleted events would satisfy the count test above whenever it happened not to
    run, so observation alone cannot establish this.
    """
    modules = sorted((pathlib.Path("src") / "khepri" / "rca").glob("*.py"))
    offenders = [
        offender
        for path in modules
        for offender in _event_deleting_functions(path.read_text(encoding="utf-8"), path.name)
    ]

    assert not offenders, (
        f"an event is deleted outside the retention sweeper: {offenders}. "
        "Only R2-08's twelve-month horizon may remove an FR-014 record."
    )
