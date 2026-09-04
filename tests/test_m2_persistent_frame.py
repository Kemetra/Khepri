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
a language switch to the organization chooser. The cases below assert its organization half against
the team surface's rather than against a literal, so the two cannot drift apart again.

**One element of the frame is absent on one surface, and one surface keeps only half of what it
would like to.** `invitation_issued` has no address of its own and shows a token `issue` returns
exactly once, so every destination a language control could name destroys the secret; it renders
none. `unavailable` has an address and may not name it -- `FR-051` and `FR-052` keep the
organization and the object identifier out of a refusal's body, and an `href` is body -- so its
control keeps the surface through a constant tail rather than keeping the address. Rendering
nothing there was tried and gives up the reader `FR-054` is about: the one who reaches a refusal
in a language they cannot read, whose recovery exit is in that language too.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.organizations import Organization
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rra.journey.copy import JOURNEY_COPY
from khepri.runtime.shell_api import (
    _UNAVAILABLE_TAIL,
    SHELL_ASSETS,
    SHELL_PREFIX,
    ShellServices,
    add_shell_routes,
)
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


class _RefusingResolver:
    """A resolver that refuses, which is one of the five causes `FR-050` collapses."""

    def for_request(self, token: str, *, organization_id: str | None, now: object) -> _Context:
        raise PermissionError("this session does not authorize the request")

    def require_owner(self, token: str, *, organization_id: str, now: object) -> _Context:
        raise PermissionError("this session does not authorize the request")


class _StubOrganizations:
    def __init__(self, organizations: list[Organization]) -> None:
        self._organizations = organizations

    def organizations_for_account(self, account_id: str) -> list[Organization]:
        return list(self._organizations)

    def memberships_for_organization(self, organization_id: str) -> list[object]:
        return []


class _StubInvitations:
    """Enough gateway to reach `invitation_issued`, which has no address to `GET`.

    Records what it was asked to commit, because one case below is about a write that must not
    happen rather than a page that must render.
    """

    def __init__(self) -> None:
        self.issued: list[object] = []

    def invitations_for_organization(
        self, organization_id: str, *, now: object = None
    ) -> tuple[object, ...]:
        return ()

    def issue(self, offer: object, *, expires_at: object, now: object) -> str:
        self.issued.append(offer)
        return "inv_a-one-time-token"


class _StubIsolation:
    def resolve_scope(self, account_id: str, organization_id: str) -> str:
        return f"scope-{organization_id}"


class _StubRecords:
    """An empty workspace, so the frame under test is the one with every built destination."""

    def dataset_versions_for_scope(self, owner_id: str) -> tuple[object, ...]:
        return ()

    def analysis_runs_for_scope(self, owner_id: str) -> tuple[object, ...]:
        return ()

    def tombstones_for_scope(self, owner_id: str) -> tuple[object, ...]:
        return ()

    def artifact_bindings_for_scope(self, owner_id: str) -> tuple[object, ...]:
        return ()


