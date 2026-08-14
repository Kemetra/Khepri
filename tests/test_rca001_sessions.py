"""R3-02: the commercial authentication session domain and its state vocabulary (`#150`, `R3`).

Domain types only. No persistence, no service, no HTTP — `R3-03` onward add those.

Two owner decisions from the `R3-01` design note §9 are settled and encoded here:

1. **The session identifier is stored as a hash**, never raw. `KHEPRI-DEC-015` §5 calls session
   identifiers bearer material under "no purpose, no retention", and every other RCA secret
   (`FR-002` credentials, `FR-016` invitations) is already hash-only. A database disclosure must not
   hand over live sessions.
2. **A single absolute expiry, no sliding renewal.** `FR-008` requires disablement to take effect
   without waiting for expiry, so renewal would make "when does this session end" a moving target
   while adding nothing the live checks do not already provide.
"""

from __future__ import annotations

import textwrap
from datetime import UTC, datetime, timedelta

import pytest

from khepri.rca.sessions import Session, StoredSession, hash_session_id

NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)
ACCOUNT = "acc_actor"
ORGANIZATION = "org_acme"


class TestTheIdentifierIsNeverStoredRaw:
    def test_issuing_a_session_returns_a_token_the_record_does_not_contain(self) -> None:
        """The raw token goes to the cookie; only its hash is retained.

        This is owner decision 1. A record that carried the raw token would make a database
        disclosure equivalent to handing over every live session.
        """
        issued = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12))

        assert issued.token, "a raw token is returned to the caller"
        assert issued.token not in repr(issued.session), (
            "the raw token must not be recoverable from the stored record"
        )
        assert issued.session.session_id_hash != issued.token

    def test_the_same_token_always_hashes_to_the_same_value(self) -> None:
        """Resolution depends on it: `R3-04` looks a session up by hashing the presented cookie."""
        issued = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12))

        assert hash_session_id(issued.token) == issued.session.session_id_hash

    def test_two_sessions_never_share_an_identifier(self) -> None:
        tokens = {
            Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12)).token for _ in range(50)
        }

        assert len(tokens) == 50

    def test_the_token_carries_the_commercial_prefix(self) -> None:
        """`R3-01` §2.1: `RRA` uses `ses_`, and its `own_` values are already byte-identical to
        RCA's. A distinct prefix keeps the two legible in evidence."""
        issued = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12))

        assert issued.token.startswith("cse_")
        assert not issued.token.startswith("ses_"), "must not collide with RRA beta sessions"


class TestTheStateVocabulary:
    """Exactly three states, derived and never stored as a flag: live, expired, revoked."""

    def test_a_fresh_session_is_live(self) -> None:
        session = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12)).session

        assert session.is_live_at(NOW)
        assert not session.is_expired_at(NOW)
        assert not session.is_revoked

    def test_a_session_expires_at_its_absolute_instant(self) -> None:
        """Owner decision 2: one absolute expiry, no sliding renewal."""
        session = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12)).session
        expiry = NOW + timedelta(hours=12)

        assert session.is_live_at(expiry - timedelta(seconds=1))
        assert session.is_expired_at(expiry), "the expiry instant itself is expired"
        assert not session.is_live_at(expiry)

    def test_activity_does_not_extend_the_horizon(self) -> None:
        """No sliding renewal. There is no operation that moves `expires_at`, so this asserts the
        absence of one rather than the behaviour of one."""
        session = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12)).session

        assert not hasattr(session, "touch")
        assert not hasattr(session, "renew")
        assert not hasattr(session, "extend")

    def test_a_revoked_session_is_not_live_even_before_expiry(self) -> None:
        """`FR-008`: revocation must not wait for expiry."""
        session = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12)).session

        revoked = session.revoked(now=NOW + timedelta(minutes=1))

        assert revoked.is_revoked
        assert not revoked.is_live_at(NOW + timedelta(minutes=2))
        assert not revoked.is_expired_at(NOW + timedelta(minutes=2)), (
            "revoked and expired are distinct states, not one flag"
        )

    def test_revoking_twice_is_refused(self) -> None:
        """A second revocation would move `revoked_at`, misdating when authority actually ended."""
        session = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12)).session
        revoked = session.revoked(now=NOW + timedelta(minutes=1))

        with pytest.raises(ValueError):
            revoked.revoked(now=NOW + timedelta(minutes=5))

    def test_revocation_returns_a_new_record(self) -> None:
        """Immutability: the original is unchanged, following every other RCA record."""
        session = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12)).session

        revoked = session.revoked(now=NOW + timedelta(minutes=1))

        assert session.revoked_at is None, "the original record is untouched"
        assert revoked.revoked_at == NOW + timedelta(minutes=1)
        assert revoked is not session


