"""`W1-07b` -- the evidence that replaces `INVITATION_HORIZON_IS_UNENFORCED`.

`KHEPRI-DEC-033` §5 says deleting that flag "is part of the evidence". Deleting the constant, its
export and its assertion together would leave **nothing that can fail if the flag returns** -- so
the evidence needs a shape, and this is it.

Written as a scan over a *pattern* rather than a check on one name, because the defect it guards is
**a horizon documented as unenforced**, not that particular constant. A guard that names only the
one instance it was written for reproduces the drift it exists to catch.
"""

from __future__ import annotations

import re
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / "src" / "khepri"
UNENFORCED = re.compile(r"^[A-Z0-9_]*_IS_UNENFORCED\s*=", re.MULTILINE)


def test_no_horizon_is_declared_unenforced() -> None:
    """`KHEPRI-DEC-033` §5 is discharged by a sweep with a caller in the shipped image, so a
    constant still announcing a horizon as unenforced would contradict the artifact that ships.

    Before `W1-07b`, `rca/invitation_retention.py:40` held `INVITATION_HORIZON_IS_UNENFORCED = True`
    and a test asserted it `is True` -- an accurate statement of a real gap. This replaces both.
    """
    modules = sorted(SOURCE.rglob("*.py"))
    # The scan's own input, asserted non-empty. A scan that can silently cover nothing passes
    # vacuously, which is how `#240`'s table stayed invisible to a guard written to catch it.
    assert len(modules) > 100, f"the scan found only {len(modules)} modules; its root is wrong"

    declared = [
        module.relative_to(SOURCE).as_posix()
        for module in modules
        if UNENFORCED.search(module.read_text(encoding="utf-8"))
    ]

    assert not declared, f"a horizon is still declared unenforced in: {declared}"


def test_the_deployed_composition_reaches_every_retention_pass() -> None:
    """Deleting a flag that says "unenforced" while the pass stays unreached would be worse than
    the flag: the documentation would improve and the behaviour would not.

    Asserted against `build_retention_sweep`, which is what `khepri-retention-sweep` calls -- so
    this is the deployed composition and not the local one. `test_local_sweeper.py` makes the
    equivalent AST assertion for `khepri.local`; both are needed, because the two compositions are
    separate call sites that could drift.
    """
    import inspect

    from khepri.runtime.wiring import build_retention_sweep

    source = inspect.getsource(build_retention_sweep)
    for sweeper in (
        "AccountRetentionSweeper",
        "MembershipEventSweeper",
        "SessionRetentionSweeper",
        "InvitationRetentionSweeper",
        "RecoverySecurityEventSweeper",
        "WorkspaceAuditSweeper",
        "DeletionEvidenceSweeper",
    ):
        assert sweeper in source, f"the deployed sweep does not reach {sweeper}"
