"""The M2 persistent frame: identity strip, journey exit, and recovery exits.

Three properties are asserted here that no other suite covers, and each of them is a defect the
shipped surfaces carried:

**The frame degrades by surface rather than rendering one fixed row.** `_unavailable` and
`_no_membership` are handed nothing but a language, deliberately -- "takes no cause, so it can
disclose none" -- so a base template referencing an organization unconditionally would turn the two
surfaces that absorb failure into 500s under `StrictUndefined`. The cases below drive every surface
in both languages, which is the only check that distinguishes a frame that degrades from one that
happens not to have been rendered on the hard path yet.

**The recovery exit is identical wherever `FR-050` applies.** That requirement forbids
distinguishing the collapsed causes "by copy, status code, page identity, or navigation state", and
an exit is navigation state. Asserting the shell's and the journey's exits against each other is
what makes that a property rather than a coincidence of two templates written on the same day.

**No organization identity reaches `/beta`.** `open_commercial_session` takes an opaque `owner_id`
so that "no `account_id`, `organization_id`, name, slug, or email reaches this function" and
`FR-032`/`FR-033` hold *by absence rather than by inspection*. The product decision to show the
organization in the journey is made; the authority is not. A test that only checked the current
templates would pass again the moment somebody wired the name through, so the case here asserts the
absence against a rendered page carrying a distinctive name.
"""

from __future__ import annotations

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


def _organization(organization_id: str, name: str) -> Organization:
    return Organization._from_storage(
        organization_id=organization_id, name=name, created_at=NOW
    )


def _shell(
    *,
    context: _Context | None = None,
    organizations: list[Organization] | None = None,
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

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_shell_and_the_journey_use_one_wording(self, language: str) -> None:
        """Two templates, one string: a different exit would be a distinguishing state."""
        assert SHELL_COPY[language]["recovery_exit"] == JOURNEY_COPY[language]["recovery_exit"]

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


class TestTheJourneyOffersOneExit:
    """`Leave analysis` on every normal step, and nothing that cancels or deletes."""

    @pytest.mark.parametrize("language", ["en", "ar"])
    @pytest.mark.parametrize("step", ["upload", "review", "processing", "report"])
    def test_every_normal_step_offers_the_exit(self, language: str, step: str) -> None:
        from tests.test_rra_journey_api import client

        html = client().get(f"/beta/{language}/{step}").text

        assert JOURNEY_COPY[language]["leave_analysis"] in html
        assert 'href="/app/' + language + '"' in html

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_brand_leaves_for_the_shell(self, language: str) -> None:
        """It pointed at `/beta/{language}`, which `common.js` reconciles straight back."""
        from tests.test_rra_journey_api import client

        html = client().get(f"/beta/{language}/upload").text

        assert f'class="brand" href="/app/{language}"' in html

    @pytest.mark.parametrize("step", ["upload", "review", "processing", "report"])
    def test_the_exit_is_navigation_and_not_a_form(self, step: str) -> None:
        """Leaving deletes nothing and cancels nothing, so it carries no method and no dialog.

        A POST here would imply a state change, and a `confirm` would claim a risk that does not
        exist. The one destructive control on these steps is `delete-content`, which stays separate.
        """
        from importlib.resources import files

        from tests.test_rra_journey_api import client

        html = client().get(f"/beta/en/{step}").text
        exit_markup = html[html.index("leave-analysis") - 60 :][:400]

        assert "method=" not in exit_markup
        # No interstitial: the exit is an anchor, so there is no handler to attach one to. Asserted
        # against the scripts rather than the markup, because a dialog would live in JS. `confirm`
        # as a word is shipped copy on these steps -- `#confirm-mapping`, "Confirmed facts" -- so
        # the needle is the call, not the string.
        for asset in ("common.js", "review.js", "processing.js", "report.js", "upload.js"):
            source = (
                files("khepri.rra.journey").joinpath("assets", asset).read_text(encoding="utf-8")
            )
            assert "window.confirm" not in source, asset
            assert "confirm(" not in source.replace("#confirm-mapping", ""), asset

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_language_control_keeps_the_step(self, language: str) -> None:
        from tests.test_rra_journey_api import client

        other = "ar" if language == "en" else "en"
        html = client().get(f"/beta/{language}/review").text

        assert f'href="/beta/{other}/review"' in html

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_expired_surface_offers_the_shared_exit(self, language: str) -> None:
        """Outside the deletion branch: `FR-050` forbids an exit that differs by cause."""
        from tests.test_rra_journey_api import client

        plain = client().get(f"/beta/{language}/expired").text
        deleted = client().get(f"/beta/{language}/expired?deletion=requested").text

        for html in (plain, deleted):
            assert JOURNEY_COPY[language]["recovery_exit"] in html
            assert f'href="/app/{language}"' in html
