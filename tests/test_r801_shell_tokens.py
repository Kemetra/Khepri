"""`R8-01` — the shell token set stays inside the system it claims to extend.

`R8-01` produces no behavior, so these are consistency checks rather than functional ones. Each is
the machine-checkable half of a claim the design note makes; a claim nothing can falsify is a claim
the next slice may quietly break.

The four here are §7's list, and the first one already earned its place: a draft of `shell.css`
carried two eyeballed green values that drifted `--ready`'s hue from 151 to 146. They looked
intentional. This is what caught them.
"""

from __future__ import annotations

import colorsys
import re
from pathlib import Path

import pytest

_ASSETS = Path(__file__).resolve().parents[1] / "src" / "khepri" / "rra" / "journey" / "assets"
SHELL = _ASSETS / "shell.css"
JOURNEY = _ASSETS / "journey.css"

#: The two values `shell.css` introduces, both derived from `--ready`'s hue at the shipped danger
#: family's saturation and lightness steps. Named here so the "no new colour" check has an explicit,
#: reviewable allowance rather than a loosened assertion.
_DERIVED = {"#a0d9be", "#eafaf3"}

#: Values the **owner supplied**, admitted by name and by the §16.5 row that supplies each one.
#:
#: A third category exists because the other two cannot honestly hold these. `_ORPHAN_BASELINE`
#: and the `shipped` set are values already in `journey.css`; `_DERIVED` is for a value *derived
#: from* a shipped ink, and the derivation test proves each one against its source. A supplied
#: palette value is neither: it comes from outside the stylesheet, and pretending it was derived
#: would make `_DERIVATION` assert a lineage that does not exist.
#:
#: **Enumerated, never a blanket allowance.** Widening the subtraction in the palette check to
#: "any value with a comment" would disarm the guard rather than honour it — the recorded
#: guard-that-disarms-itself defect. A fourth colour still fails until it is listed here with its
#: §16.5 row, which is the whole point: the set exists so surfaces do not each pick their own.
_SUPPLIED = {
    # §16.5, "Ivory and sand — surfaces": `hero-ground #F6EDDF`. `RCA-012` `FR-212`'s hero band
    # paints it behind the artwork so the headline is legible before the image decodes.
    "#f6eddf",
    # The workspace presentation reset (`RCA-010` §Scope) takes the rest of the §16.5 palette the
    # shell consumes. One entry per value, each beside the row that supplies it; §16.5 values the
    # shell does not consume (the error triplet, `ink-disabled`, `gold-eyebrow`, `gold-link`) are
    # deliberately not listed, so declaring one still fails until it is.
    #
    # §16.5 "Navy — chrome and ink": `navy-900`, `navy-950`, `ink`, `ink-muted`, `nav-label`.
    # `ink-secondary` and `ink-tertiary` are not consumed: both fall under 4.5:1 on the ivory
    # canvas, so secondary text uses `ink-muted` throughout.
    "#101c26",
    "#0b1017",
    "#16212b",
    "#55616c",
    "#a9b2b9",
    # §16.5 "Gold — brand and primary": `gold-400`, `gold-500`, `gold-600`, `gold-ink`,
    # `gold-tint`, `gold-border`. `gold-link` is not consumed: it falls under 4.5:1 on the sand
    # surface, so every link uses `gold-ink`.
    "#d5ae63",
    "#c9a45c",
    "#b98c39",
    "#7a5a17",
    "#f6ebd6",
    "#e3ce9f",
    # §16.5 "Ivory and sand — surfaces": `surface-card`, `surface-canvas`, `surface-page`,
    # `surface-sand`, `border-card`, `border-inner`, `border-strong`.
    "#ffffff",
    "#fbf9f6",
    "#e9e3da",
    "#f4eee4",
    "#ebe5dc",
    "#efe9e0",
    "#ded7cc",
    # §16.5 status triplets: success ink/fill/border, warning fill/border (the warning ink is
    # `gold-ink` above).
    "#27724f",
    "#e7f2eb",
    "#d5e5da",
    "#faeeda",
    "#f0e1c2",
}

#: The pre-handoff values the shell still declares, admitted because `journey.css` shipped them.
#:
#: This check used to subtract whatever `journey.css` held **today**, so any colour added to the
#: journey silently widened what the shell might use. `RRA-016` `FR-220` then moved the journey
#: onto the §16.5 palette, and these six -- none a §16.5 value -- left it. They are pinned here as
#: the values `journey.css` shipped at `cbeecf4`, before `FR-220`, so the admission is enumerated
#: and frozen rather than tracking another surface's stylesheet: strictly stronger, not looser.
#: That the shell still declares non-§16.5 values is an `RCA-010` residual, not this check's.
_JOURNEY_SHIPPED = frozenset(
    {
        "#1d6b45",
        "#6d201b",
        "#9a2d26",
        "#d9a49f",
        "#e3ded1",
        "#faece9",
    }
)

