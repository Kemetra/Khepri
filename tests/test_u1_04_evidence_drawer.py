"""U1-04's RED tests: the evidence drawer's structure does not exist yet.

Every RED test here fails on this tree, and each docstring says what it is waiting for.
They are the deliverable §15 requires before `U1`'s row may read
`READY_FOR_IMPLEMENTATION`.

**Every RED test is `xfail(strict=True)`**, the pattern `U1-02` used: the day the drawer
lands, its test stops xfailing and the suite *fails* until the marker is removed, so
nothing is satisfied quietly.

**The drawer is driven directly, through the production environment with the real
chrome**, because it is placed on no page in this slice. Its catalog data supply is
deferred by `RRA-012`'s Scope note; placing an unsupplied drawer would render every field
"unavailable" for a reason FR-096a does not mean. One non-RED guard below holds that line
and is deleted by the supply slice.

Plan: `docs/superpowers/plans/2026-09-02-u1-04-evidence-drawer-plan.md`.
Authority: active `RRA-012` FR-096, FR-096a, FR-097, FR-098.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest
from jinja2 import TemplateError

from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.rendering.html import _CHROME, build_environment
from khepri.rra.rendering.wording import component_chrome
from khepri.rra.report_api import _cited_figure

TEMPLATE_DIR = Path("src/khepri/rra/rendering/templates")
COMPONENTS_TEMPLATE = "_components.html.j2"
DRAWER_MARKER = 'data-component="evidence-drawer"'
ARABIC_SCRIPT = re.compile(r"[\u0600-\u06ff]")

RED = pytest.mark.xfail(strict=True, reason="U1-04 RED: the evidence drawer does not exist yet.")

#: The projection `report_api._cited_figure` builds, for a **stored** fact -- one the
#: package retains, so `precision` and `inputs` are present. Package-level coverage
#: travels beside it exactly as `CitationEvidenceResponse` carries it.
STORED_FIGURE = {
    "citation_id": "fact-stored-0001",
    "metric": "revenue",
    "name": "Revenue",
    "formula_version": "rra004.formula.v1",
    "definition": "Total value of admitted sale rows in the period.",
    "unit_kind": "money",
    "precision": 2,
    "inputs": ["amount", "quantity"],
    "coverage_manifest_identity": "coverage-manifest-7f3a",
    "coverage_signatures": ["sig-a", "sig-b"],
}

#: The same projection for a **derived** analysis figure. `_cited_figure`'s docstring:
#: precision and inputs are "absent, not empty and not recomputed". FR-096a is about
#: exactly this mapping.
DERIVED_FIGURE = {
    **STORED_FIGURE,
    "citation_id": "fact-derived-0002",
    "metric": "revenue_change",
    "precision": None,
    "inputs": None,
    "coverage_manifest_identity": None,
    "coverage_signatures": [],
}

#: The five FR-096 fields, by the value the drawer must show for `STORED_FIGURE`.
GIVEN_FIELDS = {
    "definition": STORED_FIGURE["definition"],
    "version": STORED_FIGURE["formula_version"],
    "inputs": "quantity",
    "coverage": STORED_FIGURE["coverage_manifest_identity"],
    "citation": STORED_FIGURE["citation_id"],
}


def render_drawer(given: dict[str, object], language: str = LANGUAGE_ENGLISH) -> str:
    """The drawer alone, in the production environment, with the real chrome."""
    template = build_environment().from_string(
        f'{{% from "{COMPONENTS_TEMPLATE}" import evidence_drawer %}}'
        "{{ evidence_drawer(given, chrome) }}"
    )
    return template.render(given=given, chrome=_CHROME[language])


def render_or_fail(given: dict[str, object], language: str = LANGUAGE_ENGLISH) -> str:
    """Render, and turn a missing macro or label into a test failure with the cause."""
    try:
        return render_drawer(given, language)
    except TemplateError as error:  # pragma: no cover - the RED state
        pytest.fail(f"the drawer cannot render: {error}")


# --------------------------------------------------------------------------
# FR-096 -- one drawer, rendering the five fields it is given
# --------------------------------------------------------------------------


@RED
def test_the_drawer_component_exists() -> None:
    """The macro is importable from the component template. RED: it is not defined."""
    markup = render_or_fail(STORED_FIGURE)
    assert DRAWER_MARKER in markup, "the drawer renders without its component marker"


@RED
@pytest.mark.parametrize("field", sorted(GIVEN_FIELDS))
def test_the_drawer_renders_every_given_field(field: str) -> None:
    """FR-096, per field.

    Parametrized so an implementation carrying three of the five fields reports which two
    are missing rather than one failure. The value asserted is the one handed in, so a
    field that renders a label with no value fails too.
    """
    markup = render_or_fail(STORED_FIGURE)
    assert GIVEN_FIELDS[field] in markup, f"the drawer does not render the {field} it was given"


@RED
def test_the_drawer_reuses_the_version_label_and_evidence_link() -> None:
    """FR-092: one component per concept.

    The version and the citation already have components from `U1-02`. A drawer
    rendering either its own way would be a second source of presentation truth.
    """
    markup = render_or_fail(STORED_FIGURE)
    assert 'data-component="version-label"' in markup, "the version bypasses its component"
    assert 'data-component="evidence-link"' in markup, "the citation bypasses its component"


# --------------------------------------------------------------------------
# FR-096a -- an absent field is stated as unavailable, never empty, never refused
# --------------------------------------------------------------------------


@RED
def test_an_absent_field_renders_the_unavailable_state() -> None:
    """FR-096a.

    Driven by the derived-family shape whose `inputs` the catalog returns as `None`.
    The governed unavailable word must appear, and no field in the drawer may be an
    empty element -- an empty `<dd>` is a field presented as empty, which the
    requirement names and refuses.
    """
    markup = render_or_fail(DERIVED_FIGURE)
    unavailable = component_chrome(LANGUAGE_ENGLISH)["unavailable"]
    assert unavailable in markup, "an absent field did not render the unavailable state"
    assert 'data-state="unavailable"' in markup, "the unavailable state carries no marker"
    empties = re.findall(r"<dd[^>]*>\s*</dd>", markup)
    assert not empties, f"{len(empties)} fields rendered as empty elements"


@RED
def test_an_absent_field_is_not_labelled_a_refusal() -> None:
    """FR-096a's last sentence: an absent field is not a refusal."""
    markup = render_or_fail(DERIVED_FIGURE)
    chrome = component_chrome(LANGUAGE_ENGLISH)
    assert chrome["unavailable"] != chrome["refusal_label"], (
        "the unavailable state reuses the refusal label"
    )
    assert "refused" not in markup, "the drawer marks an absent field with refusal styling"


