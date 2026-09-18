"""`RCA-010` `FR-204`-`FR-205`: visual-regression evidence for the commercial shell surfaces.

`tests/` only, and no stored image. Visual evidence here is **computed measurement** -- box
geometry, computed styles and element counts -- because a pixel digest cannot name which of
`FR-204`'s eight dimensions drifted, and a committed baseline image would be the hosted baseline
store `FR-204` excludes. Both were measured before choosing; see the execution plan's Decision 1.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

#: The reference pack. Its own README states the rule this module enforces: "Visual composition is
#: evidence. Generated product facts are not."
_PACK = Path(__file__).resolve().parents[1] / "docs" / "product" / "ui-visual-references"

#: Anything that would make an image a source of product truth (`FR-205`).
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".svg")

#: Verbs that would turn a reference image into an input rather than evidence.
_READS = re.compile(r"read_bytes|read_text|open\(|imread|Image\.|sha256|digest")


def _test_sources() -> list[Path]:
    """Every test module, anchored to `__file__` rather than the CWD.

    A bare `Path("tests")` resolves against the working directory and scans nothing when pytest
    runs from elsewhere, which passes vacuously.
    """
    return sorted(Path(__file__).resolve().parent.glob("test_*.py"))


def test_no_test_reads_a_value_out_of_a_reference_image() -> None:
    """`FR-205`: an image is evidence, not truth.

    No module may open, read, decode or digest a file from the reference pack. A test that did
    would be taking a figure, route, capability, refusal reason or governed word from a picture --
    and where an image and an active specification disagree, the specification wins.
    """
    sources = _test_sources()
    assert sources, "no test modules found, so this scan proves nothing"

    offenders = []
    for source in sources:
        for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            names_an_image = "ui-visual-references" in line or any(
                suffix in line for suffix in _IMAGE_SUFFIXES
            )
            if names_an_image and _READS.search(line):
                offenders.append(f"{source.name}:{number}")

    assert offenders == [], "a test reads product truth out of an image: " + ", ".join(offenders)


def test_the_reference_pack_is_present_so_the_scan_is_not_vacuous() -> None:
    """The scan above guards nothing if the pack has moved or emptied."""
    assert _PACK.is_dir(), f"the reference pack is missing at {_PACK}"
    images = [entry for entry in _PACK.iterdir() if entry.suffix in _IMAGE_SUFFIXES]
    assert images, "the reference pack holds no images, so `FR-205` guards nothing here"


#: The representatives, named as a reviewed literal and cross-checked against master specification
#: §16.4's covered references -- not derived from the surfaces these tests happen to drive, which
#: would be the tautology slice 4 ruled out.
#:
#: §16.4 covers #6 period comparison, #8 evidence drawer, #9 refusal, #10 Arabic RTL.
#: **#9 is absent deliberately**: no shell surface renders `.decision-refusal`,
#: `.decision-unsupported` or `.compare-refusal` (slice 9b measured this), so naming it would
#: build a run that can only produce the null case. #6 is composition only -- `compare` renders
#: chrome and three download actions and no figures -- which is what the reference covers.
_REPRESENTATIVES = {
    "decision": "§16.4 #8 evidence drawer, and #7 executive composition",
    "compare": "§16.4 #6 period comparison, composition only",
    "overview": "§16.4 #4 workspace overview, density floor",
}

#: The refusal classes slice 5's state grammar binds, checked here for reachability rather than
#: assumed absent.
_REFUSAL_CLASSES = ("decision-refusal", "decision-unsupported", "compare-refusal")


def test_every_representative_is_a_surface_the_shell_serves() -> None:
    """A representative naming a surface the shell does not serve measures nothing."""
    from tests.test_r807_shell_quality import SHELL_SURFACES

    assert _REPRESENTATIVES, "no representatives named, so this slice measures nothing"
    unknown = sorted(set(_REPRESENTATIVES) - set(SHELL_SURFACES))
    assert unknown == [], f"representatives name surfaces the shell does not serve: {unknown}"


def test_the_refusal_reference_is_recorded_as_unreachable_not_covered() -> None:
    """§16.4 covers #9 refusal; the shell renders none, and that is recorded rather than claimed.

    Fails the day a shell surface renders a refusal -- which is when #9 becomes a usable
    representative and belongs in `_REPRESENTATIVES` rather than in this exemption.
    """
    from tests.test_r807_shell_quality import SHELL_SURFACES, _html

    rendering = sorted(
        surface
        for surface in SHELL_SURFACES
        for name in _REFUSAL_CLASSES
        if f'class="{name}' in _html(surface, "en")
    )
    assert rendering == [], (
        f"{rendering} now render a refusal: add §16.4 #9 to _REPRESENTATIVES and delete this test"
    )


#: Read in the page, so every value is what the browser resolved rather than what a sheet declares.
#: One dict per surface, keyed by `FR-204`'s dimension names, so a failure says *which* of the
#: eight drifted rather than only that something moved -- the property a pixel digest cannot have.
_PROBE = """
(() => {
  const card = document.querySelector('.document-card');
  const cardStyle = card ? getComputedStyle(card) : null;
  return {
    hierarchy: {
      h1: document.querySelectorAll('h1').length,
      h2: document.querySelectorAll('h2').length,
      landmarks: document.querySelectorAll('nav, main, header').length,
    },
    density: {
      cards: document.querySelectorAll('.document-card').length,
      actions: document.querySelectorAll('a, button').length,
    },
    spacing_rhythm: cardStyle ? {
      padding: cardStyle.paddingTop,
      gap: cardStyle.marginBlockEnd,
    } : null,
    rtl: {
      dir: document.documentElement.getAttribute('dir'),
    },
  };
})()
"""


def _measure(surface: str, language: str) -> dict[str, object]:
    """One surface's measured dimensions, in a real browser at the wide viewport."""
    from playwright.sync_api import sync_playwright

    from tests.test_r807_shell_quality import _html
    from tests.test_r811_shell_accessibility import _launch_chromium, _shell_css

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": 1180, "height": 900})
            page.set_content(_html(surface, language), wait_until="domcontentloaded")
            page.add_style_tag(content=_shell_css())
            return page.evaluate(_PROBE)
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("surface", sorted(_REPRESENTATIVES))
def test_the_measured_dimensions_are_deterministic_across_two_runs(surface: str) -> None:
    """`FR-204` §Verification: the evidence is reproducible and deterministic across two runs.

    This is the property that makes measurement usable as evidence at all. It is asserted rather
    than assumed, because a measurement that varied between runs would report drift that is not
    there and hide drift that is.
    """
    first = _measure(surface, "en")
    assert first["hierarchy"], f"{surface}: nothing measured, so this proves nothing"
    assert first == _measure(surface, "en"), f"{surface}: the measurement is not deterministic"


