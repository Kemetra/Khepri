"""`U1` slice 11: the approved hero artwork reaches the workspace overview (`RCA-012` `FR-218`).

**What `#514` left open.** That slice made the artwork *servable* -- audited derivatives at the
shell's own `/app/assets/` address, digest-verified at import. It placed the artwork on nothing,
and `FR-218`'s bilingual alternative text had no `<img>` to attach to, so `RCA-012` shipped
half-verified by construction. This module is the other half.

**Why placement and alt text are one slice.** Alt text in `shell_copy.py` with no element to name
is the recorded *defined-but-never-attached* defect: governed prose in both languages reaching no
code path, with nothing failing. An `<img>` with a hardcoded alt string fails `FR-218`'s "supplied
through the existing bilingual copy mechanism". Neither half is shippable alone.

**The fixtures are `test_w105_overview_and_data.py`'s.** That module already wires the real shell
routes over stub records and is where the overview's existing guards live -- notably
`test_overview_carries_no_figure`, which this slice must keep passing. A parallel harness here
would be a second definition of "the overview surface" and would not notice when the real one
moved.
"""

from __future__ import annotations

import re

import pytest

from khepri.rra.journey.hero import HERO_JPEG_FILE, HERO_WEBP_FILE
from khepri.runtime.shell_api import SHELL_ASSETS, SHELL_PREFIX
from khepri.runtime.shell_copy import SHELL_COPY
from tests.test_w105_overview_and_data import (
    ORGANIZATION,
    _shell,
    _worked_scope,
)

#: The copy keys `FR-218` requires, named once so a rename fails in one place.
_ALT_KEY = "overview_hero_alt"

_LANGUAGES = ("en", "ar")


def _overview(language: str) -> str:
    return (
        _shell(_worked_scope())
        .get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/overview")
        .text
    )


class TestTheArtworkIsPlaced:
    """`RCA-012` `FR-212`: the artwork reaches a customer surface, at the shell's own address."""

    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_the_overview_serves_both_derivatives(self, language: str) -> None:
        """A `<picture>` naming the WebP source and the JPEG fallback.

        Both addresses are derived from `SHELL_ASSETS` and the `hero.py` constants rather than
        typed as literals, so moving the prefix or renaming a derivative fails here instead of in
        a browser that quietly 404s.
        """
        html = _overview(language)

        assert "<picture" in html
        assert f"{SHELL_ASSETS}/{HERO_WEBP_FILE}" in html
        assert f"{SHELL_ASSETS}/{HERO_JPEG_FILE}" in html

    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_the_artwork_is_eager_and_high_priority(self, language: str) -> None:
        """Above the fold: the handoff requires `eager` and `fetchpriority="high"` here, and
        `lazy` elsewhere. A lazily-loaded hero is the one that arrives after the reader has read
        past it."""
        html = _overview(language)

        assert 'loading="eager"' in html
        assert 'fetchpriority="high"' in html

    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_the_supplied_png_is_not_placed(self, language: str) -> None:
        """`FR-215`: the 2.4 MB master stays design material under `docs/`."""
        assert "khepri-hero.png" not in _overview(language)

    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_no_external_host_is_named(self, language: str) -> None:
        """`FR-216`: the artwork resolves to the shell's own origin, under the shipped
        `default-src 'none'` CSP."""
        html = _overview(language)

        assert "//fonts." not in html
        assert "cdn" not in html.lower()
        for address in (f"{SHELL_ASSETS}/{HERO_WEBP_FILE}", f"{SHELL_ASSETS}/{HERO_JPEG_FILE}"):
            assert f"https:{address}" not in html


class TestTheAlternativeTextIsGovernedAndBilingual:
    """`RCA-012` `FR-218`: supplied through the copy mechanism, not hardcoded in a template."""

    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_the_copy_module_carries_the_alt_text(self, language: str) -> None:
        assert _ALT_KEY in SHELL_COPY[language]
        assert SHELL_COPY[language][_ALT_KEY].strip()

    def test_the_two_languages_carry_different_text(self) -> None:
        """Parity is not a copy: an Arabic entry echoing the English one is an untranslated
        string that passes a presence check."""
        assert SHELL_COPY["en"][_ALT_KEY] != SHELL_COPY["ar"][_ALT_KEY]

    def test_the_arabic_alt_text_is_in_arabic_script(self) -> None:
        """The recorded defect this guards: a key present in both maps, with the English value
        pasted into the Arabic one, satisfies every parity assertion."""
        assert re.search(r"[؀-ۿ]", SHELL_COPY["ar"][_ALT_KEY])

    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_the_rendered_surface_uses_the_governed_text(self, language: str) -> None:
        html = _overview(language)

        assert f'alt="{SHELL_COPY[language][_ALT_KEY]}"' in html

    def test_the_template_hardcodes_no_alt_string(self) -> None:
        """`FR-218` names the *mechanism*, not only the outcome. A template carrying the English
        string directly would render correctly in English and silently ship it to Arabic readers.
        """
        from importlib.resources import files

        template = (
            files("khepri.runtime")
            .joinpath("shell_templates", "overview.html.j2")
            .read_text(encoding="utf-8")
        )

        assert "sunrise" not in template.lower()
        assert re.search(r'alt="[^"{]', template) is None, (
            "the overview template carries a literal alt string"
        )


