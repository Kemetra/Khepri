"""Verify the business/audit separation in the golden sample.

Committed so every claim in `../README.md` under "Mechanically verified" is
reproducible rather than asserted. Run from the repository root:

    .venv/Scripts/python.exe docs/reporting/golden-sample/verify_separation.py

Exit code 0 if every check passes, 1 otherwise. Requires no product imports --
it reads the published sample files directly, so it verifies the artifact the
owner is being asked to approve, not the code that might produce it.

THE RULE BEING CHECKED. A business surface may not show a governed identifier.
"Show" means visible text: an `id=` anchor is navigation the reader uses and is
permitted (see the visibility matrix §A.2), so the HTML check strips tags before
matching. Matching is on identifier *tokens*, never words -- an earlier version
matched the substring "revenue" and flagged the business phrase "Total revenue
change", because a business name and its identifier usually share a root.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
XLSX = HERE / "khepri-sales-review-sample.xlsx"
HTML = HERE / "khepri-sales-review-sample.html"
PDF = HERE / "khepri-sales-review-sample.pdf"

EXCEL_SHEET_NAME_LIMIT = 31

# Audit-tier worksheets: identifiers are expected here.
AUDIT_SHEETS = {"Audit Trail", "Provenance"}
# Chart machinery: audit-tier by classification, delivered by necessity, VISIBLE
# by APP-013 reasoning (excel.py:71-75).
MECHANISM_SHEETS = {"Chart Data (English)"}

IDENTIFIER_PATTERNS = {
    "snake_case identifier": r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+){1,}\b",
    "digest": r"sha256:",
    "figure/citation id": r"\b(?:fig|cit)-[0-9a-z]+\b",
    "module path": r"\b\w+/\w+\.py\b",
}

EASTERN_ARABIC_NUMERALS = r"[٠-٩]"

PDF_GUARDS = {
    "%PDF- header": b"%PDF-",
    "%%EOF trailer": b"%%EOF",
    "/StructTreeRoot": b"/StructTreeRoot",
    "/MarkInfo": b"/MarkInfo",
    "/Marked true": b"/Marked true",
    "/FontFile": b"/FontFile",
}


def _identifiers(text: str) -> list[str]:
    found: set[str] = set()
    for pattern in IDENTIFIER_PATTERNS.values():
        found.update(re.findall(pattern, text))
    return sorted(found)


def _visible_text(markup: str) -> str:
    """Rendered text only: styles dropped, SVG reduced to its labels, tags removed.

    Tags are stripped rather than searched because the rule is about what a reader
    sees. An `id=` anchor stays in the markup and must not be flagged.
    """
    markup = re.sub(r"<style.*?</style>", " ", markup, flags=re.S)
    markup = re.sub(
        r"<svg.*?</svg>",
        lambda m: " ".join(re.findall(r">([^<>]+)<", m.group(0))),
        markup,
        flags=re.S,
    )
    return re.sub(r"<[^>]+>", " ", markup)


def _sheet_text(archive: zipfile.ZipFile, index: int, shared: list[str]) -> str:
    """The shared strings one worksheet references, as one searchable blob."""
    sheet = archive.read(f"xl/worksheets/sheet{index}.xml").decode("utf-8")
    indexes = [int(m) for m in re.findall(r'<c[^>]*t="s"[^>]*><v>(\d+)</v>', sheet)]
    return " | ".join(shared[i] for i in indexes if i < len(shared))


def _tier_of(name: str) -> str:
    if name in AUDIT_SHEETS:
        return "AUDIT"
    if name in MECHANISM_SHEETS:
        return "MECHANISM"
    return "BUSINESS"


def _name_failures(name: str, tag: str) -> list[str]:
    """What is wrong with a worksheet's name or visibility, independent of content."""
    failures = []
    if len(name) > EXCEL_SHEET_NAME_LIMIT:
        failures.append(f"sheet name over {EXCEL_SHEET_NAME_LIMIT} chars: {name!r}")
    # No hidden worksheets anywhere: APP-013 permits the chart-data cells only
    # conditionally, and concealing conditional evidence is worse than not having
    # the permission (excel.py:71-75).
    if 'state="hidden"' in tag or 'state="veryHidden"' in tag:
        failures.append(f"hidden worksheet: {name!r}")
    return failures


def _sheet_verdict(tier: str, name: str, found: list[str]) -> tuple[str, list[str]]:
    """How one worksheet reads, and whether it broke the rule."""
    if tier == "AUDIT":
        return f"{len(found)} identifiers (expected)", []
    if tier == "MECHANISM":
        return f"{len(found)} identifiers, visible (required)", []
    if found:
        return f"LEAK {found[:5]}", [f"{name}: leaked {found[:5]}"]
    return "clean", []