#: `R8-01` §2's census of values `journey.css` uses below its `:root` block. The count is the
#: baseline: a slice that adds an eleventh is choosing a colour outside the system.
#: The exact hex literals `journey.css` uses below its `:root` block -- the census `R8-01`
#: §2 took. Pinned as a **set** rather than a count: `len(orphans) <= 10` left a free slot,
#: so replacing one literal with a different colour, or every literal with ten new ones,
#: passed while the palette churned completely. `R8-02` removes from this set and must never
#: add to it. Found in review on `#219`.
_ORPHAN_BASELINE = frozenset(
    {
        "#667381",
        "#6d201b",
        "#7b817e",
        "#d9a49f",
        "#e3ded1",
        "#e3e7eb",
        "#e4e8ed",
        "#f0f5fa",
        "#faece9",
        "#fafbfd",
    }
)

#: Physical properties, forbidden in favour of their logical counterparts. Mirrors
#: `test_rra006_html_surface.py`'s list, which cites `KHEPRI-DEC-005`.
_PHYSICAL = (
    "margin-left",
    "margin-right",
    "margin-top",
    "margin-bottom",
    "padding-left",
    "padding-right",
    "padding-top",
    "padding-bottom",
    "border-left",
    "border-right",
    "border-top",
    "border-bottom",
    "text-align: left",
    "text-align: right",
    "left:",
    "right:",
)


def _declarations(css: str) -> str:
    """The stylesheet with block comments removed.

    Load-bearing: `shell.css` *documents* the values it replaced, including two rejected drafts, so
    a scan that read comments would report them as declared and this file's central claim would be
    unfalsifiable in the wrong direction — reporting failures that are prose.
    """
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _hexes(css: str) -> set[str]:
    return {value.lower() for value in re.findall(r"#[0-9a-fA-F]{3,8}", css)}


def _hsl(value: str) -> tuple[int, int, int]:
    """`(hue, saturation, lightness)` in degrees and percent.

    All three, not just the hue: the derivation `shell.css` documents fixes every component, and a
    test checking one accepts a same-hue pastel at any saturation. Found in review on `#219`.
    """
    red, green, blue = (int(value[index : index + 2], 16) / 255 for index in (1, 3, 5))
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    return round(hue * 360), round(saturation * 100), round(lightness * 100)


def _hue(value: str) -> int:
    return _hsl(value)[0]


# --- the scanner is self-tested first ---------------------------------------------------------


def test_the_comment_stripper_hides_documented_values_and_keeps_declared_ones() -> None:
    """Without this, every assertion below could pass or fail for the wrong reason.

    `shell.css` names its rejected drafts in prose. A scan that counted them would fail the "no new
    colour" test on values the file exists to say it is *not* using.
    """
    sample = "/* a draft used #ff0000 */\n:root { --x: #00ff00; }"

    assert _hexes(_declarations(sample)) == {"#00ff00"}
    assert "#ff0000" in _hexes(sample), "the raw scan must see it, or this proves nothing"


# --- section 7's four checks -------------------------------------------------------------------


def test_shell_introduces_no_colour_outside_the_shipped_palette() -> None:
    """§3's central claim, made falsifiable.

    Every value must be one `journey.css` shipped (`_JOURNEY_SHIPPED`), except the two `--ready`
    companions the note declares and derives and the owner-supplied §16.5 values. Anything else
    fails here, which is the point: the token set exists so nine new surfaces do not each pick
    their own greys.
    """
    declared = _hexes(_declarations(SHELL.read_text(encoding="utf-8")))

    unexplained = declared - _JOURNEY_SHIPPED - _DERIVED - _SUPPLIED
    assert not unexplained, (
        f"{sorted(unexplained)} appear in shell.css, are not values journey.css shipped, and are "
        "not declared as derived or supplied. Either reuse a shipped value, record the "
        "derivation in _DERIVED and in the note, or — for an owner-supplied palette value — "
        "list it in _SUPPLIED with the master specification §16.5 row that supplies it."
    )


