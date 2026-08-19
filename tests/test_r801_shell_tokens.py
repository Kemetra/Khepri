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

#: `R8-01` §2's census of values `journey.css` uses below its `:root` block. The count is the
#: baseline: a slice that adds an eleventh is choosing a colour outside the system.
_ORPHAN_BASELINE = 10

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

    Every value must already appear in `journey.css`, except the two `--ready` companions the note
    declares and derives. A third addition fails here, which is the point: the token set exists so
    nine new surfaces do not each pick their own greys.
    """
    declared = _hexes(_declarations(SHELL.read_text(encoding="utf-8")))
    shipped = _hexes(JOURNEY.read_text(encoding="utf-8"))

    unexplained = declared - shipped - _DERIVED
    assert not unexplained, (
        f"{sorted(unexplained)} appear in shell.css but not in journey.css and are not declared "
        "as derived. Either reuse a shipped value or record the derivation in _DERIVED and in the "
        "note."
    )


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

    `journey.css` uses ten hex literals below its `:root` block. That is the census `R8-01` §2 took
    and the number the token set exists to stop growing. `R8-02` should reduce it by replacing those
    literals with tokens; nothing should increase it.

    Asserted as `<=` rather than `==` so the reduction `R8-02` performs does not fail the test that
    asked for it.
    """
    css = JOURNEY.read_text(encoding="utf-8")
    root_end = css.index("}", css.index(":root"))
    below_root = _declarations(css[root_end:])

    orphans = _hexes(below_root)
    assert len(orphans) <= _ORPHAN_BASELINE, (
        f"journey.css now uses {len(orphans)} literal colours below :root "
        f"(baseline {_ORPHAN_BASELINE}): {sorted(orphans)}. A new literal is a colour chosen "
        "outside the token set."
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
