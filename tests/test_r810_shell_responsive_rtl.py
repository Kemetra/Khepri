"""`U1` slice 8 -- the shell's responsive and right-to-left posture: `RCA-010` `FR-198`, `FR-199`.

**`FR-199` states its own premise, and it is true.** "The shell's stylesheets *currently contain no
physical directional property* and a slice under this document does not introduce one." So that half
is a **preservation** requirement by the specification's own words, and the work here is the
instrument, not a change. The same holds for `lang`/`dir`, `dir="auto"` and truncation: all three
already ship correctly, and what did not exist was anything that *fails* when they stop.

**Three of `FR-198`'s five named degradations are not this slice's to build**, and each is asserted
as an absence rather than faked:

- **A table** -- there is no `<table>` on any shell surface; breakdowns render as `<ul>`/`<li>`.
  "A table scrolls horizontally inside a focusable region" has nothing to scroll.
- **A chart** -- none on the shell, and `FR-198` writes the conditional itself: "a chart, **where
  one is present**". Charts are `RRA-015`'s.
- **A drawer's focus trap** -- the drawer is a native `<details>`/`<summary>` disclosure, which
  needs no trap because it is not a modal. A real trap needs JavaScript, and **`RCA-010` §Scope
  grants no JavaScript file and not the `shell_assets/` directory**. That is an *authority* limit,
  not a structural one -- see `test_the_shell_ships_no_script_by_choice_not_by_policy`.

**What runs where, stated because it decides what these guards are worth.** The repository marks
browser cases `@pytest.mark.browser`, and the marker's own description says they are "skipped when
it is not installed". CI runs `uv run pytest` with no browser install step, so **every browser case
skips in CI, including the pre-existing overflow assertion**. So this module puts as much of
`FR-198` and `FR-199` as possible into assertions that need **no browser** -- the absences, the
stylesheet scan, `lang`/`dir`, truncation and bilingual parity all run everywhere -- and keeps only
genuine layout questions behind the marker. `_launch_chromium` falls back to a browser found under
`PLAYWRIGHT_BROWSERS_PATH`, so the layout guards actually execute wherever a browser exists rather
than skipping silently on a version mismatch.
"""

from __future__ import annotations

import os
import re
from html.parser import HTMLParser
from importlib.resources import files
from pathlib import Path

import pytest

from khepri.rra.journey.security import SECURITY_HEADERS
from tests.test_r807_shell_quality import SHELL_SURFACES, _html, _without_comments

#: Widths that **bracket the shell's only breakpoint**, `max-width: 40rem` (640px), which
#: `workspace.css` uses three times (`:243`, `:327`, `:412`). The pre-existing case measures 1180
#: and 390 and so never measures *at* the switch, which is where a layout is likeliest to overflow.
_WIDTHS = (360, 639, 640, 641, 1024, 1440)

#: Physical directional properties `FR-199` forbids. `direction` is deliberately absent: it sets
#: the writing direction rather than a physical edge, and the two shipped uses are carved out below.
_PHYSICAL = (
    "left",
    "right",
    "margin-left",
    "margin-right",
    "padding-left",
    "padding-right",
    "border-left",
    "border-right",
    "float",
    "clear",
)

#: Matched at a **declaration boundary**, the idiom slice 5 established: a declaration follows `{`
#: or `;`, which occurs mid-line in a packed one-liner, so `.x { margin-left: 1rem }` is caught
#: while a selector merely containing the word is not.
_PHYSICAL_DECLARATION = re.compile(
    r"(?:[{;]\s*)(" + "|".join(_PHYSICAL) + r")\s*:",
)

#: `text-align: left|right` is physical; `start`/`end` are the logical forms.
_PHYSICAL_TEXT_ALIGN = re.compile(r"(?:[{;]\s*)text-align\s*:\s*(left|right)\b")

#: The two `direction: ltr` declarations reviewed and deliberately landed on `#377`:
#: `.change-transition` (`workspace.css:310`) and the `.decision-formula`/`.decision-citation`
#: pair (`:372`). A scan without these carves fires on working code, and the next slice narrows it
#: until it proves nothing -- the guard-that-disarms-itself failure.
_DIRECTION_EXEMPT = ("change-transition", "decision-formula", "decision-citation")

