"""The organization half of the persistent frame, defined once for the two modules that render it.

**Its own module because neither half can hold it.** `shell_api.py` already imports
`shell_invitations.py`, so a helper both need would either invert that edge or make one module the
other's utility drawer. It sits here for the same reason `ShellRendering` is passed rather than
imported: the frame has one definition, and no route group may grow a second.

**Two surfaces, one frame.** The team surface and the invitation-issued surface are both rendered
inside a resolved organization, and a reader who moves between them must not watch the header lose
an element it had a moment before. Without this the issued surface took `_render`'s defaults: no
organization, no `Team`, and an empty tail that dropped an owner on the chooser.

The language control is the one thing this does *not* settle for both. `invitation_issued` is a
`POST` result with no address of its own, so no destination re-requests it in the other language,
and reaching any of them destroys the token `issue` returned once -- so that surface renders no
control at all and says so at its own render call. What this helper answers is the organization
half, which the two surfaces must agree on; the control is a property of having an address.

`FR-042` gives the session's organization the scope and gives the address none, so the name is
matched on the identifier the resolver returned rather than on any path segment. An organization
the reader holds no membership in is not in the listing and therefore cannot be named, which is
`FR-051` holding for the same reason the chooser's enumeration does.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


def _active_organization_name(organizations: Iterable[Any], organization_id: str) -> str:
    """The display name of the session's active organization, from the listing already read.

    Falls back to the empty string rather than raising. The name is frame decoration: a listing
    whose shape does not carry one should render a frame without it, not turn a working surface
    into a 500. `StrictUndefined` still catches a template referencing a name nobody passed.
    """
    for organization in organizations:
        if getattr(organization, "organization_id", None) == organization_id:
            return str(getattr(organization, "name", ""))
    return ""


#: The destinations the frame may name, as `(copy key, surface)` in `RCA-005` `FR-121`'s order.
#: Overview and Data ship with a reader (`W1-05`); Analyses ships with detail (`W1-06`), which
#: supplies the trust state and the next valid action `#374` withheld it for.
_WORKSPACE_DESTINATIONS = (
    ("overview_title", "overview"),
    ("data_title", "data"),
)
_ANALYSES_DESTINATION = ("analyses_title", "analyses")
_TEAM_DESTINATION = ("team_title", "team")


@dataclass(frozen=True, slots=True)
class Offers:
    """Which destinations this shell may name: Overview and Data (`records`), Analyses and its
    detail (`analyses`). Decided from the wiring once (`offers_of`) and handed to the frame."""

    records: bool
    analyses: bool


def offers_workspace(services: Any) -> bool:
    """Whether Overview and Data exist on this shell: both halves of the read are wired."""
    return services.records is not None and services.isolation is not None


def offers_analyses(services: Any) -> bool:
    """Whether Analyses and Analysis detail exist: the read, the provenance behind the trust state
    and the Passport, and the bridge the artifact handoff resumes a session through. Without any
    one of them the destination is absent (`FR-049`), not present and refusing."""
    return (
        offers_workspace(services)
        and getattr(services, "provenance", None) is not None
        and getattr(services, "bridge", None) is not None
    )


def offers_of(services: Any) -> Offers:
    return Offers(records=offers_workspace(services), analyses=offers_analyses(services))


def organization_frame(
    organizations: Iterable[Any],
    organization_id: str,
    *,
    surface: str,
    offers: Offers,
) -> dict[str, Any]:
    """The frame context for a surface rendered inside one resolved organization.

    `organization_name` is what the frame shows and what its organization control is named by;
    `surface_path` is the tail the language control keeps where one renders, so switching language
    holds the surface rather than dropping the reader on the chooser (`FR-054` scenario 11), and
    the tail the navigation marks as current.

    `destinations` is the navigation, decided here and nowhere else. `FR-121` and `RCA-002`
    `FR-049` require a link to ship only with a complete surface, so Overview and Data appear
    exactly when the shell holds a reader for them (`offers.records`), and Team always -- the one
    surface every shell has. Analyses stays withheld for the prerequisite gap recorded above. A
    template that decided this would be a second place the rule lives.
    """
    workspace = _WORKSPACE_DESTINATIONS if offers.records else ()
    analyses = (_ANALYSES_DESTINATION,) if offers.records and offers.analyses else ()
    return {
        "organization_name": _active_organization_name(organizations, organization_id),
        "surface_path": f"/{organization_id}/{surface}",
        "destinations": tuple(
            (label, f"/{organization_id}/{destination}")
            for label, destination in (*workspace, *analyses, _TEAM_DESTINATION)
        ),
    }
