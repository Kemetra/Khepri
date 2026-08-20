"""The commercial bridge from an authorized RCA actor to an RRA analysis session (`R7-07`).

**Governing authority.** `KHEPRI-DEC-021`, `active` in `governance/registry.yaml`, which supersedes
`KHEPRI-DEC-020` (whose §3 withheld exactly this code) and `KHEPRI-DEC-019`. Its §2 authorizes four
parts "and no more": the entry point, its persistence, the resume lookup, and the bridge. This file
is the evidence for all four.

**The one-sentence contract**, from `KHEPRI-DEC-019` §1 carried forward unchanged by §1 of this
record: *"The organization's scope is the analysis scope. `RRA` never learns whose it is."*

## What each part is, and the defect it exists to prevent

**The entry point** (`open_commercial_session`) accepts an already-resolved opaque `owner_id` and
mints its own `session_id`. Two asymmetries with `redeem` are deliberate and both are asserted
below:

- It **accepts** an `owner_id` rather than minting one. `redeem` mints `own_...` per invitation
  because a beta participant has no organization. A second minting site is how `FR-035`'s stability
  breaks -- `allocate_owner_id` in `khepri.rca` is the single definition -- so `R7-01` §4 lists
  "mint an `owner_id` of its own" among the things the bridge must never do.
- It performs **no authorization**. `KHEPRI-DEC-019` §2's admitted shape gives it nothing that
  identifies a caller, so there is nothing it *could* authorize. Authorization happens in the
  bridge, one layer up, through `resolve_scope`. A function that took an `account_id` "to check"
  would be a second authorization site, and two sites is how they diverge.

**The resume lookup** is keyed `(owner_id, session_id)` -- exactly `uq_session_owner_scope`. §2
settles this because `owner_id` alone identifies a *set* after `20260817_0017` removed the single
-session cardinality, so a conforming implementation "would fail on multiple rows or pick an
arbitrary or stale one, and the bridge would resume the wrong analysis". It **fails closed**: a
`session_id` belonging to a different `owner_id` returns nothing rather than that session, and the
refusal is indistinguishable from "no such session" (`FR-023`, `FR-025`).

**The bridge** lives in `khepri.runtime`, per §3, and is the only place that knows both packages.

## Why these tests can fail

Each assertion below names the production change that breaks it. The four that carry the security
properties are, stated once so a reader can check them against the code rather than trust this
docstring:

1. Removing `owner_id` from the resume `WHERE` clause -> a foreign session is returned
   (`test_a_session_under_another_owner_is_not_found`, and its store-level twin).
2. Having the entry point mint its own `owner_id` -> the organization's scope is no longer the
   analysis scope (`test_the_entry_point_uses_the_owner_id_it_is_given`).
3. Dropping the `resolve_scope` call from the bridge -> a non-member reaches RRA
   (`TestTheBridgeAuthorizesBeforeEnteringRra`, four cases).
4. Adding a cross-package import -> the boundary collapses (`TestThePackageBoundaryHolds`).

**What this file does not claim.** Live re-authorization on *resume* is `R7-03`'s subject, not this
slice's; the bridge re-resolves on every call and that is asserted here, but the endpoint-level
evidence `FR-030` wants is `R7-03`'s. No endpoint exists yet -- that is `R7-05`.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rca.accounts import Account
from khepri.rca.errors import ScopeAccessDenied
from khepri.rca.isolation import IsolationService
from khepri.rca.organizations import OrganizationService
from khepri.rra.persistence import Base, SqlSessionStore
from khepri.rra.sessions import BetaSession, SessionStore, open_commercial_session
from khepri.runtime.bridge import CommercialBridge
from tests.rca_fakes import MemoryAccountStore, MemoryOrganizationStore

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
OWNER = "own_organization_scope"
OTHER_OWNER = "own_another_organization"
MEMBER = "acc_member"
OUTSIDER = "acc_outsider"
DISABLED = "acc_disabled"


def _rca(*account_ids: str, disabled: tuple[str, ...] = ()):
    """Real `IsolationService` over the in-memory stores, following `test_rca001_isolation.py`.

    `Account`, `Membership` and `IsolationScope` are `Sealed`, so tests build them through the
    services' own doors rather than by construction -- which is also why the bridge's authorization
    is exercised against the real `resolve_scope` instead of a stub of it.
    """
    accounts = MemoryAccountStore()
    store = MemoryOrganizationStore(accounts)
    for account_id in (*account_ids, *disabled):
        accounts.accounts[account_id] = Account._from_storage(  # noqa: SLF001 - the suite's pattern
            account_id=account_id,
            email=f"{account_id}@example.test",
            verifier=None,
            disabled_at=NOW if account_id in disabled else None,
        )
    return store, OrganizationService(store), IsolationService(store, accounts)


@pytest.fixture
def factory():
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def store(factory) -> SqlSessionStore:
    return SqlSessionStore(factory)


class TestTheEntryPointIsAdditiveAndUnprivileged:
    """`KHEPRI-DEC-021` §2's first part: the shape `KHEPRI-DEC-019` §2 admitted."""

    def test_it_opens_a_session_for_a_resolved_scope(self, store: SqlSessionStore) -> None:
        session = open_commercial_session(store, owner_id=OWNER, now=NOW)

        assert session.owner_id == OWNER
        assert session.session_id.startswith("ses_")
        assert session.created_at == NOW

    def test_the_entry_point_uses_the_owner_id_it_is_given(self, store: SqlSessionStore) -> None:
        """It must not mint one. `R7-01` §4 forbids a second `owner_id` minting site.

        Fails if the entry point generates `own_...` the way `redeem` does: `allocate_owner_id` in
        `khepri.rca` is the single definition, and a second one breaks `FR-035`'s promise that one
        organization always resolves to the same scope.
        """
        session = open_commercial_session(store, owner_id=OWNER, now=NOW)

        assert session.owner_id == OWNER, (
            "the entry point minted or altered the scope; the organization's scope must be the "
            "analysis scope verbatim"
        )

    def test_each_call_mints_a_distinct_session(self, store: SqlSessionStore) -> None:
        """One scope holds many analyses -- what `20260817_0017` enabled.

        `session_id` is RRA's to mint and is per-analysis, so two calls for one organization are two
        sessions rather than a conflict. Fails if the entry point reuses an id or derives it from
        `owner_id`.
        """
        first = open_commercial_session(store, owner_id=OWNER, now=NOW)
        second = open_commercial_session(store, owner_id=OWNER, now=NOW)

        assert first.session_id != second.session_id

    def test_it_persists_without_an_invitation(self, store: SqlSessionStore) -> None:
        """The gap `KHEPRI-DEC-021`'s Context names: `BetaSessionRow` had one write site.

        Before this slice the only insert lived inside `redeem_invitation`, behind the invitation
        guard, so the admitted entry point "had nowhere to persist". Fails if the new store method
        does not actually write a row.
        """
        session = open_commercial_session(store, owner_id=OWNER, now=NOW)

        assert store.get_session(session.session_id) is not None

    def test_it_accepts_nothing_that_identifies_a_caller(self) -> None:
        """§2: "accepting nothing else that identifies a caller, and performing no authorization".

        Asserted on the signature because that is where the property lives: a parameter is how an
        `account_id` or `organization_id` would arrive, and `FR-032`/`FR-033` forbid either crossing
        into RRA. Fails the moment someone adds one.
        """
        import inspect

        parameters = set(inspect.signature(open_commercial_session).parameters)

        assert parameters == {"store", "owner_id", "now"}, (
            f"the entry point's parameters are {sorted(parameters)}; only an opaque owner_id may "
            "cross into RRA -- no account, organization, name, slug, or email (FR-032, FR-033)"
        )