class TestTheActiveOrganization:
    """`FR-027`: at most one at a time. `FR-028`: none is a valid state."""

    def test_a_new_session_has_no_active_organization(self) -> None:
        """`FR-028` requires an account with no membership to authenticate. Issuing cannot take an
        organization, so an unauthorized one cannot be written down at issuance."""
        session = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12)).session

        assert session.active_organization_id is None

    def test_switching_sets_exactly_one_organization(self) -> None:
        session = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12)).session

        switched = session.switched_to(ORGANIZATION)

        assert switched.active_organization_id == ORGANIZATION
        assert session.active_organization_id is None, "the original is untouched"

    def test_switching_replaces_rather_than_accumulates(self) -> None:
        """One nullable field cannot hold two organizations — `FR-027` is structural, not
        validated."""
        session = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12)).session

        switched = session.switched_to(ORGANIZATION).switched_to("org_other")

        assert switched.active_organization_id == "org_other"

    def test_switching_carries_no_membership_authority(self) -> None:
        """**`switched_to` does not check membership, deliberately.**

        `FR-029` requires a switch to succeed "only into an organization in which the actor holds a
        current membership" — and that check must read live store state, which a domain record
        cannot do. If this method validated membership it would need a store, and the check would
        then live in two places once `R3-04` also performs it. The service owns the check; the
        record owns the state. Asserted so a later slice does not "helpfully" add validation here.

        **Judged on the AST, not on the text.** A first version of this test grepped the source for
        "membership" and failed against correct code, because the docstring *explaining* the absence
        contains the word. Text cannot tell a subject from a docstring — the same defect the `R2-07`
        event audit was rewritten to fix. What matters is whether the method *calls* anything or
        touches collaborator state, so that is what is inspected.
        """
        import ast
        import inspect

        tree = ast.parse(textwrap.dedent(inspect.getsource(Session.switched_to)))
        called = {ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
        attributes = {
            ast.unparse(node) for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }

        assert called <= {"through_door", "Session", "ValueError"}, (
            f"switched_to must not call a collaborator; it calls {called}"
        )
        assert all(name.startswith("self.") for name in attributes), (
            f"switched_to must read only its own fields; it reads {sorted(attributes)}"
        )

    def test_switching_a_revoked_session_is_refused(self) -> None:
        session = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12)).session
        revoked = session.revoked(now=NOW + timedelta(minutes=1))

        with pytest.raises(ValueError):
            revoked.switched_to(ORGANIZATION)

    def test_clearing_the_active_organization_is_possible(self) -> None:
        """`FR-030`: a session whose active-organization membership was revoked must cease to
        authorize there. Clearing the pointer is how `R3-04` expresses that without ending the
        session, which `FR-030` explicitly requires."""
        session = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12)).session
        switched = session.switched_to(ORGANIZATION)

        cleared = switched.switched_to(None)

        assert cleared.active_organization_id is None
        assert cleared.is_live_at(NOW), "the session survives losing its active organization"


class TestNoAuthorityIsCached:
    """The load-bearing absence. `FR-030` and `FR-008` are unsatisfiable if any of these is
    stored."""

    @pytest.mark.parametrize(
        "forbidden",
        ["role", "owner_id", "can_act", "is_owner", "permissions", "membership", "email"],
    )
    def test_the_record_has_no_authority_field(self, forbidden: str) -> None:
        """Any of these cached goes stale exactly when it matters — at disablement or revocation."""
        session = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12)).session

        assert not hasattr(session, forbidden)
        assert forbidden not in Session.__dataclass_fields__

    def test_the_field_set_is_exactly_what_the_design_specifies(self) -> None:
        """`R3-01` §3 fixes the shape. A field added without updating that design note fails here,
        which is the point: the row is where authority leaks in if anyone widens it casually."""
        assert set(Session.__dataclass_fields__) == {
            "session_id_hash",
            "account_id",
            "active_organization_id",
            "created_at",
            "expires_at",
            "revoked_at",
        }

    def test_no_retail_content_can_be_attached(self) -> None:
        """`FR-003` states it directly. Sealed records refuse attribute assignment outright."""
        session = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12)).session

        with pytest.raises(Exception):  # noqa: B017, PT011 -- FrozenInstanceError or AttributeError
            session.prescription_count = 5  # type: ignore[attr-defined]


