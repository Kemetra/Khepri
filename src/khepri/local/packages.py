"""The fact-package source a local pipeline reads from.

`SessionFactPackageSource` already adapts a `SessionPackageReader` onto the
pipeline's `FactPackageSource`, and `FactPackageService` satisfies that reader. So
this module is one call, kept as a named function only so the composition root
reads as a list of collaborators rather than as adapters assembled inline.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from khepri.rra.package_source import SessionFactPackageSource, SessionPackageReader
from khepri.rra.pipeline import FactPackageSource


def build_package_source(
    *,
    packages: SessionPackageReader,
    now: Callable[[], datetime],
) -> FactPackageSource:
    """Adapt the published packages onto what one leased job reads."""
    return SessionFactPackageSource(packages=packages, now=now)


__all__ = ["build_package_source"]
