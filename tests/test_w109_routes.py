"""`W1-09`'s pin routes (`RCA-005` `FR-128`, `KHEPRI-DEC-034` §1).

The first test is the one that matters. `W1-07a` shipped a route absent from the built image while
seven tests passed over a hand-wired `ShellServices` (`#382`), and `wiring.py` now carries a
comment recording it. So the deployment assertion drives `build_shell_services` -- the function the
production root actually calls -- and the behaviour tests drive the real route through a client.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rca.workspace.persistence import SqlWorkspaceRecordStore
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes
from khepri.runtime.shell_pins import offers_pins
from tests.w104_support import member
from tests.w104b_support import journey
from tests.w106_support import HTTPS, services_over
from tests.w107_support import NOW, sealed_version


def _pin_address(
    who: Any, version_id: str, *, verb: str = "pin", organization: str | None = None
) -> str:
    where = organization or who.organization_id
    return f"{SHELL_PREFIX}/en/{where}/data/{version_id}/{verb}"


def _run_address(who: Any, run_id: str, *, verb: str = "pin") -> str:
    return f"{SHELL_PREFIX}/en/{who.organization_id}/analyses/{run_id}/{verb}"


def shell_with_pins(j: Any, who: Any, *, wired: bool = True) -> TestClient:
    """A shell whose pin store is wired (or deliberately not).

    Hand-wired deliberately, for the *behaviour* tests only: it lets a deployment without pins be
    expressed. The deployment question -- does the built image declare these routes -- is answered
    by `test_the_built_image_declares_the_pin_routes`, which builds nothing by hand.
    """
    base = services_over(j, who)
    services = ShellServices(
        resolver=base.resolver,
        organizations=base.organizations,
        invitations=base.invitations,
        bridge=base.bridge,
        records=base.records,
        isolation=base.isolation,
        provenance=base.provenance,
        pins=base.records if wired else None,
    )
    app = FastAPI()
    add_shell_routes(app, services=services, clock=j.clock)
    client = TestClient(app, base_url=HTTPS)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


class TestTheDeployedImage:
    def test_the_built_image_declares_the_pin_routes(self) -> None:
        """**The assertion `#382` exists to make.**

        `W1-07a` shipped a deletion route absent from the built wheel: `ShellServices.deletion`
        kept its `None` default in `build_shell_services`, `offers_deletion` omitted the route,
        and seven tests passed over a hand-built `ShellServices` that had it. A route table
        assembled by the test proves the module works, never that the deployment declares it.

        So this reaches for `build_shell_services` -- the function the production root calls --
        and asserts on the app composed from what it returns.
        """
        from khepri.runtime.wiring import build_shell_services
        from tests.test_runtime_wiring import runtime_stack

        shell = build_shell_services(runtime_stack())
        assert shell is not None
        assert offers_pins(shell), "the built image left ShellServices.pins at its None default"

        app = FastAPI()
        add_shell_routes(app, services=shell, clock=lambda: NOW)
        paths = {route.path for route in app.routes}

        for suffix in (
            "/data/{version_id}/pin",
            "/data/{version_id}/unpin",
            "/analyses/{run_id}/pin",
            "/analyses/{run_id}/unpin",
        ):
            assert any(path.endswith(suffix) for path in paths), (suffix, sorted(paths))

    def test_the_pin_store_is_the_store_the_surfaces_read(self) -> None:
        """One object, not two over one factory.

        `pin` writes and `pins_for_scope` reads the same tables Overview and Data read, and the
        cascade that ends a pin lives inside `set_retention_state` on this very class. A second
        store would work and would be a second object holding one definition.
        """
        from khepri.runtime.wiring import build_shell_services
        from tests.test_runtime_wiring import runtime_stack

        shell = build_shell_services(runtime_stack())

        assert shell is not None
        assert isinstance(shell.pins, SqlWorkspaceRecordStore)
        assert shell.pins is shell.records

    def test_a_shell_without_pins_declares_no_pin_route(self) -> None:
        """`FR-046`: the address is unknown rather than refused differently.

        A deployment that has not wired pins declares no route at the address, so the request
        never reaches a pin body -- rather than reaching one that answers the uniform refusal,
        which would tell a caller the capability exists and was denied them.

        **The status is `405`, not `404`, and that is the shell's shape rather than a defect.**
        This shell ends with a catch-all `GET /app/{path:path}`, so an undeclared address under
        the prefix matches it and a `POST` is answered "method not allowed". The property under
        test is that no *pin* route exists, which the route-table assertion states directly; the
        status is asserted only to pin the observable behaviour of an unwired deployment.
        """
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        client = shell_with_pins(j, who, wired=False)

        response = client.post(_pin_address(who, version.version_id))

        assert response.status_code == 405
        assert not any(
            route.path.endswith("/pin") for route in client.app.routes
        ), "an unwired deployment declared a pin route"
        assert j.w.store.pins_for_scope(who.owner_id) == ()


class TestPinningThroughTheRoute:
    def test_pinning_a_version_records_it(self) -> None:
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)

        response = shell_with_pins(j, who).post(
            _pin_address(who, version.version_id), follow_redirects=False
        )

        assert response.status_code == 303
        (pin,) = j.w.store.pins_for_scope(who.owner_id)
        assert pin.object_id == version.version_id
        assert pin.object_kind == "dataset_version"

    def test_unpinning_removes_it(self) -> None:
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        client = shell_with_pins(j, who)
        client.post(_pin_address(who, version.version_id), follow_redirects=False)

        client.post(_pin_address(who, version.version_id, verb="unpin"), follow_redirects=False)

        assert j.w.store.pins_for_scope(who.owner_id) == ()

    def test_pinning_a_run_records_it_under_the_run_kind(self) -> None:
        """The analyses address, whose kind is implied by the surface rather than carried on the
        wire -- the reason there is no `/pins/{object_kind}/` route."""
        j = journey()
        who = member(j.w)
        _version, run = sealed_version(j, who, with_run=True)

        shell_with_pins(j, who).post(_run_address(who, run.run_id), follow_redirects=False)

        (pin,) = j.w.store.pins_for_scope(who.owner_id)
        assert pin.object_id == run.run_id
        assert pin.object_kind == "analysis_run"

    def test_pinning_writes_no_audit_event_through_the_route(self) -> None:
        """`FR-128` again, this time with the real route on the code path.

        The store-level test asserts the same thing; this one proves the *route* adds none of its
        own -- a shell that emitted an event beside the store call would pass that one.
        """
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        before = len(j.w.audit.events_for_scope(who.owner_id))

        shell_with_pins(j, who).post(_pin_address(who, version.version_id))

        assert len(j.w.audit.events_for_scope(who.owner_id)) == before


class TestTheOwnerGate:
    def test_an_address_naming_another_organization_is_refused(self) -> None:
        """`FR-042`: the organization segment is compared with the session's, never trusted.

        Review on `#373` found that segment ignored on a read surface, which rendered one
        organization's records under another's address. These routes write.
        """
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)

        response = shell_with_pins(j, who).post(
            _pin_address(who, version.version_id, organization="org-elsewhere"),
            follow_redirects=False,
        )

        assert response.status_code != 303
        assert j.w.store.pins_for_scope(who.owner_id) == ()

    def test_a_request_without_a_session_pins_nothing(self) -> None:
        """The effect, not the exception: a refusal that returned the uniform page while still
        writing the row would pass a status-code assertion alone."""
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        client = shell_with_pins(j, who)
        client.cookies.clear()

        client.post(_pin_address(who, version.version_id), follow_redirects=False)

        assert j.w.store.pins_for_scope(who.owner_id) == ()