# --------------------------------------------------------------------------
# FR-097 -- no per-figure population or basis
# --------------------------------------------------------------------------


@RED
def test_the_drawer_shows_no_per_figure_population_or_basis() -> None:
    """FR-097.

    A mapping carrying `population` and `basis` keys -- which no governed projection
    produces, and which a future one must not -- renders neither. The macro reads the
    keys it renders and nothing else, so an upstream field cannot leak onto the page.
    """
    smuggled = {**STORED_FIGURE, "population": "POP-LEAK", "basis": "BASIS-LEAK"}
    markup = render_or_fail(smuggled)
    assert "POP-LEAK" not in markup, "the drawer displayed a per-figure population"
    assert "BASIS-LEAK" not in markup, "the drawer displayed a per-figure basis"


# --------------------------------------------------------------------------
# FR-098 -- keyboard, with no script
# --------------------------------------------------------------------------


@RED
def test_the_drawer_opener_is_the_only_control_and_needs_no_script() -> None:
    """FR-098, as the plan's check 3 delivers it.

    A native `<details>` with a `<summary>` opener is reachable and dismissible from the
    keyboard, and the opener keeps focus when toggled, so focus "returns" to it by
    construction. That holds only if the summary is the drawer's *only* control: nothing
    in the body may carry `tabindex`, and no script may be involved.
    """
    markup = render_or_fail(STORED_FIGURE)
    assert re.search(r"<details[^>]*" + re.escape(DRAWER_MARKER), markup), (
        "the drawer is not a native disclosure element"
    )
    assert "<summary" in markup, "the drawer has no keyboard-reachable opener"
    assert "tabindex" not in markup, "the drawer body adds a focus stop"
    assert "<script" not in markup, "the drawer relies on a script"


