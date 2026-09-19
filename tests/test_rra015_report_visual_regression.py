"""`RRA-015` `FR-190`-`FR-191`: visual-regression evidence for the report and evidence surfaces.

`tests/` only, and no stored image. Visual evidence here is **computed measurement** -- box
geometry from `getBoundingClientRect`, computed styles and element counts -- because a pixel
digest cannot name which of `FR-190`'s eight dimensions drifted, and a committed baseline
image would be the hosted baseline store `FR-190` excludes. Slice 10b measured both before
choosing; this module follows that decision rather than re-litigating it.

**Counts alone would not have been layout evidence.** Element counts and computed styles can
both hold while boxes move, overlap, clip or fail to mirror, so the probe also measures real
geometry: the content column against the viewport, section offsets from the START edge (so a
correct mirror reports the same numbers in both directions), section widths, and that sections
stack without overlapping.

**No stylesheet is injected, and that is a finding rather than an omission.** The report
renders one inline `<style>` element and zero `<link rel=stylesheet>`, so `set_content` alone
produces a fully styled page. The shell twin (`test_r812_shell_visual_regression.py`) must call
`add_style_tag(_shell_css())` because the shell serves its CSS as a separate asset; copying
that call here would inject the **shell's** stylesheet into a report page, which is the
cross-family token import `FR-201` forbids.

**Two fixtures, because one leaves a covered reference unexercised.** A chart needs
`published=True`; a refusal panel needs `published=False`, since `V-concentration` closes the
refusal window when the triple publishes. Measured: published `documents` renders 3 charts and
0 refusals, unpublished renders 0 charts and 12 refusals. A module measuring only the published
fixture would never exercise §16.4 #9 while reporting green.

**Every covered reference is reachable here, so nothing is exempted.** Slice 10b had to record
#9 as unreachable because no shell surface renders a refusal. That is not the situation on
these surfaces, so #9 gets a real measurement instead of a two-sided pin.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from khepri.rra.bundle import ReportBundle
from khepri.rra.rendering.html import HtmlReportRenderer
from tests.test_rra006_html_sections import ROWS, package_for

#: The reference pack. Its own README states the rule this module enforces: "Visual
#: composition is evidence. Generated product facts are not."
_PACK = Path(__file__).resolve().parents[1] / "docs" / "product" / "ui-visual-references"

#: Anything that would make an image a source of product truth (`FR-191`).
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".svg")

#: Verbs that would turn a reference image into an input rather than evidence.
_READS = re.compile(r"read_bytes|read_text|open\(|imread|Image\.|sha256|digest")

#: Both languages. Arabic is an equal surface, not a translation.
_LANGUAGES = ("ar", "en")

#: The surfaces `RRA-015` governs, matching slice 9a's reviewed literal. `HtmlSurface` exposes
#: exactly these two mappings.
_SURFACES = ("documents", "evidence")

#: `dir` per language, the pairing a server computes from the language alone.
_DIRECTION = {"ar": "rtl", "en": "ltr"}

#: The report's OWN spacing token. `report.css:28` declares `--report-space: 1rem` and uses it
#: 17 times as 1x, 1.5x and 2x -- a 16px rhythm with an 8px half-step.
#:
#: **Deliberately not the shell's `% 4 == 0`.** `FR-201` and the allocation plan's tree-state
#: finding 1 keep the journey/report and shell scales separate, so deriving this surface's
#: rhythm from `shell.css` would be the cross-family token import slice 3 was scoped around.
_RHYTHM_PX = 8

#: Surfaces whose asymmetric boxes are sized by TEXT rather than by the grid.
#:
#: `documents`' tables carry fixed column widths, so its `td` offsets are identical in both
#: languages whatever face resolves. `evidence` lets its columns size to content, so its
#: offsets follow the rendered text -- and a `set_content` page has no HTTP origin, so
#: `@font-face` never fetches and the metrics are the HOST's, not the product's. Measured:
#: the governed Arabic face resolves on `ubuntu-latest` and not on a Windows developer
#: machine, exactly as slice 9a recorded.
_TEXT_SIZED_SURFACES = frozenset({"evidence"})

#: The drift admitted on a text-sized surface. Wide enough to absorb a fallback face,
#: narrow enough that a real reflow -- a column order reversed, a panel moved to the other
#: edge -- is hundreds of pixels and still fails.
_TEXT_METRIC_TOLERANCE_PX = 40


def _measures_arabic_text_width(surface: str) -> bool:
    """Whether this surface's inline offsets depend on the resolved Arabic face."""
    return surface in _TEXT_SIZED_SURFACES