class _UnreadableOrganizations(_StubOrganizations):
    """A listing read that fails the way a transient database fault would."""

    def __init__(self) -> None:
        super().__init__([])

    def organizations_for_account(self, account_id: str) -> list[Organization]:
        raise RuntimeError("the organization listing is unavailable")


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
            records=_StubRecords(),
            isolation=_StubIsolation(),
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

    def test_an_address_naming_another_organization_fails_closed(self) -> None:
        """`FR-042` scenario 3: the address names one organization and the session another.

        This case once asserted the opposite -- that the frame rendered the session's
        organization under the other's address -- and the dispatcher was written to match it.
        `FR-042`'s text is "MUST be compared against the session's active organization and MUST
        fail closed on disagreement", which review on `#373` read correctly. The refusal is the
        uniform one and names neither organization (`FR-051`, `FR-052`).
        """
        response = _shell(
            context=_Context("acct-1", "org-acme"),
            organizations=[
                _organization("org-acme", ORGANIZATION_NAME),
                _organization("org-other", "Someone Else Entirely"),
            ],
        ).get(f"{SHELL_PREFIX}/en/org-other/team")

        assert response.status_code == 404
        assert ORGANIZATION_NAME not in response.text
        assert "Someone Else Entirely" not in response.text

    @pytest.mark.parametrize(
        "name",
        [
            ORGANIZATION_NAME,
            # `Organization.create` restricts the name to no script, so an Arabic organization
            # naming itself in Arabic is an ordinary input rather than an edge case. A fixed
            # `dir="ltr"` reordered exactly this: the digits and the parenthesis are neutral, so
            # they take the paragraph direction the attribute forces rather than the name's.
            "\u0645\u0624\u0633\u0633\u0629 \u0632\u0641\u064a\u0631 (\u0662\u0660\u0662\u0666)",
        ],
    )
    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_name_carries_a_direction_derived_from_itself(
        self, language: str, name: str
    ) -> None:
        """`FR-055`, for both scripts the name may be in rather than the one it usually is.

        The requirement is that the run carry an explicit direction and render in isolation, not
        that the direction be `ltr`: a Latin name inside the Arabic shell needs `ltr`, and an
        Arabic name needs `rtl`, and only the value derives that from the name itself. Asserted on
        the name's own span, because the page carries other `dir` attributes -- a bare search for
        `dir="ltr"` passed with the organization name unmarked entirely.
        """
        html = _shell(
            organizations=[_organization("org-acme", name)]
        ).get(f"{SHELL_PREFIX}/{language}/org-acme/team").text

        assert f'<span id="frame-organization-name" dir="auto">{name}</span>' in html

    def test_the_chooser_does_not_offer_a_link_to_itself(self) -> None:
        """The chooser is where the organization control leads; a control to here does nothing."""
        html = _shell().get(f"{SHELL_PREFIX}/en/").text

        assert SHELL_COPY["en"]["frame_organization_label"] not in html


class TestOnlyBuiltDestinationsAreOffered:
    """`FR-049`: a navigation entry MUST NOT be rendered for a surface with no implementation.

    Team was the only destination until `W1-05` shipped Overview and Data with their links; the
    rule the class asserts is unchanged, and `test_w105_overview_and_data.py` asserts the two new
    links appear only when their reader is wired.
    """

    def test_the_frame_offers_team(self) -> None:
        html = _shell().get(f"{SHELL_PREFIX}/en/org-acme/team").text

        assert f'href="{SHELL_PREFIX}/en/org-acme/team"' in html

    @pytest.mark.parametrize("surface", ["settings", "account", "reports", "metrics", "activity"])
    def test_no_entry_exists_for_an_unimplemented_surface(self, surface: str) -> None:
        """Scenario 20: "Navigation entry for an unimplemented surface | Absent".

        `analyses` is deliberately not in this list. It was a real POST action on the chooser's
        active row before it was a surface (`R8-06`), and since `W1-05` it is a surface with its
        own link; both are implemented capabilities rather than links to a surface that has none.
        """
        for path in (f"{SHELL_PREFIX}/en/", f"{SHELL_PREFIX}/en/org-acme/team"):
            html = _shell().get(path).text

            assert f'href="{SHELL_PREFIX}/en/org-acme/{surface}"' not in html, path
            assert f'href="{SHELL_PREFIX}/en/{surface}"' not in html, path


class TestTheLanguageControlPreservesPosition:
    """`FR-047` plus scenario 11: "Language switch mid-surface | Position preserved"."""

    @pytest.mark.parametrize("language", ["en", "ar"])
    @pytest.mark.parametrize(
        "path",
        ["/", "/org-acme/team", "/org-acme/overview", "/org-acme/data", "/org-acme/analyses"],
    )
    def test_every_surface_the_frame_may_name_offers_the_control(
        self, path: str, language: str
    ) -> None:
        """Two surfaces opt out; nothing else may drift into opting out with them.

        The opt-out is a render-time flag, so the failure mode it introduces is a surface that
        quietly stops offering the switch. Every surface the frame may name a destination for is
        driven here, in both languages, so that drift is a failure rather than a thing nobody
        looked at. `invitation_issued` and `unavailable` are the two that are absent by
        construction, and each has its own case saying why.
        """
        html = _shell().get(f"{SHELL_PREFIX}/{language}{path}").text

        assert _renders_a_language_control(html), path

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
        "path",
        [
            "/",
            "/org-acme/team",
            "/org-acme/overview",
            "/org-acme/data",
            "/org-acme/analyses",
            UNKNOWN_SURFACE,
        ],
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


