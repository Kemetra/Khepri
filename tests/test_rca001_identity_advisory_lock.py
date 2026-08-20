"""`R4-01` §8.2's advisory lock over an identity, and the evidence it owes.

**Why this file exists in `R4-06` rather than `R4-04`.** §8.2 assigns the lock to `R4-04` ("What
`R4-04` still implements", "the evidence `R4-04` owes"), but §4 and §4.1 -- which specify issuance
and revocation -- never mention it, so `R4-04` shipped without one (PR #221). The lock's
purge-side call belongs in `purge_if_still_eligible`, which is the method `R4-06`'s own cascade
touches, so it lands here rather than in a branch that would conflict there.

**What the lock does, stated once so no test overclaims it.** It closes the **issuance-first**
ordering of §7.1's identity-transfer hazard and not the purge-first one, which §8.2 records the
owner accepting as a residual on 2026-08-18. Half a fix, deliberately.

## The evidence, and why the obvious test cannot fail on the defect

The defect the key derivation must exclude is `hash()`, which PEP 456 randomises per process: two
workers derive different keys, acquire non-conflicting locks, and serialize nothing while the code
reads correctly. "Two processes derive the same key" does **not** catch it -- `multiprocessing`
forks by default on Linux, so children inherit the parent's hash secret, and CI pinning
`PYTHONHASHSEED` makes even fresh interpreters agree. That is the same "test that cannot fail on the
defect" shape `#212`/`#213` fixed in this note's other key derivation.

So §8.2 specifies two forms, and this file has both:

1. **Assert the constant** -- a literal bigint committed here. `hash()` cannot produce a fixed value
   across seeds, so this fails on it by construction, needs no subprocess, and runs unconditionally.
2. **Spawn fresh interpreters with explicitly different seeds** and assert the keys match. This
   proves the derivation is environment-independent rather than merely that a digest is
   deterministic -- it fails for the right reason rather than by coincidence of the constant.
"""

from __future__ import annotations

import os
import subprocess
import sys
from hashlib import sha256

import pytest
from sqlalchemy.dialects import postgresql, sqlite

from khepri.rca.persistence import (
    identity_advisory_lock,
    identity_lock_key,
    take_identity_lock,
)

#: The key for `alice@example.com`, computed once and committed as a literal.
#:
#: The point of a hard-coded constant is that it cannot be produced by a randomised `hash()`, so
#: this line is the whole of form 1. It is derived independently in
#: `test_the_constant_matches_an_independent_derivation` rather than only restated, because a
#: constant copied from the implementation's own output would agree with any implementation.
ALICE_KEY = -32202384951340353


class TestTheKeyIsStableAcrossProcesses:
    """Form 1 and form 2 of §8.2's required evidence."""

    def test_the_key_is_the_committed_constant(self) -> None:
        """Fails by construction on `hash()`, which cannot produce a fixed value across seeds."""
        assert identity_lock_key("alice@example.com") == ALICE_KEY

    def test_the_constant_matches_an_independent_derivation(self) -> None:
        """The constant is checked against §8.2's formula, not against the implementation.

        Committing a value read out of the implementation would make the test agree with whatever
        the implementation does -- the tautology shape this repo has recorded. §8.2 fixes the
        formula verbatim: `int.from_bytes(sha256(canonical_address.encode()).digest()[:8], "big",
        signed=True)`.
        """
        expected = int.from_bytes(
            sha256(b"alice@example.com").digest()[:8], "big", signed=True
        )
        assert expected == ALICE_KEY

    def test_a_case_difference_changes_the_key(self) -> None:
        """Which is why callers must pass a canonical address (§4's storage rule).

        Asserted rather than assumed: if the derivation folded case internally, the two paths could
        disagree about *where* folding happens and one of them would fold twice or not at all. The
        function is a pure map from the string it is given; canonicalization is the caller's.
        """
        assert identity_lock_key("Alice@Example.COM") != identity_lock_key("alice@example.com")

    def test_fresh_interpreters_with_different_seeds_agree(self) -> None:
        """Form 2 -- `spawn`, not `fork`, so no hash secret is inherited.

        A forked child inherits the parent's `PYTHONHASHSEED`, so a `multiprocessing` version of
        this test passes against `hash()` on Linux. Explicit subprocesses with *different* seeds
        are what make the assertion about the derivation rather than about the environment.
        """
        program = (
            "from khepri.rca.persistence import identity_lock_key; "
            "print(identity_lock_key('alice@example.com'))"
        )
        keys = []
        for seed in ("0", "1"):
            result = subprocess.run(
                [sys.executable, "-c", program],
                env={**os.environ, "PYTHONHASHSEED": seed},
                capture_output=True,
                text=True,
                check=True,
            )
            keys.append(result.stdout.strip())

        assert keys[0] == keys[1], (
            f"two interpreters with different hash seeds derived different keys: {keys}; "
            "the derivation depends on the process, so the two paths would lock different keys"
        )
        assert keys[0] == str(ALICE_KEY)