_SHELL_SHEETS = (
    ("khepri.rra.journey", ("assets", "shell.css")),
    ("khepri.rra.journey", ("assets", "shell-components.css")),
    ("khepri.runtime", ("shell_assets", "workspace.css")),
)

_TEMPLATE_PACKAGES = (("khepri.runtime", "shell_templates"), ("khepri.runtime", "legal_templates"))


def _sheet_sources() -> list[tuple[str, str]]:
    """Each shell sheet as `(name, comment-stripped text)`, each proven non-empty."""
    sources = []
    for package, parts in _SHELL_SHEETS:
        name = parts[-1]
        text = files(package).joinpath(*parts).read_text(encoding="utf-8")
        assert text.strip(), f"{name} is empty, so this scan proves nothing"
        sources.append((name, _without_comments(text, name)))
    assert len(sources) == len(_SHELL_SHEETS)
    return sources


def _templates() -> list[tuple[str, str]]:
    """Every template in both admitted directories, as `(name, source)`."""
    found = []
    for package, directory in _TEMPLATE_PACKAGES:
        for entry in files(package).joinpath(directory).iterdir():
            if entry.name.endswith(".html.j2"):
                text = entry.read_text(encoding="utf-8")
                assert text.strip(), f"{entry.name} is empty, so this scan proves nothing"
                found.append((f"{directory}/{entry.name}", text))
    assert found, "no templates found, so this scan proves nothing"
    return found


def _pinned_chromium() -> str | None:
    """A Chromium the pinned Playwright can drive, when the default lookup misses one.

    Without this the layout guards skip on a version mismatch between the installed
    Playwright and the browser build on disk, and a skipped guard proves nothing. The
    path is discovered under `PLAYWRIGHT_BROWSERS_PATH` rather than hard-coded.
    """
    root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if not root:
        return None
    found = sorted(Path(root).glob("chromium-*/chrome-linux/chrome"))
    return str(found[-1]) if found else None


def _launch_chromium(playwright: object) -> object:
    """The pinned Chromium, or `pytest.skip` when this machine genuinely has none."""
    from playwright.sync_api import Error

    try:
        return playwright.chromium.launch()  # type: ignore[attr-defined]
    except Error as error:
        executable = _pinned_chromium()
        if executable is None:
            pytest.skip(f"Pinned Chromium is unavailable: {error}")
        return playwright.chromium.launch(executable_path=executable)  # type: ignore[attr-defined]


def _shell_css() -> str:
    """The three sheets joined **in the order the page links them**.

    Follows `test_r807_shell_quality.py:404-430` exactly: the tokens declare the palette and
    the component layer consumes it, so injecting only part measures an unstyled document.
    """
    journey = files("khepri.rra.journey").joinpath("assets")
    return "\n".join(
        (
            journey.joinpath("shell.css").read_text(encoding="utf-8"),
            journey.joinpath("shell-components.css").read_text(encoding="utf-8"),
            files("khepri.runtime")
            .joinpath("shell_assets", "workspace.css")
            .read_text(encoding="utf-8"),
        )
    )


class _Elements(HTMLParser):
    """Every element as `(tag, attrs)`, with tag and attribute names normalized.

    **A parser rather than a regex, and the difference is not cosmetic.** A raw scan
    over template source reads one serialization of the markup: `<TABLE>` slips past a
    case-sensitive `<table\\b`, `class='chart'` past a double-quoted pattern, and
    `data-href=` matches a bare `href=` substring so an element that is not a link
    counts as an action. `HTMLParser` normalizes tag and attribute names to lowercase
    and hands back attributes as keys, so each guard asks its real question.

    Jinja control tags (`{% ... %}`) and expressions are text or attribute values to the
    parser, so template source parses without pre-rendering it.
    """

    def __init__(self) -> None:
        """Start with no elements collected."""
        super().__init__(convert_charrefs=True)
        self.elements: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record a start tag and its attributes."""
        self.elements.append((tag, dict(attrs)))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record a self-closing tag, which `handle_starttag` does not see."""
        self.elements.append((tag, dict(attrs)))


