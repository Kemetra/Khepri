"""`RCA-011`: the shell serves its own typeface.

`#489` applied `--font-body` to every shell and legal page and found that the face it names cannot
load: the `@font-face` rules lived in `journey.css`, addressed `/beta/assets/`, and
`add_journey_routes` is not mounted in the deployed image. The token worked as written -- the
cascade fell through to `"Segoe UI", Tahoma, sans-serif` -- but the specific face never arrived.

This module is the evidence for closing that gap. Each test names the requirement it proves.

**Why the assertions read `fonts.py`'s constants rather than string literals.** The stylesheet, the
allowlist and the digest manifest are three places one filename and one `unicode-range` are
written. A test with the values typed in passes while those three drift apart, which is `#486`'s
recorded failure mode: guards built from rendered output fired on correct markup. Here the CSS is
compared against the constants that bind the bytes, so a subset narrowed in `fonts.py` and not in
the stylesheet fails here rather than in a browser asking for glyphs the file does not carry.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from importlib.resources import files
from pathlib import Path

import pytest

from khepri.rra.journey.security import SECURITY_HEADERS
from khepri.rra.rendering.fonts import (
    ARABIC_FILE,
    ARABIC_UNICODE_RANGE,
    FONT_DIGESTS,
    FONT_DIRECTORY,
    FONT_MEDIA_TYPE,
    FONT_PACKAGE,
    LATIN_FILE,
    LATIN_UNICODE_RANGE,
)
from khepri.runtime.shell_api import _ASSETS, SHELL_ASSETS
from tests.test_r802_shell_unavailable_surface import _client, _StubResolver

#: The repository root, anchored to this file rather than the working directory. A `Path("src")`
#: resolved from the CWD scans nothing when pytest runs from `tests/`, and a scan over nothing
#: passes vacuously -- the recorded `#486`-adjacent defect this module refuses to repeat.
_ROOT = Path(__file__).resolve().parents[1]
_JOURNEY_ASSETS = _ROOT / "src" / "khepri" / "rra" / "journey" / "assets"
_RUNTIME_ASSETS = _ROOT / "src" / "khepri" / "runtime" / "shell_assets"

#: The stylesheets a shell or legal surface links. `journey.css` is deliberately absent: it is the
#: journey's, it keeps its own `/beta/assets/` address, and `RCA-011` does not touch it.
_SHELL_STYLESHEETS = (
    _JOURNEY_ASSETS / "shell.css",
    _JOURNEY_ASSETS / "shell-components.css",
    _RUNTIME_ASSETS / "workspace.css",
)

_TYPEFACES = (ARABIC_FILE, LATIN_FILE)


def _components_css() -> str:
    return (_JOURNEY_ASSETS / "shell-components.css").read_text(encoding="utf-8")


def _declarations(css: str) -> str:
    """The stylesheet with block comments removed, as `test_r801_shell_tokens.py` does it.

    Load-bearing here for the reason that file records: this slice's comments *describe* the
    prohibitions -- "no `@import`", "the only `url()` here is the shell's own" -- and a scan that
    read prose would report the description as the violation. Syntax is checked on declarations;
    URLs are checked on raw text, because an address in a comment still points a reader at one.
    """
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


class TestFR207TheShellServesItsOwnTypeface:
    """The two subsets ship as package data and are served by exact name."""

    @pytest.mark.parametrize("file_name", _TYPEFACES)
    def test_the_face_is_served_from_the_shells_own_address(
        self, file_name: str
    ) -> None:
        response = _client().get(f"{SHELL_ASSETS}/{file_name}")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith(FONT_MEDIA_TYPE)

    @pytest.mark.parametrize("file_name", _TYPEFACES)
    def test_the_bytes_served_are_the_audited_bytes(self, file_name: str) -> None:
        """Not merely a 200: the route must hand back the face the manifest digests.

        A route serving the right name from the wrong directory would pass a status check.
        """
        response = _client().get(f"{SHELL_ASSETS}/{file_name}")

        assert hashlib.sha256(response.content).hexdigest() == FONT_DIGESTS[file_name]

    def test_an_unknown_typeface_name_is_refused(self) -> None:
        """Served by being named, not by arriving: the allowlist is a `dict`, not a listing.

        `OFL.txt` sits in the same directory as the two faces and is deliberately not served.
        """
        for name in ("OFL.txt", "NotoSansArabic-Regular-cyrillic.woff2"):
            assert _client().get(f"{SHELL_ASSETS}/{name}").status_code == 404

    def test_no_existing_allowlist_entry_was_altered(self) -> None:
        """`RCA-011` §Scope: "No existing `_ASSETS` entry is altered or removed."

        The media type moved into the entry, so the three stylesheets are re-asserted whole --
        name, package, directory and type -- rather than trusted to have survived the edit.
        """
        stylesheet = "text/css; charset=utf-8"

        assert _ASSETS["shell.css"] == ("khepri.rra.journey", "assets", stylesheet)
        assert _ASSETS["shell-components.css"] == (
            "khepri.rra.journey",
            "assets",
            stylesheet,
        )
        assert _ASSETS["workspace.css"] == (
            "khepri.runtime",
            "shell_assets",
            stylesheet,
        )

    def test_the_allowlist_gained_exactly_the_two_faces(self) -> None:
        """An extent assertion, not a subset one.

        `>=` only ever weakens: a third entry added by a later slice must fail here rather than
        pass unnoticed. This is the recorded `RCA_TABLES` drift, applied to an asset allowlist.
        """
        assert set(_ASSETS) == {
            "shell.css",
            "shell-components.css",
            "workspace.css",
            ARABIC_FILE,
            LATIN_FILE,
        }

    @pytest.mark.parametrize("file_name", _TYPEFACES)
    def test_the_entry_reads_from_the_digested_package(self, file_name: str) -> None:
        """One copy, not two. `fonts.py` verifies these exact bytes; a second copy elsewhere
        would be a face nothing checks."""
        assert _ASSETS[file_name] == (FONT_PACKAGE, FONT_DIRECTORY, FONT_MEDIA_TYPE)


class TestFR208NoShellStylesheetNamesAJourneyAddress:
    """`FR-201` is unchanged: the asset moved, the permission did not widen."""

    def test_no_shell_stylesheet_contains_a_beta_address(self) -> None:
        """Declarations, not prose: `shell-components.css` explains *why* it no longer names
        `/beta/assets/`, and that sentence is not the shell reaching for the journey's address."""
        offenders = {
            path.name: [
                line
                for line in _declarations(
                    path.read_text(encoding="utf-8")
                ).splitlines()
                if "/beta/" in line
            ]
            for path in _SHELL_STYLESHEETS
        }

        assert not any(offenders.values()), f"a shell stylesheet names /beta/: {offenders}"

    def test_the_scan_actually_read_the_stylesheets(self) -> None:
        """The emptiness assertion above is only evidence if it scanned something.

        A path anchored to the CWD reads nothing from `tests/` and reports clean. Proving the
        files exist and are non-empty is what makes the absence above a measurement.
        """
        for path in _SHELL_STYLESHEETS:
            assert path.is_file(), f"{path} is not where the scan looks"
            assert path.read_text(encoding="utf-8").strip(), f"{path} is empty"

    def test_the_scan_would_fire_on_a_beta_address(self) -> None:
        """A guard that cannot fail is not a guard. `journey.css` is the positive control: it
        genuinely carries `/beta/` addresses and is genuinely not a shell stylesheet."""
        journey = _declarations(
            (_JOURNEY_ASSETS / "journey.css").read_text(encoding="utf-8")
        )

        assert "/beta/assets/" in journey, "the control carries no /beta/ declaration"
        assert (_JOURNEY_ASSETS / "journey.css") not in _SHELL_STYLESHEETS

    @pytest.mark.parametrize("file_name", _TYPEFACES)
    def test_the_font_face_names_the_shells_own_address(self, file_name: str) -> None:
        """Derived from `SHELL_ASSETS`, so moving `SHELL_PREFIX` fails here rather than
        silently leaving the stylesheet pointing at an address nothing serves."""
        assert (
            f'url("{SHELL_ASSETS}/{file_name}") format("woff2")'
            in _declarations(_components_css())
        )