class TestTheResumeLookupIsScopedToTheOwner:
    """`KHEPRI-DEC-021` §2's third part, and the review finding on `#216` that produced it."""

    def test_it_finds_a_session_for_its_own_owner(self, store: SqlSessionStore) -> None:
        opened = open_commercial_session(store, owner_id=OWNER, now=NOW)

        resumed = store.get_session_for_owner(OWNER, opened.session_id)

        assert resumed is not None
        assert resumed.session_id == opened.session_id

    def test_a_session_under_another_owner_is_not_found(self, store: SqlSessionStore) -> None:
        """Fails closed. The security assertion of the resume path.

        Fails if `owner_id` is dropped from the `WHERE` clause -- the mutant that makes the lookup
        `session_id`-only and hands one organization another's analysis. This is `FR-023`: the
        caller supplies an identifier, and the scope it may act under comes from `resolve_scope`
        rather than from the identifier.
        """
        opened = open_commercial_session(store, owner_id=OWNER, now=NOW)

        assert store.get_session_for_owner(OTHER_OWNER, opened.session_id) is None

    def test_an_unknown_session_is_not_found(self, store: SqlSessionStore) -> None:
        assert store.get_session_for_owner(OWNER, "ses_nonexistent") is None

    def test_a_foreign_session_and_an_absent_one_are_indistinguishable(
        self, store: SqlSessionStore
    ) -> None:
        """`FR-025`/`FR-004` uniform refusal, asserted rather than assumed.

        A caller able to tell "exists but not yours" from "does not exist" learns that another
        organization holds that identifier. Both must be the same `None`. Fails if either path
        raises, returns a sentinel, or reports a reason.
        """
        opened = open_commercial_session(store, owner_id=OWNER, now=NOW)

        foreign = store.get_session_for_owner(OTHER_OWNER, opened.session_id)
        absent = store.get_session_for_owner(OTHER_OWNER, "ses_nonexistent")

        assert foreign is absent is None

    def test_the_pair_is_the_unique_constraints_own_columns(self, store: SqlSessionStore) -> None:
        """§4: no new index is required, because the lookup *is* `uq_session_owner_scope`.

        Asserted so a future change that adds a differently-keyed lookup has to confront this.
        """
        constraint = next(
            c
            for c in Base.metadata.tables["rra_beta_sessions"].constraints
            if getattr(c, "name", None) == "uq_session_owner_scope"
        )

        assert [column.name for column in constraint.columns] == ["owner_id", "session_id"]


