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


def _classified_rows(document: str) -> list[tuple[str, str]]:
    """Every `(requirement, status)` pair the document states, in document order, ranges expanded.

    A *list*, not a dict, and that is the finding from review on `#218`: collapsing into a dict here
    made a duplicated authoritative row invisible, because the second occurrence overwrote the first
    and the count stayed at 40. A copied row -- or worse, two rows disagreeing where the *last* one
    happens to match the rollup -- passed a test whose docstring promised each requirement was
    classified exactly once.
    """
    pairs: list[tuple[str, str]] = []
    for first, last, cell in _ROW.findall(document):
        status = classify(cell)
        if status is None:
            continue
        low = int(first[3:])
        high = int(last[3:]) if last else low
        for number in range(low, high + 1):
            pairs.append((f"FR-{number:03d}", status))
    return pairs


def derive_counts(document: str) -> dict[str, str]:
    """Every requirement's status, from the **authoritative** tables only.

    Later rows win, which is what makes this correct rather than convenient: the change table near
    the top lists a handful of requirements with their *previous* status, and the authoritative
    per-requirement tables come after it.

    `_classified_rows` keeps the duplicates this discards, and
    `test_no_requirement_is_classified_twice_below_the_change_table` is what inspects them.
    """
    return dict(_classified_rows(document))


def _change_table_end(document: str) -> int:
    """Where the historical change table stops.

    Its heading is stable prose in the document's opening pass -- "Four rows changed status" -- and
    the authoritative tables begin at the first `## ` after it. Rows before this boundary state a
    *previous* status and are expected to repeat a requirement the tables state again.
    """
    marker = document.find("rows changed status")
    if marker == -1:
        return 0
    following = document.find("\n## ", marker)
    return len(document) if following == -1 else following


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


def test_no_requirement_is_classified_twice_below_the_change_table() -> None:
    """**Found in review on #218**, and the test above could not see it.

    `derive_counts` returns a dict, so a duplicated authoritative row overwrote its twin and the
    count stayed at 40 -- a copied row passed, and two rows *disagreeing* passed whenever the later
    one matched the rollup. Reproduced by duplicating `FR-011`'s row: all ten tests stayed green.

    The change table near the top legitimately repeats requirements at their previous status, so the
    duplicate check starts below it.
    """
    document = STATUS.read_text(encoding="utf-8")
    authoritative = document[_change_table_end(document) :]

    seen = Counter(requirement for requirement, _ in _classified_rows(authoritative))
    repeated = {requirement: count for requirement, count in seen.items() if count > 1}

    assert not repeated, (
        f"classified more than once below the change table: {repeated}. Two rows for one "
        "requirement means the rollup counts whichever happens to come last."
    )


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


def _cause_table_counts(document: str) -> list[int]:
    """The `Count` column of the cause table, read from its rows.

    **This reads the table, and an earlier version read only the sentence.** That version extracted
    the addends from `4 + 1 + 3 + 12 + 4 = **24**` and checked they summed to `24` -- which is a
    tautology, since both halves come from the same sentence. Editing a row's count to `99` passed
    all ten tests, and that is precisely the row-versus-sum drift the test's own docstring promised
    to guard. Found in review on `#218`.

    The cause table is the one whose header is `| Cause | Requirements | Count | Roadmap |`.
    """
    header = document.find("| Cause | Requirements | Count | Roadmap |")
    assert header != -1, "the cause table's header is missing or reworded"
    body = document[header:]
    blank = body.find("\n\n")
    table = body[: blank if blank != -1 else len(body)]
    rows = table.split("\n")[2:]  # skip the header and separator rows

    counts = []
    for row in rows:
        cells = [cell.strip().strip("*") for cell in row.split("|")]
        if len(cells) < 5:
            continue
        counts.append(int(cells[3]))
    return counts