class TestFR209NoExternalReference:
    """No `@import`, no font host, no CDN, no runtime download, no new digest."""

    def test_the_component_stylesheet_has_no_external_reference(self) -> None:
        css = _components_css()
        folded = _declarations(css).lower()

        # Syntax, on declarations: this file's own comment says "no `@import`", and scanning it
        # would fail the check that sentence describes.
        assert "@import" not in folded
        assert not re.search(r"url\(\s*['\"]?(?:https?:)?//", folded)

        # Addresses, on raw text: a font host named in a comment is still a reader being pointed
        # at one, which is how `test_r801_shell_tokens.py` treats the design handoff's CDN.
        assert "http://" not in css
        assert "https://" not in css

    def test_every_url_in_the_stylesheet_is_the_shells_own_address(self) -> None:
        """An extent assertion over `url()`: the file is allowed exactly two, both same-origin.

        The `#489`-era guard forbade `url(` outright in `shell.css`. That file is untouched and
        keeps its absolute prohibition; this one now carries the shell's own asset addresses, so
        the check becomes "every URL is one of these two" rather than "there are none".
        """
        urls = re.findall(
            r"url\(\s*['\"]?([^'\")]+)", _declarations(_components_css())
        )

        assert sorted(urls) == sorted(
            f"{SHELL_ASSETS}/{name}" for name in _TYPEFACES
        )

    @pytest.mark.parametrize(
        ("file_name", "unicode_range"),
        ((ARABIC_FILE, ARABIC_UNICODE_RANGE), (LATIN_FILE, LATIN_UNICODE_RANGE)),
    )
    def test_the_declared_range_is_the_range_the_file_carries(
        self, file_name: str, unicode_range: str
    ) -> None:
        """A wider range asks the browser for glyphs the subset does not contain.

        Compared against `fonts.py`'s constant rather than a literal, so the stylesheet and the
        manifest cannot drift apart silently.
        """
        block = re.search(
            r"@font-face\s*\{[^}]*"
            + re.escape(file_name)
            + r"[^}]*unicode-range:\s*([^;]+);",
            _components_css(),
        )

        assert block is not None, f"no @font-face block for {file_name}"
        assert block.group(1).strip() == unicode_range

    def test_no_new_font_and_no_changed_digest(self) -> None:
        """`FR-209`: the files are the ones already audited. Two faces, two digests, unchanged."""
        assert set(FONT_DIGESTS) == {ARABIC_FILE, LATIN_FILE}
        assert FONT_DIGESTS[ARABIC_FILE] == (
            "4e2ca0745c908761dc5c5db951662873887c59366fa1a5693ad22c0864abf1bd"
        )
        assert FONT_DIGESTS[LATIN_FILE] == (
            "290bdad021425e6ba6263c27d38652403f9b1a9ee74f5bbd2c62905b13f71b8c"
        )


