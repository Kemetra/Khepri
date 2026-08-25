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


def organization_frame(organizations: Iterable[Any], organization_id: str) -> dict[str, str]:
    """The frame context for a surface rendered inside one resolved organization.

    `organization_name` is what the frame shows and what its organization control is named by;
    `surface_path` is the tail the language control keeps where one renders, so switching language
    holds the surface rather than dropping the reader on the chooser (`FR-054` scenario 11).
    """
    return {
        "organization_name": _active_organization_name(organizations, organization_id),
        "surface_path": f"/{organization_id}/team",
    }
