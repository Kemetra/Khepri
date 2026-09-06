"""`W1-07b` -- the sweep must be reachable from the built wheel (`KHEPRI-DEC-033` §5).

§5's obligation is discharged by evidence against the **built artifact**, not the source tree: a
source-tree assertion passes today and proves nothing, since every sweeper already exists in source.
"""

from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ENTRY_POINT = "khepri-retention-sweep"
REPOSITORY = Path(__file__).resolve().parent.parent


def test_the_composition_has_exactly_one_definition() -> None:
    """`khepri.local` re-exports the runtime composition rather than keeping a copy.

    Two compositions is the "second deletion implementation to keep correct" `local/sweeper.py`'s
    own docstring warns against. Asserted by identity, so a copy-paste fails here.
    """
    from khepri.local import sweeper as local
    from khepri.runtime import retention_sweep as runtime

    assert local.RetentionSweeper is runtime.RetentionSweeper
    assert local.RetentionPasses is runtime.RetentionPasses
    assert local.build_retention_sweeper is runtime.build_retention_sweeper



@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The actual wheel, built the way the image is built."""
    out = tmp_path_factory.mktemp("wheel")
    built = subprocess.run(
        ["uv", "build", "--wheel", "-o", str(out)],
        capture_output=True,
        text=True,
        cwd=REPOSITORY,
    )
    if built.returncode != 0:
        pytest.skip(f"uv build unavailable: {built.stderr[-300:]}")
    return next(out.glob("*.whl"))


def _entry_point_lines(wheel: Path) -> list[str]:
    """Every line of the wheel's `entry_points.txt`, across whichever `.dist-info` holds it."""
    archive = zipfile.ZipFile(wheel)
    manifests = [name for name in archive.namelist() if name.endswith("entry_points.txt")]
    return [line for name in manifests for line in archive.read(name).decode().splitlines()]


def _declared_target(wheel: Path, name: str) -> str:
    """The `module:function` the wheel declares for one console script."""
    declarations = [line for line in _entry_point_lines(wheel) if line.startswith(f"{name} =")]
    assert declarations, f"{name} is not declared in the wheel"
    return declarations[0].split("=", 1)[1].strip()


def test_the_sweep_entry_point_resolves_inside_the_built_wheel(built_wheel: Path) -> None:
    """`KHEPRI-DEC-033` §5: a caller **present in the shipped image**.

    Resolved against the wheel's **contents**, never against `entry_points.txt` alone. Measured
    while designing this slice: a wheel will happily declare a `khepri-phantom` script targeting
    `khepri.local.cli:main` while `khepri/local` is absent from that same wheel, because entry
    points come from project
    metadata and `exclude` governs packaged files. A manifest test therefore passes over a command
    that crashes on invocation -- reproducing, inside the test meant to prove §5 closed, exactly the
    unreachable-procedure shape §5 exists to close.
    """
    target = _declared_target(built_wheel, ENTRY_POINT)
    module, _, function = target.partition(":")
    assert function == "main", target

    packaged = set(zipfile.ZipFile(built_wheel).namelist())
    assert f"{module.replace('.', '/')}.py" in packaged, (
        f"{ENTRY_POINT} targets {module}, which the wheel does not package"
    )


def test_the_sweep_module_imports_with_no_excluded_package(built_wheel: Path) -> None:
    """The command must *run*, not merely be declared.

    A module that ships but reaches into the excluded `khepri.local` package puts the command in
    the image and crashes it at import. This imports the target from the **wheel's own contents**
    with the repository's `src/` off the path, so a transitive leak into an unpackaged module
    fails here rather than at a customer's invocation.
    """
    target = _declared_target(built_wheel, ENTRY_POINT)
    module, _, _ = target.partition(":")

    extracted = built_wheel.parent / "extracted"
    zipfile.ZipFile(built_wheel).extractall(extracted)

    imported = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        cwd=extracted,
        # A bare environment carrying only the extracted wheel: the repository's `src/` must not
        # be importable, or a module missing from the wheel would resolve from the checkout and
        # the test would pass over exactly the defect it exists to catch. `SYSTEMROOT` is carried
        # through because the interpreter needs it on Windows.
        env={
            "PYTHONPATH": str(extracted),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        },
    )
    assert imported.returncode == 0, imported.stderr[-600:]