class TestFR210TheFallbackChainSurvives:
    """The face becomes available; the fallback does not become unnecessary."""

    def test_the_token_keeps_its_full_declaration(self) -> None:
        shell_css = (_JOURNEY_ASSETS / "shell.css").read_text(encoding="utf-8")

        assert (
            '--font-body: "Noto Sans Arabic", "Segoe UI", Tahoma, sans-serif;' in shell_css
        )

    def test_the_body_rule_still_consumes_the_token(self) -> None:
        """`FR-210` is about the chain, not the face: a `body` rule naming the family directly
        would load the same font and silently discard three fallbacks."""
        assert re.search(
            r"body\s*\{[^}]*font-family:\s*var\(--font-body\)",
            _declarations(_components_css()),
        )

    def test_the_face_does_not_block_first_paint(self) -> None:
        """`font-display: swap` keeps the fallback load-bearing rather than decorative: text
        paints in the next available family instead of waiting on the download."""
        assert _declarations(_components_css()).count("font-display: swap;") == len(
            _TYPEFACES
        )


class TestFR211ServingATypefaceAddsNoCapability:
    """The asset route answers the same way for every caller."""

    def test_the_face_is_served_without_a_session(self) -> None:
        """No cookie, no actor resolution, no membership: a stylesheet and a font are the same
        kind of thing to this route, and neither reads who is asking."""
        response = _client().get(f"{SHELL_ASSETS}/{ARABIC_FILE}")

        assert response.status_code == 200
        assert "set-cookie" not in {k.lower() for k in response.headers}

    def test_the_answer_does_not_vary_by_caller(self) -> None:
        """Two callers, one with a forged session cookie, get byte-identical answers."""
        plain = _client().get(f"{SHELL_ASSETS}/{ARABIC_FILE}")
        forged = _client()
        forged.cookies.set("khepri_session", "forged")
        with_cookie = forged.get(f"{SHELL_ASSETS}/{ARABIC_FILE}")

        assert plain.content == with_cookie.content
        assert plain.status_code == with_cookie.status_code

    def test_the_route_is_declared_without_a_resolver(self) -> None:
        """`FR-211`: no authorization path. The route serves with `services=None`-free wiring in
        the same way the stylesheets always did -- proven by the absence of a resolver call."""
        resolver = _StubResolver()
        response = _client(resolver=resolver).get(f"{SHELL_ASSETS}/{LATIN_FILE}")

        assert response.status_code == 200
        assert resolver.calls == [], f"the asset route resolved an actor: {resolver.calls}"

    def test_the_shipped_policy_still_allows_only_same_origin_fonts(self) -> None:
        """`FR-211`: the CSP is unweakened. `font-src 'self'` is what makes the same-origin
        address above loadable, and it is also what keeps a hosted face unloadable."""
        policy = SECURITY_HEADERS["Content-Security-Policy"]

        assert "font-src 'self'" in policy
        assert "default-src 'none'" in policy


