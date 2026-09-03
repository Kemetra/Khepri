"""U1-04: the evidence drawer's structure, proven against the projection it will be handed.

These began as the RED tests `#351` landed, every one `xfail(strict=True)`; the strict
marker did its job and the markers came off when the macro landed. Each docstring still
says what the test waited for.

**The drawer is driven directly, through the production environment with the real
chrome**, so its structure is proven independently of any page. Its placement beside each
evidence figure row is `test_u1_04_drawer_placement`'s subject, and its data supply is
`RRA-013`'s; coverage reaches it as its own argument because `RRA-013` FR-104 forbids
copying it into an entry.

Plan: `docs/superpowers/plans/2026-09-02-u1-04-evidence-drawer-plan.md`.
Authority: active `RRA-012` FR-096, FR-096a, FR-097, FR-098.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from jinja2 import TemplateError

from khepri.rra.bundle import CitedEvidence
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.rendering.html import _CHROME, build_environment
from khepri.rra.rendering.wording import component_chrome

TEMPLATE_DIR = Path("src/khepri/rra/rendering/templates")
COMPONENTS_TEMPLATE = "_components.html.j2"
DRAWER_MARKER = 'data-component="evidence-drawer"'
ARABIC_SCRIPT = re.compile(r"[\u0600-\u06ff]")

#: The projection `report_api._cited_figure` builds, for a **stored** fact -- one the
#: package retains, so `precision` and `inputs` are present. Package-level coverage
#: travels beside it exactly as `CitationEvidenceResponse` carries it.
STORED_FIGURE = {
    "citation_id": "fact-stored-0001",
    "metric": "revenue",
    "formula_version": "rra004.formula.v1",
    "definition": "Total value of admitted sale rows in the period.",
    "unit_kind": "money",
    "precision": 2,
    "inputs": ["amount", "quantity"],
}

#: The bundle-level coverage the audit context carries once (`RRA-013` FR-104/FR-106),
#: handed to the drawer separately from any entry.
COVERAGE = {"manifest_identity": "coverage-manifest-7f3a", "signatures": ["sig-a", "sig-b"]}

#: No manifest at all: the package attests no coverage, so both fields are absent.
ABSENT_COVERAGE = {"manifest_identity": None, "signatures": []}

#: The same projection for a **derived** analysis figure. `_cited_figure`'s docstring:
#: precision and inputs are "absent, not empty and not recomputed". FR-096a is about
#: exactly this mapping.
DERIVED_FIGURE = {
    **STORED_FIGURE,
    "citation_id": "fact-derived-0002",
    "metric": "revenue_change",
    "precision": None,
    "inputs": None,
}

#: The five FR-096 fields, by **every** value the drawer must show for `STORED_FIGURE`.
#: Every input and every coverage value, not one representative each: a drawer
#: rendering the first input only would pass a single-value check (`#351` review).
GIVEN_FIELDS: dict[str, tuple[str, ...]] = {
    "definition": (STORED_FIGURE["definition"],),
    "version": (STORED_FIGURE["formula_version"],),
    "inputs": tuple(STORED_FIGURE["inputs"]),
    "coverage": (COVERAGE["manifest_identity"], *COVERAGE["signatures"]),
    "citation": (STORED_FIGURE["citation_id"],),
}

#: The fields `DERIVED_FIGURE` leaves absent, each checked on its own (`#351` review):
#: a drawer stating one as unavailable and the other as blank would pass a global check.
ABSENT_FIELDS = ("inputs", "coverage", "coverage_signatures")

#: A manifest that covers none of the package's admitted event kinds or statuses:
#: `_signatures_of` returns no signatures while the identity stays populated.
UNPROVEN_COVERAGE = {**COVERAGE, "signatures": []}


def render_drawer(
    given: dict[str, object],
    language: str = LANGUAGE_ENGLISH,
    *,
    coverage: dict[str, object] = COVERAGE,
    open: bool = False,
) -> str:
    """The drawer alone, in the production environment, with the real chrome."""
    template = build_environment().from_string(
        f'{{% from "{COMPONENTS_TEMPLATE}" import evidence_drawer %}}'
        "{{ evidence_drawer(given, chrome, coverage, open=open) }}"
    )
    return template.render(given=given, chrome=_CHROME[language], coverage=coverage, open=open)


def render_or_fail(
    given: dict[str, object],
    language: str = LANGUAGE_ENGLISH,
    *,
    coverage: dict[str, object] = COVERAGE,
) -> str:
    """Render, and turn a missing macro or label into a test failure with the cause."""
    try:
        return render_drawer(given, language, coverage=coverage)
    except TemplateError as error:  # pragma: no cover - a missing macro or label
        pytest.fail(f"the drawer cannot render: {error}")


# --------------------------------------------------------------------------
# FR-096 -- one drawer, rendering the five fields it is given
# --------------------------------------------------------------------------


def test_the_drawer_component_exists() -> None:
    """The macro is importable from the component template and carries its marker."""
    markup = render_or_fail(STORED_FIGURE)
    assert DRAWER_MARKER in markup, "the drawer renders without its component marker"


@pytest.mark.parametrize("field", sorted(GIVEN_FIELDS))
def test_the_drawer_renders_every_given_field(field: str) -> None:
    """FR-096, per field.

    Parametrized so an implementation carrying three of the five fields reports which two
    are missing rather than one failure. The value asserted is the one handed in, so a
    field that renders a label with no value fails too.
    """
    markup = render_or_fail(STORED_FIGURE)
    missing = [value for value in GIVEN_FIELDS[field] if value not in markup]
    assert not missing, f"the drawer drops {field} values it was given: {missing}"


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


def field_value(markup: str, label: str) -> str:
    """The `<dd>` that follows the `<dt>` carrying this label, tag and all."""
    match = re.search(r"<dt>" + re.escape(label) + r"</dt>\s*(<dd[^>]*>.*?</dd>)", markup, re.S)
    assert match, f"no field labelled {label!r} in the drawer"
    return match.group(1)


@pytest.mark.parametrize("field", ABSENT_FIELDS)
def test_an_absent_field_renders_the_unavailable_state(field: str) -> None:
    """FR-096a, per absent field.

    Driven by the derived-family shape whose `inputs` and coverage the catalog returns
    as `None`. Each absent field's own `<dd>` must carry the governed unavailable word
    and its marker -- a global check would pass a drawer that stated one field
    unavailable and left the other blank (`#351` review). No field anywhere in the
    drawer may be an empty element.
    """
    markup = render_or_fail(DERIVED_FIGURE, coverage=ABSENT_COVERAGE)
    chrome = component_chrome(LANGUAGE_ENGLISH)
    value = field_value(markup, chrome[field])
    assert chrome["unavailable"] in value, f"absent {field} did not render the unavailable state"
    assert 'data-state="unavailable"' in value, f"absent {field} carries no unavailable marker"
    empties = re.findall(r"<dd[^>]*>\s*</dd>", markup)
    assert not empties, f"{len(empties)} fields rendered as empty elements"


def test_an_absent_field_is_not_labelled_a_refusal() -> None:
    """FR-096a's last sentence: an absent field is not a refusal."""
    markup = render_or_fail(DERIVED_FIGURE, coverage=ABSENT_COVERAGE)
    chrome = component_chrome(LANGUAGE_ENGLISH)
    assert chrome["unavailable"] != chrome["refusal_label"], (
        "the unavailable state reuses the refusal label"
    )
    assert "refused" not in markup, "the drawer marks an absent field with refusal styling"


