"""Issuing and revoking invitations from the shell's team surface (`R8-05b`).

**Its own module rather than two more handlers in `shell_api.py`**, following the split that
already separates `commercial_api.py` from `external_auth_api.py`. `add_shell_routes` had grown a
route per slice, and the registrar was becoming the place every future surface lands regardless of
what it does. These two are a distinct concern: they are the shell's only *mutating* routes, and
they are the only ones that go through the owner gate.

**Both use `require_owner`, and that is the whole security property of this module.**
`InvitationService.issue` and `.revoke` take `actor_account_id` for attribution and check no
authority of their own -- both docstrings say so -- so `R6-04` placed the check in the gate. A
route here reaching for `for_request` would hand every member the ability to invite, and no
service-level test would notice.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from fastapi import FastAPI, Request, Response
from jinja2 import Environment

from khepri.rca.invitations import InvitationOffer
from khepri.rca.session_cookie import CommercialSessionCookie
from khepri.runtime.shell_frame import organization_frame

#: How long an issued invitation stays redeemable.
#:
#: `InvitationService.issue` takes `expires_at` with no default, deliberately: `FR-016` requires an
#: explicit expiry and fixes no lifetime, so a constant in the domain would put a product decision
#: there. The shell supplies one, and seven days matches the seven-day object expiry and backup
#: retention `KHEPRI-DEC-028` fixes -- its rule that "no retention horizon is quietly longer than
#: another" applies to an invitation as much as to content.
INVITATION_LIFETIME = timedelta(days=7)

#: The roles a request may name. `FR-015` fixes exactly two, and an unknown value is refused rather
#: than passed to the domain to reject: a role reaching `Invitation.create` from a form is
#: caller-supplied input, and the allowlist is where it stops.
ROLES = ("owner", "member")


def _form(body: bytes) -> dict[str, str]:
    """Parse a URL-encoded form body with the standard library.

    **No `python-multipart`, and that is a dependency decision rather than a style one.** FastAPI's
    `Form()` requires it, and the shell posts plain `application/x-www-form-urlencoded` bodies
    because the content security policy admits no inline script to build anything else. Adding a
    runtime dependency to the deployed wheel to parse two fields is a supply-chain surface the
    guardrails' "no external runtime assets" rule exists to avoid.

    Last value wins on a repeated key, matching form semantics; a missing key is absent rather than
    empty, so a caller's `not email` check still distinguishes them.
    """
    from urllib.parse import parse_qs

    parsed = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items() if values}


def owner_or_none(
    services: Any,
    session: str | None,
    clock: Callable[[], Any],
    *,
    organization_id: str,
) -> Any:
    """The owner gate, or `None` for every reason a caller must not tell apart.

    Absent cookie, unresolvable session, non-owner, and an unwired invitation gateway all return
    `None`, and every caller renders the same `unavailable`. Returning a context rather than a
    boolean follows `require_owner`'s own reasoning: a caller cannot ask the question and ignore
    the answer.

    **The organization is named to the gate rather than defaulted.** `require_owner` requires a
    target where `for_request` does not, precisely so the caller must name one -- "a default that
    is safe only when the caller remembers to pass the same value twice is not a default worth
    having" -- and it resolves the actor's live role in *that* organization before permitting
    anything.
    """
    if session is None or services.invitations is None:
        return None
    try:
        return services.resolver.require_owner(
            session, organization_id=organization_id, now=clock()
        )
    except PermissionError:
        return None


@dataclass(frozen=True, slots=True)
class ShellRendering:
    """The shell's own render surface, grouped rather than passed as five arguments.

    **Grouped for the reason `Invitation.create` and `InvitationOffer` are.** Spelling these flat
    cost nine parameters and CodeScene scored the file 9.69 on Excess Number of Function Arguments
    -- the same trap a `khepri.rra` signature hit before. They travel together on every call and
    have no meaning apart, which is what makes them one value rather than a list.

    Passed in rather than imported so this module cannot render a surface the shell does not own,
    and so `shell_api.py` keeps one definition of the security headers every response carries.
    """

    environment: Environment
    prefix: str
    language_of: Callable[[str], str]
    unavailable: Callable[..., Response]
    render: Callable[..., Response]
    team: Callable[..., Response]


def add_invitation_routes(
    app: FastAPI,
    *,
    services: Any,
    rendering: ShellRendering,
    clock: Callable[[], Any],
) -> None:
    """Declare the two mutating routes."""
    environment = rendering.environment
    language_of = rendering.language_of
    unavailable = rendering.unavailable
    render = rendering.render
    team = rendering.team

    @app.post(f"{rendering.prefix}/{{language}}/{{organization}}/team/invitations")
    async def issue_invitation(
        request: Request,
        language: str,
        organization: str,
        session: CommercialSessionCookie = None,
    ) -> Response:
        """Invite one person, as an owner of the organization the request names."""
        rendered = language_of(language)
        context = owner_or_none(services, session, clock, organization_id=organization)
        if context is None or context.organization_id is None:
            return unavailable(environment, language=rendered)

        submitted = _form(await request.body())
        email = submitted.get("email", "")
        role = submitted.get("role", "")
        if role not in ROLES or not email:
            return unavailable(environment, language=rendered)

        # **Every fallible read happens before the write, deliberately.** `issue` commits the
        # invitation and returns the only plaintext copy of its token, which is shown once and
        # cannot be recovered -- so a listing read that raised after it would 500 an owner whose
        # invitation exists and whose token is gone, and a retry would issue a second one. Read
        # the frame first and the failure costs nothing: no invitation, no orphaned token, and the
        # owner sees the same uniform refusal every other cause produces.
        #
        # The frame itself is resolved the way the team surface resolves it, so the organization
        # and `Team` controls stop vanishing on the way through this surface and returning when
        # the reader goes back.
        frame = organization_frame(
            services.organizations.organizations_for_account(context.account_id),
            context.organization_id,
        )

        now = clock()
        token = services.invitations.issue(
            InvitationOffer(
                organization_id=context.organization_id,
                intended_role=role,
                target_identity=email,
                issued_by=context.account_id,
            ),
            expires_at=now + INVITATION_LIFETIME,
            now=now,
        )
        return render(
            environment,
            "invitation_issued.html.j2",
            language=rendered,
            status_code=200,
            token=token,
            email=email,
            # The surface's "back to the team" link needs the organization segment. Without it the
            # href is two segments, `shell_surface` reads `segments[2]` as an empty surface name,
            # and an owner who just issued an invitation lands on the organization chooser instead
            # of the team they were looking at.
            organization_id=context.organization_id,
            **frame,
            # The one surface that renders no language control. It is a `POST` result with no
            # address of its own, so nothing re-requests *this page* in the other language: every
            # destination the control could name is a different surface, and reaching it discards
            # the token above, which `issue` returned once and the store keeps only a verifier of.
            # A control labelled "switch language" that in fact means "throw away the secret you
            # were just told to copy" is a worse answer than the control's absence, so it is
            # absent. The surface still renders in both languages with the same actions in each,
            # which is the parity `FR-054` asks for; `FR-055` constrains a switch that exists.
            #
            # The links that remain -- the brand, the organization, `Team`, "back to the team" --
            # leave the token behind too, but each of them says where it goes. They are the
            # reader's own decision to leave; a language control is not.
            language_switch=False,
        )

    @app.post(
        f"{rendering.prefix}/{{language}}/{{organization}}/team/invitations"
        f"/{{invitation}}/revoke"
    )
    def revoke_invitation(
        language: str,
        organization: str,
        invitation: str,
        session: CommercialSessionCookie = None,
    ) -> Response:
        """Withdraw one open invitation.

        The service refuses four causes identically -- absent, revoked, redeemed, expired, or
        another organization's -- so this handler adds no check that could distinguish them.
        """
        rendered = language_of(language)
        context = owner_or_none(services, session, clock, organization_id=organization)
        if context is None or context.organization_id is None:
            return unavailable(environment, language=rendered)
        try:
            services.invitations.revoke(
                context.organization_id,
                invitation,
                actor_account_id=context.account_id,
                now=clock(),
            )
        except Exception:  # noqa: BLE001 -- one refusal for every cause, per `FR-025`
            return unavailable(environment, language=rendered)
        return team(services, environment, language=rendered, context=context)


__all__ = [
    "INVITATION_LIFETIME",
    "ShellRendering",
    "ROLES",
    "add_invitation_routes",
    "owner_or_none",
]
