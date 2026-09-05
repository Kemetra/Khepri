"""R3-03: the session table, the external-identity link table, and their store.

Two tables in one migration, as `R3-09` §3.3 records: a session table and
`rca_external_identities`. Shipping them together costs one unused table until a provider is
admitted; shipping them apart costs a second migration and re-opens the single-head window `R2` and
`R3` have already serialized around twice.

**What the schema must make unrepresentable**, rather than merely discouraged:

- two active organizations on one session (`FR-027`) — one nullable column cannot hold two;
- an external identity linked to two accounts (`KHEPRI-DEC-018` §7) — a unique constraint, so a
  duplicate link is a write failure rather than an application check someone can forget;
- a session identifier stored raw — the column holds a hash, and `R3-02` returns the raw token only
  from `issue`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.errors import AuthenticationFailed
from khepri.rca.persistence import (
    AccountRow,
    ExternalIdentityRow,
    SessionRow,
    SqlAccountStore,
)
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.sessions import Session, hash_session_id
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    EMAIL,
    NOW,
    OTHER_EMAIL,
    factory_fixture,
)

LIFETIME = timedelta(hours=12)
PROVIDER = "clerk"
SUBJECT = "user_2abcDEF"


def _account(factory: sessionmaker, email: str = EMAIL) -> str:
    return AccountService(SqlAccountStore(factory)).create_account(email, CREDENTIAL).account_id


class TestTheSchema:
    def test_both_tables_exist(self, factory: sessionmaker) -> None:
        """`R3-09` §3.3: `R3-03` carries two tables, not one."""
        tables = set(inspect(factory.kw["bind"]).get_table_names())

        assert "rca_sessions" in tables
        assert "rca_external_identities" in tables

    def test_a_session_holds_no_authority_column(self, factory: sessionmaker) -> None:
        """The schema mirrors `R3-02`'s record. A column here is a place authority goes stale."""
        columns = {
            column["name"] for column in inspect(factory.kw["bind"]).get_columns("rca_sessions")
        }

        assert columns == {
            "session_id_hash",
            "account_id",
            "active_organization_id",
            "created_at",
            "expires_at",
            "revoked_at",
        }

    def test_the_link_table_holds_only_the_link(self, factory: sessionmaker) -> None:
        """`R3-09` §3.2: no email, no provider claim, no provider token."""
        columns = {
            column["name"]
            for column in inspect(factory.kw["bind"]).get_columns("rca_external_identities")
        }

        assert columns == {"provider", "provider_subject", "account_id", "linked_at"}


class TestTheSessionStore:
    def test_a_session_round_trips(self, factory: sessionmaker) -> None:
        account_id = _account(factory)
        store = SqlSessionStore(factory)
        issued = Session.issue(account_id, now=NOW, lifetime=LIFETIME)

        assert store.add_session(issued.session)

        resolved = store.get_session(issued.session.session_id_hash)
        assert resolved is not None
        assert resolved.account_id == account_id
        assert resolved.expires_at == NOW + LIFETIME
        assert resolved.revoked_at is None

    def test_a_session_is_looked_up_by_the_hash_of_the_presented_token(
        self, factory: sessionmaker
    ) -> None:
        """The resolution path: hash the cookie, look up the hash. The raw token is never stored,
        so it can never be the lookup key."""
        account_id = _account(factory)
        store = SqlSessionStore(factory)
        issued = Session.issue(account_id, now=NOW, lifetime=LIFETIME)
        store.add_session(issued.session)

        assert store.get_session(hash_session_id(issued.token)) is not None
        assert store.get_session(issued.token) is None, "the raw token is not a key"

    def test_an_unknown_identifier_resolves_to_nothing(self, factory: sessionmaker) -> None:
        assert SqlSessionStore(factory).get_session("f" * 64) is None

    def test_the_raw_token_never_reaches_the_database(self, factory: sessionmaker) -> None:
        """Owner decision 1, asserted against storage rather than against the record."""
        account_id = _account(factory)
        store = SqlSessionStore(factory)
        issued = Session.issue(account_id, now=NOW, lifetime=LIFETIME)
        store.add_session(issued.session)

        with factory() as database:
            stored = database.scalars(select(SessionRow.session_id_hash)).all()
        assert issued.token not in stored
        assert hash_session_id(issued.token) in stored

    def test_a_session_requires_an_account_that_exists(self, factory: sessionmaker) -> None:
        """`FR-003` resolves exactly one actor. A session naming no account resolves nobody."""
        issued = Session.issue("acc_absent", now=NOW, lifetime=LIFETIME)

        with pytest.raises(IntegrityError):
            SqlSessionStore(factory).add_session(issued.session)

    def test_revocation_is_persisted(self, factory: sessionmaker) -> None:
        account_id = _account(factory)
        store = SqlSessionStore(factory)
        issued = Session.issue(account_id, now=NOW, lifetime=LIFETIME)
        store.add_session(issued.session)

        revoked_at = NOW + timedelta(minutes=5)
        assert store.save_session(issued.session.revoked(now=revoked_at))

        resolved = store.get_session(issued.session.session_id_hash)
        assert resolved is not None
        assert resolved.revoked_at == revoked_at
        assert not resolved.is_live_at(NOW + timedelta(minutes=6))

    def test_the_active_organization_is_persisted(self, factory: sessionmaker) -> None:
        account_id = _account(factory)
        store = SqlSessionStore(factory)
        issued = Session.issue(account_id, now=NOW, lifetime=LIFETIME)
        store.add_session(issued.session)

        assert store.save_session(issued.session.switched_to("org_acme"))

        resolved = store.get_session(issued.session.session_id_hash)
        assert resolved is not None
        assert resolved.active_organization_id == "org_acme"

    def test_timestamps_come_back_timezone_aware(self, factory: sessionmaker) -> None:
        """SQLite drops tzinfo. A naive `expires_at` would compare wrongly against an aware `now`
        and silently mis-decide expiry, which is the whole point of the column."""
        account_id = _account(factory)
        store = SqlSessionStore(factory)
        issued = Session.issue(account_id, now=NOW, lifetime=LIFETIME)
        store.add_session(issued.session)

        resolved = store.get_session(issued.session.session_id_hash)
        assert resolved is not None
        assert resolved.created_at.tzinfo is not None
        assert resolved.expires_at.tzinfo is not None
        assert resolved.expires_at == NOW + LIFETIME