# --------------------------------------------------------------------------
# FR-097 -- no per-figure population or basis
# --------------------------------------------------------------------------


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


def test_a_manifest_with_no_compatible_signature_is_stated_not_implied() -> None:
    """Unproven coverage must not look present (`#352` review).

    A manifest identity can be populated while `coverage_signatures` is empty -- the
    manifest covered none of the package's admitted event kinds or statuses. The
    identity is still a fact and renders; the signatures field must say so in words
    rather than trail off. Empty is a different finding from absent, so it is not the
    unavailable state either.
    """
    markup = render_or_fail(STORED_FIGURE, coverage=UNPROVEN_COVERAGE)
    chrome = component_chrome(LANGUAGE_ENGLISH)
    signatures = field_value(markup, chrome["coverage_signatures"])
    assert _CHROME[LANGUAGE_ENGLISH]["none"] in signatures, "empty signatures rendered as nothing"
    assert 'data-state="none"' in signatures, "the empty signature state carries no marker"
    assert chrome["unavailable"] not in signatures, "empty signatures were called unavailable"
    identity = field_value(markup, chrome["coverage"])
    assert COVERAGE["manifest_identity"] in identity


def test_the_drawer_opens_for_paper_and_stays_closed_on_the_web() -> None:
    """A closed `<details>` prints collapsed (`#352` review).

    The print surface will pass `open=true` so the printed appendix carries the evidence
    and not only the opener; the web leaves the default so a reader opens what they want.
    Asserted on the element's attribute, which is the only thing that expands it -- no
    stylesheet can.
    """
    closed = render_or_fail(STORED_FIGURE)
    opened = render_drawer(STORED_FIGURE, open=True)
    assert re.search(r"<details[^>]*\sopen[\s>]", opened), "open=true did not expand the drawer"
    assert not re.search(r"<details[^>]*\sopen[\s>]", closed), "the drawer is open by default"