def _test_sources() -> list[Path]:
    """Every test module, anchored to `__file__` rather than the CWD.

    A bare `Path("tests")` resolves against the working directory and scans nothing when
    pytest runs from elsewhere, which passes vacuously.
    """
    return sorted(Path(__file__).resolve().parent.glob("test_*.py"))


#: A name bound to an image path, e.g. `ref = _PACK / "01-….png"`. Captured so a read
#: through that name on a LATER line is still attributed to the image.
_IMAGE_BINDING = re.compile(r"^\s*(\w+)\s*=.*")

#: A read, decode or digest performed through a name, e.g. `ref.read_bytes()`.
_READ_THROUGH = r"\b{name}\b\s*(?:\.\s*(?:read_bytes|read_text|open)|\))"

#: An inert line: a fixture that DEMONSTRATES the forbidden shape as data rather than
#: performing it. This module's own regression cases must contain the evasion they pin, and
#: the scan would otherwise report them as offenders.
#:
#: A marker rather than an exemption for this module. Excluding the file wholesale would
#: blind the guard on the one place most likely to touch reference images -- the same wrong
#: repair the platform scan's self-match invited.
_INERT = "scan-fixture: not a real read"


def _names_an_image(line: str) -> bool:
    """Whether this line mentions the reference pack or an image file."""
    return "ui-visual-references" in line or any(
        suffix in line for suffix in _IMAGE_SUFFIXES
    )


def _bound_name(line: str) -> set[str]:
    """The name this line binds, if it binds one, as a set for cheap union."""
    binding = _IMAGE_BINDING.match(line)
    return {binding.group(1)} if binding else set()


def _reads_through(line: str, bound: set[str]) -> bool:
    """Whether this line reads, decodes or digests through an image-bearing name."""
    return any(
        re.search(_READ_THROUGH.format(name=re.escape(name)), line) for name in bound
    )


def _image_read_lines(source: str) -> list[int]:
    """The 1-indexed lines where a module reads product truth out of an image.

    **Reads are tracked across statements, not per physical line.** The first version of
    this scan tested "names an image" and "performs a read" against the SAME line, so the
    two-statement form below slipped through while the guard reported compliance:

        reference = _PACK / "01-decision-refusal-rtl-comparison.png"   # names, no read
        payload = reference.read_bytes()   # reads, no name; scan-fixture: not a real read

    Any name bound to an image-bearing expression is therefore remembered, and a later read
    through that name is attributed to the image it came from. Unrelated image access that
    never feeds a read is left alone, as `FR-191` reaches reading values out of a picture
    rather than mentioning one.
    """
    bound: set[str] = set()
    offenders: list[int] = []

    for number, line in enumerate(source.splitlines(), 1):
        if _INERT in line:
            continue
        if _names_an_image(line):
            offenders.extend([number] if _READS.search(line) else [])
            bound.update(_bound_name(line))
            continue
        offenders.extend([number] if _reads_through(line, bound) else [])

    return offenders


def _surfaces(*, published: bool) -> dict[tuple[str, str], str]:
    """Every governed surface, keyed by (surface, language), on one fixture."""
    rendered = HtmlReportRenderer().render_html(
        ReportBundle.of(package_for(ROWS, published=published))
    )
    out: dict[tuple[str, str], str] = {}
    for surface in _SURFACES:
        mapping = getattr(rendered, surface)
        for language in _LANGUAGES:
            out[(surface, language)] = mapping[language]
    return out


#: The §16.4-covered references, mapped to the RRA subject that realizes each one. A reviewed
#: literal cross-checked against §16.2's descriptions and the pack's own README -- not derived
#: from the surfaces these tests happen to drive, which would be a tautology.
#:
#: Slice 10b claimed #6 and #8 for SHELL surfaces (`compare`, `decision`). This module claims
#: them for RRA surfaces. That is not a collision: a §16.2 reference is a design requirement,
#: and two families may each realize it on their own surface. Recorded so a later reader does
#: not read the repeated numbers as a copy-paste error.
#:
#: Each value is (surface, published, marker, languages). The language tuple is explicit
#: because one reference is language-specific by definition: `dir="rtl"` renders on the Arabic
#: document and must NOT render on the English one, so checking it against both languages
#: would report a correct surface as missing its subject.
_REFERENCE_SUBJECTS = {
    "#6 period comparison": ("documents", True, "<svg", _LANGUAGES),
    "#8 evidence drawer": ("evidence", True, "<table", _LANGUAGES),
    "#9 refusal": ("documents", False, 'class="[^"]*refus', _LANGUAGES),
    "#10 Arabic RTL": ("documents", True, 'dir="rtl"', ("ar",)),
}


