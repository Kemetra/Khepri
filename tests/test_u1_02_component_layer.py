"""U1-02: the governed data-display component layer, proven on the rendered documents.

These began as the RED tests `#348` landed -- every one `xfail(strict=True)`, failing
for a stated reason -- and the strict marker did its job: the day the layer landed the
suite failed until each marker was removed here, so nothing was satisfied quietly.

**Assertions are on the rendered document, not on a view model.** That is
`test_rra006_html_sections`'s discipline and the reason is the same: a claim about
markup only means something when it is made against what a browser would receive.

**Three of the RED tests could not go green as written, and each is corrected here
with its reason recorded**, because a test is a proposal like any other file:

- The RED placement test asked for all seven components on the *business* page. Three
  cannot appear there: a citation identifier and every field of the bundle identity --
  the versions and `row_count` -- are tier **A**, Audit, in
  `presentation-visibility-matrix.md` §A.5, which `RRA-009` enforces and `RRA-012`
  FR-095 declines to restate or relax. The evidence link, version label and coverage
  indicator therefore render in the evidence region, and `COMPONENT_REGION` says which
  surface each component is proven on.
- The RED colour test imported `khepri.rra.rendering.components`, a Python module the
  plan itself records `RRA-012` does not authorize. It now renders the macros.
- The RED fail-closed test accepted `KeyError` and `ValueError`, the exceptions a Python
  module would raise. The layer is Jinja macros under the environment's
  `StrictUndefined`, whose refusal is `UndefinedError`; the test accepts that too.

Plan: `docs/superpowers/plans/2026-09-01-u1-02-component-layer-plan.md`.
Authority: active `RRA-012`.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from jinja2 import TemplateNotFound, UndefinedError

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import GOVERNED_SECTION_STATES, FactPackage, ReportBundle, reconcile
from khepri.rra.facts import AdmittedInput, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.profiling import build_profile
from khepri.rra.rendering.html import (
    _CHROME,
    HtmlReportRenderer,
    HtmlSurface,
    build_cells,
    build_environment,
)
from khepri.rra.rendering.wording import component_chrome
from tests.rra003_contract_fixtures import (
    TEST_CONTRACT,
    manifest_for_csv,
    published_mapping_identity,
)

#: The marker every figure the component layer renders must carry. Named once so
#: the implementation and these tests cannot drift on the spelling.
FIGURE_COMPONENT_MARKER = 'data-component="figure"'
REFUSAL_COMPONENT_MARKER = 'data-component="refusal-panel"'

HEADER = b"date,revenue,units,invoice_no,product\n"
START = date(2026, 1, 1)
ROWS = [
    ("100.00", 2, "Alpha"),
    ("150.00", 3, "Beta"),
    ("200.00", 4, "Gamma"),
]

TEMPLATE_DIR = Path("src/khepri/rra/rendering/templates")
COMPONENTS_TEMPLATE = "_components.html.j2"

#: Compiled once. The Arabic block, used to prove an Arabic document carries
#: Arabic script rather than English text under an `ar` label.
ARABIC_SCRIPT = re.compile(r"[\u0600-\u06ff]")

BUSINESS = "business"
EVIDENCE = "evidence"

#: The seven FR-092 requires, each with the surface it is proven on. A test asserting
#: only the three that were easy to write would pass against an implementation
#: carrying three, which is the coverage gap this constant closes.
#:
#: The region is not a choice this file makes. `presentation-visibility-matrix.md`
#: §A.5 puts a citation identifier and every bundle-identity field -- the versions
#: and `row_count` -- in tier A, so the components that render those values render
#: in the evidence region, which is also the printed appendix. A business page
#: carrying them would violate `RRA-009`, and a business page linking to a citation
#: anchor it does not contain would be a dead link.
COMPONENT_REGION = {
    "figure": BUSINESS,
    "status-badge": BUSINESS,
    "quality-summary": BUSINESS,
    "refusal-panel": BUSINESS,
    "evidence-link": EVIDENCE,
    "version-label": EVIDENCE,
    "coverage-indicator": EVIDENCE,
}
REQUIRED_COMPONENTS = tuple(COMPONENT_REGION)


def chrome_for(language: str) -> dict:
    """The chrome mapping the render context carries, for a macro rendered alone."""
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


def surface() -> HtmlSurface:
    bundle = ReportBundle.of(package_for(ROWS))
    rendered = HtmlReportRenderer().render_html(bundle)
    # Reconciled so no assertion below rests on a page the bundle would reject.
    reconcile(rendered.content, bundle=bundle)
    return rendered


def page(language: str = LANGUAGE_ENGLISH) -> str:
    return surface().documents[language]


def region(rendered: HtmlSurface, name: str, language: str) -> str:
    return (rendered.documents if name == BUSINESS else rendered.evidence)[language]


def render_macro(call: str, language: str) -> str:
    """One macro, rendered alone in the production environment with the real chrome."""
    template = build_environment().from_string(
        f'{{% from "{COMPONENTS_TEMPLATE}" import {call.split("(")[0]} %}}{{{{ {call} }}}}'
    )
    return template.render(chrome=chrome_for(language))


# --------------------------------------------------------------------------
# FR-092, FR-101 -- one component per concept, and nothing bypassing it
# --------------------------------------------------------------------------


def test_every_figure_renders_through_the_figure_component() -> None:
    """FR-092/FR-101.

    Was RED because `report.html.j2` rendered `<td class="figure">{{ cell.text }}</td>`
    directly, and the series table rendered the same concept a second way. Two
    hand-built blocks for one concept is the duplicate presentation truth FR-092
    refuses.
    """
    rendered = page()
    figure_cells = re.findall(r"<td[^>]*class=\"[^\"]*\bfigure\b[^\"]*\"[^>]*>", rendered)
    assert figure_cells, "no figure cells rendered -- the fixture proves nothing"
    bypassing = [cell for cell in figure_cells if FIGURE_COMPONENT_MARKER not in cell]
    assert not bypassing, (
        f"{len(bypassing)} figure cells bypass the component layer: {bypassing[:3]}"
    )


def test_a_refusal_renders_through_the_refusal_panel() -> None:
    """FR-092.

    Was RED because the template rendered a bare `<p class="refused">`. The panel
    consumes `chrome.refusal_prose`, which `html.py` already supplies -- so this
    component authors no refusal wording and FR-095 holds by construction.
    """
    rendered = page()
    refusals = re.findall(r"<p[^>]*class=\"[^\"]*\brefused\b[^\"]*\"[^>]*>", rendered)
    if not refusals:
        pytest.skip("this fixture publishes every section; no refusal to check")
    bypassing = [panel for panel in refusals if REFUSAL_COMPONENT_MARKER not in panel]
    assert not bypassing, f"refusal prose bypasses the panel component: {bypassing[:3]}"


def test_no_scoped_template_renders_a_figure_outside_the_component_layer() -> None:
    """FR-101's guard, and the load-bearing test in this file.

    **It enumerates templates from the directory rather than a hand-written list.**
    A scan naming its own modules reproduces the drift it exists to catch, so this
    walks the directory and asserts the enumeration is non-empty -- a glob matching
    nothing must fail rather than pass vacuously.

    Mutation-checked before it was believed: a hand-built `<td class="figure">` added
    to `report.pdf.html.j2`, a template no test names, was caught.
    """
    templates = sorted(TEMPLATE_DIR.glob("*.j2"))
    assert templates, f"no templates enumerated under {TEMPLATE_DIR} -- the scan is blind"

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
# FR-092 -- all seven components, not only the four easy ones
# --------------------------------------------------------------------------


@pytest.mark.parametrize("component", REQUIRED_COMPONENTS)
def test_each_required_component_renders(component: str) -> None:
    """FR-092 requires exactly seven components, so each gets its own test.

    Parametrized rather than looped inside one test: a loop stops at the first
    missing component and reports one failure, while this reports which of the
    seven are absent.

    The components live as Jinja macros in a `_`-prefixed template -- the pattern
    `report.html.j2:1` already uses for the chart -- so they stay inside `RRA-012`'s
    Scope, which authorizes the rendering templates and no new Python module. Each is
    looked for on the surface `COMPONENT_REGION` assigns it, for the tier reason
    recorded there.
    """
    rendered = region(surface(), COMPONENT_REGION[component], LANGUAGE_ENGLISH)
    assert 'data-component="' + component + '"' in rendered, (
        f"the {component} component does not render on the {COMPONENT_REGION[component]} surface"
    )


@pytest.mark.parametrize("component", REQUIRED_COMPONENTS)
def test_each_component_renders_in_both_languages(component: str) -> None:
    """FR-099, per component rather than once for the whole page.

    A single page-level marker check would pass while the refusal, version or
    coverage components were absent from Arabic output entirely. Each component
    is asserted present in both documents of its region, and the Arabic document
    must carry Arabic script and `dir="rtl"` so "renders in Arabic" cannot be
    satisfied by English text on an Arabic page.
    """
    rendered = surface()
    english = region(rendered, COMPONENT_REGION[component], LANGUAGE_ENGLISH)
    arabic = region(rendered, COMPONENT_REGION[component], LANGUAGE_ARABIC)
    marker = 'data-component="' + component + '"'
    assert marker in english, component + " missing from the English document"
    assert marker in arabic, component + " missing from the Arabic document"
    assert 'dir="rtl"' in arabic, "the Arabic document is not right-to-left"
    assert ARABIC_SCRIPT.search(arabic), "the Arabic document carries no Arabic script"


def test_every_evidence_link_targets_an_anchor_in_its_own_document() -> None:
    """The evidence link is a same-document link, so its target has to exist there.

    This is the property that fixes the component's region: the citation anchors live
    in the evidence region, and a business page carrying the link would carry a dead
    one. Asserted on both languages so an anchor renamed in one template cannot leave
    one reader with links that go nowhere.
    """
    rendered = surface()
    for language in REQUIRED_LANGUAGES:
        document = rendered.evidence[language]
        targets = re.findall(r'data-component="evidence-link"[^>]*href="#([^"]+)"', document)
        assert targets, "no evidence links rendered -- the assertion below would be vacuous"
        anchors = set(re.findall(r'\bid="([^"]+)"', document))
        missing = [target for target in targets if target not in anchors]
        assert not missing, f"evidence links to anchors the document lacks: {missing[:3]}"


# --------------------------------------------------------------------------
# FR-093, FR-094 -- render what you are given, and fail closed
# --------------------------------------------------------------------------


def test_a_component_never_reformats_a_given_value() -> None:
    """FR-093.

    `FigureCell` carries no `value` field on purpose (`html.py`): "a renderer holding
    the `Decimal` beside the string is a renderer that can format the number itself."
    This proves the guarantee against a rendered page rather than restating the
    docstring -- every figure text the cells carry, at whatever precision the analysis
    published it, must survive byte-for-byte on the page.
    """
    bundle = ReportBundle.of(package_for(ROWS))
    rendered_surface = HtmlReportRenderer().render_html(bundle)
    rendered = rendered_surface.documents[LANGUAGE_ENGLISH]
    reconcile(rendered_surface.content, bundle=bundle)

    texts = {cell.text for cell in build_cells(bundle, LANGUAGE_ENGLISH) if cell.text}
    assert texts, "no cells built -- the fixture proves nothing"
    for text in texts:
        assert text in rendered, (
            "the component altered a given figure: " + repr(text) + " is not on the page"
        )


def test_an_unknown_code_fails_closed() -> None:
    """FR-094.

    A component given a state it has no governed word for must refuse -- never the
    code string, never an empty element, never a blank. The layer is macros under the
    environment's `StrictUndefined`, so the refusal is the environment's
    `UndefinedError`; a Python-side lookup would raise `KeyError`, and either is a
    refusal rather than a rendering.
    """
    environment = build_environment()
    # The macro template must EXIST before this test means anything. Without this
    # guard the render below raises `TemplateNotFound` and `pytest.raises` counts
    # it as a pass -- a test that would report fail-closed behaviour from a layer
    # that was never written.
    try:
        environment.get_template(COMPONENTS_TEMPLATE)
    except TemplateNotFound:  # pragma: no cover - the RED state
        pytest.fail(f"{COMPONENTS_TEMPLATE} does not exist; fail-closed is unproven")

    with pytest.raises((KeyError, ValueError, UndefinedError)):
        render_macro(
            'status_badge(state="not_a_governed_state", chrome=chrome)', LANGUAGE_ENGLISH
        )


def test_the_status_badge_never_reads_a_raw_section_state() -> None:
    """Guards the trap check 3 of the plan found.

    `html.py` records that the audit context does not carry a section's state -- it
    is tier Internal, which `RRA-011` excludes from the audit region. The template
    compares against `refused_state`, a governed constant. A badge specified against
    the raw field would be specified against a field that never arrives.
    """
    source = (TEMPLATE_DIR / COMPONENTS_TEMPLATE).read_text(encoding="utf-8")
    assert "section.state" not in source, (
        "the badge reads a field the render context does not carry"
    )


# --------------------------------------------------------------------------
# FR-095a, FR-099, FR-100 -- vocabulary, parity, and colour
# --------------------------------------------------------------------------


def test_every_chrome_label_exists_in_both_languages() -> None:
    """FR-095a.

    The chrome labels this layer authors carry the same import-time completeness
    assertion the tables around them use, so a label added in one language and
    forgotten in the other fails at import rather than rendering blank to an Arabic
    reader. This restates the property against the public accessor.
    """
    english = component_chrome(LANGUAGE_ENGLISH)
    arabic = component_chrome(LANGUAGE_ARABIC)
    assert english and arabic, "no component chrome labels registered"
    assert set(english) == set(arabic), (
        f"chrome labels differ by language: {set(english) ^ set(arabic)}"
    )


@pytest.mark.parametrize("language", sorted(REQUIRED_LANGUAGES))
@pytest.mark.parametrize("state", sorted(GOVERNED_SECTION_STATES))
def test_no_component_signals_status_by_colour_alone(state: str, language: str) -> None:
    """FR-100.

    A status must carry a text indicator. Every governed section state is rendered
    through the badge macro in the production environment, in each language, and the
    markup stripped of its tags must leave a word behind. The state set is read from
    the bundle, not from the chrome table, so a state admitted there and unworded here
    is a failure rather than an untested branch.
    """
    markup = render_macro(f'status_badge(state="{state}", chrome=chrome)', language)
    stripped = re.sub(r"<[^>]+>", "", markup).strip()
    assert stripped, f"the {state} badge carries no text in {language} -- colour is its only signal"
    if language == LANGUAGE_ARABIC:
        assert ARABIC_SCRIPT.search(stripped), f"the {state} badge is not worded in Arabic"


def test_the_refusal_panel_names_its_state_in_words() -> None:
    """FR-100, for the panel: its rule and tint are never the only signal."""
    for language in REQUIRED_LANGUAGES:
        markup = render_macro('refusal_panel(prose="", chrome=chrome)', language)
        label = re.search(r'class="refused__label">([^<]*)<', markup)
        assert label and label.group(1).strip(), f"the refusal panel carries no label in {language}"


def test_keyboard_reachability_is_not_claimed_for_static_components() -> None:
    """Guards the round-5 correction to `RRA-012`.

    Only the drawer and its opener are interactive under FR-098. A static figure,
    badge, version label or coverage indicator has no keyboard action, and putting
    one in the tab order adds a focus stop that does nothing.
    """
    rendered = page()
    badges = re.findall(r'<[^>]*data-component="status-badge"[^>]*>', rendered)
    assert badges, "no status badge rendered -- the assertion below would be vacuous"
    for badge in badges:
        assert "tabindex" not in badge, "a static badge should not enter the tab order"
