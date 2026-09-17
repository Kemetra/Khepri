"""`U1-05` navigation and filter presentation: the guards the shell never had.

`RCA-010` `FR-193`-`FR-197`, presenting `RCA-008` `FR-166` and `RCA-002`
`FR-047`/`FR-049`/`FR-055` without redefining any of them.

**The navigation was correct and completely unguarded.** Before this module, `grep`
for `aria-current`, `frame-surfaces` or `destinations` across `tests/` returned
nothing: no test asserted the navigation's extent, which entry is current, or that a
surface the shell does not serve stays out of it. The markup at `shell.html.j2:73-77`
was right and nothing held it there. So this module is almost all assertion and
almost no new behaviour.

**Separate from `test_r807_shell_quality.py`, which is already 788 lines.** CodeScene
gates a module at 600 lines and four responsibilities; adding a fifth subject to a
module already over the line would worsen a failing metric. Fixtures are imported
from it rather than copied -- a near-duplicate fixture trips Low Cohesion on its own.

**Two things here are pinned rather than built, and a naive guard would break both.**
There are two `<nav>` elements on the decision surface and that is correct: one is
the surface navigation carrying `aria-current="page"`, the other a distinctly
labelled source selector carrying `aria-current="true"` for a non-page selection. And
`analysis.html.j2` renders two `aria-hidden` arrow glyphs that are change separators,
not navigation affordances. A guard counting `<nav>` elements, or scanning whole
templates for glyphs, would fire on reviewed behaviour and send an implementer to
delete it.
"""

from __future__ import annotations

import re
from importlib.resources import files

from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.runtime.shell_frame import (
    _ANALYSES_DESTINATION,
    _TEAM_DESTINATION,
    _WORKSPACE_DESTINATIONS,
)
from tests.test_r807_shell_quality import SHELL_SURFACES, _html

#: The destinations the frame may name, read from the module that decides them.
#:
#: **This is the independent source, and the allocation plan was wrong to say none
#: exists.** `shell_frame.py` holds the roster -- its own comment says it is decided
#: "here and nowhere else" -- and `RCA-010` §Scope never names that file, so a slice
#: under this specification can read it and cannot edit it. That is the same property
#: that makes `GOVERNED_CHART_KINDS` a valid expectation on the `RRA` side, and it is
#: stronger evidence than the reviewed literal the allocation plan prescribed.
#:
#: `SURFACE_VIEWS` is deliberately NOT used: it holds seven semantic views against
#: four shell surfaces, and asserting one as the other is a real signal at the wrong
#: granularity.
_FRAME_ROSTER = (*_WORKSPACE_DESTINATIONS, _ANALYSES_DESTINATION, _TEAM_DESTINATION)

#: Surfaces that render the frame's navigation. `unavailable`, `no_membership` and
#: `switcher` deliberately do not: there is no resolved organization to navigate
#: within, which `shell.html.j2` decides and this module only observes.
_NAVIGATING_SURFACES = (
    "overview",
    "data",
    "analyses",
    "analysis",
    "team",
    "decision",
    "compare",
)

#: Glyphs that cannot mirror, so none may serve as a navigation affordance
#: (`FR-194`: "an arrow does not mirror").
_DIRECTIONAL_GLYPHS = "←→↑↓⇐⇒⇑⇓‹›«»"


def _navigation_regions(markup: str) -> list[str]:
    """Every `<nav>` subtree, which is where `FR-194`'s glyph rule applies.

    Scoped deliberately. `analysis.html.j2` renders two `aria-hidden` `→` change
    separators that are `FR-194`-compliant -- they are not navigation affordances,
    and they are the documented reason `.change-transition` pins `direction: ltr`
    (review on `#377`). A template-wide scan fires on them and sends a slice to
    break reviewed behaviour.
    """
    return re.findall(r"<nav\b.*?</nav>", markup, flags=re.DOTALL)


def _destination_tails(markup: str) -> list[str]:
    """The destinations the navigation names, **in the order it renders them**.

    A list rather than a set, deliberately. `shell_frame.py:110-114` builds the roster
    as an ordered tuple and `FR-121` fixes that order, so a set comparison would admit
    a navigation that shuffled its entries, named one twice, or dropped a duplicate --
    three defects a reader would see immediately and the assertion would not.
    """
    return [
        tail
        for region in _navigation_regions(markup)
        for tail in re.findall(r'href="[^"]*?/([a-z-]+)"', region)
    ]


def _current_page_count(markup: str) -> int:
    return len(re.findall(r'aria-current="page"', markup))


