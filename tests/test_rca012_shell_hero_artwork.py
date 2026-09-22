"""`RCA-012`: the shell serves its own hero artwork, as audited compressed derivatives.

**What this module proves and what it cannot.** Everything here runs in-process through
`TestClient`. It proves the allowlist, the bytes, the media types, the refusals and the manifest.
It cannot prove a browser fetches the file from a real origin -- that is
`test_rca012_shell_hero_load.py`, for the reason `test_rca011_shell_font_load.py` records: an
allowlist entry naming a file the shipped image does not carry passes every in-process test and
404s in production.

**Why the digest evidence is two-sided.** A test that calls `_require_audited` with bad bytes
proves a guard exists; it survives deleting the call site, which is the recorded "test the caller,
not the guard" defect. So the drift case reloads the module with a corrupted manifest and asserts
the *import* raises, and a second assertion pins the allowlist's hero entries to exactly the files
`hero.py` audits -- so an entry naming an unaudited file cannot be added without failing here.
"""

from __future__ import annotations

import hashlib
import importlib
import re
import shutil
import tomllib
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from pathlib import Path

import pytest

from khepri.rra.journey import hero
from khepri.rra.journey.hero import (
    HERO_DIGESTS,
    HERO_DIRECTORY,
    HERO_FILES,
    HERO_JPEG_FILE,
    HERO_JPEG_MEDIA_TYPE,
    HERO_MEDIA_TYPES,
    HERO_PACKAGE,
    HERO_WEBP_FILE,
    HERO_WEBP_MEDIA_TYPE,
    SOURCE_DIGEST,
    SOURCE_FILE,
    load_hero_artwork,
)
from khepri.rra.journey.security import SECURITY_HEADERS
from khepri.runtime.shell_api import _ASSETS, SHELL_ASSETS
from tests.test_r802_shell_unavailable_surface import _client, _StubResolver

#: Anchored to this file, never the working directory: a `Path("src")` resolved from the CWD scans
#: nothing when pytest runs from `tests/`, and a scan over nothing passes vacuously.
_ROOT = Path(__file__).resolve().parents[1]
_JOURNEY_ASSETS = _ROOT / "src" / "khepri" / "rra" / "journey" / "assets"
_RUNTIME_ASSETS = _ROOT / "src" / "khepri" / "runtime" / "shell_assets"

#: The stylesheets a shell surface links, as `test_rca011_shell_typeface.py` names them. Scanned
#: here to prove this slice introduced no external host and no journey address of its own.
_SHELL_STYLESHEETS = (
    _JOURNEY_ASSETS / "shell.css",
    _JOURNEY_ASSETS / "shell-components.css",
    _RUNTIME_ASSETS / "workspace.css",
)

#: The supplied source, which `FR-215` keeps out of every customer surface.
_SOURCE_PNG = _ROOT / SOURCE_FILE

_EXPECTED_MEDIA_TYPES = {
    HERO_JPEG_FILE: HERO_JPEG_MEDIA_TYPE,
    HERO_WEBP_FILE: HERO_WEBP_MEDIA_TYPE,
}


def _external_hosts(text: str) -> list[str]:
    """Every absolute or protocol-relative host the text names.

    One predicate, used by both the assertion and its positive control, so the control proves the
    scan fires rather than proving a `in` check unrelated to it.
    """
    return re.findall(r"(?:https?:)?//[A-Za-z0-9.-]+", text)


@contextmanager
def _preserved(target: Path, tmp_path: Path) -> Iterator[Path]:
    """Lend a shipped derivative to a test that must damage it, and put it back.

    **Restored from a copy on disk, not from bytes in memory.** A test that holds the original in
    a local and rewrites it in `finally` loses the file outright if the process is killed between
    the damage and the restore -- and these derivatives are binaries, so a truncated tree is not
    obvious on sight. The backup is written first and the module is reloaded afterwards either
    way, so the rest of the session sees the audited bytes and an audited module.
    """
    backup = tmp_path / f"{target.name}.orig"
    shutil.copy2(target, backup)
    try:
        yield target
    finally:
        shutil.copy2(backup, target)
        importlib.reload(hero)

    assert hashlib.sha256(target.read_bytes()).hexdigest() == HERO_DIGESTS[target.name]


