"""The master specification §7 asset scan over a shell component sheet (`RCA-010` `FR-206`).

Shared by `test_r807_shell_quality.py`, which runs it over the shipped sheet, and
`test_u1_slice12_hero_convergence.py`, which holds its one carve-out to a positive control.

The shell has no admitted programmatic drawing. Its one painted background is the hero's
legibility wash (`U1` slice 12, handoff §6): a gradient from the band's own ground to
`transparent`. The carve-out admits exactly that, and only as a rule whose **whole selector** is
the wash's -- a grouped selector naming the wash beside another element is not admitted, so the
other element's paint is still scanned.
"""

from __future__ import annotations

import re

#: The wash's selectors, compared whole after whitespace is collapsed.
WASH_SELECTORS = frozenset({".hero-band__scrim", '[dir="rtl"] .hero-band__scrim'})

#: The one declaration a painting wash rule may carry: a `linear-gradient` from the band's ground
#: token to `transparent`, at the band's own stops. No `url()`, no colour literal, no second layer.
WASH_VALUE = re.compile(
    r"^background-image:\s*linear-gradient\(\s*\d+deg,\s*var\(--hero-ground\)\s+"
    r"var\(--hero-solid\),\s*transparent\s+var\(--hero-fade\)\s*\)$"
)

#: An innermost rule: a selector and a body with no nested braces. An `@media` block's own brace
#: is outside the match, so the rules inside it are matched one by one.
_RULE = re.compile(r"([^{};]*)\{([^{}]*)\}")
_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _blank_comments(css: str) -> str:
    """Comments replaced by spaces of the same length, so offsets still index the original."""
    return _COMMENT.sub(lambda match: " " * len(match.group(0)), css)


def _declarations(body: str) -> list[str]:
    return [" ".join(part.split()) for part in body.split(";") if part.strip()]


def _check_wash(body: str) -> None:
    """A wash rule paints nothing, or paints exactly the admitted gradient and nothing else."""
    painting = [d for d in _declarations(body) if d.lower().startswith("background")]
    if not painting:
        return
    assert len(painting) == 1, f"the hero wash carries more than one background: {painting}"
    assert WASH_VALUE.match(painting[0]), f"the hero wash paints something else: {painting[0]}"


def without_the_wash(css: str) -> tuple[str, int]:
    """The sheet with every admitted wash rule blanked, and how many were admitted."""
    blanked = _blank_comments(css)
    remainder, admitted = list(css), 0
    for match in _RULE.finditer(blanked):
        if " ".join(match.group(1).split()) not in WASH_SELECTORS:
            continue
        _check_wash(match.group(2))
        remainder[match.start() : match.end()] = " " * (match.end() - match.start())
        admitted += 1
    return "".join(remainder), admitted


def forbidden_asset_constructs(css: str) -> list[str]:
    """The §7 asset constructs present in a component sheet once the admitted wash is removed."""
    remainder, _ = without_the_wash(css)

    # At-rule names, property names, function names and URL schemes are all
    # case-insensitive in CSS, so `@IMPORT` and `URL(HTTPS://...)` evaded the
    # substring checks entirely. Fold once and check the folded text.
    folded = remainder.lower()
    forbidden = {
        "@import": "@import" in folded,
        "external url()": bool(re.search(r"url\(\s*['\"]?https?://", folded)),
        "background-image": "background-image" in folded,
        "content artwork": bool(re.search(r"content\s*:\s*['\"][^'\"]*[^\x00-\x7F]", remainder)),
        "non-ascii glyph": bool(re.search(r"[←-➿\U0001f300-\U0001faff]", remainder)),
    }
    return sorted(name for name, present in forbidden.items() if present)
