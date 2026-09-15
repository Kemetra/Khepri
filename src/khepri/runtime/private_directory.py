"""One definition of "this directory is this process's alone" (`CWE-377`).

`S1-04`. The guard was written for the comparison render parent on `#409` and its docstring
already named the worker's workbook directory as carrying the identical exposure -- a default
inside a shared temporary namespace, created with a bare `mkdir`. It then did not cover it.
Three call sites created such a directory unguarded: the runtime pipeline, the local worker
stack, and the local CLI's own drain path.

It lives here rather than in either `wiring` module because both packages need it and
`khepri.local` importing a private name out of `khepri.runtime.wiring` would be the wrong
direction across that seam. `khepri.local` already imports `khepri.runtime.legal_api` and
`khepri.runtime.retention_sweep`, so the direction itself is established.
"""

from __future__ import annotations

import os
from pathlib import Path


def own_private_directory(path: Path, *, purpose: str) -> None:
    """Create `path` as this process user's alone, or refuse it.

    The directory is created private to the process user, a symlink is refused, and on POSIX a
    directory owned by someone else is refused rather than used. `purpose` names the directory
    in the refusal, so a workbook failure does not report itself as a comparison failure.
    """
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f"{purpose} must not be a symlink: {path}")
    # mkdir applies its mode only when it creates the directory; a path left behind by an
    # earlier run, or pre-created wider, keeps its mode unless it is set here as well.
    path.chmod(0o700)
    getuid = getattr(os, "getuid", None)
    if getuid is not None and path.stat().st_uid != getuid():
        raise RuntimeError(f"{purpose} is owned by another user: {path}")


__all__ = ["own_private_directory"]
