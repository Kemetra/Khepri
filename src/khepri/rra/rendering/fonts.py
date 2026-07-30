"""The typefaces the report carries with it, rather than hopes to find.

**Why bytes and not a font stack.** The screen surface names Arabic-capable
families and lets the reader's machine resolve them, which is right for a
browser: a reader's device has fonts. A PDF is produced in a container that has
almost none, and rendered later on a machine nobody controls. A font stack there
resolves to whatever is installed, and for Arabic the honest answer on a minimal
Linux image is *nothing* -- the page prints as boxes, or as Latin-shaped
approximations with no joining behaviour at all. So the faces are shipped as
package data, inlined into the document as `data:` URIs, and embedded by Chromium
into the PDF as subsetted font programs. The report becomes readable without
reference to its host.

**Why a digest per file.** A font is a binary blob in a governance-first
repository, and "the reviewed font" and "the font in the tree" are only the same
thing if something checks. This codebase already addresses customer uploads by
`source_sha256_hex` and profiles by `profile_digest`; a shipped binary is held to
the same standard. A face whose bytes drift from the manifest is refused at load
rather than quietly embedded.

**Provenance.** Both files are subsets of Noto Sans Arabic, licensed under the
SIL Open Font License 1.1, whose text ships beside them in `OFL.txt` as the
licence requires. They were retrieved from the Google Fonts static host, and the
`unicode-range` declared for each is the range Google Fonts declares for that
exact subset -- not a wider guess, which would ask the browser for glyphs the
file does not contain:

- `NotoSansArabic-Regular-arabic.woff2`
  `https://fonts.gstatic.com/s/notosansarabic/v33/nwpxtLGrOAZMl5nJ_wfgRg3DrWFZWsnVBJ_sS6tlqHHFlhQ5l3sQWIHPqzCfyGyfuXqAJQI.woff2`
- `NotoSansArabic-Regular-latin.woff2`
  `https://fonts.gstatic.com/s/notosansarabic/v33/nwpxtLGrOAZMl5nJ_wfgRg3DrWFZWsnVBJ_sS6tlqHHFlhQ5l3sQWIHPqzCfyGyfvHqA.woff2`

**Why one family name for both files.** `Noto Sans Arabic` is already first in
the bundled stylesheet's stack. Declaring both subsets under that one family
makes that existing first entry resolvable instead of adding a family the
stylesheet would then have to be taught about, and keeps the Latin and Arabic
text of one report metrically consistent.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from importlib import resources

FONT_PACKAGE = "khepri.rra.rendering"
FONT_DIRECTORY = "typefaces"
FONT_MEDIA_TYPE = "font/woff2"
FONT_FORMAT = "woff2"

# One family for both subsets: the name the bundled stylesheet already asks for.
FONT_FAMILY = "Noto Sans Arabic"

ARABIC_FILE = "NotoSansArabic-Regular-arabic.woff2"
LATIN_FILE = "NotoSansArabic-Regular-latin.woff2"

# The ranges Google Fonts declares for these exact subsets. The Arabic entry
# includes the presentation forms (`U+FB50-FDFF`, `U+FE70-FE74`, `U+FE76-FEFC`)
# because Arabic shaping resolves to them, and a range that stopped at the base
# block would leave shaped text reaching for a face that never matches.
ARABIC_UNICODE_RANGE = (
    "U+0600-06FF, U+0750-077F, U+0870-088E, U+0890-0891, U+0897-08E1, "
    "U+08E3-08FF, U+200C-200E, U+2010-2011, U+204F, U+2E41, U+FB50-FDFF, "
    "U+FE70-FE74, U+FE76-FEFC"
)
LATIN_UNICODE_RANGE = (
    "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, "
    "U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, "
    "U+2212, U+2215, U+FEFF, U+FFFD"
)

# The audited bytes. Recomputed on every load; see the module docstring.
FONT_DIGESTS: dict[str, str] = {
    ARABIC_FILE: "4e2ca0745c908761dc5c5db951662873887c59366fa1a5693ad22c0864abf1bd",
    LATIN_FILE: "290bdad021425e6ba6263c27d38652403f9b1a9ee74f5bbd2c62905b13f71b8c",
}

_MANIFEST: tuple[tuple[str, str], ...] = (
    (ARABIC_FILE, ARABIC_UNICODE_RANGE),
    (LATIN_FILE, LATIN_UNICODE_RANGE),
)


@dataclass(frozen=True, slots=True)
class EmbeddedFont:
    """One face, as bytes, ready to be written into a document.

    The payload is carried rather than a path, because the point of this type is
    that the document is self-contained: a renderer holding a filename would
    produce a page that resolves it at print time, on a machine that may not
    have it.
    """

    family: str
    file_name: str
    media_type: str
    font_format: str
    unicode_range: str
    payload: bytes

    def __post_init__(self) -> None:
        _require_text(self.family, "family")
        _require_text(self.file_name, "file_name")
        _require_text(self.media_type, "media_type")
        _require_text(self.font_format, "font_format")
        _require_text(self.unicode_range, "unicode_range")
        if not self.payload:
            raise ValueError("payload is required.")

    @property
    def data_uri(self) -> str:
        """The face as a `data:` URI.

        Base64 uses only characters HTML escaping leaves alone, so this reaches
        the document unchanged through an autoescaping template and needs no
        exemption. That is the whole reason the payload is inlined this way
        rather than passed as pre-built CSS.
        """
        encoded = base64.b64encode(self.payload).decode("ascii")
        return f"data:{self.media_type};base64,{encoded}"

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()


def load_report_fonts() -> tuple[EmbeddedFont, ...]:
    """Every face this package ships, checked against the audited digests."""
    return tuple(
        EmbeddedFont(
            family=FONT_FAMILY,
            file_name=file_name,
            media_type=FONT_MEDIA_TYPE,
            font_format=FONT_FORMAT,
            unicode_range=unicode_range,
            payload=_require_audited(file_name, _read(file_name)),
        )
        for file_name, unicode_range in _MANIFEST
    )


def _read(file_name: str) -> bytes:
    return (
        resources.files(FONT_PACKAGE).joinpath(FONT_DIRECTORY, file_name).read_bytes()
    )


def _require_audited(file_name: str, payload: bytes) -> bytes:
    expected = FONT_DIGESTS.get(file_name)
    if expected is None:
        raise ValueError(f"{file_name} is not an audited face.")
    if hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError(f"{file_name} does not match its audited digest.")
    return payload


def _require_text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} is required.")
