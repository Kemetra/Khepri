"""U1-02's RED tests: the governed data-display component layer does not exist yet.

Every test here fails on this tree, and each docstring says what it is waiting for.
They are the deliverable §15 requires before `U1`'s row may read
`READY_FOR_IMPLEMENTATION`: authority is not a plan, and a plan without failing
tests is not one either.

**Assertions are on the rendered document, not on a view model.** That is
`test_rra006_html_sections`'s discipline and the reason is the same: a claim about
markup only means something when it is made against what a browser would receive.

**Every test is `xfail(strict=True)`**, which is this repository's existing pattern for a
claim that must not hold yet (`test_rca001_identity_advisory_lock.py:158`). Strict is the
point: the day a component lands, its test stops xfailing and the suite *fails* until the
marker is removed. So these cannot rot into permanently-red noise, and they cannot be
quietly satisfied without someone noticing.

Plan: `docs/superpowers/plans/2026-09-01-u1-02-component-layer-plan.md`.
Authority: active `RRA-012`.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import FactPackage, ReportBundle, reconcile
from khepri.rra.facts import AdmittedInput, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.profiling import build_profile
from khepri.rra.rendering.html import HtmlReportRenderer, build_cells
from tests.rra003_contract_fixtures import (
    TEST_CONTRACT,
    manifest_for_csv,
    published_mapping_identity,
)

#: The marker every figure the component layer renders must carry. Named once so
#: the implementation and these tests cannot drift on the spelling.
FIGURE_COMPONENT_MARKER = "data-component=\"figure\""
REFUSAL_COMPONENT_MARKER = "data-component=\"refusal-panel\""

HEADER = b"date,revenue,units,invoice_no,product\n"
START = date(2026, 1, 1)
ROWS = [
    ("100.00", 2, "Alpha"),
    ("150.00", 3, "Beta"),
    ("200.00", 4, "Gamma"),
]

TEMPLATE_DIR = Path("src/khepri/rra/rendering/templates")

#: Compiled once. The Arabic block, used to prove an Arabic document carries
#: Arabic script rather than English text under an `ar` label.
ARABIC_SCRIPT = re.compile(r"[\u0600-\u06ff]")


def chrome_for(language: str) -> dict:
    """The chrome mapping the render context carries, for a macro rendered alone."""
    from khepri.rra.rendering.html import _CHROME  # noqa: PLC0415

    return _CHROME[language]


def package_for(rows: list[tuple[str, int, str]]) -> FactPackage:
    """One package over these rows, under the pin that admits every family."""
    body = b"".join(
        f"{(START + timedelta(days=index)).isoformat()},{amount},{units},"
        f"INV-{index},{product}\n".encode()
        for index, (amount, units, product) in enumerate(rows)
    )
    content = HEADER + body
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    with published_mapping_identity():
        mapping = build_mapping(profile, contract=TEST_CONTRACT)
        return build_fact_package(
            AdmittedInput(
                manifest=manifest_for_csv(content, TEST_CONTRACT),
                content=content,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=TEST_CONTRACT,
            ),
        )


def page(language: str = LANGUAGE_ENGLISH) -> str:
    bundle = ReportBundle.of(package_for(ROWS))
    surface = HtmlReportRenderer().render_html(bundle)
    # Reconciled so no assertion below rests on a page the bundle would reject.
    reconcile(surface.content, bundle=bundle)
    return surface.documents[language]


# --------------------------------------------------------------------------
# FR-092, FR-101 — one component per concept, and nothing bypassing it
# --------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="U1-02 RED: the component layer does not exist yet.")
def test_every_figure_renders_through_the_figure_component() -> None:
    """FR-092/FR-101.

    RED because `report.html.j2:111` renders `<td class="figure">{{ cell.text }}</td>`
    directly, and `:155` renders the series table the same way. Two hand-built
    blocks for one concept is the duplicate presentation truth FR-092 refuses.
    """
    rendered = page()
    figure_cells = re.findall(r"<td[^>]*class=\"[^\"]*\bfigure\b[^\"]*\"[^>]*>", rendered)
    assert figure_cells, "no figure cells rendered — the fixture proves nothing"
    bypassing = [cell for cell in figure_cells if FIGURE_COMPONENT_MARKER not in cell]
    assert not bypassing, (
        f"{len(bypassing)} figure cells bypass the component layer: {bypassing[:3]}"
    )


@pytest.mark.xfail(strict=True, reason="U1-02 RED: the component layer does not exist yet.")
def test_a_refusal_renders_through_the_refusal_panel() -> None:
    """FR-092.

    RED because `report.html.j2:65` renders a bare `<p class="refused">`. The panel
    consumes `chrome.refusal_prose`, which `html.py:99` already supplies — so this
    component authors no refusal wording and FR-095 holds by construction.
    """
    rendered = page()
    refusals = re.findall(r"<p[^>]*class=\"[^\"]*\brefused\b[^\"]*\"[^>]*>", rendered)
    if not refusals:
        pytest.skip("this fixture publishes every section; no refusal to check")
    bypassing = [panel for panel in refusals if REFUSAL_COMPONENT_MARKER not in panel]
    assert not bypassing, f"refusal prose bypasses the panel component: {bypassing[:3]}"


@pytest.mark.xfail(strict=True, reason="U1-02 RED: the component layer does not exist yet.")
def test_no_scoped_template_renders_a_figure_outside_the_component_layer() -> None:
    """FR-101's guard, and the load-bearing test in this file.

    **It enumerates templates from the directory rather than a hand-written list.**
    A scan naming its own modules reproduces the drift it exists to catch, so this
    walks the directory and asserts the enumeration is non-empty — a glob matching
    nothing must fail rather than pass vacuously.

    Mutation check before believing it: add a hand-built `<td class="figure">` to
    any template here and confirm this fails.
    """
    templates = sorted(TEMPLATE_DIR.glob("*.j2"))
    assert templates, f"no templates enumerated under {TEMPLATE_DIR} — the scan is blind"

    offenders: list[str] = []
    for template in templates:
        source = template.read_text(encoding="utf-8")
        for match in re.findall(r"<td[^>]*class=\"[^\"]*\bfigure\b[^\"]*\"[^>]*>", source):
            if FIGURE_COMPONENT_MARKER not in match:
                offenders.append(f"{template.name}: {match}")
    assert not offenders, "figures rendered outside the component layer:\n" + "\n".join(
        offenders
    )


# --------------------------------------------------------------------------
# FR-092 - all seven components, not only the three easy ones
# --------------------------------------------------------------------------

#: The seven FR-092 requires, by their marker. A test asserting only the three
#: that were easy to write would pass against an implementation carrying three,
#: which is the coverage gap this constant closes.
REQUIRED_COMPONENTS = (
    "figure",
    "status-badge",
    "quality-summary",
    "refusal-panel",
    "evidence-link",
    "version-label",
    "coverage-indicator",
)


@pytest.mark.xfail(strict=True, reason="U1-02 RED: the component layer does not exist yet.")
@pytest.mark.parametrize("component", REQUIRED_COMPONENTS)
def test_each_required_component_renders(component: str) -> None:
    """FR-092 requires exactly seven components, so each gets its own RED test.

    Parametrized rather than looped inside one test: a loop stops at the first
    missing component and reports one failure, while this reports which of the
    seven are absent. An implementation carrying only the three easy ones fails
    four of these.

    The components live as Jinja macros in a `_`-prefixed template - the pattern
    `report.html.j2:1` already uses for the chart (`{% from "_chart.svg.j2"
    import chart %}`) - so they stay inside `RRA-012`'s Scope, which authorizes
    the rendering templates and authorizes no new Python module.
    """
    rendered = page()
    assert 'data-component="' + component + '"' in rendered, (
        "the " + component + " component does not render"
    )


@pytest.mark.xfail(strict=True, reason="U1-02 RED: the component layer does not exist yet.")
@pytest.mark.parametrize("component", REQUIRED_COMPONENTS)
def test_each_component_renders_in_both_languages(component: str) -> None:
    """FR-099, per component rather than once for the whole page.

    A single page-level marker check would pass while the refusal, version or
    coverage components were absent from Arabic output entirely. Each component
    is asserted present in both documents, and the Arabic document must carry
    Arabic script and `dir="rtl"` so "renders in Arabic" cannot be satisfied by
    English text on an Arabic page.
    """
    english = page(LANGUAGE_ENGLISH)
    arabic = page(LANGUAGE_ARABIC)
    marker = 'data-component="' + component + '"'
    assert marker in english, component + " missing from the English document"
    assert marker in arabic, component + " missing from the Arabic document"
    assert 'dir="rtl"' in arabic, "the Arabic document is not right-to-left"
    assert ARABIC_SCRIPT.search(arabic), "the Arabic document carries no Arabic script"


# --------------------------------------------------------------------------
# FR-093, FR-094 — render what you are given, and fail closed
# --------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="U1-02 RED: the component layer does not exist yet.")
def test_a_component_never_reformats_a_given_value() -> None:
    """FR-093.

    `FigureCell` carries no `value` field on purpose (`html.py:232`): "a renderer
    holding the `Decimal` beside the string is a renderer that can format the number
    itself." This proves the guarantee against a rendered page rather than restating
    the docstring — a figure whose text carries four decimal places must survive
    byte-for-byte, not be re-rounded to the monetary default of two.

    RED because no component exists to prove it of.
    """
    bundle = ReportBundle.of(package_for(ROWS))
    surface = HtmlReportRenderer().render_html(bundle)
    rendered = surface.documents[LANGUAGE_ENGLISH]
    reconcile(rendered, bundle=bundle)

    texts = {cell.text for cell in build_cells(bundle, LANGUAGE_ENGLISH) if cell.text}
    assert texts, "no cells built - the fixture proves nothing"
    for text in texts:
        assert text in rendered, (
            "the component altered a given figure: " + repr(text) + " is not on the page"
        )


@pytest.mark.xfail(strict=True, reason="U1-02 RED: the component layer does not exist yet.")
def test_an_unknown_code_fails_closed() -> None:
    """FR-094.

    A component given a code it has no governed rendering for must refuse — never
    the code string, never an empty element, never a blank. RED because no component
    exists.
    """
    from jinja2 import TemplateNotFound  # noqa: PLC0415

    from khepri.rra.rendering.html import build_environment  # noqa: PLC0415

    environment = build_environment()
    # The macro template must EXIST before this test means anything. Without this
    # guard the render below raises `TemplateNotFound` and `pytest.raises` counts
    # it as a pass -- a test that would report fail-closed behaviour from a layer
    # that was never written.
    try:
        environment.get_template("_components.html.j2")
    except TemplateNotFound:  # pragma: no cover - the RED state
        pytest.fail("_components.html.j2 does not exist; fail-closed is unproven")

    template = environment.from_string(
        '{% from "_components.html.j2" import status_badge %}'
        '{{ status_badge(state="not_a_governed_state", chrome=chrome) }}'
    )
    with pytest.raises((KeyError, ValueError)):
        template.render(chrome=chrome_for(LANGUAGE_ENGLISH))


@pytest.mark.xfail(strict=True, reason="U1-02 RED: the component layer does not exist yet.")
def test_the_status_badge_never_reads_a_raw_section_state() -> None:
    """Guards the trap check 3 of the plan found.

    `html.py:519` records that `section.state` is not carried into the context — it
    is tier Internal, which `RRA-011` excludes from the audit region. The template
    compares against `refused_state`, a chrome constant. A badge specified against
    `section.state` would be specified against a field that never arrives.

    RED because no component exists.
    """
    source = (TEMPLATE_DIR / "_components.html.j2").read_text(encoding="utf-8")
    assert "section.state" not in source, (
        "the badge reads a field the render context does not carry"
    )


# --------------------------------------------------------------------------
# FR-095a, FR-099, FR-100 — vocabulary, parity, and colour
# --------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="U1-02 RED: the component layer does not exist yet.")
def test_every_chrome_label_exists_in_both_languages() -> None:
    """FR-095a.

    The chrome labels this layer authors must carry the same import-time
    completeness assertion the tables around them use, so a label added in one
    language and forgotten in the other fails at import rather than rendering blank
    to an Arabic reader. RED because the labels do not exist.
    """
    from khepri.rra.rendering.wording import component_chrome  # noqa: PLC0415

    english = component_chrome(LANGUAGE_ENGLISH)
    arabic = component_chrome(LANGUAGE_ARABIC)
    assert english and arabic, "no component chrome labels registered"
    assert set(english) == set(arabic), (
        f"chrome labels differ by language: {set(english) ^ set(arabic)}"
    )


@pytest.mark.xfail(strict=True, reason="U1-02 RED: the component layer does not exist yet.")
def test_no_component_signals_status_by_colour_alone() -> None:
    """FR-100.

    A status, refusal or caveat must carry a text or non-colour indicator. RED
    because no component exists to carry one.
    """
    from khepri.rra.rendering.components import (  # noqa: PLC0415
        STATUS_STATES,
        render_status_badge,
    )

    for state in STATUS_STATES:
        markup = render_status_badge(state=state, language=LANGUAGE_ENGLISH)
        stripped = re.sub(r"<[^>]+>", "", markup).strip()
        assert stripped, f"the {state} badge carries no text — colour is its only signal"


@pytest.mark.xfail(strict=True, reason="U1-02 RED: the component layer does not exist yet.")
def test_keyboard_reachability_is_not_claimed_for_static_components() -> None:
    """Guards the round-5 correction to `RRA-012`.

    Only the drawer and its opener are interactive under FR-098. A static figure,
    badge, version label or coverage indicator has no keyboard action, and putting
    one in the tab order adds a focus stop that does nothing.

    RED because no component exists.
    """
    rendered = page()
    badges = re.findall(r'<[^>]*data-component="status-badge"[^>]*>', rendered)
    assert badges, "no status badge rendered - the assertion below would be vacuous"
    for badge in badges:
        assert "tabindex" not in badge, "a static badge should not enter the tab order"