class TestRevokingEverySessionForAnAccount:
    """`FR-007`: completing recovery MUST invalidate **every** pre-existing session for an account.

    This is the requirement that made `R3-09` conclude Khepri must hold its own sessions at all: it
    is unsatisfiable over a bearer token Khepri cannot enumerate.
    """

    def test_every_live_session_for_the_account_is_revoked(self, factory: sessionmaker) -> None:
        account_id = _account(factory)
        store = SqlSessionStore(factory)
        hashes = []
        for _ in range(3):
            issued = Session.issue(account_id, now=NOW, lifetime=LIFETIME)
            store.add_session(issued.session)
            hashes.append(issued.session.session_id_hash)

        assert store.revoke_all_for_account(account_id, now=NOW + timedelta(minutes=1)) == 3

        for digest in hashes:
            resolved = store.get_session(digest)
            assert resolved is not None
            assert resolved.is_revoked

    def test_another_account_is_untouched(self, factory: sessionmaker) -> None:
        """The non-interference half. `FR-012` taught that these fail separately."""
        mine = _account(factory)
        theirs = _account(factory, OTHER_EMAIL)
        store = SqlSessionStore(factory)
        store.add_session(Session.issue(mine, now=NOW, lifetime=LIFETIME).session)
        other = Session.issue(theirs, now=NOW, lifetime=LIFETIME)
        store.add_session(other.session)

        store.revoke_all_for_account(mine, now=NOW + timedelta(minutes=1))

        survivor = store.get_session(other.session.session_id_hash)
        assert survivor is not None
        assert not survivor.is_revoked

    def test_an_already_revoked_session_is_not_re_dated(self, factory: sessionmaker) -> None:
        """`revoked_at` is when authority actually ended. A sweep that re-stamped it would
        misreport that, and `Session.revoked` refuses a second revocation for the same reason."""
        account_id = _account(factory)
        store = SqlSessionStore(factory)
        issued = Session.issue(account_id, now=NOW, lifetime=LIFETIME)
        store.add_session(issued.session)
        first = NOW + timedelta(minutes=1)
        store.save_session(issued.session.revoked(now=first))

        store.revoke_all_for_account(account_id, now=NOW + timedelta(minutes=30))

        resolved = store.get_session(issued.session.session_id_hash)
        assert resolved is not None
        assert resolved.revoked_at == first