class TestFR212TheShellServesItsOwnHeroArtwork:
    """The derivatives ship as package data and are served by exact name."""

    @pytest.mark.parametrize("file_name", HERO_FILES)
    def test_the_derivative_is_served_from_the_shells_own_address(
        self, file_name: str
    ) -> None:
        response = _client().get(f"{SHELL_ASSETS}/{file_name}")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith(
            _EXPECTED_MEDIA_TYPES[file_name]
        )

    @pytest.mark.parametrize("file_name", HERO_FILES)
    def test_the_bytes_served_are_the_audited_bytes(self, file_name: str) -> None:
        """Not merely a 200: the route must hand back the artwork the manifest digests.

        A route serving the right name from the wrong directory would pass a status check.
        """
        response = _client().get(f"{SHELL_ASSETS}/{file_name}")

        assert hashlib.sha256(response.content).hexdigest() == HERO_DIGESTS[file_name]

    def test_an_unlisted_asset_in_the_package_is_not_served(self) -> None:
        """Served by being named, not by arriving: the allowlist is a `dict`, not a listing.

        `journey.css` and the journey's scripts sit in the very directory the derivatives ship
        from and are deliberately not served from the shell's address.
        """
        for name in ("journey.css", "upload.js", "khepri-hero.avif"):
            assert _client().get(f"{SHELL_ASSETS}/{name}").status_code == 404

    def test_the_allowlist_gained_exactly_the_two_derivatives(self) -> None:
        """An extent assertion over the hero half, stated as equality.

        A `>=` check cannot see a third derivative added by a later slice, which is the recorded
        drift this repository has paid for more than once.

        **Selected by media type, not by package.** The two shell stylesheets ship from the very
        same `journey/assets` directory, so a rule matching on package and directory would call
        them hero entries -- the recorded defect of deriving a guard's scope from a field two
        surfaces legitimately share. An image media type is what actually distinguishes them.
        """
        hero_entries = {
            name
            for name, (_, _, media_type) in _ASSETS.items()
            if media_type.startswith("image/")
        }

        assert hero_entries == {HERO_JPEG_FILE, HERO_WEBP_FILE}

    @pytest.mark.parametrize("file_name", HERO_FILES)
    def test_the_entry_reads_from_the_audited_package(self, file_name: str) -> None:
        """One copy, not two: `hero.py` verifies these exact bytes, and a second copy elsewhere
        would be artwork nothing checks."""
        assert _ASSETS[file_name] == (
            HERO_PACKAGE,
            HERO_DIRECTORY,
            _EXPECTED_MEDIA_TYPES[file_name],
        )

    def test_every_served_hero_entry_is_one_the_manifest_audits(self) -> None:
        """**The assertion that ties the route to the verification.**

        `hero.py` checks its manifest at import, so a drifted file cannot be served -- but only
        for files the manifest actually covers. An `_ASSETS` entry naming an unaudited image in
        the same package would be served by a bare `read_bytes()` with nothing having checked it.
        This pins the two sets equal, so that entry cannot be added silently.
        """
        served = {
            name
            for name, (_, _, media_type) in _ASSETS.items()
            if media_type.startswith("image/")
        }

        assert served == set(HERO_DIGESTS)

    def test_the_selection_rule_would_notice_an_unaudited_image(self) -> None:
        """A guard that cannot fail is not a guard.

        The positive control is constructed rather than shipped: an image entry whose name the
        manifest does not cover must be visible to the rule above, or the equality it asserts is
        satisfied by a rule that sees nothing.
        """
        widened = dict(_ASSETS)
        widened["khepri-hero.avif"] = (HERO_PACKAGE, HERO_DIRECTORY, "image/avif")

        served = {
            name
            for name, (_, _, media_type) in widened.items()
            if media_type.startswith("image/")
        }

        assert served - set(HERO_DIGESTS) == {"khepri-hero.avif"}