def test_no_test_reads_a_value_out_of_a_reference_image() -> None:
    """`FR-191`: an image is evidence, not truth.

    No module may open, read, decode or digest a file from the reference pack. A test that
    did would be taking a figure, route, capability, refusal reason or governed word from a
    picture -- and where an image and an active specification disagree, the specification
    wins.
    """
    sources = _test_sources()
    assert sources, "no test modules found, so this scan proves nothing"

    offenders = [
        f"{source.name}:{number}"
        for source in sources
        for number in _image_read_lines(source.read_text(encoding="utf-8"))
    ]

    assert offenders == [], "a test reads product truth out of an image: " + ", ".join(offenders)


def test_the_image_scan_catches_a_read_split_across_two_statements() -> None:
    """The evasion the per-line form admitted, pinned so it cannot return.

    Binding the path on one line and reading through the name on the next matches neither
    predicate on either line. A scan that tested both against one line reported compliance
    while the bytes went on to supply a governed value.
    """
    split = (
        'reference = _PACK / "01-decision-refusal-rtl-comparison.png"\n'
        'payload = reference.read_bytes()\n'  # scan-fixture: not a real read
    )
    assert _image_read_lines(split) == [2], (
        "a read split across two statements is not detected, so the scan can be evaded"
    )

    same_line = (
        'payload = (_PACK / "01-decision-refusal-rtl-comparison.png")'
        '.read_bytes()\n'  # scan-fixture: not a real read
    )
    assert _image_read_lines(same_line) == [1], (  # scan-fixture: not a real read
        "the single-line form is no longer detected"
    )


def test_the_image_scan_admits_mentioning_an_image_without_reading_it() -> None:
    """`FR-191` reaches reading values out of a picture, not naming one.

    Asserted so the widened scan cannot drift into refusing every mention -- which would
    make the guard unusable and invite its deletion. This module's own docstrings name the
    pack repeatedly.
    """
    mention = (
        '_PACK = Path(__file__).parents[1] / "docs" / "product" / "ui-visual-references"\n'
        'assert _PACK.is_dir(), "the reference pack is missing"\n'
        "images = [entry for entry in _PACK.iterdir() if entry.suffix in _IMAGE_SUFFIXES]\n"
    )
    assert _image_read_lines(mention) == [], (
        "the scan flags a mention that reads no value, which would refuse legitimate code"
    )


def test_the_image_scan_is_anchored_to_the_module_not_the_working_directory() -> None:
    """The scan above must find the same modules from any CWD.

    A CWD-relative sweep passes vacuously when pytest runs from elsewhere. Asserted by
    comparing the anchored result against the same glob resolved from two different working
    directories, rather than by trusting the `__file__` expression to be correct.
    """
    import os

    anchored = _test_sources()
    assert anchored, "the anchored scan found nothing"

    original = Path.cwd()
    seen = []
    try:
        for where in (Path(__file__).resolve().parents[1], Path(__file__).resolve().parent):
            os.chdir(where)
            seen.append(_test_sources())
    finally:
        os.chdir(original)

    assert seen[0] == anchored and seen[1] == anchored, (
        "the scan's file set depends on the working directory, so it can pass vacuously"
    )


def test_the_reference_pack_is_present_so_the_scan_is_not_vacuous() -> None:
    """The scan above guards nothing if the pack has moved or emptied."""
    assert _PACK.is_dir(), f"the reference pack is missing at {_PACK}"
    images = [entry for entry in _PACK.iterdir() if entry.suffix in _IMAGE_SUFFIXES]
    assert images, "the reference pack holds no images, so `FR-191` guards nothing here"