def _elements(markup: str) -> list[tuple[str, dict[str, str | None]]]:
    """Parse markup into `(tag, attrs)` pairs, tag and attribute names lowercased."""
    parser = _Elements()
    parser.feed(markup)
    parser.close()
    return parser.elements


def _classes_of(attrs: dict[str, str | None]) -> set[str]:
    """The element's class attribute as a set of lowercased tokens."""
    return set((attrs.get("class") or "").lower().split())


def _tags_named(markup: str, *names: str) -> list[str]:
    """Every tag in `names` this markup carries, parser-normalized."""
    wanted = {name.lower() for name in names}
    return [tag for tag, _attrs in _elements(markup) if tag in wanted]


def test_no_shell_surface_renders_a_table() -> None:
    """`FR-198`'s table degradation has no subject on this shell, asserted rather than assumed.

    "A table scrolls horizontally inside a focusable region with visible focus rather than
    collapsing into a card list that loses its column relationships." The shell renders its
    breakdowns as `<ul>`/`<li>` rows and carries no `<table>` at all, so there is nothing to
    scroll and driving the degradation would be a run that can only produce the null case.

    **NOT EXERCISED, not PASS.** The day a table arrives on a shell surface it arrives against
    this guard, which says the degradation is now owed and must be built.
    """
    offenders = [name for name, source in _templates() if _tags_named(source, "table")]
    assert offenders == [], (
        f"a table reached a shell surface, so FR-198's scroll degradation is now owed: {offenders}"
    )


def test_no_shell_surface_renders_a_chart() -> None:
    """`FR-198`'s chart degradation has no subject either, and the requirement says so.

    "A chart, **where one is present**, keeps full width with reduced label density and is never
    dropped." The conditional is in the requirement, and no chart is present: charts are
    `RRA-015`'s and live on the report surfaces, not the commercial shell.

    `FR-206` bars the shell from drawing one anyway -- no CSS illustration, no one-off inline SVG
    -- and slice 2b's `test_the_shell_component_layer_draws_no_artwork` is that instrument for the
    stylesheet. This asserts the template half.
    """
    offenders = [
        name
        for name, source in _templates()
        if _tags_named(source, "svg", "canvas")
        or any("chart" in _classes_of(attrs) for _tag, attrs in _elements(source))
    ]
    assert offenders == [], (
        f"a chart reached a shell surface, so FR-198's chart degradation is now owed: {offenders}"
    )


def test_the_drawer_stays_a_native_disclosure_needing_no_focus_trap() -> None:
    """`FR-198`'s drawer degradation is DEFERRED, and this pins why it is safe to defer.

    "A drawer becomes a full-screen sheet with focus trapped and restored on close." The shell's
    drawer is a native `<details>`/`<summary>` disclosure, which opens in place and is **not a
    modal**: it traps nothing because it captures nothing. A real full-screen sheet with a focus
    trap needs JavaScript, and `RCA-010` §Scope grants no JavaScript file and not the
    `shell_assets/` directory -- an **authority** limit, not a structural one.

    So this guard holds the drawer at the shape that needs no trap. A later slice that turns it
    into a scripted overlay fails here and is told, by that failure, that it owes the trap.
    """
    drawers = [
        (name, source)
        for name, source in _templates()
        if 'class="decision-drawer"' in source
    ]
    assert drawers, "no drawer found, so this guard proves nothing"
    for name, source in drawers:
        carriers = [
            tag for tag, attrs in _elements(source) if "decision-drawer" in _classes_of(attrs)
        ]
        assert carriers and set(carriers) == {"details"}, (
            f"{name}: the drawer is no longer a native <details> disclosure: {carriers}"
        )
        assert _tags_named(source, "summary"), f"{name}: the drawer lost its <summary> control"