def _check_sheet(archive: zipfile.ZipFile, index: int, tag: str, shared: list[str]) -> list[str]:
    """One worksheet: print how it reads, return what is wrong with it."""
    name = re.search(r'name="([^"]+)"', tag).group(1)
    tier = _tier_of(name)
    found = _identifiers(_sheet_text(archive, index, shared))
    verdict, leaks = _sheet_verdict(tier, name, found)
    print(f"  {index:>2} [{tier:9}] {name:34} {verdict}")
    return _name_failures(name, tag) + leaks


def _workbook_parts(archive: zipfile.ZipFile) -> tuple[list[str], list[str]]:
    """The shared-string table and the sheet declarations, in workbook order."""
    shared = re.findall(
        r"<t[^>]*>(.*?)</t>",
        archive.read("xl/sharedStrings.xml").decode("utf-8"),
        re.S,
    )
    tags = re.findall(r"<sheet [^>]*/>", archive.read("xl/workbook.xml").decode("utf-8"))
    return shared, tags


def check_workbook() -> list[str]:
    with zipfile.ZipFile(XLSX) as archive:
        shared, tags = _workbook_parts(archive)
        print(f"\nWorkbook: {len(tags)} sheets")
        checked = [
            _check_sheet(archive, index, tag, shared) for index, tag in enumerate(tags, start=1)
        ]
    return [failure for sheet in checked for failure in sheet]


def _check_region(region: str, markup: str) -> list[str]:
    """One HTML region: print its identifier count, return a failure if it leaked.

    Only the business region can fail. The evidence region is *expected* to be full
    of identifiers -- that is what it is for.
    """
    found = _identifiers(_visible_text(markup))
    leaked = found if region == "business" else []
    print(
        f"  {region:10} {len(found):>3} identifiers{' LEAK ' + str(leaked[:5]) if leaked else ''}"
    )
    return [f"HTML {region} region leaked {leaked[:5]}"] if leaked else []


def _check_numerals(source: str) -> list[str]:
    """Arabic report text uses Western numerals (0-9); see the IA, section B.4a."""
    eastern = re.findall(EASTERN_ARABIC_NUMERALS, source)
    print(f"  {'numerals':10} {len(eastern):>3} Eastern-Arabic (must be 0)")
    return [f"{len(eastern)} Eastern-Arabic numerals (use Western 0-9)"] if eastern else []


def check_html() -> list[str]:
    source = HTML.read_text(encoding="utf-8")
    split = source.index('<h1 id="evidence"')
    print("\nHTML")
    business = _check_region("business", source[:split])
    evidence = _check_region("evidence", source[split:])
    return business + evidence + _check_numerals(source)


def _check_guard(label: str, marker: bytes, blob: bytes) -> list[str]:
    """One marker `pdf.py` refuses to publish a PDF without.

    Six markers covering four properties: a PDF container (header and trailer), a
    structure tree, mark info, and an embedded font program.
    """
    present = marker in blob
    print(f"  {label:18} {'pass' if present else 'FAIL'}")
    return [] if present else [f"PDF missing {label}"]


def check_pdf() -> list[str]:
    blob = PDF.read_bytes()
    print("\nPDF publication guards")
    checked = [_check_guard(label, marker, blob) for label, marker in PDF_GUARDS.items()]
    pages = re.search(rb"/Type\s*/Pages.*?/Count\s+(\d+)", blob, re.S)
    print(f"  {'pages':18} {pages.group(1).decode() if pages else '?'}   {len(blob) // 1024} KB")
    return [failure for guard in checked for failure in guard]


def _missing_samples() -> list[Path]:
    """Which sample files are absent, so the run can say so before checking anything."""
    return [path for path in (XLSX, HTML, PDF) if not path.exists()]


def _report(failures: list[str]) -> int:
    """Print the outcome and return the exit code it implies."""
    print()
    if not failures:
        print("[OK] business surfaces carry no governed identifier; audit surfaces carry them all")
        return 0
    print(f"[FAIL] {len(failures)} problem(s):", file=sys.stderr)
    for failure in failures:
        print(f"  - {failure}", file=sys.stderr)
    return 1


def main() -> int:
    missing = _missing_samples()
    if missing:
        for path in missing:
            print(f"[FAIL] missing sample: {path}", file=sys.stderr)
        return 1
    return _report(check_workbook() + check_html() + check_pdf())


if __name__ == "__main__":
    sys.exit(main())
