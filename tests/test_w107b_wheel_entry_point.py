"""`W1-07b` -- the sweep must be reachable from the built wheel (`KHEPRI-DEC-033` §5).

§5's obligation is discharged by evidence against the **built artifact**, not the source tree: a
source-tree assertion passes today and proves nothing, since every sweeper already exists in source.
"""

from __future__ import annotations


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