class TestTheSurfaceSurvivesTheArtworkBeingAbsent:
    """`FR-218`: decorative. A surface that fails to load it stays correct and complete."""

    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_the_heading_and_lede_do_not_live_inside_the_artwork(
        self, language: str
    ) -> None:
        """The reader's orientation must not be painted into the image.

        With the `<picture>` element removed -- which is what a blocked or failed image load
        leaves behind -- the title and the introduction are both still present.
        """
        html = _overview(language)
        without = re.sub(r"<picture\b.*?</picture>", "", html, flags=re.DOTALL)

        assert SHELL_COPY[language]["overview_title"] in without
        assert SHELL_COPY[language]["overview_intro"] in without

    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_exactly_one_h1_survives_the_placement(self, language: str) -> None:
        """`FR-200`: one `h1`, no skipped level. A hero band carrying its own heading would give
        the surface two, and the region's `aria-labelledby` would resolve to the wrong one."""
        html = _overview(language)

        assert len(re.findall(r"<h1\b", html)) == 1
        assert 'id="page-title"' in html


class TestTheGroundColourIsBehindTheArtwork:
    """The handoff's legibility rule: the headline is readable before the image decodes."""

    def test_the_token_carries_the_approved_value(self) -> None:
        """Master specification §16.5 supplies `hero-ground #F6EDDF` as an approved palette value.
        Asserted against the stylesheet rather than the handoff, because the stylesheet is what
        ships."""
        from importlib.resources import files

        shell_css = (
            files("khepri.rra.journey")
            .joinpath("assets", "shell.css")
            .read_text(encoding="utf-8")
        )

        assert re.search(r"--hero-ground:\s*#F6EDDF;", shell_css, re.IGNORECASE)

    def test_the_band_paints_the_ground_behind_the_image(self) -> None:
        """A transparent band means the headline sits on whatever is underneath while the image
        is in flight, which is the flash the ground colour exists to prevent."""
        from importlib.resources import files

        components = (
            files("khepri.rra.journey")
            .joinpath("assets", "shell-components.css")
            .read_text(encoding="utf-8")
        )

        band = re.search(r"\.hero-band\s*\{[^}]*\}", components, re.DOTALL)
        assert band is not None, "no .hero-band rule ships"
        assert "var(--hero-ground)" in band.group(0)

    def test_no_scrim_ships_while_no_copy_sits_over_the_artwork(self) -> None:
        """A scrim is a legibility overlay for text *on* the image, and this slice puts none
        there: the heading and lede stay in the document card below, which is what keeps the
        surface complete when the image fails to load.

        So a gradient here would be decoration, and `test_r807_shell_quality.py`'s no-artwork scan
        correctly refuses a painted background the surface does not need. Asserted rather than
        merely omitted, so the slice that *does* move the headline onto the band has to come back
        here and state that it is adding both the copy and the scrim the handoff pairs with it.
        """
        from importlib.resources import files

        components = (
            files("khepri.rra.journey")
            .joinpath("assets", "shell-components.css")
            .read_text(encoding="utf-8")
        )

        assert "hero-band__scrim" not in components
        assert "background-image" not in components


class TestTheArtworkIsCroppedAndNeverRedrawn:
    """§7.2 and the handoff: crop only, and the composition is never mirrored."""

    def test_the_crop_is_the_approved_focal_point(self) -> None:
        from importlib.resources import files

        components = (
            files("khepri.rra.journey")
            .joinpath("assets", "shell-components.css")
            .read_text(encoding="utf-8")
        )

        assert "object-fit: cover" in components
        assert "object-position: 62% 46%" in components

    def test_right_to_left_mirrors_the_crop_and_not_the_artwork(self) -> None:
        """The handoff is explicit: the composition is symmetrical and is **not** mirrored. Only
        the scrim flips and `object-position` moves to `38% 46%`, so the monument stays on the
        copy-free side."""
        from importlib.resources import files

        components = (
            files("khepri.rra.journey")
            .joinpath("assets", "shell-components.css")
            .read_text(encoding="utf-8")
        )

        assert "object-position: 38% 46%" in components
        assert not re.search(r"\.hero[^{]*\{[^}]*scaleX\(-1\)", components, re.DOTALL)

    def test_no_css_drawn_illustration_stands_in_for_the_artwork(self) -> None:
        """`FR-206` and §7.2: no div-art, no pseudo-element artwork, no inline SVG authored here.

        The scrim is a gradient and is permitted -- it is a legibility overlay the handoff
        specifies, not a drawing of the monument. What is forbidden is a shape standing in for
        the photograph.
        """
        from importlib.resources import files

        components = (
            files("khepri.rra.journey")
            .joinpath("assets", "shell-components.css")
            .read_text(encoding="utf-8")
        )

        hero_rules = "\n".join(
            match.group(0)
            for match in re.finditer(r"\.hero[^{]*\{[^}]*\}", components, re.DOTALL)
        )

        assert "<svg" not in hero_rules
        assert "clip-path" not in hero_rules
        assert "border-radius: 50%" not in hero_rules


class TestTheHeroRulesUseLogicalPropertiesOnly:
    """`FR-199`: right-to-left is built from logical properties, and this slice adds none."""

    def test_the_hero_rules_name_no_physical_direction(self) -> None:
        from importlib.resources import files

        components = (
            files("khepri.rra.journey")
            .joinpath("assets", "shell-components.css")
            .read_text(encoding="utf-8")
        )

        hero_rules = "\n".join(
            match.group(0)
            for match in re.finditer(r"\.hero[^{]*\{[^}]*\}", components, re.DOTALL)
        )
        declarations = re.sub(r"/\*.*?\*/", "", hero_rules, flags=re.DOTALL)

        for physical in (
            "margin-left",
            "margin-right",
            "padding-left",
            "padding-right",
            "border-left",
            "border-right",
            "text-align: left",
            "text-align: right",
        ):
            assert physical not in declarations, f"{physical} is physical; use its logical form"
