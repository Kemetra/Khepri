"""`RCA-010` `FR-204`-`FR-205`: visual-regression evidence for the commercial shell surfaces.

`tests/` only, and no stored image. Visual evidence here is **computed measurement** -- box
geometry, computed styles and element counts -- because a pixel digest cannot name which of
`FR-204`'s eight dimensions drifted, and a committed baseline image would be the hosted baseline
store `FR-204` excludes. Both were measured before choosing; see the execution plan's Decision 1.
"""

from __future__ import annotations

import re
from pathlib import Path

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
