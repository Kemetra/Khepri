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

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from importlib.resources import files

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import Error, sync_playwright

from khepri.rca.errors import ScopeAccessDenied
from khepri.rca.organizations import Organization, OrganizationMember
from khepri.rca.semantic_queries.ports import KIND_ADMITTED as VIEW_ADMITTED
from khepri.rca.semantic_queries.ports import ViewOutcome, ViewProjection
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rca.workspace.comparisons import (
    KIND_ADMITTED,
    ComparisonOutcome,
    ComparisonSurfaces,
)
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
    "compare": "/org-acme/analyses/compare/ver-a/ver-b",
    # `D1-04`. The run is a path segment because `FR-166` makes the period a source selector --
    # choosing a completed run -- rather than a view filter.
    "decision": "/org-acme/decisions/run-a",
}

#: Templates that render inside another and are never a surface of their own.
#:
#: `D1-08`'s two partials carry the decision surface's figure markup and are
#: included by both `decision.html.j2` and `decision_print.html.j2`, which is what
#: makes a print-only re-total inexpressible (`FR-159`). Neither is addressable,
#: so neither is a surface the browser cases can visit.
_LAYOUT_TEMPLATES = {
    "shell.html.j2",
    "_decision_cards.html.j2",
    "_decision_sections.html.j2",
}

#: Reachable only by POST, so the GET-driven browser cases cannot visit it.
_POST_ONLY_TEMPLATES = {"invitation_issued.html.j2"}

#: Rendered for paper, so the viewport and shell-CSS measurement below does not
#: apply: `decision_print.html.j2` deliberately does not extend `shell.html.j2`
#: and links none of the three stylesheets the browser cases inject. Measuring it
#: would report every target as too small in an unstyled document -- the exact
#: false finding this module's docstring records from before the component layer
#: existed. Its figures are measured through `decision`, whose partials it shares.
_PRINT_TEMPLATES = {"decision_print.html.j2"}


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


def _admitted_source() -> AdmittedSource:
    return AdmittedSource(
        plaintext_digest="d" * 64,
        ciphertext_digest="d" * 64,
        size_bytes=4096,
        media_type="text/csv",
        manifest_digest="d" * 64,
        mapping_version="mapping-v-alpha",
        admission_outcome="admitted",
    )


def _dataset(version_id: str, when: datetime) -> DatasetVersion:
    return DatasetVersion._from_storage(
        version_id=version_id,
        owner_id="org-acme",
        source=_admitted_source(),
        lifecycle=VersionLifecycle(created_at=when, sealed_at=when),
    )


def _completed_run(run_id: str, version_id: str, when: datetime) -> AnalysisRun:
    return AnalysisRun._from_storage(
        subject=RunSubject(run_id=run_id, owner_id="org-acme", version_id=version_id),
        outcome=RunOutcome(
            state=RUN_COMPLETED,
            package_digest="d" * 64,
            package_version="package-v-alpha",
            formula_version="formula-v-alpha",
            completed_at=when,
        ),
        started_at=when,
    )


def _earlier_run() -> AnalysisRun:
    when = NOW - timedelta(days=1)
    return AnalysisRun._from_storage(
        subject=RunSubject(run_id="run-b", owner_id="org-acme", version_id="ver-a"),
        outcome=RunOutcome(
            state=RUN_COMPLETED,
            package_digest="d" * 64,
            package_version="package-v-earlier",
            formula_version="formula-v-earlier",
            completed_at=when,
        ),
        started_at=when,
    )


def _bindings_for(*run_ids: str) -> tuple[ArtifactBinding, ...]:
    return tuple(
        ArtifactBinding._from_storage(
            run_id=run_id,
            owner_id="org-acme",
            artifact=PublishedArtifact(surface=kind, artifact_digest="d" * 64),
            published_at=NOW,
        )
        for run_id in run_ids
        for kind in REQUIRED_ARTIFACT_KINDS
    )