class TestTheShippedArtifactCarriesTheFaces:
    """`W1-07a`'s defect: a route absent from the image passes every hand-wired fixture.

    Docker is not available in CI (`test_build_image.py` says so and builds nothing), so the
    assertion is made against the wheel's *inclusion rule* rather than a running container: the
    files are under a packaged directory and outside the one exclusion the build declares.
    """

    @pytest.mark.parametrize("file_name", _TYPEFACES)
    def test_the_face_is_readable_as_package_data(self, file_name: str) -> None:
        payload = files(FONT_PACKAGE).joinpath(FONT_DIRECTORY, file_name).read_bytes()

        assert payload, f"{file_name} is not readable through the package"

    @pytest.mark.parametrize("file_name", _TYPEFACES)
    def test_the_wheel_includes_the_directory_the_faces_live_in(
        self, file_name: str
    ) -> None:
        """Read from `pyproject.toml`, not restated: a build that stopped packaging
        `src/khepri`, or started excluding `rendering`, must fail here."""
        config = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        wheel = config["tool"]["hatch"]["build"]["targets"]["wheel"]

        face = (
            _ROOT / "src" / Path(*FONT_PACKAGE.split(".")) / FONT_DIRECTORY / file_name
        )
        assert face.is_file(), f"{face} is not in the tree the wheel packages"

        relative = face.relative_to(_ROOT).as_posix()
        assert any(relative.startswith(f"{pkg}/") for pkg in wheel["packages"]), (
            f"{relative} is under no packaged root: {wheel['packages']}"
        )
        for excluded in wheel["exclude"]:
            assert not relative.startswith(f"{excluded}/"), (
                f"{relative} is excluded from the wheel by {excluded}"
            )