class TestFR213EveryDerivativeCarriesAnAuditedDigest:
    """Drift is refused at load, not detected by a test that happens to run."""

    @pytest.mark.parametrize("file_name", HERO_FILES)
    def test_the_shipped_bytes_match_the_manifest(self, file_name: str) -> None:
        payload = (
            resources.files(HERO_PACKAGE).joinpath(HERO_DIRECTORY, file_name).read_bytes()
        )

        assert hashlib.sha256(payload).hexdigest() == HERO_DIGESTS[file_name]

    def test_a_drifted_derivative_is_refused_at_import(
        self, tmp_path: Path
    ) -> None:
        """The module, not a helper: `_AUDITED` runs at module scope, so bytes that no longer
        match the manifest make the import itself fail.

        This is what makes `FR-213` structural. A test asserting `_require_audited` raises would
        survive deleting its only call site; reloading the module cannot, because the call site
        *is* the module body.

        **The drift is introduced in the bytes, not in the manifest.** Patching `HERO_DIGESTS`
        and reloading proves nothing: `importlib.reload` re-executes the module source, which
        reassigns the manifest from its literal and discards the patch before `_AUDITED` runs --
        a mutant that introduces no defect and reports as a passed proof. So the shipped file is
        genuinely perturbed on disk for the duration.
        """
        with _preserved(_JOURNEY_ASSETS / HERO_JPEG_FILE, tmp_path) as target:
            target.write_bytes(target.read_bytes() + b"drift")

            with pytest.raises(ValueError, match="does not match its audited digest"):
                importlib.reload(hero)

    def test_a_missing_derivative_is_refused_rather_than_skipped(
        self, tmp_path: Path
    ) -> None:
        """An absent file must raise, not be quietly dropped from the audited set: a manifest
        entry whose file vanished is drift too."""
        with _preserved(_JOURNEY_ASSETS / HERO_WEBP_FILE, tmp_path) as target:
            target.unlink()

            with pytest.raises(FileNotFoundError):
                importlib.reload(hero)

    def test_an_unaudited_name_is_refused_rather_than_read(self) -> None:
        """A file the manifest does not cover is not loadable through this module at all."""
        with pytest.raises(ValueError, match="is not an audited derivative"):
            hero._require_audited("khepri-hero.avif", b"bytes")

    def test_the_loader_returns_every_audited_file(self) -> None:
        """An extent assertion on the loader: a derivative dropped from the manifest must fail
        here rather than quietly stop being checked."""
        assert set(load_hero_artwork()) == {HERO_JPEG_FILE, HERO_WEBP_FILE}

    def test_the_media_type_map_covers_exactly_the_audited_files(self) -> None:
        assert set(HERO_MEDIA_TYPES) == set(HERO_DIGESTS)


class TestFR214TheDerivativesComeFromTheSuppliedSource:
    """The generating step is recorded, and something checks that it was the approved source."""

    def test_the_recorded_source_digest_is_the_supplied_artwork(self) -> None:
        """`RCA-012` records the source SHA-256 in prose; this asserts the file in the tree is
        that file, so "the approved artwork" and "the bytes generated from" are the same thing."""
        assert _SOURCE_PNG.is_file(), f"{_SOURCE_PNG} is not where the record points"
        assert (
            hashlib.sha256(_SOURCE_PNG.read_bytes()).hexdigest() == SOURCE_DIGEST
        )

    def test_the_specification_records_the_same_source_digest(self) -> None:
        """Derived from the governing document rather than restated, so a corrected spec and a
        stale constant cannot drift apart silently."""
        spec = (
            _ROOT / "governance" / "specifications" / "RCA-012.md"
        ).read_text(encoding="utf-8")

        assert SOURCE_DIGEST in spec

    @pytest.mark.parametrize("file_name", HERO_FILES)
    def test_the_derivative_carries_the_full_frame_at_native_size(
        self, file_name: str
    ) -> None:
        """No crop and no resize: the handoff admits only `object-fit`/`object-position`
        cropping, which is presentation. A derivative at another size would mean the file was
        recomposed rather than compressed."""
        pillow = pytest.importorskip("PIL.Image")
        source_size = pillow.open(_SOURCE_PNG).size

        with pillow.open(_JOURNEY_ASSETS / file_name) as derivative:
            assert derivative.size == source_size == (1400, 900)

    def test_no_upscaled_retina_derivative_ships(self) -> None:
        """The handoff asks for a 2x; a 1400px master cannot produce one without inventing
        pixels, which `FR-214` and the handoff's own "never redrawn" both forbid. Recorded as an
        assertion so a later slice adding an upscale fails rather than passes quietly."""
        for name in ("khepri-hero@2x.jpg", "khepri-hero@2x.webp"):
            assert not (_JOURNEY_ASSETS / name).exists(), (
                f"{name} ships, but no 2x master was supplied"
            )
            assert name not in _ASSETS


