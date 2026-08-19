"""`STATUS.md`'s derived figures must agree with its own rows.

**Why this exists.** `specs/001-rca-001-commercial-identity/STATUS.md` asserts one underlying
fact -- how many requirements are implemented, partial, and not implemented -- in five places:
the rollup table, its arithmetic sentence, the "N partial + M not implemented" line, the cause
table, and that table's sum. Any single-row change touches four of them, and **the total stays
constant either way**, so a partial edit produces a document that is internally inconsistent but
superficially plausible.

That is not hypothetical. PR `#214` ran four review rounds, and two of them were this exact class:
a delta column that kept its old baseline label while carrying new values, and a rollup whose split
no longer matched its rows. The count was hand-derived by script six times across that PR
and `#217`.

**Why a test rather than a `khepri_gov` rule.** `governance/README.md` states that "Markdown
explains intent but cannot override registry state", and all seventeen validator rules read only
`governance/registry.yaml` -- `_record_document` validates a governed document's *path* and
deliberately never opens it. A prose-validating rule inverts that design. `pytest` is the same
merge gate with none of the conflict, and `test_rca001_boundary.py` already establishes the
self-tested-scanner idiom this file follows.

**What this does not check.** Whether each row's status is *correct* -- that is a claim about code
and belongs to the slice that changes it. This checks only that the document agrees with itself.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
STATUS = _ROOT / "specs" / "001-rca-001-commercial-identity" / "STATUS.md"
MIGRATIONS = _ROOT / "migrations" / "versions"

#: `FR-001` … `FR-040`, the requirement set `RCA-001` declares.
_FIRST, _LAST = 1, 40

_STATUSES = ("Implemented", "Partial", "Not implemented")

#: A requirement row: `| FR-016 | Partial | …` or `| FR-017 … FR-019 | Not implemented | …`, with
#: the status optionally bolded. Identifiers are backticked in the change table near the top and
#: bare in the requirement tables below, so the pattern must tolerate both.
_ROW = re.compile(
    r"^\|\s*`?(FR-0\d\d)`?(?:\s*(?:…|\.\.\.)\s*`?(FR-0\d\d)`?)?"
    r"\s*\|\s*\*{0,2}([A-Za-z][^|*]*?)\*{0,2}\s*\|",
    re.MULTILINE,
)


def classify(text: str) -> str | None:
    """The declared status a cell names, or None when it names none.

    Case- and suffix-tolerant: the document writes `Partial`, `**Partial**`, and
    `Partial — domain only`, and all three mean the same bucket. `Implemented, vacuously` counts as
    Implemented, which is the reading the rollup's own note records for `FR-040`.
    """
    lowered = text.strip().lower()
    for status in _STATUSES:
        if lowered.startswith(status.lower()):
            return status
    return None


def derive_counts(document: str) -> dict[str, str]:
    """Every requirement's status, with `FR-017 … FR-019` ranges expanded.

    Later rows win, which is what makes this correct rather than convenient: the change table near
    the top lists a handful of requirements with their *previous* status, and the authoritative
    per-requirement tables come after it.
    """
    statuses: dict[str, str] = {}
    for first, last, cell in _ROW.findall(document):
        status = classify(cell)
        if status is None:
            continue
        low = int(first[3:])
        high = int(last[3:]) if last else low
        for number in range(low, high + 1):
            statuses[f"FR-{number:03d}"] = status
    return statuses


def _rollup_table(document: str) -> dict[str, int]:
    """The three counts the rollup table states."""
    found = {}
    for status in _STATUSES:
        match = re.search(rf"^\|\s*{re.escape(status)}\s*\|\s*(\d+)\s*\|", document, re.MULTILINE)
        assert match is not None, f"the rollup table has no {status!r} row"
        found[status] = int(match.group(1))
    return found


# --- the scanner is self-tested first, following test_rca001_boundary.py -----------------------


def test_the_scanner_reads_the_shapes_the_document_actually_uses() -> None:
    """**The load-bearing test in this file.** A parser that matched nothing would make every
    assertion below it pass while checking nothing, which is the failure mode
    `test_rca_import_checker_flags_and_clears_expected_cases` exists to prevent.

    Each case below is a shape `STATUS.md` really contains: backticked and bare identifiers, an
    em-dash range, a bolded status, a status with a trailing qualifier, and a separator row.
    """
    sample = "\n".join(
        (
            "| FR | Status | Gap |",
            "|---|---|---|",
            "| FR-001 | Implemented | — |",
            "| `FR-002` | **Partial** | something |",
            "| FR-003 … FR-005 | Not implemented | a range |",
            "| FR-006 | Partial — domain only | a qualifier |",
            "| FR-007 | Implemented, vacuously | the FR-040 shape |",
        )
    )

    derived = derive_counts(sample)

    assert derived == {
        "FR-001": "Implemented",
        "FR-002": "Partial",
        "FR-003": "Not implemented",
        "FR-004": "Not implemented",
        "FR-005": "Not implemented",
        "FR-006": "Partial",
        "FR-007": "Implemented",
    }


def test_the_scanner_ignores_rows_that_are_not_requirement_rows() -> None:
    """Known-good cases that must *not* match: the separator, a header, and the change table's
    `| FR | Was | Now |` shape whose second column is a status but whose meaning is historical."""
    assert derive_counts("|---|---|---|") == {}
    assert derive_counts("| FR | Status | Gap |") == {}
    assert derive_counts("| Program | Status | Reason |") == {}


def test_the_scanner_lets_a_later_row_win() -> None:
    """The change table near the top states a requirement's *previous* status. The authoritative
    tables come after, so the last mention is the one that counts -- without this, a promoted row
    would be counted at its old value and the rollup would look wrong when it was right."""
    sample = "| FR-003 | Partial | was |\n| FR-003 | Implemented | now |"

    assert derive_counts(sample) == {"FR-003": "Implemented"}


# --- the document agrees with itself ----------------------------------------------------------


def test_every_requirement_is_classified_exactly_once() -> None:
    """`FR-001` … `FR-040` with no gap. A missing requirement would make the rollup add up while
    describing 39 things, which is the shape a silently-dropped row takes."""
    derived = derive_counts(STATUS.read_text(encoding="utf-8"))

    missing = [f"FR-{n:03d}" for n in range(_FIRST, _LAST + 1) if f"FR-{n:03d}" not in derived]
    assert not missing, f"no status row for {missing}"
    assert len(derived) == _LAST - _FIRST + 1, f"classified {len(derived)}, expected 40"


def test_the_rollup_table_matches_the_requirement_rows() -> None:
    """The check that would have caught two of `#214`'s four review rounds.

    Re-derived from the rows rather than trusted, because the *total* is unchanged by moving one
    requirement between buckets -- so an edit that updates the table and not the rows, or the rows
    and not the table, leaves a document that sums correctly and says something false.
    """
    document = STATUS.read_text(encoding="utf-8")
    derived = Counter(derive_counts(document).values())
    stated = _rollup_table(document)

    assert {status: derived[status] for status in _STATUSES} == stated, (
        f"rows say {dict(derived)}, the rollup table says {stated}"
    )


def test_the_rollup_sums_to_the_declared_requirement_count() -> None:
    document = STATUS.read_text(encoding="utf-8")
    stated = _rollup_table(document)

    assert sum(stated.values()) == _LAST - _FIRST + 1, (
        f"{stated} sums to {sum(stated.values())}, not {_LAST - _FIRST + 1}"
    )


def test_the_not_fully_implemented_sentence_matches_the_rollup() -> None:
    """A fourth place the same fact is written -- "24 requirements are not fully implemented
    (15 partial + 9 not implemented)". `#214`'s round 4 found it disagreeing with the table."""
    document = STATUS.read_text(encoding="utf-8")
    stated = _rollup_table(document)

    match = re.search(
        r"(\d+) requirements are not fully implemented \((\d+) partial \+ (\d+) not implemented\)",
        document,
    )
    assert match is not None, "the not-fully-implemented sentence is missing or reworded"
    total, partial, absent = (int(group) for group in match.groups())

    assert (partial, absent) == (stated["Partial"], stated["Not implemented"]), (
        f"the sentence says {partial}/{absent}, the rollup says "
        f"{stated['Partial']}/{stated['Not implemented']}"
    )
    assert total == partial + absent, f"{total} != {partial} + {absent}"