class TestTheBridgeAuthorizesBeforeEnteringRra:
    """`KHEPRI-DEC-021` §2's fourth part and §3's location. The adversarial cases.

    Every case asserts the *effect* -- that no RRA session row exists -- rather than only that an
    exception was raised. A gate that raises *after* writing has still written, and this repo has
    recorded that a DENY test asserting only the exception proves nothing about the state.
    """

    def test_a_member_opens_a_session_for_their_organizations_scope(
        self, store: SqlSessionStore
    ) -> None:
        organizations_store, organizations, isolation = _rca(MEMBER)
        organization = organizations.create_organization("Acme", MEMBER, now=NOW)
        bridge = CommercialBridge(isolation=isolation, store=store)

        session = bridge.open(
            account_id=MEMBER, organization_id=organization.organization_id, now=NOW
        )

        scope = organizations_store.get_scope(organization.organization_id)
        assert scope is not None
        assert session.owner_id == scope.owner_id
        assert store.get_session(session.session_id) is not None

    def test_a_non_member_is_refused_and_no_session_is_created(
        self, store: SqlSessionStore
    ) -> None:
        """The wrong-account case. Fails if the bridge skips `resolve_scope`."""
        _, organizations, isolation = _rca(MEMBER, OUTSIDER)
        organization = organizations.create_organization("Acme", MEMBER, now=NOW)
        bridge = CommercialBridge(isolation=isolation, store=store)

        with pytest.raises(ScopeAccessDenied):
            bridge.open(
                account_id=OUTSIDER, organization_id=organization.organization_id, now=NOW
            )

        assert _session_count(store) == 0

    def test_a_disabled_account_is_refused(self, store: SqlSessionStore) -> None:
        """`resolve_scope` refuses `can_act is False`; the bridge must not bypass it.

        This is the precondition project memory records as blocking for any consumer of
        `resolve_scope`, and the bridge is a consumer. The disabled account is the organization's
        own owner, so the refusal cannot be attributed to non-membership instead.
        """
        _, organizations, isolation = _rca(disabled=(DISABLED,))
        organization = organizations.create_organization("Acme", DISABLED, now=NOW)
        bridge = CommercialBridge(isolation=isolation, store=store)

        with pytest.raises(ScopeAccessDenied):
            bridge.open(
                account_id=DISABLED, organization_id=organization.organization_id, now=NOW
            )

        assert _session_count(store) == 0

    def test_an_unknown_organization_is_refused(self, store: SqlSessionStore) -> None:
        _, _organizations, isolation = _rca(MEMBER)
        bridge = CommercialBridge(isolation=isolation, store=store)

        with pytest.raises(ScopeAccessDenied):
            bridge.open(account_id=MEMBER, organization_id="org_missing", now=NOW)

        assert _session_count(store) == 0

    def test_an_unknown_account_is_refused(self, store: SqlSessionStore) -> None:
        _, organizations, isolation = _rca(MEMBER)
        organization = organizations.create_organization("Acme", MEMBER, now=NOW)
        bridge = CommercialBridge(isolation=isolation, store=store)

        with pytest.raises(ScopeAccessDenied):
            bridge.open(
                account_id="acc_missing", organization_id=organization.organization_id, now=NOW
            )

        assert _session_count(store) == 0

    def test_every_refusal_carries_the_same_message(self, store: SqlSessionStore) -> None:
        """`FR-025` at the bridge: four causes, one indistinguishable refusal.

        Non-membership, disablement, an absent account and an absent organization must not be
        tellable apart -- a caller who can distinguish them enumerates which accounts and
        organizations exist.
        """
        _, organizations, isolation = _rca(MEMBER, OUTSIDER, disabled=(DISABLED,))
        organization = organizations.create_organization("Acme", MEMBER, now=NOW)
        organization_id = organization.organization_id
        disabled_org = organizations.create_organization("Beta", DISABLED, now=NOW)
        bridge = CommercialBridge(isolation=isolation, store=store)

        messages = set()
        for account_id, target in (
            (OUTSIDER, organization_id),
            (DISABLED, disabled_org.organization_id),
            ("acc_missing", organization_id),
            (OUTSIDER, "org_missing"),
        ):
            with pytest.raises(ScopeAccessDenied) as raised:
                bridge.open(account_id=account_id, organization_id=target, now=NOW)
            messages.add(str(raised.value))

        assert len(messages) == 1, (
            f"four causes produced {len(messages)} distinct messages ({messages}); a caller able "
            "to tell them apart learns which accounts and organizations exist"
        )

    def test_the_bridge_never_passes_an_organization_identifier_to_rra(
        self, store: SqlSessionStore
    ) -> None:
        """`FR-032`/`FR-033`: only the opaque `owner_id` crosses.

        Asserted on the persisted row rather than by reading the bridge, so it holds however the
        bridge is written.
        """
        _, organizations, isolation = _rca(MEMBER)
        organization = organizations.create_organization("Acme", MEMBER, now=NOW)
        bridge = CommercialBridge(isolation=isolation, store=store)

        session = bridge.open(
            account_id=MEMBER, organization_id=organization.organization_id, now=NOW
        )
        stored = store.get_session(session.session_id)

        assert stored is not None
        assert organization.organization_id not in repr(stored), (
            "an organization identifier reached RRA; only the opaque owner_id may cross"
        )
        assert MEMBER not in repr(stored), "an account identifier reached RRA"

    def test_resume_re_resolves_authority_rather_than_trusting_the_session(
        self, store: SqlSessionStore
    ) -> None:
        """A revoked member cannot resume a session they opened while a member.

        `FR-030` requires a membership change to take effect for decisions made after it. The
        endpoint-level evidence belongs to `R7-03`; this asserts the bridge re-resolves on every
        call rather than treating a held `session_id` as authority. Fails if `resume` looks the
        session up before authorizing, or skips authorization because an identifier was supplied.
        """
        organizations_store, organizations, isolation = _rca(MEMBER)
        organization = organizations.create_organization("Acme", MEMBER, now=NOW)
        bridge = CommercialBridge(isolation=isolation, store=store)
        opened = bridge.open(
            account_id=MEMBER, organization_id=organization.organization_id, now=NOW
        )

        del organizations_store.memberships[(organization.organization_id, MEMBER)]

        with pytest.raises(ScopeAccessDenied):
            bridge.resume(
                account_id=MEMBER,
                organization_id=organization.organization_id,
                session_id=opened.session_id,
                now=NOW,
            )

    def test_resume_returns_the_session_for_an_authorized_member(
        self, store: SqlSessionStore
    ) -> None:
        _, organizations, isolation = _rca(MEMBER)
        organization = organizations.create_organization("Acme", MEMBER, now=NOW)
        bridge = CommercialBridge(isolation=isolation, store=store)
        opened = bridge.open(
            account_id=MEMBER, organization_id=organization.organization_id, now=NOW
        )

        resumed = bridge.resume(
            account_id=MEMBER,
            organization_id=organization.organization_id,
            session_id=opened.session_id,
            now=NOW,
        )

        assert resumed is not None
        assert resumed.session_id == opened.session_id

    def test_resume_refuses_a_session_belonging_to_another_organization(
        self, store: SqlSessionStore
    ) -> None:
        """The cross-organization case, end to end through the bridge.

        Two organizations, each with its own owner. One authorized member names the other's
        `session_id`. Fails if the resume lookup is not owner-scoped -- the same mutant the
        store-level test catches, asserted at the layer a caller actually reaches.
        """
        _, organizations, isolation = _rca(MEMBER, OUTSIDER)
        mine = organizations.create_organization("Acme", MEMBER, now=NOW)
        theirs = organizations.create_organization("Beta", OUTSIDER, now=NOW)
        bridge = CommercialBridge(isolation=isolation, store=store)
        my_session = bridge.open(
            account_id=MEMBER, organization_id=mine.organization_id, now=NOW
        )

        stolen = bridge.resume(
            account_id=OUTSIDER,
            organization_id=theirs.organization_id,
            session_id=my_session.session_id,
            now=NOW,
        )

        assert stolen is None, (
            "an authorized member of one organization resumed another organization's analysis by "
            "naming its session_id; the resume lookup must be scoped to the resolved owner_id"
        )

    def test_a_missing_session_and_a_foreign_one_are_indistinguishable_through_the_bridge(
        self, store: SqlSessionStore
    ) -> None:
        """`FR-025` on the resume path: both are the same `None`, not two outcomes."""
        _, organizations, isolation = _rca(MEMBER, OUTSIDER)
        mine = organizations.create_organization("Acme", MEMBER, now=NOW)
        theirs = organizations.create_organization("Beta", OUTSIDER, now=NOW)
        bridge = CommercialBridge(isolation=isolation, store=store)
        my_session = bridge.open(
            account_id=MEMBER, organization_id=mine.organization_id, now=NOW
        )

        foreign = bridge.resume(
            account_id=OUTSIDER,
            organization_id=theirs.organization_id,
            session_id=my_session.session_id,
            now=NOW,
        )
        absent = bridge.resume(
            account_id=OUTSIDER,
            organization_id=theirs.organization_id,
            session_id="ses_nonexistent",
            now=NOW,
        )

        assert foreign is absent is None