class TestTheExternalIdentityLink:
    """`KHEPRI-DEC-018` §7, enforced by the database rather than by an application check."""

    def test_a_link_resolves_to_its_account(self, factory: sessionmaker) -> None:
        account_id = _account(factory)
        store = SqlSessionStore(factory)

        assert store.link_external_identity(PROVIDER, SUBJECT, account_id, now=NOW)

        assert store.account_for_external_identity(PROVIDER, SUBJECT) == account_id

    def test_an_unlinked_subject_resolves_to_nothing(self, factory: sessionmaker) -> None:
        assert SqlSessionStore(factory).account_for_external_identity(PROVIDER, "nobody") is None

    def test_the_same_subject_from_a_different_provider_is_a_different_identity(
        self, factory: sessionmaker
    ) -> None:
        """The key is the pair. Two providers may legitimately mint the same subject string."""
        mine = _account(factory)
        theirs = _account(factory, OTHER_EMAIL)
        store = SqlSessionStore(factory)
        store.link_external_identity(PROVIDER, SUBJECT, mine, now=NOW)

        assert store.link_external_identity("other", SUBJECT, theirs, now=NOW)

        assert store.account_for_external_identity(PROVIDER, SUBJECT) == mine
        assert store.account_for_external_identity("other", SUBJECT) == theirs

    def test_linking_an_already_linked_identity_fails_closed(self, factory: sessionmaker) -> None:
        """`§7`: "A second attempt to link an already-linked external identity is refused."

        Refused rather than re-pointed: re-pointing a link is account takeover.
        """
        mine = _account(factory)
        theirs = _account(factory, OTHER_EMAIL)
        store = SqlSessionStore(factory)
        store.link_external_identity(PROVIDER, SUBJECT, mine, now=NOW)

        assert not store.link_external_identity(PROVIDER, SUBJECT, theirs, now=NOW)

        assert store.account_for_external_identity(PROVIDER, SUBJECT) == mine, (
            "the existing link did not move"
        )

    def test_the_uniqueness_is_a_database_constraint(self, factory: sessionmaker) -> None:
        """Asserted against a direct write, not through the store.

        An application-level check can be bypassed by any caller reaching the row, which is the
        seam `#151` was opened to close. The constraint holds regardless of the caller.
        """
        mine = _account(factory)
        theirs = _account(factory, OTHER_EMAIL)
        store = SqlSessionStore(factory)
        store.link_external_identity(PROVIDER, SUBJECT, mine, now=NOW)

        with pytest.raises(IntegrityError), factory.begin() as database:
            database.add(
                ExternalIdentityRow(
                    provider=PROVIDER,
                    provider_subject=SUBJECT,
                    account_id=theirs,
                    linked_at=NOW,
                )
            )

    def test_one_account_may_hold_several_links(self, factory: sessionmaker) -> None:
        """An account that later adds enterprise SSO beside a password provider needs two links.
        `R3-09` §3 chose a dedicated table over columns on `rca_accounts` for exactly this."""
        account_id = _account(factory)
        store = SqlSessionStore(factory)

        assert store.link_external_identity(PROVIDER, SUBJECT, account_id, now=NOW)
        assert store.link_external_identity("sso", "saml|abc", account_id, now=NOW)

        assert store.account_for_external_identity(PROVIDER, SUBJECT) == account_id
        assert store.account_for_external_identity("sso", "saml|abc") == account_id

    def test_a_link_requires_an_account_that_exists(self, factory: sessionmaker) -> None:
        with pytest.raises(IntegrityError), factory.begin() as database:
            database.add(
                ExternalIdentityRow(
                    provider=PROVIDER,
                    provider_subject=SUBJECT,
                    account_id="acc_absent",
                    linked_at=NOW,
                )
            )

    def test_external_account_and_link_commit_together(self, factory: sessionmaker) -> None:
        account = AccountService(SqlAccountStore(factory)).preprovision_external_account(
            EMAIL, PROVIDER, SUBJECT, now=NOW
        )

        with factory() as database:
            assert database.get(AccountRow, account.account_id) is not None
            link = database.get(ExternalIdentityRow, (PROVIDER, SUBJECT))
            assert link is not None and link.account_id == account.account_id

    def test_duplicate_subject_leaves_no_orphan_account(self, factory: sessionmaker) -> None:
        service = AccountService(SqlAccountStore(factory))
        original = service.preprovision_external_account(EMAIL, PROVIDER, SUBJECT, now=NOW)

        with pytest.raises(AuthenticationFailed):
            service.preprovision_external_account(
                OTHER_EMAIL, PROVIDER, SUBJECT, now=NOW
            )

        with factory() as database:
            accounts = database.scalars(select(AccountRow)).all()
            assert [row.account_id for row in accounts] == [original.account_id]


class TestUnlinkingLeavesBusinessStateIntact:
    """`KHEPRI-DEC-018` §7: the account, its memberships, and its audit events survive."""

    def test_unlinking_removes_only_the_link(self, factory: sessionmaker) -> None:
        account_id = _account(factory)
        store = SqlSessionStore(factory)
        store.link_external_identity(PROVIDER, SUBJECT, account_id, now=NOW)

        assert store.unlink_external_identity(PROVIDER, SUBJECT)

        assert store.account_for_external_identity(PROVIDER, SUBJECT) is None
        assert SqlAccountStore(factory).get_account(account_id) is not None, (
            "the account survives losing its external identity"
        )

    def test_unlinking_an_absent_link_reports_nothing_done(self, factory: sessionmaker) -> None:
        assert not SqlSessionStore(factory).unlink_external_identity(PROVIDER, "nobody")

    def test_the_account_may_be_relinked(self, factory: sessionmaker) -> None:
        """`§7`: "The account becomes unauthenticatable until relinked." So relinking must work,
        and the uniqueness constraint must not have retained the old row."""
        account_id = _account(factory)
        store = SqlSessionStore(factory)
        store.link_external_identity(PROVIDER, SUBJECT, account_id, now=NOW)
        store.unlink_external_identity(PROVIDER, SUBJECT)

        assert store.link_external_identity(PROVIDER, "user_new", account_id, now=NOW)

        assert store.account_for_external_identity(PROVIDER, "user_new") == account_id


