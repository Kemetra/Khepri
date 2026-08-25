"""The team surface reaches its own invitation route (`R8-05b`).

`R8-05b` shipped `issue_invitation` reading `email` and `role` from a form body, and shipped no
form. The pending list's withdraw button was the only control on the surface, so an owner could
un-invite and never invite: the route existed and nothing in the product could reach it.

**These cases drive the form rather than inspecting it.** A test asserting `name="email"` appears in
the markup passes while the action URL points nowhere, which is the exact shape of the original
defect -- one half present, the other absent, nothing comparing them. So the action and the field
names are read out of the rendered page and posted back, and the assertion is that the service
recorded the offer. A renamed route, a renamed field, or a role the allowlist refuses all fail here.

**The role option values are asserted against `ROLES` itself.** `FR-015` fixes exactly two, and a
select offering a third would post a value `issue_invitation` refuses -- reaching the reader as the
uniform "unavailable" surface that `FR-052` forbids explaining. A dead end is worse than a missing
control, because the reader cannot tell it from a fault.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes
from khepri.runtime.shell_invitations import ROLES

NOW = datetime(2026, 8, 22, tzinfo=UTC)


@dataclass
class _Context:
    account_id: str
    organization_id: str | None
    role: str | None = "owner"

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"


class _StubResolver:
    def __init__(self, context: _Context) -> None:
        self._context = context

    def for_request(
        self, token: str, *, organization_id: str | None = None, now: object = None
    ) -> _Context:
        return self._context

    def require_owner(
        self, token: str, *, organization_id: str, now: object = None
    ) -> _Context:
        return self._context


class _StubInvitations:
    def __init__(self) -> None:
        self.issued: list[tuple[str, str, str]] = []

    def invitations_for_organization(
        self, organization_id: str, *, now: object = None
    ) -> tuple[object, ...]:
        return ()

    def issue(self, offer: object, *, expires_at: object, now: object) -> str:
        self.issued.append(
            (offer.organization_id, offer.target_identity, offer.intended_role)
        )
        return "inv_a-one-time-token"

    def revoke(self, *args: object, **kwargs: object) -> None:  # pragma: no cover
        raise AssertionError("these cases never revoke")


class _StubOrganizations:
    def organizations_for_account(self, account_id: str) -> list[object]:
        return [object()]

    def memberships_for_organization(self, organization_id: str) -> list[object]:
        return []


def _shell(role: str = "owner") -> tuple[TestClient, _StubInvitations]:
    invitations = _StubInvitations()
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=_StubResolver(_Context("acct-1", "org-acme", role)),
            organizations=_StubOrganizations(),
            invitations=invitations,
        ),
        clock=lambda: NOW,
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client, invitations


#: The create form, distinguished from the withdraw form by where its action ends. The withdraw
#: action continues `/{invitation_id}/revoke`, so the closing quote is what tells them apart -- a
#: needle matching both would be satisfied by the surface that already shipped.
_CREATE_FORM = re.compile(
    r'<form method="post" action="([^"]*/team/invitations)">(.*?)</form>', re.DOTALL
)


def _create_form(html: str) -> tuple[str, str]:
    match = _CREATE_FORM.search(html)
    assert match is not None, "the team surface renders no invitation-creation form"
    return match.group(1), match.group(2)


class TestTheFormReachesTheRoute:
    """The whole point: what the page renders is what the route accepts."""

    def test_the_rendered_form_issues_an_invitation_when_posted_back(self) -> None:
        """A round trip, so a renamed route or field fails rather than passing on a substring."""
        client, invitations = _shell()
        action, body = _create_form(client.get(f"{SHELL_PREFIX}/en/org-acme/team").text)
        names = re.findall(r'name="(\w+)"', body)
        assert set(names) == {"email", "role"}, names
        answers = {"email": "invitee@example.test", "role": "member"}

        response = client.post(action, data={name: answers[name] for name in names})

        assert response.status_code == 200
        assert invitations.issued == [
            ("org-acme", "invitee@example.test", "member")
        ]

    def test_the_default_selection_is_a_role_the_route_accepts(self) -> None:
        """A placeholder option would post a refused value and land on `unavailable`."""
        client, invitations = _shell()
        action, body = _create_form(client.get(f"{SHELL_PREFIX}/en/org-acme/team").text)
        selected = re.search(r'<option value="([^"]*)" selected>', body)
        assert selected is not None, "no role is preselected, so a submit can post nothing"

        response = client.post(
            action, data={"email": "invitee@example.test", "role": selected.group(1)}
        )

        assert response.status_code == 200
        assert invitations.issued != []

    def test_every_offered_role_is_one_the_allowlist_admits(self) -> None:
        """`FR-015` fixes two; an option outside `ROLES` is a control that only ever refuses."""
        client, _ = _shell()
        _, body = _create_form(client.get(f"{SHELL_PREFIX}/en/org-acme/team").text)

        offered = re.findall(r'<option value="([^"]*)"', body)
        assert offered, "the role select offers nothing, so this proves nothing"
        assert set(offered) == set(ROLES)


class TestTheOwnerGateIsMirroredInTheMarkup:
    """`require_owner` refuses a member, so the surface offers a member nothing to submit."""

    def test_a_member_is_not_shown_the_form(self) -> None:
        client, _ = _shell(role="member")

        html = client.get(f"{SHELL_PREFIX}/en/org-acme/team").text

        assert _CREATE_FORM.search(html) is None

    def test_an_owner_is(self) -> None:
        """The negative case above is only evidence if the positive one differs."""
        client, _ = _shell(role="owner")

        html = client.get(f"{SHELL_PREFIX}/en/org-acme/team").text

        assert _CREATE_FORM.search(html) is not None


class TestTheFieldsAreLabelledAndDirected:
    """`FR-055` and the accessibility bar the shell already holds every other control to."""

    def test_each_control_has_a_label_bound_to_its_id(self) -> None:
        client, _ = _shell()
        _, body = _create_form(client.get(f"{SHELL_PREFIX}/en/org-acme/team").text)

        controls = re.findall(r'<(?:input|select) id="([^"]+)"', body)
        assert controls, "the form has no controls, so this proves nothing"
        labelled = set(re.findall(r'<label for="([^"]+)">', body))
        assert set(controls) == labelled

    def test_the_email_field_is_pinned_to_latin_direction(self) -> None:
        """`FR-055`: an address typed into an RTL field renders with its parts reordered."""
        client, _ = _shell()
        _, body = _create_form(
            client.get(f"{SHELL_PREFIX}/ar/org-acme/team").text
        )

        email_input = re.search(r'<input id="invite-email"[^>]*>', body)
        assert email_input is not None
        assert 'dir="ltr"' in email_input.group(0)
        assert 'autocomplete="email"' in email_input.group(0)

    def test_the_form_is_translated(self) -> None:
        """`FR-054`: equivalent action text in both, and neither borrows the other's."""
        client, _ = _shell()
        _, english = _create_form(client.get(f"{SHELL_PREFIX}/en/org-acme/team").text)
        _, arabic = _create_form(client.get(f"{SHELL_PREFIX}/ar/org-acme/team").text)

        assert english != arabic


