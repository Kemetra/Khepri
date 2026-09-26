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
        # Two, so the chooser renders the switch (`#594`) beside the active organization's link,
        # and every browser case measures the button that switch is.
        return [
            Organization._from_storage(
                organization_id="org-acme", name="Acme", created_at=NOW
            ),
            Organization._from_storage(
                organization_id="org-globex", name="Globex", created_at=NOW
            ),
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


@dataclass(frozen=True)
class _PendingInvitation:
    """What `team.html.j2` reads off an invitation, and nothing more.

    A real `Invitation` is `Sealed` and must be minted through its own door; the
    template needs three attributes, so a stand-in keeps this fixture from reaching
    into another family's constructor. One pending invitation is what makes
    `.invitation-role` render, which `U1` slice 2b retokenized and must measure.
    """

    invitation_id: str = "inv-1"
    target_identity: str = "invited@example.test"
    intended_role: str = "member"


class _StubInvitations:
    def invitations_for_organization(self, organization_id: str, *, now: object = None):
        return (_PendingInvitation(),)

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
            else (("revenue", "700.00", None, ()),)
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
            # `#594`: with a switcher the chooser's other rows are switch buttons. The route is
            # never called here; only its presence changes what the chooser renders.
            switcher=object(),
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


#: `legal_page.html.j2` extends this, so it is never a surface of its own.
_LEGAL_LAYOUT_TEMPLATES = {"legal.html.j2"}


def test_every_legal_template_is_measured() -> None:
    """`legal_templates/` is in `RCA-010` §Scope; the scan above reaches `shell_templates/` only.

    Two-sided drift detection, the same shape as the assertion above: the files on disk are
    compared against the measured set union the layouts, so forgetting either side fails. It is
    **not independent** -- `tests/` is in the same §Scope, so a slice can edit both sides. It is
    stronger than a tautology and weaker than independence, and is labelled as exactly that.

    One template serves six pages, so this asserts template extent, not page extent. Page extent
    is `test_the_legal_roster_matches_the_served_inventory` in `test_r811_shell_accessibility.py`.
    """
    templates = {
        entry.name
        for entry in files("khepri.runtime").joinpath("legal_templates").iterdir()
        if entry.name.endswith(".html.j2")
    }

    assert templates, "no legal templates found, so this test proves nothing"
    assert templates == {"legal_page.html.j2"} | _LEGAL_LAYOUT_TEMPLATES


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


#: Type values that name no size, so they carry no raw literal to tokenize.
_INHERITED_TYPE_VALUES = frozenset({"inherit", "initial", "unset", "revert"})

#: A `font` shorthand may carry a numeric weight and line-height that are not sizes:
#: `font: 700 var(--text-sm)/1 monospace` is fully tokenized. Strip those parts before
#: looking for a raw size, so the scan flags the size and not the weight.
_NON_SIZE_NUMERICS = re.compile(
    r"(?:\b[1-9]00\b|\bnormal\b|\bbold\b|/\s*[\d.]+)", flags=re.IGNORECASE
)


def _without_comments(text: str, name: str) -> str:
    """CSS with comments removed, refusing the one input that disarms the removal.

    A `/*` or `*/` inside a CSS string literal turns the non-greedy `/\\*.*?\\*/` into a
    weapon: with `content: "/*"` above a rule and `content: "*/"` below it, the real
    rule between them is deleted before any scan sees it, and every guard built on
    this helper reports green over a file it never read. Refuse that shape outright --
    no shell stylesheet has a legitimate reason to put a comment delimiter in a
    string -- rather than trying to parse around it.

    Every caller shares this, because a second stripper without the guard reopens the
    hole for whichever file it reads.
    """
    assert text.strip(), f"{name} is empty, so this test proves nothing"
    assert not re.search(r"""["'][^"'\n]*(?:/\*|\*/)[^"'\n]*["']""", text), (
        f"{name}: a comment delimiter inside a string literal would disarm stripping"
    )
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


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
    # A `/*` or `*/` inside a CSS string literal disarms the stripper: with
    # `content: "/*"` above a rule and `content: "*/"` below it, the non-greedy
    # `/\*.*?\*/` eats the real rule between them and every scan over the result goes
    # blind. Refuse that shape outright rather than trying to parse around it -- this
    # sheet has no legitimate reason to put a comment delimiter in a string.
    return _without_comments(text, "shell-components.css")


def _selector_parts(css: str) -> list[str]:
    """Every comma-separated selector part, with `:is()`/`:where()` unwrapped.

    Equality on the whole captured selector string is what an earlier form of the
    skip-link count used, and it missed a second mechanism three ways: a grouped
    selector (`.skip-link, .alt`), an `:is(.skip-link, .alt)` wrapper, and the
    string-literal comment escape above. Counting *parts* is what the assertion
    actually means.
    """
    unwrapped = re.sub(r":(?:is|where)\(([^)]*)\)", r"\1", css, flags=re.IGNORECASE)
    parts: list[str] = []
    for selector in re.findall(r"([^{}]+)\{", unwrapped):
        parts.extend(part.strip() for part in selector.split(",") if part.strip())
    return parts


def test_the_shell_declares_exactly_one_skip_link_mechanism() -> None:
    """`RCA-010` §Scope, master specification §19 slice 2b.

    The existing test proves a skip link is *reachable*. It cannot see a **second**
    mechanism added beside the first, which is the drift slice 2b exists to close:
    `journey.css` and `shell-components.css` each defined one, and nothing counted
    either. The count is the assertion; presence is already covered above.
    """
    css = _shell_component_css()
    parts = _selector_parts(css)

    assert parts, "no rules found in shell-components.css, so this test proves nothing"
    # A *mechanism* is a distinct thing the sheet styles as a skip link, so the
    # pseudo-class variants of one selector are one mechanism: `.skip-link` and
    # `.skip-link:focus` are the shipped pair. What must stay at one is the number of
    # distinct base selectors whose target *is* a skip link -- a second class name
    # standing in for the same affordance is the drift this counts, and a grouped or
    # `:is()`-wrapped selector no longer hides it.
    mechanisms = {
        part for part in parts if re.split(r"::?", part, maxsplit=1)[0] == ".skip-link"
    }
    bases = {re.split(r"::?", part, maxsplit=1)[0] for part in mechanisms}
    assert bases == {".skip-link"}, f"unexpected skip-link selectors: {sorted(bases)}"
    skip_like = {
        base
        for part in parts
        if "skip" in (base := re.split(r"::?", part, maxsplit=1)[0]).lower()
    }
    assert skip_like == {".skip-link"}, (
        f"expected one skip-link mechanism, found {len(skip_like)}: {sorted(skip_like)}"
    )


def test_the_shell_component_layer_declares_no_raw_type_size() -> None:
    """`RCA-010` §Scope, master specification §G.1.

    Scans `font-size` **and** the `font` shorthand. A scan worded for `font-size`
    alone passes over a size hidden in the shorthand -- the defect the allocation
    plan carried in its first draft, and the reason `journey.css` has five such
    sizes on the companion plan's side. `font: inherit` carries no size.
    """
    css = _shell_component_css()
    assert css.strip(), "shell-components.css is empty, so this test proves nothing"

    # Case-insensitive: CSS property names and unit identifiers are, so a scan that
    # is not lets `FONT-SIZE: 0.9REM` through. Found by mutating this test.
    offenders = [
        match.group(0).strip()
        for match in re.finditer(
            r"\bfont(?:-size)?\s*:\s*([^;}]+)", css, flags=re.IGNORECASE
        )
        if match.group(1).strip().lower() not in _INHERITED_TYPE_VALUES
        # ANY numeric literal, not an allowlist of three units: `font-size: 12pt` is
        # valid CSS and bypassed a `(rem|px|em)` check entirely, as do `pc`, `ch`,
        # `ex`, `vw`, `%` and a bare `0`. A raw number in a type declaration is the
        # defect; which unit it wears is not the question.
        and re.search(r"\d", _NON_SIZE_NUMERICS.sub("", match.group(1)))
    ]
    assert offenders == [], f"raw type sizes must use the token scale: {offenders}"


def test_the_shell_and_journey_type_scales_stay_separate() -> None:
    """`RCA-010` `FR-201`: a shell presentation value is the shell's.

    Asserted in **both** directions, because a leak either way breaks the boundary
    both allocation plans rely on and neither previously measured. The two scales are
    a deliberate separation, not a duplication: `journey.css` records that its two
    small tokens are "a separate decision, not a rounding of the same one".
    """
    # Comments are stripped on every side. Each sheet's header prose *names* the other
    # surface's tokens to explain the separation -- `journey.css:37` says its names are
    # "distinct from the shell's own `--text-*`" -- and a substring check over raw text
    # reads that explanation as the violation it warns against.
    journey_assets = files("khepri.rra.journey").joinpath("assets")

    def _rules(name: str) -> str:
        text = journey_assets.joinpath(name).read_text(encoding="utf-8")
        return _without_comments(text, name)

    shell_tokens = _rules("shell.css")
    shell_components = _rules("shell-components.css")
    journey = _rules("journey.css")

    assert "--journey-" not in shell_tokens, "shell.css names a journey property"
    assert "--journey-" not in shell_components, (
        "shell-components.css names a journey property"
    )
    # Symmetry is the point, and an earlier form of this test did not have it: it
    # forbade only a *declaration* on the journey side, so `journey.css` could carry
    # `var(--text-sm)` -- a reference to a shell token -- and pass. `FR-201` forbids
    # naming another surface's value at all, not merely declaring it. Found by
    # mutating this test rather than by reading it.
    assert "--text-" not in journey, "journey.css names a shell type token"


def test_the_shell_component_layer_draws_no_artwork() -> None:
    """`RCA-010` `FR-206`: the master specification §7 asset policy, unrelaxed.

    The shell has no admitted programmatic-drawing exception -- unlike the `RRA`
    side, where a data-driven chart is the one expected drawing. Its one painted
    background is the hero's legibility wash, which is not a drawing:
    `tests/shell_asset_scan.py` admits exactly that rule, by whole selector, and holds
    it to a ground-to-transparent gradient. Scoping the scan to the stylesheet also
    keeps it clear of the two `aria-hidden` change separators in `analysis.html.j2`,
    which are template content and `FR-194`-compliant.
    """
    from tests.shell_asset_scan import forbidden_asset_constructs, without_the_wash

    css = _shell_component_css()

    assert without_the_wash(css)[1], "the wash this scan admits is gone; remove the carve-out"
    found = forbidden_asset_constructs(css)
    assert found == [], f"forbidden asset constructs in shell-components.css: {found}"


def _linked_shell_css() -> str:
    """All three sheets, in the order `shell.html.j2:7-9` links them.

    Injecting only one measures an unstyled document, which is how an earlier form of
    the viewport test reported every target as too small.
    """
    journey_assets = files("khepri.rra.journey").joinpath("assets")
    return "\n".join(
        (
            journey_assets.joinpath("shell.css").read_text(encoding="utf-8"),
            journey_assets.joinpath("shell-components.css").read_text(encoding="utf-8"),
            files("khepri.runtime")
            .joinpath("shell_assets", "workspace.css")
            .read_text(encoding="utf-8"),
        )
    )


@pytest.mark.browser
@pytest.mark.parametrize("language", ["en", "ar"])
def test_the_shell_skip_link_is_visible_only_when_focused(language: str) -> None:
    """`RCA-010` §Scope and §Verification: measured in the browser, not read off CSS.

    The stylesheet-level tests beside this one prove there is exactly **one**
    skip-link mechanism and that it is first in the document. Neither observes
    behaviour: a `.skip-link` rule could move off-screen and stay there on focus, and
    every static scan would still pass. This is the slice's only behavioural
    assertion, so it measures the bounding box in both languages -- the off-screen
    idiom is `inset-inline-start`, which resolves to opposite sides under `rtl`.
    """
    html = _html("team", language)
    css = _linked_shell_css()
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Error as error:
            pytest.skip(f"Pinned Chromium is unavailable: {error}")
        try:
            page = browser.new_page(viewport={"width": 1180, "height": 900})
            page.set_content(html, wait_until="domcontentloaded")
            page.add_style_tag(content=css)
            skip = page.locator(".skip-link").first

            unfocused = skip.bounding_box()
            assert unfocused is not None, "the skip link must exist to be measured"
            width = page.evaluate("innerWidth")
            off_screen = unfocused["x"] + unfocused["width"] <= 0 or unfocused["x"] >= width
            assert off_screen, f"the skip link must start off-screen, got x={unfocused['x']}"

            skip.focus()
            focused = skip.bounding_box()
            assert focused is not None
            # The whole link, not just its leading edge: a wide one whose left edge is
            # on-screen can still run off the far side, and the requirement is that a
            # keyboard reader can see what they have focused.
            assert focused["x"] >= 0, (
                f"focused skip link starts off-screen: {focused['x']}"
            )
            assert focused["x"] + focused["width"] <= width, (
                "a focused skip link must fit inside the viewport: "
                f"x={focused['x']} width={focused['width']} viewport={width}"
            )
            assert focused["height"] >= 44, (
                f"the skip link is a pointer target: {focused['height']}px < 44px"
            )
        finally:
            browser.close()


@pytest.mark.browser
def test_the_team_surface_type_sizes_resolve_from_the_token_scale() -> None:
    """`RCA-010` §Scope: the computed size, not the declaration.

    `var(--text-sm)` resolves to nothing if the token sheet is absent or the name is
    misspelled, and the element would silently inherit. Reading the stylesheet cannot
    see that; a computed style can. The expected value is the token's own -- 0.82rem
    at a 16px root -- which is 0.88px below the `0.875rem` this slice replaced.
    """
    html = _html("team", "en")
    css = _linked_shell_css()
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Error as error:
            pytest.skip(f"Pinned Chromium is unavailable: {error}")
        try:
            page = browser.new_page(viewport={"width": 1180, "height": 900})
            page.set_content(html, wait_until="domcontentloaded")
            page.add_style_tag(content=css)

            declared = page.evaluate(
                "getComputedStyle(document.documentElement)"
                ".getPropertyValue('--text-sm').trim()"
            )
            assert declared == "0.82rem", f"--text-sm must be declared, got {declared!r}"

            # Every selector this slice retokenized must be PRESENT and measured. An
            # earlier form skipped an absent one, so it measured `.member-role` alone
            # and would have passed with the other two declarations deleted. The
            # fixture renders all three: a disabled member gives `.member-state`, and
            # `_StubInvitations` yields one pending invitation for `.invitation-role`.
            for selector in (".member-state", ".member-role", ".invitation-role"):
                locator = page.locator(selector).first
                assert locator.count() == 1, f"{selector} must render to be measured"
                size = page.evaluate(
                    "s => getComputedStyle(document.querySelector(s)).fontSize", selector
                )
                assert size == "13.12px", f"{selector} computed {size}, expected 13.12px"
        finally:
            browser.close()