def test_the_shell_ships_no_script_by_choice_not_by_policy() -> None:
    """The shell carries no script -- and the reason is **choice**, not prohibition.

    **This corrects a claim slice 5 shipped.** `test_r808_shell_state_grammar.py` asserted that
    the shell's `default-src 'none'` CSP "forbids the script a client-side loading affordance
    would need". It does not. The shipped policy is
    `default-src 'none'; script-src 'self'; style-src 'self'; ...` and **`script-src 'self'`
    explicitly permits same-origin script** -- `default-src` is only the fallback for directives
    not otherwise named. The journey ships five `.js` files under that identical policy.

    The true invariant is narrower and honest: the commercial shell ships **no script at all**,
    by choice, and this guard is what keeps that true. A guard resting on a false reason invites
    the next author to "fix" the CSP, which `FR-206` forbids and which would not be the problem.
    """
    assert "script-src 'self'" in SECURITY_HEADERS["Content-Security-Policy"], (
        "the policy no longer permits same-origin script, so this test's premise has changed"
    )
    offenders = [name for name, source in _templates() if _tags_named(source, "script")]
    assert offenders == [], f"a script reached a shell surface: {offenders}"


def test_the_shell_stylesheets_use_no_physical_directional_property() -> None:
    """`FR-199`: "right-to-left presentation is built from **logical CSS properties only**".

    The requirement states its own premise -- the sheets "currently contain no physical
    directional property and a slice under this document does not introduce one" -- so this is a
    **preservation** guard and passes on arrival. Its value is the mutation record.

    `direction` is **not** scanned as physical: it sets the writing direction rather than a
    physical edge, and the two shipped uses are `.change-transition` and the
    `.decision-formula`/`.decision-citation` pair, reviewed and deliberately landed on `#377` to
    hold an LTR run of digits inside Arabic prose. They are carved out by name in
    `test_only_the_reviewed_direction_declarations_ship`, so the exemption is stated rather than
    silently folded into this scan.
    """
    offenders = []
    for name, css in _sheet_sources():
        offenders += [f"{name}: {match.group(1)}" for match in _PHYSICAL_DECLARATION.finditer(css)]
        offenders += [
            f"{name}: text-align: {match.group(1)}" for match in _PHYSICAL_TEXT_ALIGN.finditer(css)
        ]
    assert offenders == [], "a physical directional property reached a shell sheet:\n" + "\n".join(
        offenders
    )


def test_only_the_reviewed_direction_declarations_ship() -> None:
    """The `direction: ltr` carve-out, held to exactly the two the review landed.

    Without this the exemption above is a blanket: any new `direction` declaration would inherit
    a justification written for two specific, reviewed lines. Counted and attributed, so a third
    one fails here and has to be argued for on its own terms rather than riding `#377`.
    """
    found = []
    for name, css in _sheet_sources():
        for match in re.finditer(r"([^{}]*)\{([^{}]*)\}", css):
            values = re.findall(r"(?:[{;]\s*)direction\s*:\s*([a-z-]+)", "{" + match.group(2))
            if values:
                found.append((name, match.group(1).strip(), values))

    assert found, "no direction declaration found at all, so the carve-out proves nothing"

    unreviewed = []
    for name, selector, values in found:
        # **Every part of a grouped selector must be named.** Substring containment on
        # the whole selector lets `.change-transition, .new` carry `.new` in on the
        # exemption -- the carve-out becoming a hole, which is the failure this guard
        # exists to prevent.
        parts = [part.strip() for part in selector.split(",") if part.strip()]
        if not all(any(exempt in part for exempt in _DIRECTION_EXEMPT) for part in parts):
            unreviewed.append(f"{name}: {selector!r} is not the reviewed set")
        # And the exemption is for `ltr` specifically: `#377` landed an LTR run of
        # digits inside Arabic prose, which is not a licence for any direction at all.
        if any(value != "ltr" for value in values):
            unreviewed.append(f"{name}: {selector!r} declares direction {values}, not ltr")

    assert unreviewed == [], (
        f"a direction declaration ships that review #377 did not land: {unreviewed}"
    )