def test_the_navigation_names_exactly_the_frames_roster() -> None:
    """`FR-193`, `FR-194`: the extent, against a source this slice cannot edit.

    Equality plus non-empty, never `>=`: a membership check that only ever weakens
    cannot see a destination added. The comparison is **ordered**: `FR-121` fixes the
    sequence and `shell_frame.py:110-114` renders it from an ordered tuple, so a set
    would admit a shuffled navigation as equal to a correct one.
    """
    assert _FRAME_ROSTER, "an empty roster would satisfy any subset claim"

    markup = _html("overview", LANGUAGE_ENGLISH)
    regions = _navigation_regions(markup)
    assert regions, "no navigation rendered, so this test proves nothing"

    rendered = _destination_tails(markup)
    ordered = [destination for _label, destination in _FRAME_ROSTER]
    assert rendered == ordered, f"navigation renders {rendered}, roster is {ordered}"
    expected = set(ordered)

    # **The assertion above is two-sided drift detection, not independence, and
    # saying so is the point.** The template renders whatever `shell_frame.py`
    # computes, so dropping a destination from the roster moves BOTH sides together
    # and the equality still holds -- verified by mutation, which passed. It catches
    # a template that stops rendering what the roster names, which is real drift, and
    # it cannot catch the roster itself shrinking.
    #
    # What does catch that is the templates on disk: a destination the navigation
    # names must have a template that renders it, and `shell_templates/` is a
    # directory no roster derives from. A roster shrunk by one leaves a template with
    # no entry pointing at it.
    templates = {
        entry.name.removesuffix(".html.j2")
        for entry in files("khepri.runtime").joinpath("shell_templates").iterdir()
        if entry.name.endswith(".html.j2")
    }
    assert templates, "no templates found, so this half proves nothing"
    missing = sorted(expected - templates)
    assert missing == [], f"navigation names a destination with no template: {missing}"

    # Every destination-shaped template is named by the navigation. The exemptions
    # are stated rather than inferred: the frame itself, two partials, the print
    # surface, the POST-only result, and the surfaces reachable without a resolved
    # organization. A template added outside those fails here, which is what makes
    # this the independent half.
    exempt = {
        "shell",
        "_decision_cards",
        "_decision_sections",
        "decision_print",
        "invitation_issued",
        "no_membership",
        "switcher",
        "unavailable",
        "analysis",
        "decision",
        "compare",
    }
    unnamed = sorted(templates - expected - exempt)
    assert unnamed == [], f"a destination-shaped template is in no navigation: {unnamed}"


def test_at_most_one_entry_claims_to_be_the_current_page() -> None:
    """`FR-194` and §D.3 rule 3: a cardinality rule on nav ITEMS, not on surfaces.

    "`aria-current="page"` on exactly one nav item" forbids two entries both claiming
    to be current. It does not assert every surface is a destination -- and three are
    not. `analysis`, `decision` and `compare` are detail surfaces reached THROUGH a
    destination, and none appears in `shell_frame.py`'s roster, so marking one current
    would tell a screen-reader user they are on Analyses when they are on one
    analysis. A false "you are here" is worse than none.

    So: never more than one, anywhere; and exactly one on each surface the roster
    names. The `== 1` set is derived from `_FRAME_ROSTER` rather than listed, so it
    stays tied to the independent source.

    **An earlier form of this test asserted `== 1` everywhere and failed on three
    surfaces.** The test was wrong, not the markup -- recorded because the failure
    looked like a defect, and reading §D.3 against the tree is what settled it.
    """
    destinations = {destination for _label, destination in _FRAME_ROSTER}
    assert destinations, "an empty roster would make the second claim vacuous"

    for surface in _NAVIGATING_SURFACES:
        count = _current_page_count(_html(surface, LANGUAGE_ENGLISH))
        assert count <= 1, f"{surface} marks {count} entries as the current page"
        if surface in destinations:
            assert count == 1, f"{surface} is a destination and marks none current"


def test_every_navigation_landmark_says_what_it_is_for() -> None:
    """`FR-194` and master specification §D.3: a second landmark must be named.

    This is what admits the decision surface's source selector without admitting a
    duplicated navigation: two `<nav>`s are fine when their accessible names differ,
    and two with the same name are indistinguishable to a screen-reader user.
    """
    for surface in _NAVIGATING_SURFACES:
        regions = _navigation_regions(_html(surface, LANGUAGE_ENGLISH))
        assert regions, f"{surface} renders no navigation"
        labels = [
            match.group(1)
            for region in regions
            if (match := re.search(r'aria-label="([^"]*)"', region))
        ]
        assert len(labels) == len(regions), f"{surface} has an unlabelled landmark"
        assert all(label.strip() for label in labels), f"{surface} has a blank label"
        assert len(set(labels)) == len(labels), f"{surface} reuses a landmark name"


def test_no_navigation_region_carries_a_directional_glyph() -> None:
    """`FR-194`: "no literal directional glyph ... because an arrow does not mirror".

    Scoped to navigation regions. The two `aria-hidden` arrows in `analysis.html.j2`
    are change separators and stay -- the next test pins that, so the scope of this
    guard is itself asserted rather than left to a reader's judgement.
    """
    for surface in _NAVIGATING_SURFACES:
        for region in _navigation_regions(_html(surface, LANGUAGE_ENGLISH)):
            found = [glyph for glyph in _DIRECTIONAL_GLYPHS if glyph in region]
            assert found == [], f"{surface} navigation carries {found}"