@pytest.mark.browser
@pytest.mark.parametrize("surface", sorted(_REPRESENTATIVES))
def test_the_spacing_rhythm_comes_from_the_token_scale(surface: str) -> None:
    """`FR-204` spacing rhythm: the card's padding and gap sit on the 4px rhythm.

    Asserted against the rhythm the token scale declares, never against a value read out of a
    reference image -- which `FR-205` forbids and which would make the picture the source.
    """
    measured = _measure(surface, "en")["spacing_rhythm"]
    assert measured is not None, f"{surface}: no card measured, so this proves nothing"
    for name, value in measured.items():
        pixels = float(str(value).removesuffix("px"))
        assert pixels % 4 == 0, f"{surface}: spacing_rhythm {name} is {value}, off the 4px rhythm"


@pytest.mark.browser
@pytest.mark.parametrize("surface", sorted(_REPRESENTATIVES))
def test_the_right_to_left_rendering_mirrors_rather_than_reflows(surface: str) -> None:
    """`FR-204` RTL: Arabic is the same page mirrored, not a different composition.

    Hierarchy and density are language-invariant by construction -- the same template renders
    both -- so a divergence here is a real visual-language drift rather than a translation
    artifact. This is the dimension §16.4 covers outright (#10).
    """
    english, arabic = _measure(surface, "en"), _measure(surface, "ar")
    assert english["rtl"]["dir"] == "ltr", f"{surface}: English is not ltr"
    assert arabic["rtl"]["dir"] == "rtl", f"{surface}: Arabic is not rtl"
    assert english["hierarchy"] == arabic["hierarchy"], (
        f"{surface}: hierarchy differs by language -- "
        f"{english['hierarchy']} vs {arabic['hierarchy']}"
    )
    assert english["density"] == arabic["density"], (
        f"{surface}: density differs by language -- {english['density']} vs {arabic['density']}"
    )


@pytest.mark.browser
@pytest.mark.parametrize("surface", sorted(_REPRESENTATIVES))
def test_the_body_typeface_is_the_shell_token_not_a_browser_default(surface: str) -> None:
    """`FR-204` typography: the shell's declared typeface reaches the page.

    `shell.css` declares `--font-body`, and before `shell-components.css` applied it to `body`
    every shell and legal page rendered in the browser's default serif -- measured by this slice
    as `"Times New Roman"`. The assertion reads the **declared** list rather than the resolved
    face, so it is stable across platforms and across whichever families a host has installed.

    **This test is not font-load evidence, and was never able to be.** It builds the page with
    `set_content` plus `add_style_tag`, so there is no HTTP origin for a relative `url()` in an
    `@font-face` to resolve against and no face is ever fetched here. Since `RCA-011` the shell
    serves its own Noto Sans Arabic from `/app/assets/` rather than the journey's `/beta/assets/`;
    that the browser really requests and loads it is proven from a real origin in
    `test_rca011_shell_font_load.py`. What this case still proves is that the governed chain
    reaches `body`, which is exactly what `#489` found missing.
    """
    from playwright.sync_api import sync_playwright

    from tests.test_r807_shell_quality import _html
    from tests.test_r811_shell_accessibility import _launch_chromium, _shell_css

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": 1180, "height": 900})
            page.set_content(_html(surface, "en"), wait_until="domcontentloaded")
            page.add_style_tag(content=_shell_css())
            declared = page.evaluate("getComputedStyle(document.body).fontFamily")
            assert "Noto Sans Arabic" in declared, (
                f"{surface}: body resolves to {declared!r}, not the shell's `--font-body`"
            )
            assert "serif" not in declared.replace("sans-serif", ""), (
                f"{surface}: body falls back to a serif -- {declared!r}"
            )
        finally:
            browser.close()