# --------------------------------------------------------------------------
# FR-095a, FR-099 -- labels in both languages, and Arabic that is Arabic
# --------------------------------------------------------------------------


@RED
def test_the_drawer_chrome_labels_exist_in_both_languages() -> None:
    """FR-095a: the four labels the drawer needs, in both languages."""
    needed = {"drawer_open", "definition", "inputs", "unavailable"}
    for language in REQUIRED_LANGUAGES:
        missing = needed - set(component_chrome(language))
        assert not missing, f"drawer chrome missing in {language}: {sorted(missing)}"


@RED
def test_the_drawer_renders_in_both_languages() -> None:
    """FR-099: the Arabic drawer carries Arabic script, not English under an `ar` label."""
    english = render_or_fail(STORED_FIGURE, LANGUAGE_ENGLISH)
    arabic = render_or_fail(STORED_FIGURE, LANGUAGE_ARABIC)
    assert DRAWER_MARKER in english and DRAWER_MARKER in arabic
    labels_only = re.sub(r"<code>[^<]*</code>", "", arabic)
    assert ARABIC_SCRIPT.search(labels_only), "the Arabic drawer carries no Arabic script"


# --------------------------------------------------------------------------
# The fixture's honesty, and the line this slice holds
# --------------------------------------------------------------------------


@RED
def test_the_fixture_matches_the_projection_the_drawer_will_be_handed() -> None:
    """The plan's check 1: the fixture stands in for `_cited_figure`, so it must match it.

    The per-figure keys are read from the projection's source rather than restated, so a
    field added to or removed from `_cited_figure` fails here instead of leaving the
    drawer proven against a shape the supply slice no longer produces. The package-level
    coverage pair is the one addition, exactly as `CitationEvidenceResponse` carries it.

    RED until the drawer exists: a fixture proven honest for a component that is not
    there would report a green the plan has not earned.
    """
    source = inspect.getsource(_cited_figure)
    projected = set(re.findall(r'^\s+"([a-z_]+)":', source, re.M))
    assert projected, "no keys read from _cited_figure -- the guard is blind"
    package_level = {"coverage_manifest_identity", "coverage_signatures"}
    assert set(STORED_FIGURE) == projected | package_level, (
        f"fixture drifted from the projection: {set(STORED_FIGURE) ^ (projected | package_level)}"
    )
    render_or_fail(STORED_FIGURE)


def test_no_surface_places_the_drawer_before_its_supply_exists() -> None:
    """Not RED: the guard this slice holds until the supply slice deletes it.

    A drawer placed on a page with nothing supplying it renders every field unavailable
    -- and FR-096a's unavailable state means *the catalog declined to state this*, not
    *nothing was wired yet*. So no page template may call the macro until the supply
    exists. Enumerated from the directory, not a list; asserts the enumeration is
    non-empty; excludes only the component template, which defines the macro.
    """
    templates = [t for t in sorted(TEMPLATE_DIR.glob("*.j2")) if t.name != COMPONENTS_TEMPLATE]
    assert templates, f"no templates enumerated under {TEMPLATE_DIR} -- the guard is blind"
    placing = [t.name for t in templates if "evidence_drawer" in t.read_text(encoding="utf-8")]
    assert not placing, f"the drawer is placed before its supply exists: {placing}"
