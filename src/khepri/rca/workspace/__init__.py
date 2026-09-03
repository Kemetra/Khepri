"""The organization workspace: dataset versions, analysis runs, history and deletion (`RCA-005`).

A subpackage rather than a flat module, because `RCA-005`'s scope names
`src/khepri/rca/workspace/` and allocates domain contracts, persistence and
services to it. The sibling `rra/` package is laid out the same way for the
same reason.

Nothing here computes. A workspace surface selects and presents facts and
artifacts that `RRA-004`, `RRA-006` and `RRA-008` already produced; a module in
this package that derived, rounded or summed a figure would be a second source
of truth for a published number.
"""

from __future__ import annotations
