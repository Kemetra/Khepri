"""The M2 persistent frame: the shell's identity strip and its recovery exit.

Four properties are asserted here that no other suite covers, and each of them is a defect the
shipped surfaces carried:

**The frame degrades by surface rather than rendering one fixed row.** `_unavailable` and
`_no_membership` are handed nothing but a language, deliberately -- "takes no cause, so it can
disclose none" -- so a base template referencing an organization unconditionally would turn the two
surfaces that absorb failure into 500s under `StrictUndefined`. The cases below drive every surface
in both languages, which is the only check that distinguishes a frame that degrades from one that
happens not to have been rendered on the hard path yet.

**The recovery exit carries no cause.** `FR-050` forbids distinguishing the collapsed causes "by
copy, status code, page identity, or navigation state", and an exit is navigation state -- so the
shell's exit is one string, one target, present whichever cause brought the reader there. The
journey's `expired` needs the same exit and does not get one here: `RCA-002` excludes "any change
to the `RRA` beta journey, its routes, its templates, or its assets" and no `RRA` specification
governs that frame, so the beta half is untouched and the two-sided assertion belongs to whichever
slice carries that authority.

**No organization identity reaches `/beta`.** `open_commercial_session` takes an opaque `owner_id`
so that "no `account_id`, `organization_id`, name, slug, or email reaches this function" and
`FR-032`/`FR-033` hold *by absence rather than by inspection*. The product decision to show the
organization in the journey is made; the authority is not. A test that only checked the current
templates would pass again the moment somebody wired the name through, so the case here asserts the
absence against a rendered page carrying a distinctive name.

**Every surface that resolves an organization frames it the same way.** `invitation_issued` is
rendered by `issue_invitation` rather than by the dispatcher, so it is the one surface a frame
written in the dispatcher can silently miss -- and it did, taking `_render`'s defaults and sending
a language switch to the organization chooser. The cases below assert its frame against the team
surface's rather than against a literal, so the two cannot drift apart again.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.organizations import Organization
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rra.journey.copy import JOURNEY_COPY
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes
from khepri.runtime.shell_copy import SHELL_COPY

NOW = datetime(2026, 8, 22, tzinfo=UTC)

#: Distinctive enough that finding it in journey markup means it was passed, not coincidence.
ORGANIZATION_NAME = "Zephyr Provisioning Collective"

#: A path that actually reaches `unavailable`. The dispatcher reads the surface from `segments[2]`,
#: so a two-segment address leaves it empty and matches the chooser instead: `/app/en/anything`
#: renders the switcher at 200. Three segments are what make the surface name present and unknown.
#: See the note in the module docstring of the finding this suite reports.
UNKNOWN_SURFACE = "/org-acme/no-such-surface"


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

    def for_request(self, token: str, *, organization_id: str | None, now: object) -> _Context:
        return self._context

    def require_owner(self, token: str, *, organization_id: str, now: object) -> _Context:
        return self._context


class _StubOrganizations:
    def __init__(self, organizations: list[Organization]) -> None:
        self._organizations = organizations

    def organizations_for_account(self, account_id: str) -> list[Organization]:
        return list(self._organizations)

    def memberships_for_organization(self, organization_id: str) -> list[object]:
        return []


class _StubInvitations:
    """Enough gateway to reach `invitation_issued`, which has no address to `GET`."""

    def invitations_for_organization(
        self, organization_id: str, *, now: object = None
    ) -> tuple[object, ...]:
        return ()

    def issue(self, offer: object, *, expires_at: object, now: object) -> str:
        return "inv_a-one-time-token"


def _organization(organization_id: str, name: str) -> Organization:
    return Organization._from_storage(
        organization_id=organization_id, name=name, created_at=NOW
    )


def _shell(
    *,
    context: _Context | None = None,
    organizations: list[Organization] | None = None,
    invitations: _StubInvitations | None = None,
) -> TestClient:
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=_StubResolver(context or _Context("acct-1", "org-acme")),
            organizations=_StubOrganizations(
                organizations
                if organizations is not None
                else [_organization("org-acme", ORGANIZATION_NAME)]
            ),
            invitations=invitations,
        ),
        clock=lambda: NOW,
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


class TestTheBrandIsAWayHome:
    """It was a bare `<span>` in the shell and a self-referential link in the journey."""

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_shell_brand_links_to_the_chooser(self, language: str) -> None:
        html = _shell().get(f"{SHELL_PREFIX}/{language}/org-acme/team").text

        assert f'href="{SHELL_PREFIX}/{language}"' in html
        assert "<span class=\"brand\">" not in html

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_brand_carries_an_accessible_name(self, language: str) -> None:
        """A wordmark is a picture of a name, not a name."""
        html = _shell().get(f"{SHELL_PREFIX}/{language}/org-acme/team").text

        assert SHELL_COPY[language]["frame_home_label"] in html


class TestTheOrganizationIsNamedWhereItIsResolved:
    """The reader must be able to answer "which organization am I working in" (`FR-042`)."""

    def test_the_team_surface_names_the_active_organization(self) -> None:
        html = _shell().get(f"{SHELL_PREFIX}/en/org-acme/team").text

        assert ORGANIZATION_NAME in html

    def test_the_name_follows_the_session_not_the_address(self) -> None:
        """`FR-042` gives the address no authority over scope, so neither may the frame.

        The address names one organization and the session another; the frame must show the
        session's. A frame reading the path would show `org-other` here.
        """
        html = _shell(
            context=_Context("acct-1", "org-acme"),
            organizations=[
                _organization("org-acme", ORGANIZATION_NAME),
                _organization("org-other", "Someone Else Entirely"),
            ],
        ).get(f"{SHELL_PREFIX}/en/org-other/team").text

        assert ORGANIZATION_NAME in html
        assert "Someone Else Entirely" not in html

    def test_a_latin_name_carries_its_direction_in_arabic(self) -> None:
        """`FR-055`: a Latin run inside Arabic prose reorders visually without an explicit dir."""
        html = _shell().get(f"{SHELL_PREFIX}/ar/org-acme/team").text

        assert 'dir="ltr"' in html

    def test_the_chooser_does_not_offer_a_link_to_itself(self) -> None:
        """The chooser is where the organization control leads; a control to here does nothing."""
        html = _shell().get(f"{SHELL_PREFIX}/en/").text

        assert SHELL_COPY["en"]["frame_organization_label"] not in html


class TestTeamIsTheOnlyDestination:
    """`FR-049`: a navigation entry MUST NOT be rendered for a surface with no implementation."""

    def test_the_frame_offers_team(self) -> None:
        html = _shell().get(f"{SHELL_PREFIX}/en/org-acme/team").text

        assert f'href="{SHELL_PREFIX}/en/org-acme/team"' in html

    @pytest.mark.parametrize("surface", ["settings", "account", "reports", "metrics", "activity"])
    def test_no_entry_exists_for_an_unimplemented_surface(self, surface: str) -> None:
        """Scenario 20: "Navigation entry for an unimplemented surface | Absent".

        `analyses` is deliberately not in this list. It is a real POST action on the chooser's
        active row -- `R8-06`, merged -- and not a navigation entry, so its address appearing in a
        form `action` is the implemented capability rather than a link to a surface that has none.
        """
        for path in (f"{SHELL_PREFIX}/en/", f"{SHELL_PREFIX}/en/org-acme/team"):
            html = _shell().get(path).text

            assert f'href="{SHELL_PREFIX}/en/org-acme/{surface}"' not in html, path
            assert f'href="{SHELL_PREFIX}/en/{surface}"' not in html, path


class TestTheLanguageControlPreservesPosition:
    """`FR-047` plus scenario 11: "Language switch mid-surface | Position preserved"."""

    def test_the_shell_keeps_the_surface(self) -> None:
        html = _shell().get(f"{SHELL_PREFIX}/en/org-acme/team").text

        assert f'href="{SHELL_PREFIX}/ar/org-acme/team"' in html

    def test_the_chooser_keeps_the_chooser(self) -> None:
        html = _shell().get(f"{SHELL_PREFIX}/en/").text

        assert f'href="{SHELL_PREFIX}/ar"' in html

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_control_names_the_target_language_with_its_own_lang(self, language: str) -> None:
        """A reader who cannot read the current language must still recognise the control."""
        html = _shell().get(f"{SHELL_PREFIX}/{language}/org-acme/team").text
        copy = SHELL_COPY[language]

        assert copy["frame_language"] in html
        assert f'lang="{copy["frame_language_code"]}"' in html


class TestEverySurfaceCarriesTheFrame:
    """The two surfaces that absorb failure receive only a language, by design."""

    @pytest.mark.parametrize("language", ["en", "ar"])
    @pytest.mark.parametrize(
        "path", ["/", "/org-acme/team", UNKNOWN_SURFACE]
    )
    def test_the_frame_renders_without_a_500(self, path: str, language: str) -> None:
        """`StrictUndefined` turns a missing variable into a render failure, not a blank."""
        response = _shell().get(f"{SHELL_PREFIX}/{language}{path}")

        assert response.status_code in (200, 404)
        assert SHELL_COPY[language]["frame_home_label"] in response.text

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_no_membership_surface_carries_the_frame(self, language: str) -> None:
        response = _shell(organizations=[]).get(f"{SHELL_PREFIX}/{language}/")

        assert response.status_code == 200
        assert SHELL_COPY[language]["frame_home_label"] in response.text

    def test_a_refusal_names_no_organization(self) -> None:
        """`FR-052`: one denial, examined alone, discloses nothing about the object."""
        response = _shell().get(f"{SHELL_PREFIX}/en{UNKNOWN_SURFACE}")

        assert response.status_code == 404
        assert ORGANIZATION_NAME not in response.text


class TestTheRecoveryExitIsIndistinguishable:
    """`FR-050` forbids telling the collapsed causes apart by navigation state."""

    def test_the_unavailable_surface_offers_a_way_out(self) -> None:
        response = _shell().get(f"{SHELL_PREFIX}/en{UNKNOWN_SURFACE}")

        assert response.status_code == 404
        assert SHELL_COPY["en"]["recovery_exit"] in response.text
        assert f'href="{SHELL_PREFIX}/en"' in response.text

    def test_the_exit_names_no_cause(self) -> None:
        exit_copy = SHELL_COPY["en"]["recovery_exit"].lower()

        for cause in ("expire", "delete", "member", "session", "denied", "forbidden"):
            assert cause not in exit_copy


class TestNoOrganizationIdentityReachesTheJourney:
    """The absence-based boundary at `sessions.py`, asserted rather than assumed.

    `open_commercial_session` takes an opaque `owner_id` and nothing else, so `FR-032`/`FR-033` hold
    by absence. Showing the organization in the journey is an approved product direction with no
    implementation authority yet, so the absence is the current contract and belongs in a test: the
    day somebody wires the name through, this is what says the authority came first.
    """

    def test_the_journey_copy_carries_no_organization_vocabulary(self) -> None:
        for language in ("en", "ar"):
            for key in JOURNEY_COPY[language]:
                assert "organization" not in key, f"{language}.{key}"

    @pytest.mark.parametrize("language", ["en", "ar"])
    @pytest.mark.parametrize("step", ["upload", "review", "processing", "report", "expired"])
    def test_no_rendered_journey_page_carries_organization_vocabulary(
        self, step: str, language: str
    ) -> None:
        """Asserted on the rendered page, not on the template source.

        The first version of this case read `base.html.j2` and stripped Jinja comments before
        searching. It survived a mutant that added `{{ organization_name }}` to the header: the
        comment explaining this very boundary contains the word many times, and splitting on the
        last `#}` left only the file's tail. A rendered page cannot hide a variable in a comment,
        because comments do not render -- so the render is the haystack.
        """
        from tests.test_rra_journey_api import client

        html = client().get(f"/beta/{language}/{step}").text.lower()

        # A *named* organization or a commercial identifier, not the word itself: the recovery exit
        # says "go to your organizations", which is a destination and names nobody. What the
        # boundary forbids is identity reaching this half, so the needles are the things that would
        # only be here if something wired the session's organization through.
        for forbidden in ("acme", "zephyr", "owner_id", "account_id", "org-", "organization_id"):
            assert forbidden not in html, f"{step}/{language} carries {forbidden}"

        # The template must interpolate no organization variable at all. Checked against the
        # rendered page, so a value hidden in a Jinja comment cannot satisfy it.
        assert "organization_name" not in html

    def test_the_journey_render_context_carries_no_commercial_state(self) -> None:
        """The render call is the boundary: what is not passed cannot be shown."""
        import inspect

        from khepri.rra.journey import routes

        source = inspect.getsource(routes.JourneyEndpoints._page_response)

        for forbidden in ("organization", "account_id", "owner_id", "session_id"):
            assert forbidden not in source, forbidden


#: The language control, read out of the frame rather than guessed at. `frame-language` is the only
#: class on it, and the href is the next attribute -- so a control that stopped preserving the
#: surface changes this capture rather than merely adding an anchor somewhere else on the page.
_LANGUAGE_CONTROL = re.compile(r'class="frame-language"\s+href="([^"]+)"')


def _language_control(html: str) -> str:
    match = _LANGUAGE_CONTROL.search(html)
    assert match is not None, "the frame renders no language control"
    return match.group(1)


class TestTheBetaJourneyIsUntouched:
    """`RCA-002`'s exclusion, asserted rather than remembered.

    The specification this slice is authorized by excludes "any change to the `RRA` beta journey,
    its routes, its templates, or its assets", and the registry holds no successor `RRA`
    specification governing the journey's frame. An earlier revision of this slice gave the journey
    a brand pointing at `/app` and a `Leave analysis` exit -- markup that would also have reached a
    generic 404 in a beta-only deployment, where `add_shell_routes(services=None)` declares no
    `/app` routes at all.

    So the boundary is a case rather than a note: a journey page that grows a link into the
    commercial prefix fails here, whichever half wrote it, until a specification says it may.
    """

    @pytest.mark.parametrize("language", ["en", "ar"])
    @pytest.mark.parametrize("step", ["upload", "review", "processing", "report", "expired"])
    def test_no_journey_page_links_into_the_commercial_shell(
        self, step: str, language: str
    ) -> None:
        """A beta-only deployment declares no `/app` route, so such a link is also a 404."""
        from tests.test_rra_journey_api import client

        html = client().get(f"/beta/{language}/{step}").text

        assert f'href="{SHELL_PREFIX}' not in html, f"{step}/{language}"

    def test_the_shell_stylesheet_does_not_reach_the_journey(self) -> None:
        """`shell-components.css` sits in the journey's asset directory and is the shell's.

        It is the one file under `khepri.rra.journey` this slice changes, and it is a journey asset
        by path only: `shell.html.j2` is the sole template that links it, and the exclusion is about
        the beta surface rather than about a directory. Asserted so that stays true.
        """
        from tests.test_rra_journey_api import client

        for step in ("upload", "review", "processing", "report", "expired"):
            assert "shell-components.css" not in client().get(f"/beta/en/{step}").text, step


class TestTheIssuedInvitationSurfaceCarriesTheSameFrame:
    """The one surface reached only by `POST`, and the one the frame forgot.

    `invitation_issued` is rendered by `issue_invitation` rather than by the dispatcher, so it
    received `organization_id` and nothing else. The frame took `_render`'s defaults: no
    `organization_name`, therefore no organization and no `Team`; and an empty `surface_path`,
    therefore a language control pointing at `{prefix}/{alternate}` -- the organization chooser.

    An owner who switched language on this page lost the surface *and* the scope, on the one page
    in the product whose secret is shown once and cannot be shown again. Nothing raised: the empty
    tail is a valid address that renders a real page, which is why this needs a case rather than a
    type.
    """

    def _issued(self, language: str) -> str:
        client = _shell(invitations=_StubInvitations())
        response = client.post(
            f"{SHELL_PREFIX}/{language}/org-acme/team/invitations",
            data={"email": "invitee@example.test", "role": "member"},
        )

        assert response.status_code == 200
        assert "inv_a-one-time-token" in response.text
        return response.text

    @pytest.mark.parametrize("language,alternate", [("en", "ar"), ("ar", "en")])
    def test_the_language_control_keeps_the_team_surface(
        self, language: str, alternate: str
    ) -> None:
        """The assertion the defect fails: it captured `{prefix}/{alternate}`, the chooser."""
        assert (
            _language_control(self._issued(language))
            == f"{SHELL_PREFIX}/{alternate}/org-acme/team"
        )

    def test_the_frame_names_the_organization_it_acted_in(self) -> None:
        """It vanished on the way through, and returned when the reader went back."""
        assert ORGANIZATION_NAME in self._issued("en")

    def test_the_frame_offers_team_here_too(self) -> None:
        """Asserted inside `frame-surfaces`, not anywhere on the page.

        The surface has carried a "back to the team" link with this exact href since `R8-05b`, so a
        bare search for it passes with no frame at all -- which is what makes the enclosing element
        the needle rather than the address.
        """
        issued = self._issued("en")
        nav = issued[issued.index('class="frame-surfaces"') :][:300]

        assert f'href="{SHELL_PREFIX}/en/org-acme/team"' in nav

    def test_the_team_surface_and_this_one_agree(self) -> None:
        """One helper resolves both, so the header cannot differ between them.

        Asserted against the team surface rather than against a literal: a frame that changed on
        both surfaces together is a change, and a frame that changed on one is the defect.
        """
        team = _shell().get(f"{SHELL_PREFIX}/en/org-acme/team").text

        assert _language_control(self._issued("en")) == _language_control(team)