class TestTheRefusalKeepsItsSurfaceAcrossLanguages:
    """`FR-055` on the surface that absorbs every failure, bounded by `FR-051` and `FR-052`.

    The frame gave `unavailable` a language control and no tail to keep, so it took `_render`'s
    empty default and pointed at `{prefix}/{alternate}`. For an authenticated reader that address
    renders the organization chooser at `200` -- exactly the "returning them to an entry surface"
    `FR-055` names.

    Two repairs were written before this one. Echoing the reader's own address preserves the
    position exactly and is the one thing this surface may not do: the merged cases in
    `test_r802_shell_unavailable_surface.py` assert the body carries neither the organization it
    was asked about nor the object identifier, with no exception for a value the reader supplied,
    and an `href` is body. Rendering no control at all satisfies every rule and strands the reader
    `FR-054` is about -- the one who reaches a refusal in a language they cannot read, on a page
    whose recovery exit is in that language too.

    So the control keeps the *surface* rather than the address, through one constant tail that
    names nothing. Its correctness rests on nothing being implemented under that name, which is
    why the case below is about the constant rather than about any surface that renders it.
    """

    def test_the_canonical_refusal_tail_reaches_the_refusal(self) -> None:
        """The constant resolves to `unavailable` because nothing is implemented under it.

        `FR-046` requires an unknown path to resolve to the shared unavailable surface, so this
        uses that rule as written rather than working around it -- but a link that is correct
        *because* nothing is there stops being correct the day something is. This is what makes
        that day a failing case instead of a silent redirection: implement a surface named
        `unavailable` and this fails, naming the constant that has to move.
        """
        response = _shell().get(f"{SHELL_PREFIX}/en{_UNAVAILABLE_TAIL}")

        assert response.status_code == 404
        assert SHELL_COPY["en"]["recovery_exit"] in response.text

    @pytest.mark.parametrize(
        "tail",
        [
            "/no-such-surface",
            "/org-acme/no-such-surface",
            "/a/b/c/d",
            # `FR-046`: a surface is an exact address. A path that begins with one and carries
            # more is an unknown path, not the surface it begins with (`#373` review).
            "/org-acme/team/extra",
            "/org-acme/overview/extra",
            "/org-acme/data/no-such-object",
            # Two trailing slashes are two empty tails, not the one tolerated one.
            "/org-acme/team//",
            "/org-acme/data//",
        ],
    )
    def test_an_unknown_address_of_any_shape_reaches_the_refusal(self, tail: str) -> None:
        """`FR-046` is about the address being unknown, not about how many segments it has.

        The two-segment case is the one that escaped: `shell_surface` reads the surface name at
        index 2, so `/en/no-such-surface` left it `""` -- the same value the bare `/en` produces --
        and the dispatcher answered with the chooser at `200`. An unknown path rendering an entry
        surface is the one outcome `FR-046` forbids, and testing the extracted surface name could
        not see it because the defect was in which segment got read. So these enumerate address
        *shapes* rather than surface names, and the parametrisation is the point: restore the
        `surface == ""` test alone and the first case fails.
        """
        response = _shell().get(f"{SHELL_PREFIX}/en{tail}")

        assert response.status_code == 404
        assert SHELL_COPY["en"]["recovery_exit"] in response.text

    @pytest.mark.parametrize("language,alternate", [("en", "ar"), ("ar", "en")])
    def test_the_switch_stays_on_a_refusal(self, language: str, alternate: str) -> None:
        """Followed rather than asserted as a string.

        A link that merely *looks* preserved and lands on an entry surface is the whole defect, so
        the case walks it: the reader must still be on a refusal, in the language they chose.
        """
        client = _shell()
        control = _language_control(client.get(f"{SHELL_PREFIX}/{language}{UNKNOWN_SURFACE}").text)
        switched = client.get(control)

        assert switched.status_code == 404
        assert SHELL_COPY[alternate]["recovery_exit"] in switched.text
        assert ORGANIZATION_NAME not in switched.text

    def test_no_refusal_names_the_address_that_produced_it(self) -> None:
        """`FR-051` and `FR-052`, restated here as the reason the tail is a constant.

        The merged suite asserts this against `ScopeAccessDenied`; this asserts it against the
        frame, so a later revision that gives the control the reader's own tail fails in the suite
        that introduced the control rather than only in the one that predates it.
        """
        response = _shell().get(f"{SHELL_PREFIX}/en/a-very-distinctive-org-slug/no-such-surface")

        assert response.status_code == 404
        assert "a-very-distinctive-org-slug" not in response.text

    def test_every_collapsed_cause_answers_the_same_way(self) -> None:
        """`FR-050`: the causes must not be told apart by navigation state, and a link is some.

        Three causes reaching `unavailable` by different routes -- no session at all, a resolver
        that refuses, and a surface the shell does not implement -- at one address. Byte-identical
        bodies rather than identical links, so navigation state cannot drift from the rest.
        """
        address = f"{SHELL_PREFIX}/en{UNKNOWN_SURFACE}"

        no_session = _shell()
        no_session.cookies.clear()

        refused = FastAPI()
        add_shell_routes(
            refused,
            services=ShellServices(
                resolver=_RefusingResolver(),
                organizations=_StubOrganizations(
                    [_organization("org-acme", ORGANIZATION_NAME)]
                ),
                invitations=None,
            ),
            clock=lambda: NOW,
        )
        refusing_client = TestClient(refused)
        refusing_client.cookies.set(SESSION_COOKIE, "a-session-token")

        bodies = {
            client.get(address).text for client in (no_session, refusing_client, _shell())
        }

        assert len(bodies) == 1, "the collapsed causes are distinguishable"


