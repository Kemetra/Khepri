"""`S1-04`: every workbook directory is created as this process's alone (`CWE-377`).

`#434` item 5. The comparison render parent was hardened on `#409`; the three workbook sites
were not, and the guard's own docstring named the omission. These tests drive the real entry
points rather than the guard, so deleting a call site fails a test here -- a test that called
`own_private_directory` directly would survive that deletion and prove nothing.

The extent test is the one that matters most: the three sites were found by sweeping `src/`
for `mkdir(`, not by reading the triage note, which named one of them.
"""

from __future__ import annotations

import ast
import inspect
import os
from pathlib import Path

import pytest

from khepri.local import cli as local_cli
from khepri.local import wiring as local_wiring
from khepri.runtime import wiring as runtime_wiring
from khepri.runtime.private_directory import own_private_directory

GUARD = "own_private_directory"


def _symlink_or_skip(tmp_path: Path, name: str) -> Path:
    target = tmp_path / f"{name}-elsewhere"
    target.mkdir()
    link = tmp_path / name
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"symlinks unavailable here: {error}")
    return link


def test_the_guard_refuses_a_symlink(tmp_path) -> None:
    """A symlink pre-placed at the path redirects every write that follows it."""
    link = _symlink_or_skip(tmp_path, "workbooks")

    with pytest.raises(RuntimeError, match="symlink"):
        own_private_directory(link, purpose="worker workbook directory")


def test_the_guard_closes_a_pre_existing_wide_directory(tmp_path) -> None:
    """`mkdir` applies its mode only on creation, so a directory left wide by an earlier run
    keeps that mode unless the guard sets it."""
    if os.name != "posix":
        pytest.skip("POSIX permission bits only")
    chosen = tmp_path / "workbooks"
    chosen.mkdir(mode=0o777)
    chosen.chmod(0o777)

    own_private_directory(chosen, purpose="worker workbook directory")

    assert chosen.stat().st_mode & 0o777 == 0o700


def test_the_guard_names_its_purpose_in_the_refusal(tmp_path) -> None:
    """Two kinds of directory share one guard, so a workbook failure must not report itself
    as a comparison failure."""
    link = _symlink_or_skip(tmp_path, "workbooks")

    with pytest.raises(RuntimeError, match="worker workbook directory"):
        own_private_directory(link, purpose="worker workbook directory")


def _creates_a_directory_through_the_guard(function) -> bool:
    """True when `function`'s body creates its directory through the guard and not by `mkdir`.

    Structural, over the real source, because the alternative -- building a `LocalStack` --
    reaches PostgreSQL and localstack, so those tests skip in CI and would report `NOT
    EXERCISED` as a pass.
    """
    tree = ast.parse(inspect.getsource(function))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    guarded = any(
        isinstance(call.func, ast.Name) and call.func.id == GUARD for call in calls
    )
    bare_mkdir = any(
        isinstance(call.func, ast.Attribute) and call.func.attr == "mkdir"
        for call in calls
    )
    return guarded and not bare_mkdir


@pytest.mark.parametrize(
    ("label", "function"),
    [
        ("runtime pipeline", runtime_wiring.build_pipeline),
        ("local worker stack", local_wiring.build_worker_stack),
        ("local cli drain", local_cli._work),
    ],
)
def test_every_workbook_entry_point_creates_its_directory_through_the_guard(
    label: str, function
) -> None:
    assert _creates_a_directory_through_the_guard(function), (
        f"{label} must create its workbook directory through {GUARD}, not a bare mkdir"
    )


def _is_mkdir_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "mkdir"
    )


def _mkdir_lines(module: Path) -> list[int]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    return [node.lineno for node in ast.walk(tree) if _is_mkdir_call(node)]


def test_no_unguarded_mkdir_survives_anywhere_in_the_package() -> None:
    """The extent assertion. A per-site test leaves site four open when someone adds it;
    this fails on any `mkdir` in `src/` that is not the guard's own."""
    root = Path(inspect.getfile(runtime_wiring)).parents[1]
    guard_source = Path(inspect.getfile(own_private_directory)).resolve()
    modules = [m for m in sorted(root.rglob("*.py")) if m.resolve() != guard_source]

    offenders = [
        f"{module.relative_to(root)}:{line}"
        for module in modules
        for line in _mkdir_lines(module)
    ]

    assert offenders == [], f"unguarded mkdir outside the guard: {offenders}"
    assert modules, "the sweep found no modules, so it proves nothing"