def _cause_table_rows(document: str) -> list[tuple[int, set[str]]]:
    """Each cause row as `(stated count, requirements that row names)`, association kept.

    **The row association is what `_cause_table_requirements` throws away.** Unioning every
    row's identities and validating the count list separately means neither check can see a
    requirement that moved *between* rows: moving `FR-017` out of the four-item row into the
    `FR-016` row leaves the union identical and the count list `[4, 1, 3, 12, 4]` identical,
    while the two rows then name 3 and 2. Both cause tests passed on that edit. Found in review
    on `#218`, and it is the third round of one defect -- each earlier fix widened *which* facts
    are compared without asking whether they were still compared *per row*.
    """
    header = document.find("| Cause | Requirements | Count | Roadmap |")
    assert header != -1, "the cause table's header is missing or reworded"
    body = document[header:]
    blank = body.find("\n\n")
    table = body[: blank if blank != -1 else len(body)]

    rows: list[tuple[int, set[str]]] = []
    for row in table.split("\n")[2:]:
        cells = [cell.strip().strip("*") for cell in row.split("|")]
        if len(cells) < 5:
            continue
        named: set[str] = set()
        for match in re.finditer(r"`?(FR-0\d\d)`?(?:\s*(?:…|\.\.\.)\s*`?(FR-0\d\d)`?)?", cells[2]):
            low = int(match.group(1)[3:])
            high = int(match.group(2)[3:]) if match.group(2) else low
            named.update(f"FR-{number:03d}" for number in range(low, high + 1))
        rows.append((int(cells[3]), named))
    return rows


def _cause_table_requirements(document: str) -> set[str]:
    """Every requirement the cause table names, ranges expanded.

    **The Count column is not the claim.** An earlier version read only the counts, so replacing an
    incomplete requirement with an implemented one — `FR-005` for `FR-002` — passed every
    assertion while the table described the wrong set. Reproduced before fixing. Found in review on
    `#218`, and it is the second round of the same defect: the first fix widened the check from the
    sentence to the Count column without asking what else the test's own name promised.
    """
    header = document.find("| Cause | Requirements | Count | Roadmap |")
    assert header != -1, "the cause table's header is missing or reworded"
    body = document[header:]
    blank = body.find("\n\n")
    table = body[: blank if blank != -1 else len(body)]

    named: set[str] = set()
    for row in table.split("\n")[2:]:
        cells = [cell.strip().strip("*") for cell in row.split("|")]
        if len(cells) < 5:
            continue
        for match in re.finditer(r"`?(FR-0\d\d)`?(?:\s*(?:…|\.\.\.)\s*`?(FR-0\d\d)`?)?", cells[2]):
            low = int(match.group(1)[3:])
            high = int(match.group(2)[3:]) if match.group(2) else low
            named.update(f"FR-{number:03d}" for number in range(low, high + 1))
    return named


def test_the_cause_table_names_exactly_the_incomplete_requirements() -> None:
    """The counts agreeing is not the same claim as the *right requirements* being counted.

    A row that swapped `FR-005` for `FR-002` — an Implemented requirement — kept its count at 3 and
    passed every assertion in this file. So the identities are compared as sets against the
    Partial-plus-Not-implemented rows, which is what the test below's name has always promised.
    Found in review on `#218`.
    """
    document = STATUS.read_text(encoding="utf-8")
    derived = derive_counts(document)

    incomplete = {
        requirement
        for requirement, status in derived.items()
        if status in ("Partial", "Not implemented")
    }
    named = _cause_table_requirements(document)

    assert named == incomplete, (
        f"the cause table names {sorted(named - incomplete)} that are not incomplete, and omits "
        f"{sorted(incomplete - named)}. Counts matching does not mean the right requirements are "
        "counted."
    )


def test_each_cause_row_counts_the_requirements_it_names() -> None:
    """A `Count` cell must describe *its own row*, not the table's total.

    The union and the count list are both blind to a requirement moving between rows, because
    neither changes when one does. This is the assertion that does change. Found in review on
    `#218`.
    """
    document = STATUS.read_text(encoding="utf-8")

    for stated, named in _cause_table_rows(document):
        assert stated == len(named), (
            f"a cause row states {stated} but names {len(named)}: {sorted(named)}. "
            "The Count column describes the row it sits in."
        )