class TestTheRecordIsSealed:
    def test_the_constructor_is_not_reachable_without_a_door(self) -> None:
        """`records.py`'s two-door rule: construction goes through `issue` or `_from_storage`."""
        with pytest.raises(Exception):  # noqa: B017, PT011 -- the seal's own refusal
            Session(
                session_id_hash="deadbeef",
                account_id=ACCOUNT,
                active_organization_id=None,
                created_at=NOW,
                expires_at=NOW + timedelta(hours=1),
                revoked_at=None,
            )

    def test_dataclasses_replace_is_refused(self) -> None:
        """The seal exists so state changes are methods, not field substitutions."""
        import dataclasses

        session = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12)).session

        with pytest.raises(Exception):  # noqa: B017, PT011 -- the seal's own refusal
            dataclasses.replace(session, account_id="acc_someone_else")


class TestRehydrationFromStorage:
    """`R3-03` needs a door that reconstructs a stored row without re-minting anything."""

    def test_a_stored_row_round_trips_unchanged(self) -> None:
        original = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12)).session

        rehydrated = Session._from_storage(
            StoredSession(
                session_id_hash=original.session_id_hash,
                account_id=original.account_id,
                active_organization_id=original.active_organization_id,
                created_at=original.created_at,
                expires_at=original.expires_at,
                revoked_at=original.revoked_at,
            )
        )

        assert rehydrated == original

    def test_rehydration_does_not_mint_a_new_identifier(self) -> None:
        """A door that generated a fresh hash would silently orphan every stored session."""
        rehydrated = Session._from_storage(
            StoredSession(
                session_id_hash="a" * 64,
                account_id=ACCOUNT,
                active_organization_id=ORGANIZATION,
                created_at=NOW,
                expires_at=NOW + timedelta(hours=12),
                revoked_at=None,
            )
        )

        assert rehydrated.session_id_hash == "a" * 64

    def test_a_revoked_row_rehydrates_as_revoked(self) -> None:
        revoked_at = NOW + timedelta(minutes=5)

        rehydrated = Session._from_storage(
            StoredSession(
                session_id_hash="b" * 64,
                account_id=ACCOUNT,
                active_organization_id=None,
                created_at=NOW,
                expires_at=NOW + timedelta(hours=12),
                revoked_at=revoked_at,
            )
        )

        assert rehydrated.is_revoked
        assert not rehydrated.is_live_at(NOW + timedelta(minutes=6))


class TestNoCollisionWithRraBetaSessions:
    """`R3-01` §2.1 records a live ambiguity: `rra/sessions.py` and `rca/organizations.py` already
    mint byte-identical `own_` values distinguishable only by which table holds them. R3 must not
    reproduce that one layer up."""

    def test_the_stored_hash_is_not_mistakable_for_an_rra_identifier(self) -> None:
        """The hash is 64 hex characters and carries no prefix at all, so it cannot be confused
        with `ses_` or `own_` material."""
        session = Session.issue(ACCOUNT, now=NOW, lifetime=timedelta(hours=12)).session

        assert len(session.session_id_hash) == 64
        assert not session.session_id_hash.startswith(("ses_", "own_", "cse_"))
        assert all(character in "0123456789abcdef" for character in session.session_id_hash)

    def test_nothing_infers_provenance_from_an_identifier_shape(self) -> None:
        """`R3-01` §2.1: "Nothing may infer provenance from an `owner_id` string." A validator that
        accepted "looks like an owner id" would accept either kind.

        **Judged on string literals in the AST, not on the file text** — the module docstring and
        `SESSION_ID_PREFIX`'s comment both discuss `own_` and `ses_` precisely to explain why the
        prefix is distinct, and a text search cannot tell that prose from a comparison. What would
        be wrong is a *literal* the code compares against.
        """
        import ast
        import inspect

        from khepri.rca import sessions

        tree = ast.parse(inspect.getsource(sessions))
        docstrings = {
            node.value.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
        }
        literals = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value not in docstrings
        }

        assert not any(literal.startswith(("own_", "ses_")) for literal in literals), (
            f"no literal may encode an RRA identifier shape; found {sorted(literals)}"
        )
