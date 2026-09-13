"""RCA-008 `D1-08` -- presentation without recalculation.

Authority: active `RCA-008` `FR-159`, `FR-168`, §Retention. Plan:
`docs/superpowers/plans/2026-09-13-d1-08-execution-plan.md`.

Print is in scope. A stored snapshot is barred three ways over. **Export is an
open owner reading and this module asserts its refusal, not its absence** -- the
restrictive reading is a default taken because the slice may not ship on the
permissive one, never a finding that export is forbidden.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.semantic_queries.queries import SemanticQueryActions
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rra.persistence import SqlFactPackageRepository
from khepri.runtime.semantic_view_adapter import SemanticViewAdapter
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes
from tests.w104_support import Member
from tests.w104b_support import Journey, journey
from tests.w106_support import HTTPS, completed_run, isolation, services_over
from tests.w110_support import ScopedResolver, two_members


def _shell(j: Journey, who: Member) -> TestClient:
    """A shell authenticated as `who`, with the production decision collaborator."""
    base = services_over(j, who)
    context = base.resolver.for_request("", organization_id=None, now=None)
    services = ShellServices(
        resolver=ScopedResolver(context, organization_id=who.organization_id),
        organizations=base.organizations,
        records=base.records,
        isolation=base.isolation,
        provenance=base.provenance,
        decisions=SemanticQueryActions(
            isolation=isolation(j),
            sources=j.w.store,
            port=SemanticViewAdapter(SqlFactPackageRepository(j.w.factory)),
        ),
    )
    app = FastAPI()
    add_shell_routes(app, services=services, clock=j.clock)
    client = TestClient(app, base_url=HTTPS)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


def _address(who: Member, run_id: str, *, printable: bool = False) -> str:
    tail = "?print=1" if printable else ""
    return f"{SHELL_PREFIX}/en/{who.organization_id}/decisions/{run_id}{tail}"


# --- FR-159: print projects, it does not derive ------------------------------


def test_print_carries_the_same_figures_as_the_screen() -> None:
    """`FR-159` -- a figure re-derived for the page is derived outside a projection.

    Not "both render without error": the *same* run rendered both ways must carry
    an identical set of figures. A print layout that re-groups or re-totals would
    pass a smoke test and fail this one.
    """
    world = journey()
    who, _other = two_members(world)
    run, _job, _session = completed_run(world, who)
    shell = _shell(world, who)
    screen = shell.get(_address(who, run.run_id))
    printed = shell.get(_address(who, run.run_id, printable=True))
    assert screen.status_code == 200
    assert printed.status_code == 200
    assert _figures(printed.text) == _figures(screen.text)


def test_print_renders_the_decision_cards() -> None:
    """A print surface that renders nothing would satisfy the equality above."""
    world = journey()
    who, _other = two_members(world)
    run, _job, _session = completed_run(world, who)
    printed = _shell(world, who).get(_address(who, run.run_id, printable=True))
    assert "decision-card" in printed.text
    assert _figures(printed.text) != ()


def test_the_print_surface_is_distinguishable_from_the_screen() -> None:
    """The guard that keeps the three tests around it from being no-ops.

    Until print exists, `?print=1` is an undeclared parameter the route reads and
    ignores (`FR-137` forbids declaring one, because a declared parameter that
    did not match would be silently dropped). So a print request returns the
    ordinary page, "print equals screen" is trivially true, and "no CSV was
    served" is true of every page ever rendered.

    This asserts the surface actually branches. It must fail before `D1-08` and
    pass after; if it ever passes for the wrong reason, the three tests around it
    are attesting nothing.
    """
    world = journey()
    who, _other = two_members(world)
    run, _job, _session = completed_run(world, who)
    shell = _shell(world, who)
    screen = shell.get(_address(who, run.run_id))
    printed = shell.get(_address(who, run.run_id, printable=True))
    assert 'data-surface="print"' in printed.text
    assert 'data-surface="print"' not in screen.text


def _figures(markup: str) -> tuple[str, ...]:
    """Every rendered figure, in document order, as the template marks them.

    `decision.html.j2` marks a card's figure `data-line="value"` and a breakdown
    cell `data-cell="<name>"`. Both are captured: a print layout that dropped or
    re-totalled the breakdown rows while keeping the cards would otherwise pass.
    """
    import re

    return tuple(
        re.findall(
            r'data-line="value">([^<]*)<|data-cell="[^"]*">([^<]*)<', markup
        )
    )


# --- Retention: print remembers nothing --------------------------------------


def test_print_is_not_recorded_and_leaves_no_state() -> None:
    """§Retention -- "no layout, filter, sort, or dismissal state" of its own.

    Asserted at the write seam rather than by comparing two responses: a stable
    response proves the *render* is stable, not that nothing was stored.
    """
    world = journey()
    who, _other = two_members(world)
    run, _job, _session = completed_run(world, who)
    before = _rows(world)
    _shell(world, who).get(_address(who, run.run_id, printable=True))
    assert _rows(world) == before


def _rows(j: Journey) -> dict[str, int]:
    """Row counts for every table, so a new stored row anywhere is visible."""
    from sqlalchemy import func, select

    from khepri.rca.persistence import Base

    with j.w.factory() as session:
        return {
            table.name: session.execute(
                select(func.count()).select_from(table)
            ).scalar_one()
            for table in Base.metadata.sorted_tables
        }


# --- FR-161: the basis of a figure reaches the paper ------------------------


def test_the_evidence_drawer_is_open_on_paper() -> None:
    """`FR-161` -- a figure's basis must be reachable from the surface carrying it.

    On screen the drawer is a `<details>` the reader opens. **On paper there is
    no opening it**: a closed `<details>` prints only its `<summary>`, so the
    definition, formula, versions, units and applied filters would leave the
    page while the figures stayed. That is not a styling nit -- it prints
    numbers whose basis the reader cannot reach.

    The markup is shared with the screen (`FR-159`), so the equality test cannot
    see this: both surfaces emit the same `<details>`. The difference is in what
    renders, which is why this asserts the print stylesheet's rule.
    """
    world = journey()
    who, _other = two_members(world)
    run, _job, _session = completed_run(world, who)
    printed = _shell(world, who).get(_address(who, run.run_id, printable=True))
    assert "decision-drawer" in printed.text
    assert ".decision-drawer > *:not(summary)" in printed.text
    assert "display: revert !important" in printed.text


# --- The export reading: refused, and raised ---------------------------------


def test_export_is_refused_while_its_reading_is_open() -> None:
    """`RCA-008`:158 -- "no cross-organization access, sharing, or export".

    Whether "cross-organization" modifies `export` is not resolvable from the
    document. The `D1-06`-`D1-10` refinement directs the reading that does *not*
    let the slice ship, so export is refused here **by default, not by finding**.
    The day the owner rules, this test is the one to revisit.
    """
    world = journey()
    who, _other = two_members(world)
    run, _job, _session = completed_run(world, who)
    refused = _shell(world, who).get(
        f"{SHELL_PREFIX}/en/{who.organization_id}/decisions/{run.run_id}?export=csv"
    )
    assert refused.status_code == 200
    assert "text/csv" not in refused.headers.get("content-type", "")
    assert "attachment" not in refused.headers.get("content-disposition", "")
    # The header assertions alone are satisfied by an ordinary page that
    # silently IGNORED `export=csv`, which is the `FR-137` defect rather than
    # the refusal. `export` names no published view's filter, so it reaches the
    # seam and earns the governed unsupported-parameter wording -- assert that
    # the reader is actually told, not merely that no CSV was served.
    assert 'data-control="unsupported"' in refused.text