class TestTheAssetRefusalOffersNoSwitch:
    """The one refusal rendered without resolving the actor, and the hole that left.

    `shell_asset` answers an unlisted name with `unavailable` before any session is read, so the
    canonical tail is not a refusal for every reader who could reach it. An authenticated account
    in no organization is the case: `FR-048` puts it on the next-step surface at `200` before the
    dispatcher reads a surface name at all, so that reader followed the control off a `404` and
    onto a next step -- the same "different surface" the control was fixed to stop doing.

    The dispatcher is right and is not what changed. `FR-048` requires that account to reach the
    next step and be denied every organization-scoped surface, so a canonical tail that outranked
    it would be the defect. An asset name is not a surface a reader is on, so that refusal offers
    no control instead.
    """

    def test_an_unlisted_asset_renders_no_control(self) -> None:
        response = _shell(organizations=[]).get(f"{SHELL_ASSETS}/not-allowed.css")

        assert response.status_code == 404
        assert not _renders_a_language_control(response.text)

    def test_the_dispatcher_still_answers_the_next_step_first(self) -> None:
        """The behaviour the asset refusal defers to, asserted so it is a decision not an accident.

        If this ever answered `404`, the asset refusal could carry the control again -- and the
        reason it cannot would have gone away silently.
        """
        response = _shell(organizations=[]).get(f"{SHELL_PREFIX}/en{_UNAVAILABLE_TAIL}")

        assert response.status_code == 200
        assert SHELL_COPY["en"]["recovery_exit"] not in response.text

    def test_a_member_following_the_tail_still_reaches_the_refusal(self) -> None:
        """The fix must not have cost the readers the control was restored for."""
        response = _shell().get(f"{SHELL_PREFIX}/ar{_UNAVAILABLE_TAIL}")

        assert response.status_code == 404
        assert SHELL_COPY["ar"]["recovery_exit"] in response.text


