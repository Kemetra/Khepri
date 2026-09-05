"""Responsive, accessible, bilingual quality evidence for the shell (`R8-07`).

Authorized by `RCA-002`. Extends `test_rra_journey_browser.py`'s shape to the four shell surfaces
`R8-02` through `R8-06` delivered, and adds the two obligations the journey does not carry.

**`FR-055` is the one the journey never had to satisfy.** A Latin-script run inside Arabic prose
renders with its parts visually reordered unless it carries an explicit direction, and the shell is
the first surface to show email addresses -- the most common instance of that hazard in the
product. The journey shows none, so no existing test covers it.

**The parametrisation is the coverage claim.** Four surfaces, two languages, two viewports. A test
that walked only the surfaces it happened to remember would grow stale as surfaces are added, so
`SHELL_SURFACES` is asserted against the shell's own template directory: a template added without a
case here fails rather than going unmeasured.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from importlib.resources import files

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import Error, sync_playwright

from khepri.rca.errors import ScopeAccessDenied
from khepri.rca.organizations import Organization, OrganizationMember
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rca.workspace.contracts import (
    RUN_COMPLETED,
    AdmittedSource,
    AnalysisRun,
    ArtifactBinding,
    DatasetVersion,
    PublishedArtifact,
    RunOutcome,
    RunSubject,
    VersionLifecycle,
)
from khepri.rca.workspace.store import WorkspaceHistory
from khepri.rca.workspace.tombstones import SectionStates
from khepri.rra.bundle import ORDERED_SECTIONS
from khepri.rra.report_artifacts import REQUIRED_ARTIFACT_KINDS
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes
from khepri.runtime.shell_provenance import Provenance

NOW = datetime(2026, 8, 22, tzinfo=UTC)

#: Every shell surface a person can reach, by the path that renders it.
#:
#: `invitation_issued` is absent deliberately: it is reachable only by POST, and the browser cases
#: below drive GETs. `test_every_shell_template_is_measured` is what keeps that an explicit
#: exemption rather than a gap.
SHELL_SURFACES = {
    "unavailable": "/no-such-surface",
    "no_membership": "/",
    "switcher": "/",
    "team": "/org-acme/team",
    "overview": "/org-acme/overview",
    "data": "/org-acme/data",
    "analyses": "/org-acme/analyses",
    "analysis": "/org-acme/analyses/run-a",
}

#: Templates that render inside another and are never a surface of their own.
_LAYOUT_TEMPLATES = {"shell.html.j2"}

#: Reachable only by POST, so the GET-driven browser cases cannot visit it.
_POST_ONLY_TEMPLATES = {"invitation_issued.html.j2"}


@dataclass
class _Context:
    account_id: str
    organization_id: str | None
    role: str | None = "owner"

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"


class _StubResolver:
    def __init__(
        self, context: _Context | None = None, raises: Exception | None = None
    ) -> None:
        self._context = context or _Context("acct-1", "org-acme")
        self._raises = raises

    def for_request(
        self, token: str, *, organization_id: str | None = None, now: object = None
    ) -> _Context:
        if self._raises is not None:
            raise self._raises
        return self._context

    def require_owner(
        self, token: str, *, organization_id: str, now: object = None
    ) -> _Context:
        if self._raises is not None:
            raise self._raises
        return self._context


class _StubOrganizations:
    def __init__(self, *, memberships: bool = True) -> None:
        self._memberships = memberships

    def organizations_for_account(self, account_id: str) -> list[Organization]:
        if not self._memberships:
            return []
        return [
            Organization._from_storage(
                organization_id="org-acme", name="Acme", created_at=NOW
            )
        ]

    def memberships_for_organization(self, organization_id: str) -> list[OrganizationMember]:
        return [
            OrganizationMember(
                account_id="acct-1",
                email="someone@example.test",
                role="owner",
                disabled=False,
            ),
            OrganizationMember(
                account_id="acct-2",
                email="gone@example.test",
                role="member",
                disabled=True,
            ),
        ]


class _StubInvitations:
    def invitations_for_organization(self, organization_id: str, *, now: object = None):
        return ()

    def issue(self, offer: object, *, expires_at: object, now: object) -> str:  # pragma: no cover
        raise AssertionError("the browser cases drive GETs only")

    def revoke(self, *args: object, **kwargs: object) -> None:  # pragma: no cover
        raise AssertionError("the browser cases drive GETs only")


class _StubIsolation:
    def resolve_scope(self, account_id: str, organization_id: str) -> str:
        return f"scope-{organization_id}"


class _StubRecords:
    """One admitted data version with one completed analysis, so both new surfaces render rows
    rather than their empty states."""

    def history_for_scope(self, owner_id: str) -> WorkspaceHistory:
        version = DatasetVersion._from_storage(
            version_id="ver-a",
            owner_id="org-acme",
            source=AdmittedSource(
                plaintext_digest="d" * 64,
                ciphertext_digest="d" * 64,
                size_bytes=4096,
                media_type="text/csv",
                manifest_digest="d" * 64,
                mapping_version="mapping-v-alpha",
                admission_outcome="admitted",
            ),
            lifecycle=VersionLifecycle(created_at=NOW, sealed_at=NOW),
        )
        run = AnalysisRun._from_storage(
            subject=RunSubject(run_id="run-a", owner_id="org-acme", version_id="ver-a"),
            outcome=RunOutcome(
                state=RUN_COMPLETED,
                package_digest="d" * 64,
                package_version="package-v-alpha",
                formula_version="formula-v-alpha",
                completed_at=NOW,
            ),
            started_at=NOW,
        )
        bindings = tuple(
            ArtifactBinding._from_storage(
                run_id="run-a",
                owner_id="org-acme",
                artifact=PublishedArtifact(surface=kind, artifact_digest="d" * 64),
                published_at=NOW,
            )
            for kind in REQUIRED_ARTIFACT_KINDS
        )
        # `W1-08`: an earlier completed run under other governed versions, so detail renders the
        # Methodology Change Notice and the matrix measures it.
        earlier = AnalysisRun._from_storage(
            subject=RunSubject(run_id="run-b", owner_id="org-acme", version_id="ver-a"),
            outcome=RunOutcome(
                state=RUN_COMPLETED,
                package_digest="d" * 64,
                package_version="package-v-earlier",
                formula_version="formula-v-earlier",
                completed_at=NOW - timedelta(days=1),
            ),
            started_at=NOW - timedelta(days=1),
        )
        return WorkspaceHistory(
            versions=(version,), runs=(run, earlier), bindings=bindings, tombstones=()
        )


class _StubProvenance:
    """A Passport for `run-a`: the attested period, the admitted scale, and a quality summary in
    which every section answered, so detail renders every region it has."""

    def for_run(self, owner_id: str, run: object, version: object) -> Provenance:
        return Provenance(
            session_id="ses-a",
            job_id="job-a",
            covered_start=date(2026, 1, 5),
            covered_end=date(2026, 1, 7),
            timezone="Africa/Cairo",
            aggregate_scope="all-stores",
            attested_by="Operator",
            row_count=4,
            sections=SectionStates(**dict.fromkeys(ORDERED_SECTIONS, "answered")),
            reachable=True,
        )


class _StubBridge:
    def open(self, **kwargs: object) -> object:  # pragma: no cover
        raise AssertionError("the browser cases drive GETs only")

    def resume(self, **kwargs: object) -> object:  # pragma: no cover
        raise AssertionError("the browser cases drive GETs only")


def _client(surface: str) -> TestClient:
    """One app per surface, configured so that surface is what renders."""
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=_StubResolver(
                raises=ScopeAccessDenied() if surface == "unavailable" else None
            ),
            organizations=_StubOrganizations(memberships=surface != "no_membership"),
            invitations=_StubInvitations(),
            records=_StubRecords(),
            isolation=_StubIsolation(),
            provenance=_StubProvenance(),
            bridge=_StubBridge(),
        ),
        clock=lambda: NOW,
    )
    client = TestClient(app, base_url="https://testserver")
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


def _html(surface: str, language: str) -> str:
    path = SHELL_SURFACES[surface]
    return _client(surface).get(f"{SHELL_PREFIX}/{language}{path}").text


def test_every_shell_template_is_measured() -> None:
    """A template added without a browser case fails here rather than going unmeasured.

    The emptiness assertion matters for the usual reason: a renamed template directory would make
    a scan of it vacuously satisfy every claim.
    """
    templates = {
        entry.name
        for entry in files("khepri.runtime").joinpath("shell_templates").iterdir()
        if entry.name.endswith(".html.j2")
    }

    assert templates, "no shell templates found, so this test proves nothing"
    measured = {f"{surface}.html.j2" for surface in SHELL_SURFACES}
    assert templates == measured | _LAYOUT_TEMPLATES | _POST_ONLY_TEMPLATES


@pytest.mark.browser
@pytest.mark.parametrize("viewport", [(1180, 900), (390, 844)])
@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_shell_surfaces_are_operable_at_every_viewport(
    surface: str, language: str, viewport: tuple[int, int]
) -> None:
    """`FR-053`, `FR-054`, `FR-056`: direction, structure, no overflow, operable targets."""
    # Both sheets, in the order the page links them: the tokens declare the palette and the
    # component layer consumes it. Injecting only the tokens would measure an unstyled document
    # and report every target as too small -- which is exactly what this test did before the
    # component layer existed, and what it correctly found.
    journey_assets = files("khepri.rra.journey").joinpath("assets")
    css = "\n".join(
        (
            journey_assets.joinpath("shell.css").read_text(encoding="utf-8"),
            journey_assets.joinpath("shell-components.css").read_text(encoding="utf-8"),
            # `W1-05`'s rules, from the runtime package: `RCA-005` keeps them out of the
            # journey's tree, and this measurement must load what the page links.
            files("khepri.runtime")
            .joinpath("shell_assets", "workspace.css")
            .read_text(encoding="utf-8"),
        )
    )
    html = _html(surface, language)
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Error as error:
            pytest.skip(f"Pinned Chromium is unavailable: {error}")
        try:
            page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
            page.emulate_media(reduced_motion="reduce")
            page.set_content(html, wait_until="domcontentloaded")
            page.add_style_tag(content=css)

            assert page.locator("html").get_attribute("dir") == (
                "rtl" if language == "ar" else "ltr"
            )
            assert page.locator("h1").count() == 1
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            for locator in page.locator("button:visible, a:visible").all():
                box = locator.bounding_box()
                assert box is not None and box["height"] >= 44
        finally:
            browser.close()


@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_every_surface_renders_in_both_languages(surface: str) -> None:
    """`FR-053`: equivalent state in both, and neither falls back to the other's text."""
    english = _html(surface, "en")
    arabic = _html(surface, "ar")

    assert english != arabic, "the two languages rendered identically, so one is not translated"
    assert 'lang="en"' in english
    assert 'lang="ar"' in arabic
    assert 'dir="rtl"' in arabic


def test_a_latin_run_inside_arabic_prose_carries_its_direction() -> None:
    """`FR-055`, and the case the journey never had to answer.

    An email address is a Latin run; unmarked inside RTL prose the bidirectional algorithm reorders
    its parts visually. The team surface is the first place the product shows one.
    """
    arabic = _html("team", "ar")

    assert 'dir="ltr">someone@example.test' in arabic


def test_the_skip_link_is_first_in_the_document() -> None:
    """A skip link that is not the first focusable element is a skip link nobody reaches."""
    for surface in SHELL_SURFACES:
        html = _html(surface, "en")
        body = html.split("<body", 1)[1]
        assert body.index("skip-link") < body.index("<main")