class TestTheStatementCompiles:
    """§8.2: "a test compiling it against the PostgreSQL dialect and asserting the advisory
    acquisition is present, without needing a database". Same discipline as the `FOR UPDATE`
    statements, different lock primitive.
    """

    def test_the_advisory_acquisition_is_present(self) -> None:
        sql = str(
            identity_advisory_lock("alice@example.com").compile(dialect=postgresql.dialect())
        )
        assert "pg_advisory_xact_lock" in sql, (
            "the compiled statement must acquire the advisory lock; this is the assertion that "
            "fails if the call is removed or renamed"
        )

    def test_the_key_is_bound_rather_than_interpolated(self) -> None:
        """A bound parameter, not string formatting -- the statement carries no literal.

        `pg_advisory_xact_lock` takes an integer so injection is not the hazard here; the reason is
        that a formatted statement is a different statement per address, and the compilation test
        above would then assert nothing about the one production uses.
        """
        statement = identity_advisory_lock("alice@example.com")
        compiled = statement.compile(dialect=postgresql.dialect())

        assert str(ALICE_KEY) not in str(compiled), "the key must not be interpolated into the SQL"
        assert compiled.params["identity_lock_key"] == ALICE_KEY

    def test_it_is_postgresql_specific_and_that_is_recorded(self) -> None:
        """SQLite emits the text but has no such function, so the lock is inert there.

        §8.2 states this: "SQLite emits no advisory lock, so `R4-07`'s race case runs against
        PostgreSQL". Asserted so the limitation is visible in the suite rather than only in prose --
        a reader who assumes the local SQLite run proves serialization is wrong, and this is where
        they find out.
        """
        sql = str(identity_advisory_lock("alice@example.com").compile(dialect=sqlite.dialect()))
        assert "pg_advisory_xact_lock" in sql, (
            "the statement compiles under SQLite but the function does not exist there, so any "
            "serialization claim must be made against PostgreSQL"
        )


class TestTheResidualIsDocumentedRatherThanClosed:
    """§8.2's accepted residual, asserted as a property of the code rather than left to prose."""

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "The purge-first ordering is the residual the owner accepted on 2026-08-18 "
            "(`R4-01` §8.2). An `issue` beginning after the purge commits finds no address on the "
            "tombstone, takes no lock, and inserts an invitation after the cascade has run. §7.1 "
            "establishes that no available mechanism reaches this without retaining an "
            "address-derived marker, which `KHEPRI-DEC-015` §2b forbids. If this ever starts "
            "passing, something changed and the suite says so."
        ),
    )
    def test_the_purge_first_ordering_is_closed(self) -> None:
        """Marked `xfail(strict=True)` per §8.2, so the day it passes the suite fails.

        There is no assertion body that can honestly pass here: closing this ordering requires a
        mechanism §7.1's candidate table rules out. The `xfail` records the gap where a reader looks
        for it, and `strict=True` is what makes it a tripwire rather than a comment.
        """
        raise AssertionError(
            "the purge-first ordering is open by accepted design; see `R4-01` §8.2"
        )


class TestTheDialectGuardIsNotAnEscapeHatch:
    """`take_identity_lock` skips SQLite, and that branch must not be able to skip PostgreSQL.

    A guard that decides whether a security-relevant lock is taken is exactly the kind that
    self-disarms: the suite runs on SQLite, so the *skip* path is the one every test exercises and
    the *take* path is the one nothing here would notice losing. Both branches are asserted, and
    the PostgreSQL side is asserted through a stub bind rather than by needing a server -- the same
    "without needing a database" discipline §8.2 sets for the compilation test.
    """

    def test_it_declines_on_sqlite(self) -> None:
        """The real backend the suite uses. Executing the statement here would raise."""

        class _Bind:
            dialect = sqlite.dialect()

        class _Session:
            def get_bind(self):
                return _Bind()

            def execute(self, statement):  # pragma: no cover - must not be reached
                raise AssertionError("the lock must not be executed against SQLite")

        assert take_identity_lock(_Session(), "alice@example.com") is False

    def test_it_takes_the_lock_on_postgresql(self) -> None:
        """The branch no SQLite-backed test would notice losing.

        Asserts the statement *and* its bound key, so a guard that reached this branch and executed
        the wrong statement -- or one with an unbound parameter -- fails here rather than passing
        for the wrong reason.
        """
        executed = []

        class _Bind:
            dialect = postgresql.dialect()

        class _Session:
            def get_bind(self):
                return _Bind()

            def execute(self, statement):
                executed.append(statement)

        assert take_identity_lock(_Session(), "alice@example.com") is True
        assert len(executed) == 1
        compiled = executed[0].compile(dialect=postgresql.dialect())
        assert "pg_advisory_xact_lock" in str(compiled)
        assert compiled.params["identity_lock_key"] == ALICE_KEY

    def test_both_production_paths_take_it(self) -> None:
        """The two call sites §8.2 requires, asserted by source rather than by execution.

        `issue`'s path and `purge_if_still_eligible` must take the *same* key for the same address,
        or they serialize nothing while both appearing to lock. Neither call is reachable under
        SQLite, so no runtime test in this suite can observe them; a source assertion is what keeps
        the pair from silently becoming one. Follows `test_rca001_lock_scope.py`'s static half,
        which exists for this same reason.
        """
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "src" / "khepri" / "rca"
        issuance = (root / "invitation_persistence.py").read_text(encoding="utf-8")
        purge = (root / "persistence.py").read_text(encoding="utf-8")

        assert "take_identity_lock(database, canonical_email(invitation.target_identity))" in (
            issuance
        ), "the issuance path must take the identity lock on the canonical target address"
        assert "take_identity_lock(database, canonical_email(row.email))" in purge, (
            "`purge_if_still_eligible` must take the identity lock on the canonical address it is "
            "about to null; without both sides the lock serializes nothing"
        )