class TestTheBrandIsOperableByItsVisibleName:
    """WCAG 2.5.3 "Label in Name", which an `aria-label` on a wordmark quietly breaks.

    The brand read `aria-label="{{ copy.frame_home_label }}"` over a visible `KHEPRI`. An
    `aria-label` *replaces* the descendant text rather than adding to it, so on the Arabic shell
    the accessible name was `الصفحة الرئيسية لخِبري` while the only thing on the control was the
    Latin wordmark: a speech-input reader who said what they could see could not operate it.

    The wordmark still needs words -- a picture of a name is not a name -- so they follow it now
    instead of standing in for it, through the pair the organization control already uses.
    """

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_accessible_name_begins_with_the_visible_wordmark(self, language: str) -> None:
        """Source order is the composition order, so the visible text comes first."""
        html = _shell().get(f"{SHELL_PREFIX}/{language}/org-acme/team").text
        brand = html[html.index('class="brand"') :][:400]

        assert 'aria-labelledby="frame-brand-name frame-brand-purpose"' in brand
        assert brand.index('id="frame-brand-name"') < brand.index('id="frame-brand-purpose"')
        assert "KHEPRI" in brand

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_purpose_is_still_carried_and_still_localized(self, language: str) -> None:
        """Fixing the name must not cost the words the wordmark cannot say."""
        html = _shell().get(f"{SHELL_PREFIX}/{language}/org-acme/team").text

        assert SHELL_COPY[language]["frame_home_label"] in html

    def test_no_aria_label_stands_in_for_visible_text_in_the_frame(self) -> None:
        """The pattern, not the instance: `aria-label` on an element with its own text is the bug.

        `frame-surfaces` keeps its `aria-label` and is not this: the label names the landmark, not
        a control, and a `nav` has no text of its own for it to replace.
        """
        html = _shell().get(f"{SHELL_PREFIX}/ar/org-acme/team").text

        assert 'aria-label="KHEPRI"' not in html
        assert f'aria-label="{SHELL_COPY["ar"]["frame_home_label"]}"' not in html


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


def _renders_a_language_control(html: str) -> bool:
    """Whether the control is on the page at all, for the one surface that must not carry it."""
    return _LANGUAGE_CONTROL.search(html) is not None


#: The organization half of the frame: the control that names it and the `Team` entry beside it.
#: Captured whole so that two surfaces resolving it through one helper can be compared as markup
#: rather than as a handful of substrings that could each pass for a different reason.
_ORGANIZATION_FRAME = re.compile(
    r'<a class="frame-organization".*?</nav>', re.DOTALL
)


