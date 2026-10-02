from __future__ import annotations

import ast
from pathlib import Path

RRA_DIR = Path(__file__).resolve().parents[1] / "src" / "khepri" / "rra"
RCA_DIR = Path(__file__).resolve().parents[1] / "src" / "khepri" / "rca"

RCA_TARGET = "khepri.rca"
RRA_TARGET = "khepri.rra"


def _is_target(dotted: str, target: str) -> bool:
    return dotted == target or dotted.startswith(target + ".")


def _resolve_relative(package: str, level: int, module: str | None) -> str:
    """Resolve a relative import's dotted target against the importing module's package.

    Mirrors ``importlib.util.resolve_name`` semantics: one dot (level=1) refers to
    ``package`` itself, each additional dot strips one trailing component.
    """
    bits = package.split(".")
    base_len = len(bits) - (level - 1)
    base = ".".join(bits[:base_len]) if base_len > 0 else ""
    if module:
        return f"{base}.{module}" if base else module
    return base


def _imports_target_submodule(node: ast.ImportFrom, resolved: str, target: str) -> bool:
    """True when the node is ``from <target's parent> import <target's leaf>``.

    For ``khepri.rca`` that is ``from khepri import rca``; for ``khepri.rra``,
    ``from khepri import rra``.
    """
    parent, _, leaf = target.rpartition(".")
    return resolved == parent and any(alias.name == leaf for alias in node.names)


def _import_offense(node: ast.Import, target: str) -> str | None:
    for alias in node.names:
        if _is_target(alias.name, target):
            return f"line {node.lineno}: import {alias.name}"
    return None


def _import_from_offense(node: ast.ImportFrom, package: str, target: str) -> str | None:
    """Describe an offending ``from ... import ...``, or None when it is clean.

    Absolute and relative forms differ only in how the target is resolved, so both
    collapse onto the same two checks: the resolved module IS the target (or below
    it), or it is the target's parent and one of the names is the target's leaf.
    """
    if node.level == 0:
        resolved = node.module or ""
        spelling = resolved
    else:
        resolved = _resolve_relative(package, node.level, node.module)
        spelling = f"{'.' * node.level}{node.module or ''}"

    if _is_target(resolved, target):
        return f"line {node.lineno}: from {spelling} import ..."
    if _imports_target_submodule(node, resolved, target):
        leaf = target.rpartition(".")[2]
        return f"line {node.lineno}: from {spelling or '.' * node.level} import {leaf}"
    return None


def find_import_offenses(source: str, package: str, target: str) -> list[str]:
    """Return a description for each import in ``source`` that reaches into ``target``.

    ``package`` is the dotted package the source file lives in, e.g. ``khepri.rra`` for
    a plain module or ``khepri.rra.analysis`` for a module inside that subpackage.
    ``target`` is the dotted package no import may reach, e.g. ``khepri.rca``.
    """
    offenses: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            offense = _import_offense(node, target)
        elif isinstance(node, ast.ImportFrom):
            offense = _import_from_offense(node, package, target)
        else:
            continue
        if offense is not None:
            offenses.append(offense)
    return offenses


def find_rca_import_offenses(source: str, package: str) -> list[str]:
    """`find_import_offenses` with ``khepri.rca`` as the target (the RRA→RCA direction)."""
    return find_import_offenses(source, package, RCA_TARGET)


_SRC_DIR = RRA_DIR.parents[1]  # .../src, so relative parts start with "khepri"


def _package_for(path: Path) -> str:
    """Dotted package containing ``path``.

    Both a plain module (``rra/sessions.py``) and a package initializer
    (``rra/analysis/__init__.py``) report the directory they live in as their
    containing package, matching Python's own ``__package__`` semantics.
    """
    rel_parts = path.relative_to(_SRC_DIR).parts[:-1]
    return ".".join(rel_parts)


def package_modules(package_dir: Path) -> list[Path]:
    """Every module under ``package_dir``, subpackages included, in a stable order.

    The population a scan visits. A caller asserts its size, because a scan over no
    files reports no offenders and so passes while proving nothing.
    """
    return sorted(p for p in package_dir.rglob("*.py") if "__pycache__" not in p.parts)


def package_import_offenses(package_dir: Path, target: str) -> list[str]:
    """Every import under ``package_dir`` that reaches into ``target``. Empty is passing."""
    return [
        f"{path.relative_to(_SRC_DIR)}:{offense}"
        for path in package_modules(package_dir)
        for offense in find_import_offenses(
            path.read_text(encoding="utf-8"), _package_for(path), target
        )
    ]


def test_no_rra_module_imports_rca() -> None:
    files = package_modules(RRA_DIR)
    assert len(files) >= 50, f"expected recursive scan to cover subpackages, found {len(files)}"
    assert package_import_offenses(RRA_DIR, RCA_TARGET) == []


def test_rca_import_checker_flags_and_clears_expected_cases() -> None:
    flagged_cases = [
        ("import khepri.rca", "khepri.rra"),
        ("from khepri.rca.accounts import Account", "khepri.rra"),
        ("from khepri import rca", "khepri.rra"),
        ("from ..rca import accounts", "khepri.rra"),
        ("from ...rca import accounts", "khepri.rra.analysis"),
        ("from .. import rca", "khepri.rra"),
    ]
    for source, package in flagged_cases:
        assert find_rca_import_offenses(source, package), f"expected a flag for: {source!r}"

    clear_cases = [
        ("import khepri.rra.sessions", "khepri.rra"),
        ("from khepri.rra import sessions", "khepri.rra"),
        ("from . import sessions", "khepri.rra"),
        ('"""A docstring mentioning khepri.rca for illustration only."""', "khepri.rra"),
        ("# a comment mentioning khepri.rca should not trip the checker", "khepri.rra"),
    ]
    for source, package in clear_cases:
        assert not find_rca_import_offenses(source, package), f"unexpected flag for: {source!r}"


def test_the_checker_takes_its_target_rather_than_assuming_rca() -> None:
    """The same checker serves the RCA→RRA direction (`KHEPRI-DEC-021` §3, #226).

    Each form is flagged for the target it reaches and cleared for the other, so a
    target that silently fell back to ``khepri.rca`` fails here.
    """
    reaches_rra = [
        ("import khepri.rra.sessions", "khepri.rca"),
        ("from khepri import rra", "khepri.rca"),
        ("from ..rra import sessions", "khepri.rca"),
        ("from .. import rra", "khepri.rca"),
    ]
    for source, package in reaches_rra:
        assert find_import_offenses(source, package, RRA_TARGET), f"expected: {source!r}"
        assert not find_import_offenses(source, package, RCA_TARGET), f"unexpected: {source!r}"
    assert not find_import_offenses("import khepri.rraX", "khepri.rca", RRA_TARGET)


def test_rca_package_exists_and_is_importable() -> None:
    assert (RCA_DIR / "__init__.py").exists()


def test_rca_declares_no_rra_table_dependency() -> None:
    from khepri.rca.persistence import Base

    for table in Base.metadata.tables.values():
        assert table.name.startswith("rca_")
