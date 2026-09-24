"""`U1` slice 12: the asset scan's one carve-out admits the hero wash and nothing else.

`tests/shell_asset_scan.py` lets exactly one rule paint a background: the hero's legibility wash.
These are its positive controls. Each builds a sheet the carve-out must *not* admit and asserts the
scan still refuses it, so the carve-out cannot quietly become a blanket `background-image` pass.
"""

from __future__ import annotations

import pytest

from tests.shell_asset_scan import forbidden_asset_constructs, without_the_wash

_WASH = (
    ".hero-band__scrim {\n  position: absolute;\n  background-image: linear-gradient(\n"
    "    90deg,\n    var(--hero-ground) var(--hero-solid),\n    transparent var(--hero-fade)\n"
    "  );\n}\n"
)


def test_the_admitted_wash_passes_and_is_counted() -> None:
    assert without_the_wash(_WASH)[1] == 1
    assert forbidden_asset_constructs(_WASH) == []


def test_a_painted_background_on_another_selector_still_fails() -> None:
    sheet = _WASH + ".hero-band { background-image: linear-gradient(90deg, red, blue); }\n"

    assert "background-image" in forbidden_asset_constructs(sheet)


def test_a_grouped_selector_naming_the_wash_is_not_admitted() -> None:
    """The carve-out compares the whole selector, so a neighbour cannot ride along with it."""
    sheet = _WASH.replace(".hero-band__scrim {", ".hero-band, .hero-band__scrim {", 1)

    assert without_the_wash(sheet)[1] == 0
    assert "background-image" in forbidden_asset_constructs(sheet)


def test_a_wash_that_draws_an_image_is_refused() -> None:
    sheet = '.hero-band__scrim { background-image: url("/app/assets/drawn"); }\n'

    with pytest.raises(AssertionError, match="paints something else"):
        forbidden_asset_constructs(sheet)


def test_a_wash_with_a_second_background_is_refused() -> None:
    sheet = _WASH.replace("  position: absolute;\n", "  background-color: red;\n", 1)

    with pytest.raises(AssertionError, match="more than one background"):
        forbidden_asset_constructs(sheet)


def test_a_wash_inside_a_media_query_is_still_matched_on_its_own() -> None:
    """The narrow viewport's `display: none` wash rule sits inside `@media`; it paints nothing and
    is admitted, while a painted neighbour inside the same block is still scanned."""
    sheet = (
        _WASH
        + "@media (max-width: 40rem) {\n  .hero-band__scrim { display: none; }\n"
        + "  .x { background-image: linear-gradient(0deg, red, blue); }\n}\n"
    )

    assert without_the_wash(sheet)[1] == 2
    assert "background-image" in forbidden_asset_constructs(sheet)