def test_the_row_scanner_catches_a_requirement_moved_between_rows() -> None:
    """**The mutation, planted.** Without this the helper above is unproven: the defect it
    exists for leaves the table superficially plausible, so a passing suite is not evidence.

    `FR-017` moves out of the four-item row into the `FR-016` row. Both counts are then wrong,
    while the union of identities and the list of counts are both unchanged -- which is exactly
    why the two older cause tests cannot see it.
    """
    sound = "\n".join(
        (
            "| Cause | Requirements | Count | Roadmap |",
            "|---|---|---|---|",
            "| a | FR-017, FR-018, FR-019, FR-020 | 4 | `R4` |",
            "| b | FR-016 | 1 | `R4-03` |",
        )
    )
    moved = "\n".join(
        (
            "| Cause | Requirements | Count | Roadmap |",
            "|---|---|---|---|",
            "| a | FR-018, FR-019, FR-020 | 4 | `R4` |",
            "| b | FR-016, FR-017 | 1 | `R4-03` |",
        )
    )

    # The union and the counts are identical across the two, so the older checks are blind.
    assert _cause_table_requirements(sound) == _cause_table_requirements(moved)
    assert _cause_table_counts(sound) == _cause_table_counts(moved)

    # The per-row view is not.
    assert all(stated == len(named) for stated, named in _cause_table_rows(sound))
    assert [(stated, len(named)) for stated, named in _cause_table_rows(moved)] == [
        (4, 3),
        (1, 2),
    ]


def test_the_cause_table_accounts_for_every_incomplete_requirement() -> None:
    """The fifth place the same fact lives. Its rows name counts per cause and its closing line sums
    them, so a row edited without the sum -- or the reverse -- is the same defect one table over.

    Three comparisons, because two of them are not the same claim: the table's own rows must sum to
    the sentence's total, the sentence's addends must match the table's rows *in order*, and the
    total must equal the rollup's incomplete count. The first two are what an earlier version
    collapsed into a tautology.
    """
    document = STATUS.read_text(encoding="utf-8")
    stated = _rollup_table(document)
    incomplete = stated["Partial"] + stated["Not implemented"]

    match = re.search(
        r"^((?:\d+ \+ )+\d+) = \*\*(\d+)\*\*, matching the rollup", document, re.MULTILINE
    )
    assert match is not None, "the cause table's arithmetic line is missing or reworded"
    sentence_addends = [int(part) for part in match.group(1).split(" + ")]
    claimed = int(match.group(2))
    table_counts = _cause_table_counts(document)

    assert table_counts == sentence_addends, (
        f"the cause table's rows are {table_counts}, the sentence adds {sentence_addends}. "
        "One was edited without the other."
    )
    assert sum(table_counts) == claimed, (
        f"the cause table's rows sum to {sum(table_counts)}, the sentence states {claimed}"
    )
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

    def git(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments], cwd=_ROOT, capture_output=True, text=True, check=False
        )

    # **Shallowness is established independently, and only then does this skip.** An earlier version
    # skipped whenever `git cat-file` returned nonzero -- but that is the same exit status for "the
    # object is absent because the clone is shallow" and "the SHA has a typo and never existed", so
    # the advertised missing-commit defect could not fail in any checkout. From review on `#218`.
    shallow = git("rev-parse", "--is-shallow-repository").stdout.strip() == "true"

    found = git("cat-file", "-t", match.group(1))
    if found.returncode != 0:
        if shallow:
            pytest.skip(f"{match.group(1)} is outside a shallow clone's history")
        raise AssertionError(
            f"the baseline names {match.group(1)}, which is not an object in this repository. "
            "The clone is not shallow, so the identifier is wrong."
        )
    assert found.stdout.strip() == "commit", (
        f"{match.group(1)} resolves to a {found.stdout.strip()}, not a commit"
    )

    # **Existing is not the claim; the header says `main`.** A SHA from a topic branch -- this
    # PR's own head, say -- is a real commit object, so the check above passes while the stated
    # baseline never belonged to the branch the document names. `--is-ancestor` is the
    # difference between "this object exists somewhere" and "this is a state of `main`". Found
    # in review on `#218`, and it is the same shape as the shallow-clone confusion above: one
    # exit status standing for two different facts.
    #
    # `main` may be absent in a detached CI checkout, so its absence skips rather than fails --
    # established independently, so a missing ref can never be misread as a bad ancestor.
    if git("rev-parse", "--verify", "--quiet", "refs/heads/main").returncode != 0:
        pytest.skip("no local `main` ref in this checkout to test ancestry against")

    ancestry = git("merge-base", "--is-ancestor", match.group(1), "main")
    assert ancestry.returncode == 0, (
        f"the baseline names {match.group(1)}, which is a commit but is not an ancestor of "
        "`main`. The header claims a state of `main`, so a topic-branch or orphaned commit is "
        "a false baseline even though the object exists."
    )

    # An abbreviated SHA that matches two objects is `git`'s ambiguity error, which the check above
    # would report as "not an object". Naming it separately so the message is actionable.
    assert "ambiguous" not in found.stderr.lower(), (
        f"the baseline {match.group(1)} is ambiguous; use more characters"
    )


