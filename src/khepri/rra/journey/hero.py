"""The hero artwork the shell carries with it, rather than fetches (`RCA-012`).

**Why derivatives and not the supplied file.** The owner's approved Product UI handoff supplies
one 2.4 MB PNG at `docs/ui/design_handoff_khepri_product_ui/assets/khepri-hero.png`. Its §09
requires that a compressed derivative reach the customer surface rather than that file, and
`FR-215` makes that a prohibition: the PNG stays design material under `docs/` and is not served.
So the bytes below are generated from it, once, and shipped as package data.

**Why a digest per file, verified here rather than in a test.** `FR-213` holds a shipped binary to
the discipline `rendering/fonts.py` already applies to the typefaces: "the approved artwork" and
"the bytes in the tree" are only the same thing if something checks. A test that checks is not
enough -- it proves the bytes were right when the suite ran, not that a drifted file is refused by
the thing that serves it. `_AUDITED` is therefore evaluated at **module scope**, so a derivative
whose bytes drift raises on import and the application does not start. There is no path that
serves an unverified hero byte, because there is no path that reaches this module without the
check having already run.

That is deliberately stronger than the typefaces, whose shell entries are read from disk by the
asset route without a digest check (`fonts.py` verifies them on the PDF path, which the shell does
not take). `FR-213` asks for the fonts' *discipline*, and the discipline is the manifest; applying
it at import is how a route that does a bare read still cannot serve drift.

**Provenance.** One source, recorded as `SOURCE_DIGEST` and asserted nowhere else, because
`FR-214` requires the generating step to be recoverable rather than asserted. Both derivatives are
the full frame at its native 1400x900 -- no crop, no resize, no filter, no recolour. The handoff
forbids redrawing the artwork and admits only `object-fit: cover` and `object-position` cropping,
which is presentation and belongs to the surface, not to the file.

Generated with Pillow 12.3.0 from the RGBA source, whose alpha channel is fully opaque
(`getextrema() == (255, 255)`), so the `RGBA -> RGB` conversion discards nothing:

- `khepri-hero.jpg`  -- JPEG, quality 80, `optimize=True`, progressive, 4:2:0 subsampling
- `khepri-hero.webp` -- WebP, quality 80, `method=6`

Both are written with no EXIF and no ICC profile, which is what makes regeneration reproducible:
the same source through the same parameters produces byte-identical files, and the digests below
are therefore a check a future regeneration can actually pass.

**No 2x derivative ships.** The handoff §09 asks for "a 2x for retina" beside the 1x, but the
supplied master *is* 1400px wide: a 2x could only be upscaled, which invents pixels the approved
artwork never carried and contradicts the same page's "photographic source, never redrawn" and
`FR-214`'s "from that exact supplied source and from nothing else". A true 2x needs a re-supplied
master and is a decision for the presentation slice, not a file this one can synthesize.

**This module serves nothing.** It names files and attests their bytes. The address, the allowlist
entry and the route are `shell_api.py`'s, and `RCA-012` authorizes exactly the allowlist half
there.
"""

from __future__ import annotations

import hashlib
from importlib import resources

#: The package and directory the derivatives ship in, as `shell_api.py`'s allowlist names them.
HERO_PACKAGE = "khepri.rra.journey"
HERO_DIRECTORY = "assets"

HERO_JPEG_FILE = "khepri-hero.jpg"
HERO_WEBP_FILE = "khepri-hero.webp"

HERO_JPEG_MEDIA_TYPE = "image/jpeg"
HERO_WEBP_MEDIA_TYPE = "image/webp"

#: The supplied source, recorded as provenance (`FR-213`). This file is **not** served: it stays
#: under `docs/` as design material, which is `FR-215`.
SOURCE_FILE = "docs/ui/design_handoff_khepri_product_ui/assets/khepri-hero.png"
SOURCE_DIGEST = "12a68450bf6edf1b7aec67a0cdae1741afae5fa81f4fdf6ef7a6a28266a3afd6"

#: The audited bytes. Recomputed on every load; see the module docstring.
HERO_DIGESTS: dict[str, str] = {
    HERO_JPEG_FILE: "e813b5190df441ffde52f793f8740dab0ae7b1c82d0d22b8672ee1d7847ccf80",
    HERO_WEBP_FILE: "584a28f0000d0d2fa2bbcc9d7b2fccee898057587861dad0b938d2c60c21f15a",
}

#: Each derivative with the media type it must be served as. A `.webp` served as `text/css` is not
#: served, so the type belongs beside the name rather than being inferred at the route.
HERO_MEDIA_TYPES: dict[str, str] = {
    HERO_JPEG_FILE: HERO_JPEG_MEDIA_TYPE,
    HERO_WEBP_FILE: HERO_WEBP_MEDIA_TYPE,
}


def _read(file_name: str) -> bytes:
    return (
        resources.files(HERO_PACKAGE).joinpath(HERO_DIRECTORY, file_name).read_bytes()
    )


def _require_audited(file_name: str, payload: bytes) -> bytes:
    expected = HERO_DIGESTS.get(file_name)
    if expected is None:
        raise ValueError(f"{file_name} is not an audited derivative.")
    if hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError(f"{file_name} does not match its audited digest.")
    return payload


def load_hero_artwork() -> dict[str, bytes]:
    """Every derivative this package ships, checked against the audited digests."""
    return {
        file_name: _require_audited(file_name, _read(file_name))
        for file_name in HERO_DIGESTS
    }


#: The check, run at import. A drifted derivative raises here, so the application does not start
#: rather than starting and serving it. `shell_api.py` importing any name from this module has
#: already paid for this verification; see the module docstring.
_AUDITED = load_hero_artwork()

#: The audited names, for a consumer that must not name a file this module does not attest.
HERO_FILES: tuple[str, ...] = tuple(HERO_DIGESTS)

__all__ = [
    "HERO_DIGESTS",
    "HERO_DIRECTORY",
    "HERO_FILES",
    "HERO_JPEG_FILE",
    "HERO_JPEG_MEDIA_TYPE",
    "HERO_MEDIA_TYPES",
    "HERO_PACKAGE",
    "HERO_WEBP_FILE",
    "HERO_WEBP_MEDIA_TYPE",
    "SOURCE_DIGEST",
    "SOURCE_FILE",
    "load_hero_artwork",
]
