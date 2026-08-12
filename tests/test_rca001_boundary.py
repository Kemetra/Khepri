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


def find_rca_import_offenses(source: str, package: str) -> list[str]:
    """Return a description for each import in ``source`` that reaches into khepri.rca.

    ``package`` is the dotted package the source file lives in, e.g. ``khepri.rra`` for
    a plain module or ``khepri.rra.analysis`` for a module inside that subpackage.
    """
    offenses: list[str] = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_rca_target(alias.name):
                    offenses.append(f"line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                module = node.module or ""
                if _is_rca_target(module):
                    offenses.append(f"line {node.lineno}: from {module} import ...")
                elif module == "khepri":
                    for alias in node.names:
                        if alias.name == "rca":
                            offenses.append(f"line {node.lineno}: from khepri import rca")
            else:
                resolved = _resolve_relative(package, node.level, node.module)
                if _is_rca_target(resolved):
                    dots = "." * node.level
                    target = f"{dots}{node.module or ''}"
                    offenses.append(f"line {node.lineno}: from {target} import ...")
                elif resolved == "khepri":
                    for alias in node.names:
                        if alias.name == "rca":
                            offenses.append(
                                f"line {node.lineno}: from {'.' * node.level} import rca"
                            )
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