def test_the_palette_check_still_refuses_an_unlisted_colour() -> None:
    """The positive control for the check above, added with `_SUPPLIED` (`RCA-012` slice 11).

    A third category is a third way to weaken the guard. If `_SUPPLIED` had been written as a
    blanket allowance — anything commented, anything matching a pattern — the assertion above
    would still pass and would no longer be measuring anything. This drives the same subtraction
    with a colour in none of the three sets and requires it to survive as unexplained.
    """
    invented = "#abcdef"

    assert invented not in _DERIVED
    assert invented not in _SUPPLIED

    assert invented not in _JOURNEY_SHIPPED

    assert {invented} - _JOURNEY_SHIPPED - _DERIVED - _SUPPLIED == {invented}


#: The token *pairings* the derivation asserts — which shipped ink supplies the hue, and which
#: shipped step each companion copies. **Only names, no values.** The values come from `shell.css`.
#:
#: An earlier version carried the hex literals too, which made the whole test hermetic: it
#: compared constants in the table against constants in the test body and never opened the
#: stylesheet, so swapping `--ready-border` and `--ready-surface` in `shell.css` passed every
#: assertion — the palette check permits the same value *set* either way. Reproduced. From review
#: on `#219`, and it is the third round on this one test: each earlier fix widened the comparison
#: without asking whether the assertion read the artifact or a restatement of it.
_DERIVATION = (
    ("--ready-border", "--danger-border"),
    ("--ready-surface", "--danger-surface"),
)

#: The ink whose hue every companion above must hold.
_DERIVED_FROM = "--ready"


def _token_values(css: str) -> dict[str, str]:
    """Every `--name: #value;` declaration in the stylesheet, comments excluded.

    This is what makes the derivation test read the artifact rather than a copy of it.
    """
    return {
        match.group(1): match.group(2).lower()
        for match in re.finditer(
            r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;", _declarations(css)
        )
    }


def test_the_token_reader_sees_declarations_and_not_comments() -> None:
    """Self-tested, because every assertion below now depends on it reading the right thing."""
    sample = "/* --fake: #ff0000; */\n:root { --real: #00FF00; --other: #123456 }"

    values = _token_values(sample)

    assert values == {"--real": "#00ff00"}, "a comment leaked in, or a value without `;` was missed"


@pytest.mark.parametrize(("name", "counterpart"), _DERIVATION)
def test_each_derived_value_matches_its_counterpart_step_exactly(
    name: str, counterpart: str
) -> None:
    """The allowance in the previous test is only honest if the derivation is the documented one.

    `shell.css` promises `--ready`'s hue **at the saturation and lightness steps the shipped danger
    family uses** — three components, not one, and read from the stylesheet rather than from a table
    restating it. Two earlier versions failed differently: the first checked only the hue, accepting
    a same-hue pastel at any saturation; the second checked all three but against literals in this
    file, so swapping the two declarations in `shell.css` changed nothing it could see.

    Tolerances are one degree and one percent, which is 8-bit rounding and nothing more.
    """
    declared = _token_values(SHELL.read_text(encoding="utf-8"))

    for token in (name, counterpart, _DERIVED_FROM):
        assert token in declared, f"{token} is not declared in shell.css"

    hue, saturation, lightness = _hsl(declared[name])
    ink_hue = _hue(declared[_DERIVED_FROM])
    _, reference_saturation, reference_lightness = _hsl(declared[counterpart])

    assert abs(hue - ink_hue) <= 3, (
        f"{name} is {declared[name]} (hue {hue}); {_DERIVED_FROM} is hue {ink_hue}. A companion "
        "off the ink's hue is a new colour wearing the name of a step."
    )
    assert abs(saturation - reference_saturation) <= 1, (
        f"{name} is S{saturation}; {counterpart} is S{reference_saturation}. The derivation copies "
        "the danger family's step, so a different saturation is a chosen value, not a derived one."
    )
    assert abs(lightness - reference_lightness) <= 1, (
        f"{name} is L{lightness}; {counterpart} is L{reference_lightness}. Same reason as the "
        "saturation: the step is the thing being copied."
    )


def test_the_derivation_table_covers_every_declared_derived_value() -> None:
    """`_DERIVED` is the allowance and `_DERIVATION` the proof, and the two must describe the same
    values. A value added to the allowance and forgotten in the proof would be admitted by the
    palette check and never have its derivation verified — the loophole one level up.

    The proven set is resolved **through the stylesheet**, not from a literal, so this cannot pass
    by two tables agreeing with each other while disagreeing with `shell.css`.
    """
    declared = _token_values(SHELL.read_text(encoding="utf-8"))
    proven = {declared[name] for name, _ in _DERIVATION if name in declared}

    assert proven == _DERIVED, (
        f"the palette check allows {sorted(_DERIVED)}; the derivation proves {sorted(proven)}, "
        "resolved from shell.css. Every allowance needs a row in _DERIVATION, and every row must "
        "name a token the stylesheet declares."
    )