def test_the_cause_table_accounts_for_every_incomplete_requirement() -> None:
    """The fifth place. Its rows name counts per cause and its closing line sums them, so a row
    edited without the sum -- or the reverse -- is the same defect one table over."""
    document = STATUS.read_text(encoding="utf-8")
    stated = _rollup_table(document)
    incomplete = stated["Partial"] + stated["Not implemented"]

    match = re.search(
        r"^((?:\d+ \+ )+\d+) = \*\*(\d+)\*\*, matching the rollup", document, re.MULTILINE
    )
    assert match is not None, "the cause table's arithmetic line is missing or reworded"
    addends = [int(part) for part in match.group(1).split(" + ")]
    claimed = int(match.group(2))

    assert sum(addends) == claimed, f"{match.group(1)} sums to {sum(addends)}, stated {claimed}"
    assert claimed == incomplete, (
        f"the cause table accounts for {claimed}, the rollup has {incomplete} incomplete"
    )


# --- the header's baseline is real ------------------------------------------------------------


def test_the_baseline_commit_exists_in_history() -> None:
    """`#214`'s round 4 found the header pinning `00e0f47` while the rows had moved past it.
    A commit that does not exist at all is the stronger version of the same defect."""
    document = STATUS.read_text(encoding="utf-8")

    match = re.search(r"\*\*Baseline:\*\* `main` @ `([0-9a-f]{7,40})`", document)
    assert match is not None, "the header states no baseline commit"

    result = subprocess.run(
        ["git", "cat-file", "-t", match.group(1)],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"commit {match.group(1)} unreachable in this checkout (shallow clone?)")
    assert result.stdout.strip() == "commit", f"{match.group(1)} is not a commit"


def test_the_stated_migration_head_is_the_real_head() -> None:
    """The header names a migration head. A stale one sends a reader to the wrong parent for the
    next revision, which is how a chain forks."""
    document = STATUS.read_text(encoding="utf-8")

    match = re.search(r"Migration head `(\d{8}_\d{4})`", document)
    assert match is not None, "the header states no migration head"

    revisions = {
        m.group(1)
        for path in MIGRATIONS.glob("*.py")
        for m in [
            re.search(
                r'^revision: str = "(\d{8}_\d{4})"',
                path.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
        ]
        if m
    }
    parents = {
        m.group(1)
        for path in MIGRATIONS.glob("*.py")
        for m in [
            re.search(
                r'^down_revision: str \| None = "(\d{8}_\d{4})"',
                path.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
        ]
        if m
    }
    heads = revisions - parents

    assert heads == {match.group(1)}, (
        f"the header says {match.group(1)}, the tree's head is {heads}"
    )