class TestThePackageBoundaryHolds:
    """`KHEPRI-DEC-021` §3: "a flat prohibition, not an allowlist".

    Both packages stay ignorant of each other and `khepri.runtime` knows both, which is what a
    composition root is for. §3 chose the stricter of the two readings deliberately, so that it
    "needs no maintenance as the bridge grows".
    """

    def test_khepri_rca_imports_no_khepri_rra_module(self) -> None:
        offenders = _cross_imports("rca", "khepri.rra")

        assert offenders == [], (
            f"{offenders} import khepri.rra; a bridge inside khepri.rca would make every RCA test "
            "transitively depend on RRA (R7-01 §3)"
        )

    def test_khepri_rra_imports_no_khepri_rca_module(self) -> None:
        offenders = _cross_imports("rra", "khepri.rca")

        assert offenders == [], (
            f"{offenders} import khepri.rca; RRA must not depend on commercial identity concepts "
            "(FR-039 keeps it independently testable)"
        )

    def test_the_scan_can_see_the_modules_it_claims_to_check(self) -> None:
        """The emptiness assertion. A scan over zero files passes while proving nothing.

        This repo has recorded that shape twice: a guard scoped so narrowly it self-disarms. Both
        prohibitions above return `[]` on an empty file list, so the population is asserted here.
        """
        for package in ("rca", "rra"):
            modules = list((_source_root() / package).glob("*.py"))
            assert len(modules) > 5, f"khepri.{package} scan found only {len(modules)} modules"

    def test_the_bridge_lives_in_the_packaged_composition_layer(self) -> None:
        """§3: `khepri.local` is excluded from the wheel, so a bridge there is undeployable.

        `pyproject.toml` excludes `src/khepri/local`, and the Dockerfile validates
        `khepri.runtime.*`. A bridge the deployed web role cannot import is not an authorization.
        """
        assert (_source_root() / "runtime" / "bridge.py").exists()
        assert not (_source_root() / "local" / "bridge.py").exists()

    def test_the_bridge_is_the_module_that_knows_both_packages(self) -> None:
        source = (_source_root() / "runtime" / "bridge.py").read_text(encoding="utf-8")

        assert "khepri.rca" in source
        assert "khepri.rra" in source