def _organization_frame(html: str) -> str:
    match = _ORGANIZATION_FRAME.search(html)
    assert match is not None, "the frame names no organization"
    return match.group(0)


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

    @pytest.mark.parametrize("language", ["en", "ar"])
    @pytest.mark.parametrize("step", ["upload", "review", "processing", "report", "expired"])
    def test_no_shell_owned_asset_reaches_the_journey(self, step: str, language: str) -> None:
        """No `/beta` page may reference anything the shell serves. `RRA-010` Verification.

        `shell.css` and `shell-components.css` sit in the journey's asset directory and are the
        shell's: `shell.html.j2` is their only linking template, and the exclusion is about the beta
        surface rather than about a directory.

        **The asset set is read from `shell_api._ASSETS` rather than spelled out here**, because
        that dict *is* the definition of a shell-owned asset -- the allowlist the shell serves by
        exact name. An earlier revision named `shell-components.css` alone, so `shell.css` could
        have been linked from a journey template with this guard still green, and `shell.css` is
        the more consequential leak of the two: it declares the tokens, so a journey rule could
        then resolve a shell-declared custom property. `RRA-010` excludes exactly that dependency
        and required this widening before any slice relied on the boundary.

        Reading the allowlist also makes the invariant outlive this slice. A future shell-owned
        asset is covered the moment it is served, with no edit here -- which a hardcoded list
        could not do, and a list that drifts is how the single-filename version came to
        under-cover.

        **Markup alone is not the boundary.** Two ways a shell asset could load while the HTML
        named only journey-owned files: the response could be an error page that mentions no asset
        at all, and the journey's own stylesheet could pull one in transitively. So the page is
        asserted to have rendered, and the served stylesheet is scanned too -- with `@import`
        banned outright rather than its targets enumerated, since a name-scan loses to a relative
        path and `shell.css`'s own suite already holds itself to the same rule.

        A stylesheet injected at runtime by journey JavaScript would need a browser-level
        assertion, which this in-process frame test is the wrong place for; no journey script
        constructs a stylesheet link today.
        """
        from khepri.runtime.shell_api import _ASSETS
        from tests.test_rra_journey_api import client

        assert _ASSETS, "the shell serves no assets; this guard would assert nothing"

        response = client().get(f"/beta/{language}/{step}")

        # An error page names no asset, so the scan below would pass having proved nothing.
        assert response.status_code == 200, f"/beta/{language}/{step} -> {response.status_code}"
        html = response.text

        stylesheet = (
            files("khepri.rra.journey")
            .joinpath("assets", "journey.css")
            .read_text(encoding="utf-8")
        )
        assert "@import" not in stylesheet, "an @import can pull in an asset the markup never names"

        for asset in _ASSETS:
            assert asset not in html, f"{asset} reached /beta/{language}/{step}"
            assert asset not in stylesheet, f"journey.css references {asset}"


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

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_this_surface_renders_no_language_control(self, language: str) -> None:
        """The one surface where the control cannot keep its promise, so it is not offered.

        `invitation_issued` is a `POST` result with no address of its own. No destination
        re-requests *this page* in the other language, and every destination the control could
        name discards the token above -- `issue` returns it once and the store keeps only a salted
        verifier, so an owner who switched language could not recover what they were expected to
        share. A revision of this slice pointed the control at the team surface, which fixed the
        scope it lost and left the loss that matters intact.

        `FR-054`'s parity survives: the surface renders in both languages, and this case runs in
        both, so the actions are equivalent in each. `FR-055` constrains a switch that exists.
        """
        assert not _renders_a_language_control(self._issued(language))

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_token_and_its_warning_are_still_what_the_surface_offers(
        self, language: str
    ) -> None:
        """Absence is only correct if the reason for it is still on the page.

        Removing the control would also "pass" if this surface had stopped rendering the secret it
        exists to show, so the reason is asserted next to the absence.
        """
        issued = self._issued(language)

        assert "inv_a-one-time-token" in issued
        assert SHELL_COPY[language]["invitation_token_once"] in issued

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
        start = issued.index('class="frame-surfaces"')
        nav = issued[start : issued.index("</nav>", start)]

        assert f'href="{SHELL_PREFIX}/en/org-acme/team"' in nav

    def test_the_frame_is_resolved_before_the_token_is_issued(self) -> None:
        """The frame read is fallible, and it must not be fallible *after* the write.

        `issue` commits the invitation and returns the only plaintext copy of its token; the store
        keeps a salted verifier and nothing else. A listing read that raised after it would answer
        500 to an owner whose invitation exists and whose token is unrecoverable, and whose retry
        would issue a second one. Ordering is the whole fix, so ordering is what this pins: with
        the read failing, the gateway is never reached at all.
        """
        invitations = _StubInvitations()
        app = FastAPI()
        add_shell_routes(
            app,
            services=ShellServices(
                resolver=_StubResolver(_Context("acct-1", "org-acme")),
                organizations=_UnreadableOrganizations(),
                invitations=invitations,
            ),
            clock=lambda: NOW,
        )
        client = TestClient(app)
        client.cookies.set(SESSION_COOKIE, "a-session-token")

        with pytest.raises(RuntimeError):
            client.post(
                f"{SHELL_PREFIX}/en/org-acme/team/invitations",
                data={"email": "invitee@example.test", "role": "member"},
            )

        assert invitations.issued == [], "an invitation was committed for a response that failed"

    def test_the_team_surface_and_this_one_agree(self) -> None:
        """One helper resolves both, so the organization half cannot differ between them.

        Asserted against the team surface rather than against a literal: a frame that changed on
        both surfaces together is a change, and a frame that changed on one is the defect. The
        language control is deliberately not compared -- it is the one element these two surfaces
        differ on, and the case above is what pins that difference.
        """
        team = _shell().get(f"{SHELL_PREFIX}/en/org-acme/team").text

        assert _organization_frame(self._issued("en")) == _organization_frame(team)

