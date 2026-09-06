"""Shared setup for `W1-10`'s lifecycle and isolation tests (`RCA-005` `FR-127`, `FR-109`).

**What this module exists to make possible.** `RCA-005`:180-181 requires the isolation tests to
drive *real requests across two organizations* and assert the uniform denial *byte-for-byte*. Both
halves already existed in this repository and had never met: the two-org HTTP tests
(`test_w106_analysis_detail.py:349`, `test_w107_deletion_route.py:35`) compare a substring or a
status code, and the one byte-for-byte comparison (`test_r802_shell_unavailable_surface.py:239`)
runs over stub resolvers with no workspace rows beneath it. A substring assertion cannot see a
denial that grew a distinguishing detail, which is the whole failure mode `FR-051` names.

Setup runs through **production verbs** -- the journey admits, the worker settles, the sweeper
purges -- rather than shaping rows directly, for the reason `w107_support.py` records: raw setup
exempts the transition it skips, so a mutant of the bypassed verb survives every test built on it.

**The isolation boundary under these tests is real.** `w105_support.services_over` stubs only the
*session checkpoint* -- who the cookie resolves to -- and hands the shell the world's own stores
and a real `IsolationService`. So a shell authenticated as one member, pointed at another
organization's address, exercises the real boundary; that is how `test_w106_analysis_detail.py:349`
already reads, and these tests extend the pattern to the surfaces and verbs that lacked it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from khepri.runtime.shell_api import SHELL_PREFIX
from tests.w104_support import Member
from tests.w104b_support import Journey
from tests.w106_support import analyses_address, detail_address, handoff_address

#: Substrings that must never appear in a refusal (`FR-051`). An organization's own identifier is
#: not here: the address the caller already typed carries it, and the surfaces that legitimately
#: answer echo it. What may not appear is anything naming the scope the caller was refused.
LEAKABLE = ("@", "example.test")


@dataclass(frozen=True, slots=True)
class Denials:
    """Responses that must be one another's equal, and what they were asked for.

    Grouped so the failure message can say which addresses disagreed rather than only that two
    strings differed -- five loose parameters would also trip CodeScene's argument gate.
    """

    responses: tuple[Any, ...]
    addresses: tuple[str, ...]


def assert_uniform_denial(
    denials: Denials, *, forbidden: tuple[str, ...] = (), status: int = 404
) -> None:
    """Every response is the *same* answer, compared byte-for-byte (`FR-127`, `FR-051`).

    Three properties, and the first is the one no existing W1 test asserted:

    1. **Identical bytes.** Not "each contains `unavailable_title`" -- identical status and
       identical body. A denial that grows a detail distinguishing *absent* from *forbidden* hands
       back existence, and a substring assertion cannot see it happen. The comparison is over
       `.content` and not `.text`: `.text` is the body *decoded*, so two responses that differ
       in encoding but agree once decoded would compare equal, and this claims bytes. The leak
       checks below stay on `.text`, where a decoded string is the right thing to search.
    2. **The shape this surface refuses in**, so a test cannot pass because two surfaces both
       answered `200`. Read surfaces refuse with `404` and the `unavailable` body. The deletion
       route's uniform answer is the `303` back to Data that a *successful* delete also gets --
       deliberately, because a `404` for an identifier this scope does not hold, against a `303`
       for one it does, is the enumeration oracle the uniformity exists to close. Pass `status`
       for a surface whose uniform answer is not `404`.
    3. **No leaked identifier**, per `FR-051`: the answer names neither the object asked for nor
       the scope that holds it.
    """
    assert len(denials.responses) >= 2, "a uniform-denial claim needs at least two responses"
    first, *rest = denials.responses
    assert first.status_code == status, (
        f"{denials.addresses[0]} answered {first.status_code}, not the expected {status}"
    )
    for index, other in enumerate(rest, start=1):
        assert other.status_code == first.status_code, (
            f"{denials.addresses[index]} answered {other.status_code}, "
            f"{denials.addresses[0]} answered {first.status_code}"
        )
        assert other.content == first.content, (
            f"{denials.addresses[index]} and {denials.addresses[0]} are not the same refusal; "
            "a denial that varies by cause discloses which cause applied"
        )
    for index, response in enumerate(denials.responses):
        for leak in (*LEAKABLE, *forbidden):
            assert leak not in response.text, (
                f"{denials.addresses[index]} leaked {leak!r} into a refusal (`FR-051`)"
            )


class ScopedResolver:
    """The session checkpoint that **compares the named organization**, as production does.

    `w105_support.StubResolver` returns its one context whatever `organization_id` it is handed, so
    a route that ignores the path segment and trusts the session's own organization passes every
    test built on it. `w107_support._RefusingOwnerGate` was written to close the *owner* half of
    that blindness; this closes the *scope* half, which is wider: it reaches every route taking an
    `{organization}` segment, not only the owner-gated one.

    `rca/authorization_resolution.py:89-105` is the behaviour modelled here -- a named organization
    that is not the session's active one is refused with the same content-free error as a
    non-member, deliberately, so a caller cannot enumerate organizations one probe at a time.
    """

    def __init__(self, context: Any, *, organization_id: str) -> None:
        self._context = context
        self._organization_id = organization_id

    def _checked(self, organization_id: str | None) -> Any:
        from khepri.rca.errors import ScopeAccessDenied

        if organization_id is not None and organization_id != self._organization_id:
            raise ScopeAccessDenied("Resource is unavailable.")
        return self._context

    def for_request(self, token: str, *, organization_id: str | None, now: object) -> Any:
        return self._checked(organization_id)

    def require_owner(self, token: str, *, organization_id: str, now: object) -> Any:
        return self._checked(organization_id)


class PermissiveResolver:
    """A checkpoint that resolves the session and **does not compare** the named organization.

    Not a straw man: `w105_support.StubResolver` behaves exactly this way, and every shell composed
    with it in this repository is blind to a route that trusts the `{organization}` segment. Review
    on `#373` found a read surface doing precisely that, rendering one organization's records under
    another's address.

    Routes carry their own comparison for this reason -- `shell_deletion.py:88-95` says so in as
    many words: *"it does not get to assume that every resolver it is composed with enforces the
    comparison."* A guard that only ever runs behind a stricter guard has no evidence of its own;
    one outcome test passes with either alone. This composition is how the route's own check is
    put on the code path by itself.
    """

    def __init__(self, context: Any) -> None:
        self._context = context

    def for_request(self, token: str, *, organization_id: str | None, now: object) -> Any:
        return self._context

    def require_owner(self, token: str, *, organization_id: str, now: object) -> Any:
        return self._context


def shell_across(j: Journey, who: Member) -> Any:
    """A shell authenticated as `who` whose resolver compares the organization it is asked about.

    This is the composition `FR-127`'s cross-organization cases need: the world's real stores, the
    real `IsolationService`, and a checkpoint that refuses a named organization other than the
    session's -- so pointing it at another scope's address exercises a refusal rather than
    silently rewriting the request to the caller's own scope.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from khepri.rca.session_cookie import SESSION_COOKIE
    from khepri.runtime.shell_api import ShellServices, add_shell_routes
    from tests.w106_support import HTTPS, services_over

    base = services_over(j, who)
    services = ShellServices(
        resolver=ScopedResolver(
            base.resolver.for_request("", organization_id=None, now=None),
            organization_id=who.organization_id,
        ),
        organizations=base.organizations,
        invitations=base.invitations,
        bridge=base.bridge,
        records=base.records,
        isolation=base.isolation,
        provenance=base.provenance,
    )
    app = FastAPI()
    add_shell_routes(app, services=services, clock=j.clock)
    client = TestClient(app, base_url=HTTPS)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