class TestFR215TheSuppliedPngIsNotServed:
    """The 2.4 MB source stays design material."""

    def test_the_source_png_is_not_in_the_allowlist(self) -> None:
        assert "khepri-hero.png" not in _ASSETS

    def test_the_source_png_is_not_served_from_the_shells_address(self) -> None:
        assert _client().get(f"{SHELL_ASSETS}/khepri-hero.png").status_code == 404

    def test_the_source_png_did_not_move_into_the_package(self) -> None:
        """`FR-215` is about reachability, not only about the route: a copy under `src/` would be
        one directory-listing change away from being served."""
        assert not (_JOURNEY_ASSETS / "khepri-hero.png").exists()
        assert not list((_ROOT / "src").rglob("khepri-hero.png"))

    def test_the_shipped_derivatives_are_smaller_than_the_source(self) -> None:
        """What §09 asked for: a compressed derivative reaches the surface, not the master."""
        source_bytes = _SOURCE_PNG.stat().st_size

        for file_name in HERO_FILES:
            shipped = (_JOURNEY_ASSETS / file_name).stat().st_size
            assert shipped < source_bytes / 4, (
                f"{file_name} is {shipped} bytes against a {source_bytes}-byte master"
            )


class TestFR216NoExternalReference:
    """No CDN, no image host, no runtime download, and an unweakened policy."""

    def test_the_shipped_policy_still_allows_only_same_origin_images(self) -> None:
        """The directive parsed and compared whole, not matched as a substring.

        `"img-src 'self'" in policy` is satisfied by `img-src 'self' https://cdn.example`, which
        is the exact widening `FR-216` forbids -- a guard that passes in the one case it exists
        to catch. Equality on the parsed source list makes it an extent assertion: an added host
        fails here rather than reading as unchanged.
        """
        directives = {
            parts[0]: parts[1:]
            for directive in SECURITY_HEADERS["Content-Security-Policy"].split(";")
            if (parts := directive.split())
        }

        assert directives["img-src"] == ["'self'"]
        assert directives["default-src"] == ["'none'"]

    def test_the_policy_check_would_fire_on_an_added_image_host(self) -> None:
        """The positive control for the assertion above, run through the same parse."""
        widened = "default-src 'none'; img-src 'self' https://cdn.example"

        directives = {
            parts[0]: parts[1:]
            for directive in widened.split(";")
            if (parts := directive.split())
        }

        assert directives["img-src"] != ["'self'"]

    def test_no_shell_stylesheet_names_an_external_host(self) -> None:
        for path in _SHELL_STYLESHEETS:
            assert path.is_file(), f"{path} is not where the scan looks"
            assert not _external_hosts(path.read_text(encoding="utf-8"))

    def test_the_scan_would_fire_on_an_external_host(self) -> None:
        """A guard that cannot fail is not a guard.

        The control is run through `_external_hosts` -- the *same* predicate the assertion above
        uses -- rather than through a separate `in` check. Asserting only that some other file
        contains `https://` would pass even if the scan loop's body were `pass`; this cannot,
        because it is the scan itself reporting a hit.
        """
        control = (
            _ROOT
            / "docs"
            / "ui"
            / "design_handoff_khepri_product_ui"
            / "design-files"
            / "Khepri Handoff.dc.html"
        )

        assert control.is_file()
        assert _external_hosts(control.read_text(encoding="utf-8", errors="ignore"))
        assert control not in _SHELL_STYLESHEETS


class TestFR217NoShellStylesheetNamesAJourneyAddress:
    """The asset moved into the shell's ownership; the permission did not widen."""

    def test_no_shell_stylesheet_names_a_beta_address(self) -> None:
        offenders = {
            path.name: [
                line
                for line in re.sub(
                    r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S
                ).splitlines()
                if "/beta/" in line
            ]
            for path in _SHELL_STYLESHEETS
        }

        assert not any(offenders.values()), f"a shell stylesheet names /beta/: {offenders}"

    def test_no_beta_asset_address_was_introduced_for_the_artwork(self) -> None:
        """`FR-217`: the derivatives resolve at the shell's own prefix, never the journey's."""
        assert SHELL_ASSETS == "/app/assets"

        for file_name in HERO_FILES:
            assert _client().get(f"/beta/assets/{file_name}").status_code in (404, 405)


