"""The one place a sizing declaration is read, and the only shape it may arrive in.

`KHEPRI-DEC-007` fixes every size in this platform and requires that changing one is a governed
change rather than an operational adjustment. That holds only if the values live in a reviewable
document whose bytes will be covered by a digest once the environment descriptor exists, so they
live in `governance/benchmarks/` and are read from there. No digest covers this file today.

`sizing.resolve_sizing` already refuses a missing, blank, or non-integer field. This module adds no
tolerance of its own: it locates the document, insists it is a mapping of strings, and hands it
over. Nothing here supplies a fallback, because a template synthesized around a guessed size is
indistinguishable from one synthesized around an approved size once it is deployed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from khepri.infra.sizing import InfrastructureSizing, SizingRefused, resolve_sizing

SIZING_DECLARATION = (
    Path(__file__).resolve().parents[3]
    / "governance"
    / "benchmarks"
    / "KHEPRI-BMK-001-sizing.yaml"
)


def load_sizing(path: Path | None = None) -> InfrastructureSizing:
    """Read the governed declaration and resolve it, refusing anything incomplete."""
    document = path if path is not None else SIZING_DECLARATION
    parsed = yaml.safe_load(document.read_text(encoding="utf-8"))
    return resolve_sizing(_require_mapping(parsed))


def _require_mapping(parsed: Any) -> dict[str, str]:
    if not isinstance(parsed, dict):
        raise SizingRefused("A sizing declaration must be a mapping.")
    return {str(key): str(value) for key, value in parsed.items()}
