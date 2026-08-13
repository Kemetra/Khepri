from __future__ import annotations

import ast
from pathlib import Path

RRA_DIR = Path(__file__).resolve().parents[1] / "src" / "khepri" / "rra"
RCA_DIR = Path(__file__).resolve().parents[1] / "src" / "khepri" / "rca"

_TARGET = "khepri.rca"


def _is_rca_target(dotted: str) -> bool:
    return dotted == _TARGET or dotted.startswith(_TARGET + ".")


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


def _imports_rca_submodule(node: ast.ImportFrom) -> bool:
    """True when the node is ``from <package-that-is-khepri> import rca``."""
    return any(alias.name == "rca" for alias in node.names)


def _import_offense(node: ast.Import) -> str | None:
    for alias in node.names:
        if _is_rca_target(alias.name):
            return f"line {node.lineno}: import {alias.name}"
    return None


def _import_from_offense(node: ast.ImportFrom, package: str) -> str | None:
    """Describe an offending ``from ... import ...``, or None when it is clean.

    Absolute and relative forms differ only in how the target is resolved, so both
    collapse onto the same two checks: the target IS khepri.rca (or below it), or the
    target is ``khepri`` and one of the names is ``rca``.
    """
    if node.level == 0:
        resolved = node.module or ""
        spelling = resolved
    else:
        resolved = _resolve_relative(package, node.level, node.module)
        spelling = f"{'.' * node.level}{node.module or ''}"

    if _is_rca_target(resolved):
        return f"line {node.lineno}: from {spelling} import ..."
    if resolved == "khepri" and _imports_rca_submodule(node):
        return f"line {node.lineno}: from {spelling or '.' * node.level} import rca"
    return None


def find_rca_import_offenses(source: str, package: str) -> list[str]:
    """Return a description for each import in ``source`` that reaches into khepri.rca.

    ``package`` is the dotted package the source file lives in, e.g. ``khepri.rra`` for
    a plain module or ``khepri.rra.analysis`` for a module inside that subpackage.
    """
    offenses: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            offense = _import_offense(node)
        elif isinstance(node, ast.ImportFrom):
            offense = _import_from_offense(node, package)
        else:
            continue
        if offense is not None:
            offenses.append(offense)
    return offenses


_SRC_DIR = RRA_DIR.parents[1]  # .../src, so relative parts start with "khepri"


def _package_for(path: Path) -> str:
    """Dotted package containing ``path``.

    Both a plain module (``rra/sessions.py``) and a package initializer
    (``rra/analysis/__init__.py``) report the directory they live in as their
    containing package, matching Python's own ``__package__`` semantics.
    """
    rel_parts = path.relative_to(_SRC_DIR).parts[:-1]
    return ".".join(rel_parts)


def test_no_rra_module_imports_rca() -> None:
    offenders: list[str] = []
    files = [p for p in RRA_DIR.rglob("*.py") if "__pycache__" not in p.parts]
    assert len(files) >= 50, f"expected recursive scan to cover subpackages, found {len(files)}"
    for path in sorted(files):
        source = path.read_text(encoding="utf-8")
        package = _package_for(path)
        for offense in find_rca_import_offenses(source, package):
            offenders.append(f"{path.relative_to(_SRC_DIR)}:{offense}")
    assert offenders == []


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


def test_rca_package_exists_and_is_importable() -> None:
    assert (RCA_DIR / "__init__.py").exists()


def test_rca_declares_no_rra_table_dependency() -> None:
    from khepri.rca.persistence import Base

    for table in Base.metadata.tables.values():
        assert table.name.startswith("rca_")