def _source_root() -> Path:
    return Path(__file__).resolve().parents[1] / "src" / "khepri"


def _cross_imports(package: str, forbidden: str) -> list[str]:
    offenders = []
    for module in sorted((_source_root() / package).rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imported_from = isinstance(node, ast.ImportFrom) and (
                node.module or ""
            ).startswith(forbidden)
            imported_plain = isinstance(node, ast.Import) and any(
                alias.name.startswith(forbidden) for alias in node.names
            )
            if imported_from or imported_plain:
                offenders.append(module.name)
    return sorted(set(offenders))


def _session_count(store: SqlSessionStore) -> int:
    with store._factory() as database:  # noqa: SLF001 - counting rows is the assertion
        return int(database.scalar(sa.text("SELECT count(*) FROM rra_beta_sessions")) or 0)


class TestTheProtocolAndItsDoubleAgree:
    """The fake/protocol parity tripwire this repo requires, applied to `SessionStore`.

    A double whose signature drifts from the Protocol makes every test using it prove something
    about a shape production does not have.
    """

    def test_the_sql_store_implements_every_protocol_method(self, store: SqlSessionStore) -> None:
        """Structural, because `SessionStore` is not `@runtime_checkable` -- and must not become so
        just to let a test use `isinstance`. Compares the method set so a Protocol method the SQL
        store never implemented fails here rather than at runtime in production.
        """
        declared = {
            name
            for name in vars(SessionStore)
            if not name.startswith("_")
        }
        missing = [name for name in declared if not hasattr(store, name)]

        assert declared, "the protocol scan found no methods; it would pass against anything"
        assert missing == [], f"SqlSessionStore does not implement {missing}"

    def test_the_protocol_declares_both_new_methods(self) -> None:
        assert hasattr(SessionStore, "open_commercial_session_row")
        assert hasattr(SessionStore, "get_session_for_owner")

    def test_a_beta_session_still_has_no_commercial_field(self) -> None:
        """`FR-037`: RRA's existing controls stay covered unmodified.

        The entry point adds a write path, not a column. Fails if someone adds a "current session"
        marker -- which §2 refuses because it would reintroduce, one layer up, the cardinality
        `20260817_0017` removed.
        """
        fields = set(BetaSession.__dataclass_fields__)

        assert fields == {
            "owner_id",
            "session_id",
            "created_at",
            "content_expires_at",
            "consent_version",
            "consented_at",
            "deletion_requested_at",
            "content_deleted_at",
        }, f"BetaSession gained or lost a field: {sorted(fields)}"