class _StubRecords:
    """Two admitted versions, each with a completed analysis, so Analyses can offer Compare
    and both workspace surfaces render rows rather than their empty states."""

    def history_for_scope(self, owner_id: str) -> WorkspaceHistory:
        del owner_id
        other_at = NOW - timedelta(hours=1)
        # `W1-08`: `run-b` is an earlier completed run under other governed versions, so
        # detail renders the Methodology Change Notice and the matrix measures it.
        return WorkspaceHistory(
            versions=(_dataset("ver-a", NOW), _dataset("ver-b", other_at)),
            runs=(
                _completed_run("run-a", "ver-a", NOW),
                _completed_run("run-c", "ver-b", other_at),
                _earlier_run(),
            ),
            bindings=_bindings_for("run-a", "run-b", "run-c"),
            tombstones=(),
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

    def for_runs(self, owner_id: str, runs: tuple) -> dict:
        return {run.run_id: self.for_run(owner_id, run, None) for run in runs}


class _StubBridge:
    def open(self, **kwargs: object) -> object:  # pragma: no cover
        raise AssertionError("the browser cases drive GETs only")

    def resume(self, **kwargs: object) -> object:  # pragma: no cover
        raise AssertionError("the browser cases drive GETs only")


class _StubComparisons:
    def request(self, request: object, *, now: object) -> ComparisonOutcome:
        return ComparisonOutcome(
            kind=KIND_ADMITTED,
            surfaces=ComparisonSurfaces(
                claims={},
                html={"en": "<p>ok</p>", "ar": "<p>حسنا</p>"},
                pdf={"en": b"%PDF", "ar": b"%PDF"},
                excel=b"xlsx",
                subject_run_id="run-a",
                # `run-c` is `ver-b`'s run; `run-b` belongs to `ver-a` (review on `#411`).
                baseline_run_id="run-c",
            ),
        )


class _StubDecisions:
    """`D1-04`. One admitted overview and one governed availability, for any request.

    A stub at the `SemanticQueryActions` seam rather than a live one, because what these cases
    measure is the rendered surface: direction, structure, overflow and target size. The
    selection behind it is `test_d104_breakdowns_and_limits`' subject.
    """

    def request(self, asked: object) -> ViewOutcome:
        view = asked.view.view_id  # type: ignore[attr-defined]
        rows = (
            (("revenue", "available", None, ()),)
            if view == "MetricAvailabilityView"
            else (("revenue", "700.00", "complete", ()),)
        )
        fields = (
            ("metric", "availability", "reason", "versions")
            if view == "MetricAvailabilityView"
            else ("metric", "value", "population", "versions")
        )
        return ViewOutcome(
            kind=VIEW_ADMITTED,
            projection=ViewProjection(
                view_id=view,
                view_version=asked.view.view_version,  # type: ignore[attr-defined]
                fields=fields,
                rows=rows,
            ),
        )


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
            comparisons=_StubComparisons(),
            decisions=_StubDecisions(),
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
    assert templates == (
        measured | _LAYOUT_TEMPLATES | _POST_ONLY_TEMPLATES | _PRINT_TEMPLATES
    )


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
            # Every interactive control the target-size requirement governs, not only the
            # ones the shell happened to render before Compare added selects (`#411`).
            controls = "button:visible, a:visible, select:visible, input:visible"
            for locator in page.locator(controls).all():
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


def _shell_component_css() -> str:
    """The shell's component rules, with comments removed.

    Comment-stripping is load-bearing rather than hygiene: a rule inside a `/* ... */`
    block is not a live mechanism, and a count that included one would report a defect
    that does not exist. A guard that cries wolf is a guard the next slice narrows.
    """
    text = (
        files("khepri.rra.journey")
        .joinpath("assets", "shell-components.css")
        .read_text(encoding="utf-8")
    )
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def _selectors(css: str) -> list[str]:
    return [selector.strip() for selector in re.findall(r"([^{}]+)\{", css)]


def test_the_shell_declares_exactly_one_skip_link_mechanism() -> None:
    """`RCA-010` §Scope, master specification §19 slice 2b.

    The existing test proves a skip link is *reachable*. It cannot see a **second**
    mechanism added beside the first, which is the drift slice 2b exists to close:
    `journey.css` and `shell-components.css` each defined one, and nothing counted
    either. The count is the assertion; presence is already covered above.
    """
    css = _shell_component_css()
    selectors = _selectors(css)

    assert selectors, "no rules found in shell-components.css, so this test proves nothing"
    base = [selector for selector in selectors if selector == ".skip-link"]
    assert len(base) == 1, f"expected one .skip-link mechanism, found {len(base)}"


def test_the_shell_component_layer_declares_no_raw_type_size() -> None:
    """`RCA-010` §Scope, master specification §G.1.

    Scans `font-size` **and** the `font` shorthand. A scan worded for `font-size`
    alone passes over a size hidden in the shorthand -- the defect the allocation
    plan carried in its first draft, and the reason `journey.css` has five such
    sizes on the companion plan's side. `font: inherit` carries no size.
    """
    css = _shell_component_css()
    assert css.strip(), "shell-components.css is empty, so this test proves nothing"

    offenders = [
        match.group(0).strip()
        for match in re.finditer(r"\bfont(?:-size)?\s*:\s*([^;}]+)", css)
        if match.group(1).strip() != "inherit"
        and re.search(r"\d*\.?\d+(rem|px|em)\b", match.group(1))
    ]
    assert offenders == [], f"raw type sizes must use the token scale: {offenders}"


def test_the_shell_and_journey_type_scales_stay_separate() -> None:
    """`RCA-010` `FR-201`: a shell presentation value is the shell's.

    Asserted in **both** directions, because a leak either way breaks the boundary
    both allocation plans rely on and neither previously measured. The two scales are
    a deliberate separation, not a duplication: `journey.css` records that its two
    small tokens are "a separate decision, not a rounding of the same one".
    """
    journey_assets = files("khepri.rra.journey").joinpath("assets")
    shell_tokens = journey_assets.joinpath("shell.css").read_text(encoding="utf-8")
    shell_components = journey_assets.joinpath("shell-components.css").read_text(
        encoding="utf-8"
    )
    journey = journey_assets.joinpath("journey.css").read_text(encoding="utf-8")

    for name, text in (
        ("shell.css", shell_tokens),
        ("shell-components.css", shell_components),
        ("journey.css", journey),
    ):
        assert text.strip(), f"{name} is empty, so this test proves nothing"

    assert "--journey-" not in shell_tokens, "shell.css names a journey property"
    assert "--journey-" not in shell_components, (
        "shell-components.css names a journey property"
    )
    declared = re.findall(r"(--text-[a-z0-9-]+)\s*:", journey)
    assert declared == [], f"journey.css declares shell type tokens: {declared}"


def test_the_shell_component_layer_draws_no_artwork() -> None:
    """`RCA-010` `FR-206`: the master specification §7 asset policy, unrelaxed.

    The shell has no admitted programmatic-drawing exception -- unlike the `RRA`
    side, where a data-driven chart is the one expected drawing -- so this scan needs
    no carve-out. Scoping it to the stylesheet also keeps it clear of the two
    `aria-hidden` change separators in `analysis.html.j2`, which are template content
    and `FR-194`-compliant.
    """
    css = _shell_component_css()
    assert css.strip(), "shell-components.css is empty, so this test proves nothing"

    forbidden = {
        "@import": "@import" in css,
        "external url()": bool(re.search(r"url\(\s*['\"]?https?://", css)),
        "background-image": "background-image" in css,
        "content artwork": bool(re.search(r"content\s*:\s*['\"][^'\"]*[^\x00-\x7F]", css)),
        "non-ascii glyph": bool(re.search(r"[←-➿\U0001f300-\U0001faff]", css)),
    }
    found = sorted(name for name, present in forbidden.items() if present)
    assert found == [], f"forbidden asset constructs in shell-components.css: {found}"
