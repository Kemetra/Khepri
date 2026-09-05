"""The owner-only route that ends a dataset version (`W1-07a`; `RCA-005` `FR-123`).

Its own module, as `shell_invitations.py` and `shell_artifact_handoff.py` are: `shell_api.py`
dispatches the read surfaces, and a mutating route that grew inside it would push that module past
what CodeScene admits while burying the one write this shell performs among the reads.

**Owner-only, through a gate of its own rather than `shell_invitations.owner_or_none`.** That one
returns `None` when `services.invitations is None`, which is right for a surface the invitation
gateway serves and wrong here: a deployment with deletion wired and invitations absent would refuse
every delete for a reason that has nothing to do with deletion. The shape is the same -- a context
rather than a boolean, for `require_owner`'s reason that a caller cannot ask the question and ignore
the answer -- and every cause a caller must not tell apart still answers `None`: absent cookie,
unresolvable session, non-owner, disagreeing organization. Each renders the same uniform refusal
(`FR-050`).

**No confirmation step here, and no affordance.** `W1-07a` ships the capability and its
guarantees; the Data surface's delete control, its confirmation and their bilingual copy are a
later slice's. `KHEPRI-DEC-033` §5 forbids any surface stating that content expires automatically
until `W1-07b`'s sweep ships with a caller, and shipping no deletion copy at all is the cleanest
way to hold that line while this slice lands.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Response
from fastapi.responses import RedirectResponse

from khepri.rca.session_cookie import CommercialSessionCookie
from khepri.runtime.shell_invitations import ShellRendering


def offers_deletion(services: Any) -> bool:
    """Whether this deployment wired the deletion service. A shell without it does not declare
    the route at all, so the address is unknown rather than refused differently (`FR-046`)."""
    return getattr(services, "deletion", None) is not None


def _owner_or_none(
    services: Any, session: str | None, clock: Callable[[], datetime], *, organization_id: str
) -> Any:
    """The owner gate this route needs, and nothing beyond it."""
    if session is None:
        return None
    try:
        return services.resolver.require_owner(
            session, organization_id=organization_id, now=clock()
        )
    except PermissionError:
        return None


def add_deletion_route(
    app: FastAPI,
    *,
    services: Any,
    rendering: ShellRendering,
    clock: Callable[[], datetime],
) -> None:
    """Declare the deletion route, where this deployment offers deletion."""
    if not offers_deletion(services):
        return

    environment = rendering.environment
    language_of = rendering.language_of
    unavailable = rendering.unavailable

    @app.post(f"{rendering.prefix}/{{language}}/{{organization}}/data/{{version_id}}/delete")
    def delete_version(
        language: str,
        organization: str,
        version_id: str,
        session: CommercialSessionCookie = None,
    ) -> Response:
        """End one dataset version, and everything `KHEPRI-DEC-033` §2 names as cascading from it.

        A version this scope does not hold reaches `delete_version` and answers `deleted=False`,
        which is the same response a genuine repeat gets -- so the route cannot be used to learn
        whether another organization's identifier exists.
        """
        rendered = language_of(language)
        context = _owner_or_none(services, session, clock, organization_id=organization)
        if context is None or context.organization_id is None:
            return unavailable(environment, language=rendered)
        # `FR-042`: the address names an organization, and it must be *compared* with the session's
        # rather than trusted. `require_owner` resolves the actor's role in the organization it is
        # given, so a correct resolver has already refused a mismatch -- but this route ends a
        # customer's data, and it does not get to assume that every resolver it is composed with
        # enforces the comparison. Review on `#373` found this segment ignored on a *read* surface,
        # which rendered one organization's records under another's address; the same omission here
        # would delete them.
        if context.organization_id != organization:
            return unavailable(environment, language=rendered)
        owner_id = services.isolation.resolve_scope(context.account_id, context.organization_id)
        services.deletion.delete_version(
            owner_id,
            version_id,
            actor_account_id=context.account_id,
            now=clock(),
        )
        # Back to the Data surface, which now lists one fewer version. A `303` rather than a
        # rendered page because this slice ships no deletion surface of its own to render, and a
        # POST result that re-renders on refresh would repeat the request -- harmless here, since
        # the repeat is idempotent, but the redirect is what makes that irrelevant rather than
        # merely survivable. `delete_version` answers the same way for a version this scope never
        # held, so the destination does not distinguish the two.
        return RedirectResponse(
            url=f"{rendering.prefix}/{rendered}/{context.organization_id}/data", status_code=303
        )


__all__ = ["add_deletion_route", "offers_deletion"]