def test_the_change_arrows_survive_the_glyph_rule() -> None:
    """The scope of the guard above, pinned.

    `analysis.html.j2` renders `<span class="change-arrow" aria-hidden="true">→</span>`
    twice. They are `FR-194`-compliant: change separators inside a transition row,
    not navigation affordances, hidden from assistive technology, and the documented
    reason `.change-transition` pins `direction: ltr` (review on `#377`).

    Asserting they are *present* is what stops a later slice widening the glyph scan
    to whole templates and then "fixing" reviewed behaviour to satisfy it.
    """
    markup = _html("analysis", LANGUAGE_ENGLISH)
    arrows = re.findall(
        r'<span\b[^>]*class="[^"]*\bchange-arrow\b[^"]*"[^>]*>.*?</span>',
        markup,
        flags=re.DOTALL,
    )
    # Both of them, and each one's hidden state. A substring check for the class and
    # a separate one for the glyph pass with one arrow deleted, or with `aria-hidden`
    # stripped off the pair -- the glyph would still be somewhere in the markup and
    # the class would still be on something. Neither is what this test claims to pin.
    assert len(arrows) == 2, f"expected two change separators, found {len(arrows)}"
    for arrow in arrows:
        assert "→" in arrow, f"a change separator lost its glyph: {arrow}"
        assert 'aria-hidden="true"' in arrow, (
            f"a change separator is exposed to assistive technology: {arrow}"
        )
    for region in _navigation_regions(markup):
        assert "change-arrow" not in region, "a change separator is not navigation"


def test_no_navigation_entry_is_a_promise() -> None:
    """`FR-193`: no "coming soon", no disabled control standing in for a surface.

    The interface never invents capability. A destination enters navigation in the
    slice that implements it, so an entry that cannot be followed is a defect
    whatever it is styled as.
    """
    for surface in _NAVIGATING_SURFACES:
        for region in _navigation_regions(_html(surface, LANGUAGE_ENGLISH)):
            lowered = region.lower()
            assert "coming soon" not in lowered
            assert "disabled" not in lowered
            assert "aria-disabled" not in lowered
            # Every entry that exists is a real address: an anchor with no `href` is
            # a promise. A landmark with NO entries is admitted only when it states
            # the absence positively -- `decision.html.j2` renders a governed
            # `role="note"` when no completed run exists, which is `RCA-008`
            # `FR-163`'s "the record says there is none" rather than a dead
            # affordance. An earlier form of this test required anchors and failed
            # on that correct markup.
            anchors = re.findall(r"<a\b[^>]*>", region)
            assert all("href=" in anchor for anchor in anchors), (
                f"{surface} navigation has an anchor with no address"
            )
            if not anchors:
                assert 'role="note"' in region, (
                    f"{surface} renders an empty landmark with no stated reason"
                )


def test_the_navigation_renders_in_both_languages() -> None:
    """`FR-195`, `RCA-002` `FR-054`: parity, asserted on the navigation itself.

    The roster is the same in both languages because it is the same roster; what
    differs is the words. A surface that named fewer destinations in Arabic would
    be a capability difference dressed as a translation gap.

    Counts alone would not say that: two languages can agree on four entries while
    naming different ones, or the same ones in a different order. So the addresses
    are compared as **ordered sequences**, against the roster in both languages. The
    anchor count is kept beside it because it covers the whole landmark -- including
    the decision surface's source selector, whose entries carry no destination tail.
    """
    ordered = [destination for _label, destination in _FRAME_ROSTER]
    for surface in _NAVIGATING_SURFACES:
        counts = {}
        rendered = {}
        for language in (LANGUAGE_ENGLISH, LANGUAGE_ARABIC):
            markup = _html(surface, language)
            regions = _navigation_regions(markup)
            assert regions, f"{surface} renders no navigation in {language}"
            counts[language] = sum(
                len(re.findall(r"<a\b", region)) for region in regions
            )
            rendered[language] = _destination_tails(markup)
        assert counts[LANGUAGE_ENGLISH] == counts[LANGUAGE_ARABIC], (
            f"{surface} offers {counts} entries -- the languages disagree"
        )
        for language, tails in rendered.items():
            assert tails == ordered, (
                f"{surface} names {tails} in {language}, roster is {ordered}"
            )


def test_the_measured_surfaces_cover_every_navigating_one() -> None:
    """The extent of this module's own coverage, so a surface cannot slip past it.

    `_NAVIGATING_SURFACES` is a reviewed literal -- there is no roster of "surfaces
    that render the frame" to read, because `shell.html.j2` decides it by branching
    on a resolved organization. So the claim asserted here is narrower and honest:
    every surface named is one `SHELL_SURFACES` knows, and any surface added to that
    map without a decision about navigation fails here.
    """
    assert SHELL_SURFACES, "no shell surfaces known, so this proves nothing"
    unknown = sorted(set(_NAVIGATING_SURFACES) - set(SHELL_SURFACES))
    assert unknown == [], f"named a surface the harness cannot render: {unknown}"

    # The surfaces deliberately excluded, and why, so the exclusion is reviewed
    # rather than forgotten: none of the three has a resolved organization to
    # navigate within.
    excluded = sorted(set(SHELL_SURFACES) - set(_NAVIGATING_SURFACES))
    assert excluded == ["no_membership", "switcher", "unavailable"], (
        f"a surface's navigation status changed without a decision: {excluded}"
    )