@pytest.mark.parametrize("language", ("en", "ar"))
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_lang_and_dir_are_server_computed(surface: str, language: str) -> None:
    """`FR-199`: "`lang` and `dir` remain server-computed and are never inferred in a template"."""
    markup = _html(surface, language)
    assert f'lang="{language}"' in markup, f"{surface} did not carry lang={language}"
    assert f'dir="{"rtl" if language == "ar" else "ltr"}"' in markup, (
        f"{surface} did not carry the direction its language implies"
    )


def test_the_template_infers_neither_lang_nor_dir() -> None:
    """`FR-199`, the other half: the values come from context, never a template-side guess.

    A template that wrote `dir="rtl"` behind `{% if language == 'ar' %}` would satisfy the
    rendered assertion above while moving the decision into the presentation layer, which is what
    "never inferred in a template" forbids.
    """
    frame = next(source for name, source in _templates() if name.endswith("shell.html.j2"))
    html_tag = re.search(r"<html[^>]*>", frame)
    assert html_tag is not None, "the frame no longer opens an <html> element"
    assert 'lang="{{ language }}"' in html_tag.group(0), "lang is not taken from context"
    assert 'dir="{{ direction }}"' in html_tag.group(0), "dir is not taken from context"


def test_customer_controlled_values_carry_dir_auto() -> None:
    """`FR-199`: "`dir="auto"` continues to isolate customer-controlled mixed-script values".

    The organization name is the customer-controlled string on the frame, and a Latin run inside
    Arabic prose needs its own direction or it reorders around the surrounding text.
    """
    frame = next(source for name, source in _templates() if name.endswith("shell.html.j2"))
    name_span = re.search(r'<span id="frame-organization-name"[^>]*>', frame)
    assert name_span is not None, "the organization name span is gone"
    assert 'dir="auto"' in name_span.group(0), (
        "the customer-controlled organization name lost its direction isolation"
    )


def test_truncation_keeps_the_full_value_in_the_dom() -> None:
    """`FR-199`: truncation is visual only, "with the full value retained in the DOM".

    A `text-overflow: ellipsis` rule shortens what is painted and leaves the text node whole, so
    the accessible name stays complete. What would break the requirement is truncating in the
    template -- a Jinja `|truncate` on a value the reader needs -- which this asserts against.
    """
    ellipsis = [name for name, css in _sheet_sources() if "text-overflow" in css]
    assert ellipsis, "no visual truncation found, so this guard proves nothing"

    offenders = [
        name for name, source in _templates() if re.search(r"\|\s*truncate\b", source)
    ]
    assert offenders == [], (
        f"a template truncates a value, so the accessible name is no longer complete: {offenders}"
    )


@pytest.mark.browser
@pytest.mark.parametrize("language", ("en", "ar"))
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_no_shell_surface_overflows_at_any_supported_width(surface: str, language: str) -> None:
    """`FR-198`: "There is no page-level horizontal overflow at **any supported width**".

    **Extends `test_shell_surfaces_are_operable_at_every_viewport`, never duplicates it.** That
    case measures 1180 and 390 and owns the target-size and `dir` assertions; this one measures
    the widths that **bracket the shell's only breakpoint**, `max-width: 40rem`, which
    `workspace.css` uses at `:243`, `:327` and `:412`. 639 / 640 / 641 sit either side of the
    switch, which is exactly where a layout that reflows is likeliest to overflow and is the one
    place two fixed viewports can never look.

    Every scrolling region must be explicit and bounded: a page that scrolls sideways has an
    unbounded one somewhere.
    """
    from playwright.sync_api import sync_playwright

    markup = _html(surface, language)
    css = _shell_css()
    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": _WIDTHS[0], "height": 900})
            page.set_content(markup, wait_until="domcontentloaded")
            page.add_style_tag(content=css)
            for width in _WIDTHS:
                page.set_viewport_size({"width": width, "height": 900})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                    f"{surface} overflows horizontally at {width}px in {language}"
                )
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("width", (360, 1024))
def test_the_trust_state_stays_adjacent_to_its_figure(width: int) -> None:
    """`FR-198`: "trust state stays adjacent to its figure at every width".

    Adjacency is asserted as **containment in the same card**, not as pixel proximity: at 360px
    `.decision-entry` becomes a column (`workspace.css:412`), so the availability moves *below*
    the figure rather than beside it, and a distance check would fail on correct reflow. What
    must not happen is the trust state leaving the card that carries the figure it qualifies --
    `FR-161`'s "reachable from the surface carrying the figure they qualify".
    """
    from playwright.sync_api import sync_playwright

    from tests.test_r808_shell_state_grammar import _admitted_surface, _rendered

    markup = _rendered(_admitted_surface(), "en")
    css = _shell_css()
    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.set_content(markup, wait_until="domcontentloaded")
            page.add_style_tag(content=css)
            # Paired with the figure, not merely inside some card. Each card carries
            # exactly one `.decision-value`, so "the closest card holds one figure" is
            # the pairing -- and it needs no identifier added to production markup,
            # which this slice has no authority to change.
            qualified = page.evaluate(
                "Array.from(document.querySelectorAll('.decision-availability')).map(s => {"
                "  const card = s.closest('.decision-card');"
                "  return card === null"
                "    ? 0"
                "    : card.querySelectorAll('.decision-value').length;"
                "})"
            )
            assert qualified, f"no trust state rendered at {width}px, so this proves nothing"
            assert all(count == 1 for count in qualified), (
                f"a trust state is not paired with exactly one figure at {width}px: {qualified}"
            )
        finally:
            browser.close()