class TestFR218TheArtworkCarriesNoGovernedMeaning:
    """The asset half. The bilingual alternative text is `RCA-010`'s; see the module note below.

    `RCA-012` §Exclusions places the handoff §6 placement rules under a presentation slice
    governed by `RCA-010`, whose §Scope admits `shell_copy.py` and the shell templates. This slice
    adds no template and no copy entry, so what is provable here is that the artwork states
    nothing governed and that no surface depends on it.
    """

    def test_the_artwork_reaches_no_template(self) -> None:
        """Asset-only: no shell template references the derivatives yet, so no surface can have
        become dependent on one loading."""
        templates = _ROOT / "src" / "khepri" / "runtime" / "shell_templates"
        assert templates.is_dir()

        for path in templates.rglob("*.j2"):
            body = path.read_text(encoding="utf-8")
            for file_name in HERO_FILES:
                assert file_name not in body, (
                    f"{path.name} places the artwork; that is RCA-010's slice"
                )

    def test_the_module_names_no_figure_population_or_state(self) -> None:
        """`FR-218`: decorative. The manifest carries file names, media types and digests -- no
        metric, no refusal, no caveat and no governed vocabulary."""
        assert set(HERO_DIGESTS) == {HERO_JPEG_FILE, HERO_WEBP_FILE}
        assert all(len(digest) == 64 for digest in HERO_DIGESTS.values())


class TestTheShippedArtifactCarriesTheArtwork:
    """`W1-07a`'s defect: a route absent from the image passes every hand-wired fixture."""

    @pytest.mark.parametrize("file_name", HERO_FILES)
    def test_the_derivative_is_readable_as_package_data(self, file_name: str) -> None:
        payload = (
            resources.files(HERO_PACKAGE).joinpath(HERO_DIRECTORY, file_name).read_bytes()
        )

        assert payload, f"{file_name} is not readable through the package"

    @pytest.mark.parametrize("file_name", HERO_FILES)
    def test_the_wheel_includes_the_directory_the_artwork_lives_in(
        self, file_name: str
    ) -> None:
        """Read from `pyproject.toml`, not restated: a build that stopped packaging
        `src/khepri`, or started excluding the journey package, must fail here."""
        config = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        wheel = config["tool"]["hatch"]["build"]["targets"]["wheel"]

        artwork = (
            _ROOT / "src" / Path(*HERO_PACKAGE.split(".")) / HERO_DIRECTORY / file_name
        )
        assert artwork.is_file(), f"{artwork} is not in the tree the wheel packages"

        relative = artwork.relative_to(_ROOT).as_posix()
        assert any(relative.startswith(f"{pkg}/") for pkg in wheel["packages"]), (
            f"{relative} is under no packaged root: {wheel['packages']}"
        )
        for excluded in wheel["exclude"]:
            assert not relative.startswith(f"{excluded}/"), (
                f"{relative} is excluded from the wheel by {excluded}"
            )


class TestServingTheArtworkAddsNoCapability:
    """The asset route answers the same way for every caller (`RCA-012` §Exclusions)."""

    def test_the_artwork_is_served_without_a_session(self) -> None:
        response = _client().get(f"{SHELL_ASSETS}/{HERO_JPEG_FILE}")

        assert response.status_code == 200
        assert "set-cookie" not in {k.lower() for k in response.headers}

    def test_the_answer_does_not_vary_by_caller(self) -> None:
        plain = _client().get(f"{SHELL_ASSETS}/{HERO_WEBP_FILE}")
        forged = _client()
        forged.cookies.set("khepri_session", "forged")
        with_cookie = forged.get(f"{SHELL_ASSETS}/{HERO_WEBP_FILE}")

        assert plain.content == with_cookie.content
        assert plain.status_code == with_cookie.status_code

    def test_the_route_resolves_no_actor_for_the_artwork(self) -> None:
        resolver = _StubResolver()
        response = _client(resolver=resolver).get(f"{SHELL_ASSETS}/{HERO_JPEG_FILE}")

        assert response.status_code == 200
        assert resolver.calls == [], f"the asset route resolved an actor: {resolver.calls}"