def _migration_metadata(source: str) -> tuple[str | None, str | None]:
    """A migration's `(revision, down_revision)`, tolerant of how the value is quoted.

    **Either quote style, and a missing annotation.** An earlier version matched
    `revision: str = "…"` exactly, which silently ignored any migration whose value was
    single-quoted — the shape `migrations/script.py.mako` generates, because its template is
    `${repr(up_revision)}` and `repr` prefers single quotes. A generated migration would have been
    skipped entirely, leaving `heads` unchanged and a stale documented head passing. Found in review
    on `#218`.

    `None` for `down_revision` means the value is `None` in the source — the base revision — a real
    answer and not a parse failure. `_revisions_and_parents` distinguishes the two.
    """
    revision = re.search(
        r"^revision(?::\s*str)?\s*=\s*['\"](\d{8}_\d{4})['\"]", source, re.MULTILINE
    )
    parent = re.search(
        r"^down_revision(?::\s*[^=]+)?=\s*(?:['\"](\d{8}_\d{4})['\"]|None)", source, re.MULTILINE
    )
    return (
        revision.group(1) if revision else None,
        parent.group(1) if parent and parent.group(1) else None,
    )


def _revisions_and_parents() -> tuple[set[str], set[str]]:
    """Every revision identifier and every parent, with unparsed files reported rather than skipped.

    The assertion is the point: a migration this cannot read is a migration whose revision never
    enters `revisions`, so it can never be the head and a stale documented head passes. Failing
    loudly on an unreadable file is what makes the head check trustworthy.
    """
    revisions: set[str] = set()
    parents: set[str] = set()
    unreadable: list[str] = []

    for path in sorted(MIGRATIONS.glob("*.py")):
        revision, parent = _migration_metadata(path.read_text(encoding="utf-8"))
        if revision is None:
            unreadable.append(path.name)
            continue
        revisions.add(revision)
        if parent is not None:
            parents.add(parent)

    assert not unreadable, (
        f"could not read a revision identifier from {unreadable}. A migration this parser skips "
        "cannot be the head, so a stale documented head would pass."
    )
    return revisions, parents


def test_the_metadata_parser_accepts_both_quote_styles() -> None:
    """Self-tested, because the whole head check rests on this parser seeing every migration.

    The single-quoted case is not hypothetical: `migrations/script.py.mako` writes
    `${repr(up_revision)}`, and `repr` prefers single quotes.
    """
    double = 'revision: str = "20260818_0018"\ndown_revision: str | None = "20260817_0017"\n'
    single = "revision: str = '20260818_0018'\ndown_revision: str | None = '20260817_0017'\n"
    base = 'revision: str = "20260101_0001"\ndown_revision: str | None = None\n'

    assert _migration_metadata(double) == ("20260818_0018", "20260817_0017")
    assert _migration_metadata(single) == ("20260818_0018", "20260817_0017")
    assert _migration_metadata(base) == ("20260101_0001", None)
    assert _migration_metadata("# not a migration\n") == (None, None)


def test_the_stated_migration_head_is_the_real_head() -> None:
    """The header names a migration head. A stale one sends a reader to the wrong parent for the
    next revision, which is how a chain forks."""
    document = STATUS.read_text(encoding="utf-8")

    match = re.search(r"Migration head `(\d{8}_\d{4})`", document)
    assert match is not None, "the header states no migration head"

    revisions, parents = _revisions_and_parents()
    heads = revisions - parents

    assert heads == {match.group(1)}, (
        f"the header says {match.group(1)}, the tree's head is {heads}"
    )
