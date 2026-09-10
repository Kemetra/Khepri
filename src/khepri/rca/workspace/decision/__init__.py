"""Decision read models for the executive workspace (`D1`; active `RCA-008`).

`RCA-008` §Scope: "decision read models only, assembling projections into
surface-ready structures and computing nothing." A new subpackage rather than
files beside `RCA-005`'s, so §Scope's "`RCA-005`'s existing files are untouched"
is checkable by path rather than by review.

Nothing is re-exported here. A convenience alias would let a surface reach a
read model without naming which one, and `FR-160` wants every read to name its
view.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
