"""`R8-01` — the shell token set stays inside the system it claims to extend.

`R8-01` produces no behavior, so these are consistency checks rather than functional ones. Each is
the machine-checkable half of a claim the design note makes; a claim nothing can falsify is a claim
the next slice may quietly break.

The palette check is the central one. `#572` retired the last pre-handoff values the shell
declared, so every colour in `shell.css` is now a master specification §16.5 value, listed in
`_SUPPLIED` beside the row that supplies it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ASSETS = Path(__file__).resolve().parents[1] / "src" / "khepri" / "rra" / "journey" / "assets"
SHELL = _ASSETS / "shell.css"
JOURNEY = _ASSETS / "journey.css"

#: Values the **owner supplied**, admitted by name and by the §16.5 row that supplies each one.
#:
#: Since `#572` this is the **only** admission: the pre-handoff values `journey.css` once shipped,
#: and the two `--ready` companions derived from them, are no longer declared, so their allowances
#: were removed with them rather than left as free slots.
#:
#: **Enumerated, never a blanket allowance.** Widening the subtraction in the palette check to
#: "any value with a comment" would disarm the guard rather than honour it — the recorded
#: guard-that-disarms-itself defect. An unlisted colour still fails until it is listed here with its
#: §16.5 row, which is the whole point: the set exists so surfaces do not each pick their own.
_SUPPLIED = {
    # §16.5, "Ivory and sand — surfaces": `hero-ground #F6EDDF`. `RCA-012` `FR-212`'s hero band
    # paints it behind the artwork so the headline is legible before the image decodes.
    "#f6eddf",
    # The workspace presentation reset (`RCA-010` §Scope) takes the rest of the §16.5 palette the
    # shell consumes. One entry per value, each beside the row that supplies it; §16.5 values the
    # shell does not consume (the error fill and border, `ink-disabled`, `gold-eyebrow`,
    # `gold-link`) are deliberately not listed, so declaring one still fails until it is.
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
    # §16.5 status triplets: error ink `#B0392F`. `--danger` paints the one destructive warning
    # (`.invitation-warning`); `#572` moved it off the pre-handoff `#9a2d26`.
    "#b0392f",
}

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


def test_shell_introduces_no_colour_outside_the_approved_palette() -> None:
    """§3's central claim, made falsifiable: every declared value is a §16.5 value.

    Anything else fails here, which is the point: the token set exists so new surfaces do not each
    pick their own greys. Before `#572` six pre-handoff values were also admitted because
    `journey.css` once shipped them; that `RCA-010` residual is closed.
    """
    declared = _hexes(_declarations(SHELL.read_text(encoding="utf-8")))

    unexplained = declared - _SUPPLIED
    assert not unexplained, (
        f"{sorted(unexplained)} appear in shell.css and are not master specification §16.5 "
        "values. Use a §16.5 value and list it in _SUPPLIED beside the row that supplies it."
    )


def test_the_palette_check_still_refuses_an_unlisted_colour() -> None:
    """The positive control for the check above, added with `_SUPPLIED` (`RCA-012` slice 11).

    A third category is a third way to weaken the guard. If `_SUPPLIED` had been written as a
    blanket allowance — anything commented, anything matching a pattern — the assertion above
    would still pass and would no longer be measuring anything. This drives the same subtraction
    with a colour outside `_SUPPLIED` and requires it to survive as unexplained, including a value
    the shell declared before `#572` retired it.
    """
    for invented in ("#abcdef", "#9a2d26", "#1d6b45"):
        assert {invented} - _SUPPLIED == {invented}


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
