"""RCA-008 Verification -- cross-organization isolation on the decision surface.

`test_d104_breakdowns_and_limits` stubs the collaborator and only mismatches the
path organization against the session. This module drives a real
`SemanticQueryActions` + adapter: the session matches the path organization, and
the `run_id` belongs to another organization.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.semantic_queries.queries import SemanticQueryActions
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rra.persistence import SqlFactPackageRepository
from khepri.runtime.semantic_view_adapter import SemanticViewAdapter
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes
from khepri.runtime.shell_decisions import DECISION_COPY
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


def _address(who: Member, run_id: str) -> str:
    return f"{SHELL_PREFIX}/en/{who.organization_id}/decisions/{run_id}"


def test_a_foreign_run_is_the_same_unavailable_as_a_missing_run() -> None:
    """`FR-146` / RCA-008 Verification: a stranger's run_id discloses nothing."""
    world = journey()
    who, other = two_members(world)
    run, _job, _session = completed_run(world, who)
    own = _shell(world, who).get(_address(who, run.run_id))
    assert "decision-card" in own.text

    shell = _shell(world, other)
    foreign = shell.get(_address(other, run.run_id))
    missing = shell.get(_address(other, "run-does-not-exist"))
    marker = "SRC"

    assert foreign.status_code == missing.status_code
    assert foreign.text.replace(run.run_id, marker) == missing.text.replace(
        "run-does-not-exist", marker
    )
    assert DECISION_COPY["en"]["unavailable"] in foreign.text
    assert "decision-card" not in foreign.text
    assert "decision-value" not in foreign.text
    assert who.owner_id not in foreign.text
    assert who.organization_id not in foreign.text