def test_no_external_reference_anywhere_in_the_stylesheet() -> None:
    """The gate `test_rra_journey_pages.py:18-19` applies to rendered pages, applied here.

    The roadmap's UI guardrails forbid external fonts, analytics, CDNs, and runtime assets, and
    `docs/ui/design_handoff_khepri/README.md:691-700` proposes two of them — Google Fonts and a
    unpkg CDN. That handoff is detailed enough to look authoritative, so the prohibition is
    asserted rather than trusted to a reader noticing.
    """
    text = SHELL.read_text(encoding="utf-8")
    body = _declarations(text)

    # Raw text for URLs: a CDN address in a comment is still a reader being pointed at one, and the
    # handoff README is exactly that kind of pointer.
    assert "http://" not in text
    assert "https://" not in text

    # Declarations only for syntax. `@import` and `url()` matter as instructions to the browser, and
    # this file's own comment says "no `@import`, no font host" -- scanning the comment made that
    # sentence fail the check it describes.
    assert "@import" not in body
    assert "url(" not in body, "assets belong to journey.css's allowlist, not here"


@pytest.mark.parametrize("physical", _PHYSICAL)
def test_no_physical_css_property(physical: str) -> None:
    """`journey.css` uses logical properties throughout but has no test holding it there;
    `report.css` does (`test_rra006_html_surface.py:406-424`, citing `KHEPRI-DEC-005`). The shell
    stylesheet starts with the test rather than acquiring one later.

    A token file declaring no layout cannot violate this today. It is here so it cannot start:
    `R8-02` adds rules to this file, and the assertion is already in place when it does.
    """
    assert physical not in _declarations(SHELL.read_text(encoding="utf-8")).lower(), (
        f"{physical!r} has a logical counterpart; an RTL layout that mirrors correctly cannot be "
        "built from physical properties."
    )


def test_the_orphan_value_count_does_not_grow() -> None:
    """§7's item 4, and the one that keeps this slice from eroding.

    `journey.css` uses ten hex literals below its `:root` block -- the census `R8-01` §2 took.
    `R8-02` should reduce that set by replacing literals with tokens; nothing should enter it.

    **Asserted as a subset, not a count.** `<=` was chosen so the reduction `R8-02` performs
    could not fail the test that asked for it, but it also let a substitution through: swap one
    censused literal for a new colour and the count is unchanged, and ten new colours replacing
    all ten pass identically. A subset check keeps the property that mattered -- removals pass
    -- while refusing the additions the count could not see. Found in review on `#219`.
    """
    css = JOURNEY.read_text(encoding="utf-8")
    root_end = css.index("}", css.index(":root"))
    below_root = _declarations(css[root_end:])

    orphans = _hexes(below_root)

    # Subset, not size. A count leaves a free slot for any substitution; this permits only
    # removal, which is the direction `R8-02` moves in.
    introduced = orphans - _ORPHAN_BASELINE
    assert not introduced, (
        f"journey.css uses {sorted(introduced)} below :root, which is not in the R8-01 census. "
        "A colour outside the token set is a colour chosen outside the design, and replacing a "
        "censused literal with a new one keeps the count identical -- so the count is not the "
        "assertion."
    )


def test_the_token_file_declares_tokens_and_no_rules() -> None:
    """`R8-01`'s output is design, not implementation. One `:root` block and nothing else — a rule
    here would be `R8-02`'s work landing a slice early, and the roadmap's guardrails forbid building
    surfaces that do not exist yet."""
    body = _declarations(SHELL.read_text(encoding="utf-8")).strip()

    assert body.startswith(":root {")
    assert body.endswith("}")
    assert body.count("{") == 1, "a second block means this file has started styling something"


def test_every_token_the_note_promises_is_present() -> None:
    """The scales are the deliverable. A note describing a spacing ramp beside a file without one
    would be the documentation-drift this repository keeps finding."""
    body = _declarations(SHELL.read_text(encoding="utf-8"))

    for family, count in (("--space-", 8), ("--text-", 9), ("--radius", 4)):
        declared = len(re.findall(rf"{re.escape(family)}[\w-]*\s*:", body))
        assert declared >= count, f"{family}* declares {declared} tokens, expected at least {count}"

    singles = ("--touch-min", "--shell-width", "--measure-prose", "--font-body", "--line-subtle")
    for single in singles:
        assert f"{single}:" in body, f"{single} is described in R8-01 but not declared"