def test_no_baseline_image_or_visual_testing_platform_is_introduced() -> None:
    """`FR-190`: the shipped Playwright/Chromium, and no hosted baseline store.

    A stored baseline committed beside this module would BE the baseline store the
    requirement excludes, so its absence is asserted rather than assumed.
    """
    # `rglob`, not `iterdir`: the latter sees only direct children, so `tests/baselines/
    # report.png` -- the conventional place a baseline store would appear -- passed the
    # first version of this guard untouched.
    root = Path(__file__).resolve().parent
    stored = sorted(
        str(entry.relative_to(root))
        for entry in root.rglob("*")
        if entry.suffix in _IMAGE_SUFFIXES
    )
    assert stored == [], f"a baseline image is stored under the test tree: {stored}"

    # Assembled from fragments so this module's own source never contains a whole platform
    # name. Spelling them out here would make the scan match ITSELF, and the obvious repair
    # -- excluding this module -- would blind the guard on the one file most likely to
    # introduce a snapshot platform. The names are reassembled at runtime and match real
    # usage anywhere, including here.
    platforms = re.compile(
        "|".join(
            first + rest
            for first, rest in (
                ("per", "cy"),
                ("appli", "tools"),
                ("chroma", "tic"),
                ("to_match_", "snapshot"),
                ("assert_", "snapshot"),
            )
        )
    )
    offenders = [
        source.name
        for source in _test_sources()
        if platforms.search(source.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"a visual-testing platform is referenced: {offenders}"


def test_every_named_reference_resolves_to_a_surface_that_renders_its_subject() -> None:
    """A reference naming nothing measures nothing.

    This is what keeps the mapping honest: an entry whose subject does not render on the
    stated fixture is a null case, and a null case is NOT EXERCISED rather than a pass.
    """
    assert _REFERENCE_SUBJECTS, "no references named, so this slice measures nothing"

    missing = []
    for reference, (surface, published, marker, languages) in _REFERENCE_SUBJECTS.items():
        documents = _surfaces(published=published)
        for language in languages:
            if not re.search(marker, documents[(surface, language)]):
                missing.append(f"{reference} -> {surface}/{language}")

    assert missing == [], (
        "a covered reference has no subject on the surface it names, so it would be "
        f"measured over nothing: {missing}"
    )


def test_the_refusal_reference_is_measured_rather_than_exempted() -> None:
    """§16.4 #9 is reachable on these surfaces, unlike on the shell's.

    Slice 10b recorded #9 as unreachable because no shell surface renders a refusal. The
    report surface renders refusal panels on the unpublished fixture, so this module owes it
    a measurement. Asserted with a count rather than presence, so a fixture that stopped
    producing refusals fails here rather than silently measuring an empty set.
    """
    documents = _surfaces(published=False)
    for language in _LANGUAGES:
        panels = re.findall(r'class="[^"]*refus', documents[("documents", language)])
        assert panels, (
            f"documents/{language} renders no refusal panel on the unpublished fixture, "
            "so §16.4 #9 would be measured over nothing"
        )

    published = _surfaces(published=True)
    for language in _LANGUAGES:
        assert not re.findall(r'class="[^"]*refus', published[("documents", language)]), (
            f"documents/{language} renders a refusal on the PUBLISHED fixture too, so the "
            "two-fixture split this module rests on no longer holds"
        )


def _launch_chromium(playwright: object) -> object:
    """The pinned Chromium, or `pytest.skip` when this machine genuinely has none.

    In CI a skip is fatal: `.github/scripts/require_browser_tests.py` fails the job if any
    `browser`-marked test skips, because the pinned Chromium being unavailable is exactly the
    silent-green regression `FND-005` closed. This branch exists for a developer machine
    without the browser installed.
    """
    from playwright.sync_api import Error

    try:
        return playwright.chromium.launch()  # type: ignore[attr-defined]
    except Error as error:  # pragma: no cover - depends on the environment
        pytest.skip(f"Pinned Chromium is unavailable: {error}")


#: Read in the page, so every value is what the browser resolved rather than what a sheet
#: declares. Keyed by `FR-190`'s dimension names, so a failure says *which* of the eight
#: drifted rather than only that something moved -- the property a pixel digest cannot have.
#:
#: The selectors are the report's own, not the shell's: `evidence` renders zero charts and
#: zero `nav`, so a probe written for `.document-card` would measure nothing here.
_PROBE = """
(() => {
  return {
    hierarchy: {
      h1: document.querySelectorAll('h1').length,
      h2: document.querySelectorAll('h2').length,
      h3: document.querySelectorAll('h3').length,
      landmarks: document.querySelectorAll('nav, main, header').length,
    },
    density: {
      tables: document.querySelectorAll('table').length,
      rows: document.querySelectorAll('tr').length,
      actions: document.querySelectorAll('a[href], button').length,
      charts: document.querySelectorAll('svg[role="img"]').length,
    },
    spacing_rhythm: (() => {
      // Measured on the elements `report.css` actually puts `--report-space` on: `body`
      // (`:51-52`, 2x block and 1x inline) and `section` (`:166`, 2x block-end). `main`
      // carries no padding at all, so probing it measured 0px -- and `0 % n == 0` for every
      // n, which made this dimension pass against any rhythm whatsoever.
      const bodyStyle = getComputedStyle(document.body);
      const section = document.querySelector('section');
      const out = {
        body_padding_block: bodyStyle.paddingBlockStart,
        body_padding_inline: bodyStyle.paddingInlineStart,
      };
      if (section) {
        out.section_margin_block_end = getComputedStyle(section).marginBlockEnd;
      }
      return out;
    })(),
    typography: {
      body: getComputedStyle(document.body).fontFamily,
    },
    geometry: (() => {
      // Real box geometry. Counts and computed styles can BOTH hold while boxes move,
      // overlap, clip or fail to mirror -- so a module claiming visual regression on
      // counts alone measures composition and not layout.
      //
      // Rounded to whole pixels: sub-pixel text metrics differ with the resolved face,
      // and a `set_content` page has no HTTP origin, so `@font-face` never fetches and
      // fractional widths become a property of the HOST rather than the product.
      const viewport = document.documentElement.clientWidth;
      const round = (value) => Math.round(value);
      const rtl = getComputedStyle(document.documentElement).direction === 'rtl';
      const sections = [...document.querySelectorAll('section')].slice(0, 3);
      const body = document.body.getBoundingClientRect();
      return {
        // The content column must not exceed the viewport: the overflow defect.
        body_within_viewport: body.width <= viewport + 1,
        body_width: round(body.width),
        // Inline offset from the START edge, so a mirrored layout reports the SAME
        // value in both directions and a broken mirror does not.
        //
        // Measured on elements that are ASYMMETRIC in the inline axis. Every block-level
        // box here is full-width and centred, so its start offset equals its left offset
        // in BOTH directions -- comparing those asserts 62 == 62 and passes whether the
        // page mirrors or ignores direction entirely. Measured: `section`, `.disclosure`,
        // `ul` and `h2` are all [62, 1118] in each language.
        //
        // `li` and `td` really do mirror. `li` carries `padding-inline-start`, so it sits
        // at left 82 in English and 62 in Arabic; `td` reverses column order, 823 -> 62.
        // Those are the boxes a broken mirror actually moves.
        asymmetric_inline_starts: [...document.querySelectorAll('li, td')]
          .slice(0, 4)
          .map((element) => {
            const box = element.getBoundingClientRect();
            return round(rtl ? viewport - box.right : box.left);
          }),
        // The same boxes' raw left offsets. Under a correct mirror these DIFFER between
        // languages; asserted so the pair above cannot silently become a tautology again.
        asymmetric_raw_lefts: [...document.querySelectorAll('li, td')]
          .slice(0, 4)
          .map((element) => round(element.getBoundingClientRect().left)),
        section_inline_starts: sections.map((element) => {
          const box = element.getBoundingClientRect();
          return round(rtl ? viewport - box.right : box.left);
        }),
        section_widths: sections.map((element) =>
          round(element.getBoundingClientRect().width)
        ),
        // Stacked, not overlapping: each section begins at or after the previous ends.
        sections_stack_without_overlap: sections.every((element, index) => {
          if (index === 0) { return true; }
          const previous = sections[index - 1].getBoundingClientRect();
          return element.getBoundingClientRect().top >= previous.bottom - 1;
        }),
      };
    })(),
    rtl: {
      dir: document.documentElement.getAttribute('dir'),
      lang: document.documentElement.getAttribute('lang'),
    },
  };
})()
"""


def _measure(document: str, *, width: int = 1180) -> dict[str, object]:
    """One surface's measured dimensions, in a real browser.

    No `add_style_tag`: the report inlines its stylesheet, so the page is fully styled from
    `set_content` alone. Injecting the shell's sheet here would import another family's
    tokens.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": width, "height": 900})  # type: ignore[attr-defined]
            page.set_content(document, wait_until="domcontentloaded")
            return page.evaluate(_PROBE)
        finally:
            browser.close()  # type: ignore[attr-defined]


@pytest.mark.browser
@pytest.mark.parametrize("surface", _SURFACES)
def test_the_measured_dimensions_are_deterministic_across_two_runs(surface: str) -> None:
    """`FR-190` §Verification: the evidence is reproducible and deterministic across two runs.

    This is the property that makes measurement usable as evidence at all. It is asserted
    rather than assumed, because a measurement that varied between runs would report drift
    that is not there and hide drift that is.
    """
    document = _surfaces(published=True)[(surface, "en")]
    first = _measure(document)
    assert first["hierarchy"], f"{surface}: nothing measured, so this proves nothing"
    assert first == _measure(document), f"{surface}: the measurement is not deterministic"


@pytest.mark.browser
@pytest.mark.parametrize("surface", _SURFACES)
def test_the_spacing_rhythm_comes_from_the_report_token_scale(surface: str) -> None:
    """`FR-190` spacing rhythm: the surface's padding sits on the report's own rhythm.

    Asserted against `--report-space`, which `report.css` declares and uses 17 times as 1x,
    1.5x and 2x -- a 16px rhythm with an 8px half-step. **Not** against the shell's 4px
    scale: `FR-201` keeps the two families' token scales separate, and importing the shell's
    rhythm here would be the cross-family coupling slice 3 was scoped around.

    Never against a value read out of a reference image, which `FR-191` forbids and which
    would make the picture the source.
    """
    measured = _measure(_surfaces(published=True)[(surface, "en")])["spacing_rhythm"]
    assert measured, f"{surface}: nothing measured, so this proves nothing"
    for name, value in measured.items():
        pixels = float(str(value).removesuffix("px"))
        # Zero is the vacuous case and is refused explicitly. `0 % n == 0` holds for EVERY
        # divisor, so a zero measurement passes against any rhythm whatsoever -- which is
        # what an earlier probe of `main` did, and what mutating `_RHYTHM_PX` to 7 exposed.
        assert pixels > 0, (
            f"{surface}: spacing_rhythm {name} is {value}, which satisfies every rhythm and "
            "therefore measures none"
        )
        assert pixels % _RHYTHM_PX == 0, (
            f"{surface}: spacing_rhythm {name} is {value}, off the report's "
            f"{_RHYTHM_PX}px rhythm"
        )


@pytest.mark.browser
@pytest.mark.parametrize("surface", _SURFACES)
def test_the_right_to_left_rendering_mirrors_rather_than_reflows(surface: str) -> None:
    """`FR-190` RTL: Arabic is the same page mirrored, not a different composition.

    Hierarchy and density are language-invariant by construction -- the same template renders
    both -- so a divergence here is a real visual-language drift rather than a translation
    artifact. This is the dimension §16.4 covers outright (#10).
    """
    documents = _surfaces(published=True)
    english = _measure(documents[(surface, "en")])
    arabic = _measure(documents[(surface, "ar")])

    assert english["rtl"]["dir"] == _DIRECTION["en"], f"{surface}: English is not ltr"
    assert arabic["rtl"]["dir"] == _DIRECTION["ar"], f"{surface}: Arabic is not rtl"
    assert english["hierarchy"] == arabic["hierarchy"], (
        f"{surface}: hierarchy differs by language -- "
        f"{english['hierarchy']} vs {arabic['hierarchy']}"
    )
    assert english["density"] == arabic["density"], (
        f"{surface}: density differs by language -- {english['density']} vs {arabic['density']}"
    )

    # Geometry, because counts and computed styles can both hold while the boxes fail to
    # mirror. Offsets are measured from the START edge, so a correctly mirrored layout
    # reports the SAME numbers in both directions and a broken mirror reports different
    # ones -- which comparing `left` could never distinguish from correct mirroring.
    for language, measured in (("en", english), ("ar", arabic)):
        assert measured["geometry"]["body_within_viewport"], (
            f"{surface}/{language}: the content column is "
            f"{measured['geometry']['body_width']}px and overflows the viewport"
        )
        assert measured["geometry"]["sections_stack_without_overlap"], (
            f"{surface}/{language}: sections overlap rather than stacking"
        )

    assert english["geometry"]["section_widths"] == arabic["geometry"]["section_widths"], (
        f"{surface}: section widths differ by language -- "
        f"{english['geometry']['section_widths']} vs {arabic['geometry']['section_widths']}"
    )

    # The mirror itself, on boxes that actually move. Two assertions, because either alone
    # is satisfiable by a page that ignores direction:
    #   * equal offsets FROM THE START EDGE -- the same composition in both directions;
    #   * DIFFERENT raw left offsets -- proof the page really mirrored rather than
    #     rendering identically, which is what made the centred-box version a tautology.
    english_starts = english["geometry"]["asymmetric_inline_starts"]
    arabic_starts = arabic["geometry"]["asymmetric_inline_starts"]
    assert english_starts, f"{surface}: no asymmetric box measured, so this proves nothing"
    if _measures_arabic_text_width(surface):
        # Offsets on this surface follow TEXT metrics, and a `set_content` page has no
        # HTTP origin, so `@font-face` never fetches and the width depends on the face the
        # HOST happens to have. Compared as a tolerance rather than pinned: an exact match
        # would encode a machine-specific number, which is the defect slice 9a recorded
        # when `evidence/ar` was briefly pinned and then reported `XPASS(strict)` in CI.
        drift = [abs(a - b) for a, b in zip(english_starts, arabic_starts, strict=True)]
        assert max(drift) <= _TEXT_METRIC_TOLERANCE_PX, (
            f"{surface}: asymmetric boxes drift {drift}px from the start edge, beyond the "
            f"{_TEXT_METRIC_TOLERANCE_PX}px text-metric tolerance -- a real reflow"
        )
    else:
        assert english_starts == arabic_starts, (
            f"{surface}: asymmetric boxes sit at different offsets from the start edge -- "
            f"{english_starts} vs {arabic_starts}, so the layout reflows rather than mirrors"
        )
    assert english["geometry"]["asymmetric_raw_lefts"] != (
        arabic["geometry"]["asymmetric_raw_lefts"]
    ), (
        f"{surface}: the asymmetric boxes occupy identical raw positions in both "
        "languages, so the page renders the same rather than mirroring and the "
        "start-edge comparison above is measuring nothing"
    )


@pytest.mark.browser
def test_the_refusal_composition_is_language_invariant() -> None:
    """§16.4 #9, measured in the browser rather than in the markup.

    The unpublished fixture is the only one that renders refusals, so this case carries the
    reference that slice 10b could only record as absent.
    """
    documents = _surfaces(published=False)
    english = _measure(documents[("documents", "en")])
    arabic = _measure(documents[("documents", "ar")])

    assert english["hierarchy"] == arabic["hierarchy"], (
        "the refusal surface's hierarchy differs by language -- "
        f"{english['hierarchy']} vs {arabic['hierarchy']}"
    )
    assert english["density"] == arabic["density"], (
        f"the refusal surface's density differs by language -- "
        f"{english['density']} vs {arabic['density']}"
    )
    assert english["density"]["charts"] == 0, (
        "the unpublished fixture renders a chart, so it is not the refusal-bearing fixture "
        "this case relies on"
    )

    # The refusal surface is laid out, not merely composed. A refusal panel that overflowed
    # or overlapped its neighbour would leave every count above unchanged.
    for language, measured in (("en", english), ("ar", arabic)):
        assert measured["geometry"]["body_within_viewport"], (
            f"the refusal surface overflows the viewport in {language} at "
            f"{measured['geometry']['body_width']}px"
        )
        assert measured["geometry"]["sections_stack_without_overlap"], (
            f"the refusal surface's sections overlap in {language}"
        )

    # Same two-sided mirror check as the RTL case: equal from the start edge, different
    # raw positions. Either alone passes on a page that ignores direction.
    assert english["geometry"]["asymmetric_inline_starts"] == (
        arabic["geometry"]["asymmetric_inline_starts"]
    ), (
        "the refusal surface reflows rather than mirrors -- "
        f"{english['geometry']['asymmetric_inline_starts']} vs "
        f"{arabic['geometry']['asymmetric_inline_starts']}"
    )
    assert english["geometry"]["asymmetric_raw_lefts"] != (
        arabic["geometry"]["asymmetric_raw_lefts"]
    ), (
        "the refusal surface occupies identical raw positions in both languages, so it "
        "renders the same rather than mirroring"
    )