class TestTheAccountRowSurvivesEveryHorizon:
    """`R3-09` §3.1's verified finding: a `RESTRICT` FK onto `rca_accounts` can never block a purge,
    because the purge tombstones the row rather than deleting it."""

    def test_a_purged_account_keeps_its_row_and_its_links(self, factory: sessionmaker) -> None:
        from khepri.rca.lifecycle import AccountRetentionSweeper, LifecycleService
        from khepri.rca.persistence import SqlOrganizationStore

        accounts = SqlAccountStore(factory)
        account_id = _account(factory)
        store = SqlSessionStore(factory)
        store.link_external_identity(PROVIDER, SUBJECT, account_id, now=NOW)
        LifecycleService(accounts, SqlOrganizationStore(factory)).disable_account(
            account_id, now=NOW
        )

        purged = AccountRetentionSweeper(accounts).sweep(now=NOW + timedelta(days=760))

        assert purged.purged_accounts == 1
        surviving = accounts.get_account(account_id)
        assert surviving is not None, "the tombstone keeps the row"
        assert surviving.email is None, "identity is gone"
        assert store.account_for_external_identity(PROVIDER, SUBJECT) == account_id, (
            "the FK held: nothing was deleted, so nothing cascaded"
        )


class TestTheMigration:
    def test_the_head_is_the_session_revision(self) -> None:
        """One migration, one head.

        The single-head half is the durable claim and must never be relaxed: two heads mean two
        migrations in flight, which `AGENTS.md` resolves by re-pointing the second's
        `down_revision` rather than by merging them.

        The pinned revision is deliberately *not* generalized away. A head count alone would pass
        for a revision chained onto the wrong parent, so the identifier is updated by each slice
        that adds a migration -- which is what forces that slice to notice it is now the one in
        flight. `R3-03` wrote `20260815_0016` here; `R7-02` (`KHEPRI-DEC-020` §2) added
        `20260817_0017` on top of it, dropping `rra_beta_sessions.UNIQUE (owner_id)` so one
        commercial scope may hold more than one analysis. `R4-03` then added `20260818_0018`
        (`rca_invitations`), and the reframed `R5-05` consequence added `20260821_0019`
        (`rca_recovery_security_events`). The `KHEPRI-DEC-008` portability slice then added
        `20260822_0020`, which retires the `aws:kms` CHECK constraints and the `kms_key_id`
        column on both storage tables. `W1-02` then added `20260904_0021`, the `RCA-005`
        workspace tables. `W1-04` then added `20260905_0022`, the workspace audit event table
        (`FR-125`). `W1-04b` then added `20260905_0023`, the run-to-report link the worker
        settles a run through. `W1-06` then added `20260905_0024`, the provenance record a
        completed run retains. `W1-08` then added `20260905_0025`, the four `RRA-008` family
        versions on that record (`FR-116`). `W1-07a` then added `20260906_0026`, the deletion action
        and the `already_deleted` outcome, and is the head this pin now names.
        """
        import subprocess

        result = subprocess.run(
            ["uv", "run", "alembic", "heads"], capture_output=True, text=True, check=True
        )

        assert result.stdout.count("(head)") == 1, result.stdout
        assert "20260906_0026" in result.stdout


def test_a_session_and_an_rra_beta_session_cannot_be_confused(factory: sessionmaker) -> None:
    """`R3-01` §2.1: RRA already mints `own_` values byte-identical to RCA's, and R3 must not
    reproduce that ambiguity. The stored session key is a bare 64-character hash with no prefix at
    all, so it cannot be mistaken for `ses_` or `own_` material."""
    account_id = _account(factory)
    store = SqlSessionStore(factory)
    issued = Session.issue(account_id, now=NOW, lifetime=LIFETIME)
    store.add_session(issued.session)

    with factory() as database:
        stored = database.scalars(select(SessionRow.session_id_hash)).all()

    assert len(stored) == 1
    assert len(stored[0]) == 64
    assert not stored[0].startswith(("ses_", "own_", "cse_"))
    assert datetime.now(UTC).tzinfo is not None  # sanity: the test clock is aware