def shell_mis_composed(j: Journey, who: Member) -> Any:
    """A shell with deletion wired and a resolver that does **not** compare the organization.

    The composition a route must survive. Everything else is the real thing -- real stores, real
    `IsolationService`, real `DeletionService` -- so what a test over this shell exercises is the
    route's own `context.organization_id != organization` comparison, alone on the code path.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from khepri.rca.session_cookie import SESSION_COOKIE
    from khepri.runtime.shell_api import ShellServices, add_shell_routes
    from tests.w106_support import HTTPS, services_over
    from tests.w107_support import deletion_service

    base = services_over(j, who)
    services = ShellServices(
        resolver=PermissiveResolver(base.resolver.for_request("", organization_id=None, now=None)),
        organizations=base.organizations,
        invitations=base.invitations,
        bridge=base.bridge,
        records=base.records,
        isolation=base.isolation,
        provenance=base.provenance,
        deletion=deletion_service(j),
    )
    app = FastAPI()
    add_shell_routes(app, services=services, clock=j.clock)
    client = TestClient(app, base_url=HTTPS)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


def overview_address(who: Member, language: str = "en") -> str:
    return f"{SHELL_PREFIX}/{language}/{who.organization_id}/overview"


def data_address(who: Member, language: str = "en") -> str:
    return f"{SHELL_PREFIX}/{language}/{who.organization_id}/data"


def two_members(j: Journey) -> tuple[Member, Member]:
    """Two real organizations in one world, each with its own owner.

    Both are made by the production verb, so each carries a real opaque scope; a hand-built second
    scope would not exercise the isolation key `FR-109` is about.
    """
    from tests.w104_support import member

    return member(j.w), member(j.w, email="other@example.test", name="Other")


__all__ = [
    "LEAKABLE",
    "Denials",
    "PermissiveResolver",
    "ScopedResolver",
    "shell_across",
    "shell_mis_composed",
    "analyses_address",
    "assert_uniform_denial",
    "data_address",
    "detail_address",
    "handoff_address",
    "overview_address",
    "two_members",
]
