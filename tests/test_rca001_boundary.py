from __future__ import annotations

from pathlib import Path

RRA_DIR = Path(__file__).resolve().parents[1] / "src" / "khepri" / "rra"
RCA_DIR = Path(__file__).resolve().parents[1] / "src" / "khepri" / "rca"


def test_no_rra_module_imports_rca() -> None:
    offenders = [
        path.name
        for path in sorted(RRA_DIR.glob("*.py"))
        if "khepri.rca" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_rca_package_exists_and_is_importable() -> None:
    assert (RCA_DIR / "__init__.py").exists()


def test_rca_declares_no_rra_table_dependency() -> None:
    from khepri.rca.persistence import Base

    for table in Base.metadata.tables.values():
        assert table.name.startswith("rca_")