# --------------------------------------------------------------------------
# FR-095a, FR-099 -- labels in both languages, and Arabic that is Arabic
# --------------------------------------------------------------------------


def test_the_drawer_chrome_labels_exist_in_both_languages() -> None:
    """FR-095a: the four labels the drawer needs, in both languages."""
    needed = {"drawer_open", "definition", "inputs", "unavailable", "coverage_signatures"}
    for language in REQUIRED_LANGUAGES:
        missing = needed - set(component_chrome(language))
        assert not missing, f"drawer chrome missing in {language}: {sorted(missing)}"


def test_the_drawer_renders_in_both_languages() -> None:
    """FR-099: the Arabic drawer carries Arabic script, not English under an `ar` label."""
    english = render_or_fail(STORED_FIGURE, LANGUAGE_ENGLISH)
    arabic = render_or_fail(DERIVED_FIGURE, LANGUAGE_ARABIC, coverage=ABSENT_COVERAGE)
    assert DRAWER_MARKER in english and DRAWER_MARKER in arabic
    # Every label the drawer authors, checked one by one rather than "Arabic appears
    # somewhere": an Arabic opener over English field labels would pass a page-level
    # search (`#351` review). The derived shape is used so the unavailable state is
    # among the words checked.
    labels = re.findall(r"<summary[^>]*>([^<]*)</summary>|<dt>([^<]*)</dt>", arabic)
    words = [opener or label for opener, label in labels]
    words += re.findall(r'<dd data-state="unavailable">([^<]*)</dd>', arabic)
    words += re.findall(r'class="version-label__name">([^<]*)<', arabic)
    assert len(words) >= 8, f"too few drawer labels found to judge parity: {words}"
    not_arabic = [word for word in words if not ARABIC_SCRIPT.search(word)]
    assert not not_arabic, f"drawer labels not in Arabic: {not_arabic}"


# --------------------------------------------------------------------------
# The fixture's honesty, and the line this slice holds
# --------------------------------------------------------------------------


def test_the_fixture_matches_the_projection_the_drawer_will_be_handed() -> None:
    """The fixture stands in for the audit context's evidence entry, so it must match it.

    The per-figure keys are read from `CitedEvidence.as_entry` -- the projection
    `RRA-013` supplies and the evidence region hands the drawer -- rather than restated,
    so a field added to or removed from it fails here instead of leaving the drawer
    proven against a shape no page produces. Coverage is not among them: `RRA-013`
    carries it once at bundle level and the drawer takes it separately.

    The render at the end ties the fixture to the macro, so a fixture proven honest for
    a component that is not there cannot report a green the plan has not earned.
    """
    projected = set(
        CitedEvidence(
            citation_id="c",
            metric="m",
            unit_kind="u",
            formula_version="v",
            precision=None,
            inputs=None,
        ).as_entry("d")
    )
    assert projected, "no keys read from the evidence entry -- the guard is blind"
    assert set(STORED_FIGURE) == projected, (
        f"fixture drifted from the projection: {set(STORED_FIGURE) ^ projected}"
    )
    render_or_fail(STORED_FIGURE)