class TestTheSuccessSurfaceReachesTheTeamItCameFrom:
    """The link out of `invitation_issued`, followed rather than pattern-matched.

    The href it shipped with -- `{prefix}/{language}/team` -- is a valid URL that renders a real
    page, so nothing raised and no assertion on the markup would have caught it. `shell_surface`
    reads the surface name from `segments[2]`, and with the organization segment missing that index
    holds `""`, which resolves to the switcher. An owner who had just invited somebody was returned
    to the organization chooser.

    So these follow the link and assert on the surface that answers, which is the only check the
    original defect fails.
    """

    def _issued_page(self, language: str) -> tuple[TestClient, str]:
        client, _ = _shell()
        action, body = _create_form(
            client.get(f"{SHELL_PREFIX}/{language}/org-acme/team").text
        )
        names = re.findall(r'name="(\w+)"', body)
        answers = {"email": "invitee@example.test", "role": "member"}
        response = client.post(
            action, data={name: answers[name] for name in names}
        )
        assert response.status_code == 200
        return client, response.text

    def test_following_the_link_lands_on_the_team_surface(self) -> None:
        """The assertion the defect fails: the switcher answered instead."""
        client, issued = self._issued_page("en")
        href = re.search(r'<a href="([^"]+)"', issued)
        assert href is not None, "the success surface offers no way back"

        landed = client.get(href.group(1))

        assert landed.status_code == 200
        # The team surface names the pending list; the switcher never does.
        assert "invitations-title" in landed.text

    def test_the_link_carries_the_organization_it_acted_on(self) -> None:
        """A back-link to the wrong organization is the same defect wearing a path."""
        _, issued = self._issued_page("en")
        href = re.search(r'<a href="([^"]+)"', issued)
        assert href is not None
        assert href.group(1) == f"{SHELL_PREFIX}/en/org-acme/team"

    def test_the_link_holds_in_arabic(self) -> None:
        """`FR-054`: the language segment travels with the organization segment."""
        client, issued = self._issued_page("ar")
        href = re.search(r'<a href="([^"]+)"', issued)
        assert href is not None
        assert href.group(1) == f"{SHELL_PREFIX}/ar/org-acme/team"

        landed = client.get(href.group(1))

        assert landed.status_code == 200
        assert "invitations-title" in landed.text
