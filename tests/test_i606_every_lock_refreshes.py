"""Every row lock in `src/khepri` refreshes what it locks (`#606`).

A `SELECT ... FOR UPDATE` over a row the session already holds returns the held object unchanged
unless the statement carries `populate_existing`. The re-check that follows the lock then decides
on the state from before the wait. `#606` and `#610` were that defect on `run_for_update`; nothing
about it is specific to that statement, so the rule is checked for every lock rather than for the
three named in `rca/workspace/locks.py`.

The scan is of source rather than of compiled statements, because most locks are built inline and
a statement nobody names cannot be imported to compile. It reads `src/khepri` by its path from this
file, never from the working directory, so it cannot pass by scanning nothing.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src" / "khepri"

#: Every `.with_for_update(...)` call in `src/khepri` at the commit that added this test. A new lock
#: changes this number on purpose, so whoever adds one reads why it must refresh.
#: 19 since #535's artifact migration, whose row lock (`rra/envelope_migration.py`) refreshes.
LOCK_SITES = 19


def _modules() -> Iterator[tuple[Path, ast.Module]]:
    for path in sorted(SOURCE.rglob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _parents(tree: ast.Module) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _is_call_of(node: ast.AST, name: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == name
    )


def _refreshes(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> bool:
    """Whether the lock call is the receiver of `.execution_options(populate_existing=True)`."""
    attribute = parents.get(call)
    options = parents.get(attribute) if isinstance(attribute, ast.Attribute) else None
    if options is None or not _is_call_of(options, "execution_options"):
        return False
    return any(
        keyword.arg == "populate_existing"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is True
        for keyword in options.keywords
    )


def _lock_calls() -> Iterator[tuple[str, ast.Call, bool]]:
    for path, tree in _modules():
        parents = _parents(tree)
        for node in ast.walk(tree):
            if _is_call_of(node, "with_for_update"):
                where = f"{path.relative_to(SOURCE)}:{node.lineno}"
                yield where, node, _refreshes(node, parents)


def test_the_scan_reads_the_package() -> None:
    assert (SOURCE / "rca" / "workspace" / "locks.py").is_file(), f"not the package: {SOURCE}"


def test_every_lock_refreshes_the_rows_it_locks() -> None:
    stale = [where for where, _call, refreshes in _lock_calls() if not refreshes]
    assert not stale, f"locks that can return a held row unrefreshed (#606): {stale}"


def test_the_lock_sites_are_the_ones_counted() -> None:
    found = [where for where, _call, _refreshes in _lock_calls()]
    assert len(found) == LOCK_SITES, f"{len(found)} lock sites, not {LOCK_SITES}: {found}"


def test_no_lock_is_taken_through_a_keyword() -> None:
    """`Session.get`, `refresh` and `Query` accept `with_for_update=`, which this scan cannot pair
    with `populate_existing`; none is used, and this keeps it so."""
    keyword_locks = [
        f"{path.relative_to(SOURCE)}:{node.lineno}"
        for path, tree in _modules()
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and any(keyword.arg == "with_for_update" for keyword in node.keywords)
    ]
    assert not keyword_locks, f"a lock taken by keyword: {keyword_locks}"