#: What `FR-199` requires to be present in both languages or neither: "a caveat, refusal,
#: evidence link, state, or action present in one language is present in the other". Counted by
#: **class**, never by text -- the text is precisely what differs between them.
_PARITY_CLASSES = (
    "decision-caveats",
    "decision-refusal",
    "decision-unsupported",
    "compare-refusal",
    "decision-empty",
    "decision-unavailable",
    "decision-absence",
    "decision-evidence-absent",
    "decision-evidence-unavailable",
    "decision-drawer",
    "decision-availability",
    "empty-state",
)


def _class_census(markup: str) -> dict[str, int]:
    """How many elements carry each parity-bearing class, by parsed class token.

    Tokenized rather than substring-matched, so `class='decision-empty'` and a
    differently cased attribute are counted the same as the shipped spelling.
    """
    carried = [_classes_of(attrs) for _tag, attrs in _elements(markup)]
    return {name: sum(name in classes for classes in carried) for name in _PARITY_CLASSES}


def _action_census(markup: str) -> tuple[int, int]:
    """How many actions the surface offers: anchors with an address, and buttons.

    **`href` is read as a parsed attribute, never as a substring.** `data-href=`
    contains the text `href=`, so a substring test counts an element that is not a link
    at all -- and a parity comparison built on that count could balance a real anchor in
    one language against a `data-href` carrier in the other.
    """
    anchors = [attrs for tag, attrs in _elements(markup) if tag == "a" and "href" in attrs]
    return (len(anchors), len(_tags_named(markup, "button")))


@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_every_governed_element_is_present_in_both_languages(surface: str) -> None:
    """`FR-199`: a caveat, refusal, evidence link, state or action in one language is in the other.

    **Counted by class, never by text.** The words are what a translation changes; what must not
    change is which governed elements exist. A surface offering an evidence drawer in English and
    not in Arabic would be a capability difference dressed as a translation gap, and comparing
    rendered sentences could never see it.

    Actions are counted beside the classes because `FR-199` names them explicitly: an anchor with
    an address, and a button. `test_every_surface_renders_in_both_languages`
    (`test_r807_shell_quality.py`) already asserts the two renders *differ*; this asserts what
    must stay the same underneath that difference.
    """
    english = _html(surface, "en")
    arabic = _html(surface, "ar")

    assert _class_census(english) == _class_census(arabic), (
        f"{surface} offers different governed elements per language: "
        f"en={_class_census(english)} ar={_class_census(arabic)}"
    )
    assert _action_census(english) == _action_census(arabic), (
        f"{surface} offers a different number of actions per language: "
        f"en={_action_census(english)} ar={_action_census(arabic)}"
    )
