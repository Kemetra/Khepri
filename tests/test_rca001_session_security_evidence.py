"""R3-08: no retail content, role, or stale membership authority is stored in session identity.

**Why a separate suite when `R3-02` … `R3-05` each assert pieces of this.** Those slices test the
behavior they implement; a behavioral test passes as long as the current code path does the right
thing. This suite tests the *shape* — the schema, the record, the module's imports — so that a
future slice cannot add a role column, cache a membership, or reach into `khepri.rra` without a
failure here. The requirement is that these things remain unrepresentable, and representability is
a structural property.

**The three claims, and why each is a real hazard rather than ceremony:**

1. **No cached authority.** `FR-008` and `FR-030` require account status, membership, and role to
   be live per request. Any of them stored on the session goes stale exactly when it matters —
   the moment authority is revoked — and the staleness is invisible, because the type checker and
   every happy-path test still pass.
2. **No retail content.** `FR-036`/`FR-037` keep the commercial boundary one-directional. A
   session carrying a dataset, report, or `owner_id` would put retail material in the
   authentication path, where `FR-040`'s content-free rule does not expect it.
3. **No raw bearer material at rest.** `KHEPRI-DEC-015` §5 calls session identifiers bearer
   material. A database disclosure must not hand over live sessions.

Structural assertions are made against the AST rather than by matching text: `R2`'s findings
record two tests that were green against broken code because text matching stood in for structure.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
from dataclasses import fields
from datetime import timedelta

from sqlalchemy import inspect as sqla_inspect
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.actor_resolution import ActorResolver, ResolvedActor
from khepri.rca.persistence import SessionRow, SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from khepri.rca.sessions import SESSION_ID_PREFIX, Session, hash_session_id
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    EMAIL,
    NOW,
    factory_fixture,
)

LIFETIME = timedelta(hours=12)

#: Every word that would name cached authority on a session. Checked against columns, record
#: fields, and the resolved actor's attributes alike.
AUTHORITY_WORDS = (
    "role",
    "owner",
    "member",
    "membership",
    "permission",
    "can_act",
    "is_owner",
    "enabled",
    "disabled",
    "scope",
    "admin",
    "privilege",
)

#: Retail vocabulary. A session naming any of these has crossed the commercial boundary.
RETAIL_WORDS = ("dataset", "report", "upload", "package", "profile", "artifact", "delivery")

#: Every module on the commercial authentication path. Named once so a module added to the path
#: later is added to every structural check at once rather than to whichever the author recalled.
SESSION_MODULES = ("sessions", "session_service", "session_persistence", "actor_resolution")


def _account(factory: sessionmaker) -> str:
    return AccountService(SqlAccountStore(factory)).create_account(EMAIL, CREDENTIAL).account_id


def _rca_source(module_name: str) -> str:
    return pathlib.Path(f"src/khepri/rca/{module_name}.py").read_text(encoding="utf-8")


def _imported_modules(source: str) -> set[str]:
    """Every module name this source imports, however it spells the import.

    Both `import x` and `from x import y` are collected, so a caller asks one question -- "is this
    module imported" -- instead of branching on the two node types at each call site. That
    branching is what made the first version of these tests a four-level nest.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _called_names(source: str) -> set[str]:
    """Every bare function name called here, e.g. `print(...)` but not `obj.print(...)`."""
    return {
        node.func.id
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def _attribute_calls(source: str) -> set[str]:
    """Every method name called on something, e.g. the `x` of `obj.x(...)`.

    A *call*, never a mention: `session_service` names `assert_account_active` in prose to explain
    why it does not call it, and a substring search counts that explanation as a call site.
    """
    return {
        node.func.attr
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


class TestTheSchemaOffersNoAuthorityColumn:
    def test_no_column_names_authority(self) -> None:
        """`FR-030`. The schema does not offer a column that could go stale.

        Asserted over the mapper rather than the source, so a column added through any mechanism —
        a mixin, a later migration's model change — is caught.
        """
        columns = {column.key.lower() for column in sqla_inspect(SessionRow).columns}
        for column in columns:
            for word in AUTHORITY_WORDS:
                assert word not in column, f"`{column}` names authority on a session row"

    def test_no_column_names_retail_content(self) -> None:
        """`FR-036`, `FR-037`. The commercial boundary is one-directional."""
        columns = {column.key.lower() for column in sqla_inspect(SessionRow).columns}
        for column in columns:
            for word in RETAIL_WORDS:
                assert word not in column, f"`{column}` names retail content on a session row"

    def test_the_columns_are_exactly_the_six_identity_carries(self) -> None:
        """An allowlist, not a denylist.

        The word checks above catch a column named `role`; they do not catch one named `flags` or
        `context` holding the same thing under a vaguer name. Pinning the exact set means any
        addition -- however named -- fails here and has to be argued for explicitly.
        """
        assert {column.key for column in sqla_inspect(SessionRow).columns} == {
            "session_id_hash",
            "account_id",
            "active_organization_id",
            "created_at",
            "expires_at",
            "revoked_at",
        }

    def test_the_active_organization_is_a_pointer_not_a_grant(
        self, factory: sessionmaker
    ) -> None:
        """`active_organization_id` is the one organization-shaped column, and it is not authority.

        It records *where* the actor is working, never *what they may do there* -- `FR-029`
        requires a switch to succeed only into a current membership, and that answer is read live.
        Storing an organization is safe precisely because holding it grants nothing.
        """
        session = Session.issue(_account(factory), now=NOW, lifetime=LIFETIME).session
        switched = session.switched_to("org_whatever")
        assert switched.active_organization_id == "org_whatever"
        # Pointing at an organization confers nothing readable from the record itself.
        assert not any(
            word in attribute.lower()
            for attribute in dir(switched)
            for word in ("role", "permission", "can_")
        )


class TestTheRecordCachesNothing:
    def test_the_session_record_has_exactly_the_stored_fields(self) -> None:
        assert {field.name for field in fields(Session)} == {
            "session_id_hash",
            "account_id",
            "active_organization_id",
            "created_at",
            "expires_at",
            "revoked_at",
        }

    def test_the_resolved_actor_exposes_no_authority(self, factory: sessionmaker) -> None:
        """`R3-05` returns identity and permission-to-act-at-all, never permission-to-act-here."""
        assert {field.name for field in fields(ResolvedActor)} == {"session", "account"}

    def test_resolution_reads_account_state_every_time(self, factory: sessionmaker) -> None:
        """`FR-008`'s live-read requirement, asserted by counting reads rather than by outcome.

        A resolver that cached the account after the first call would pass every behavioral test
        in `R3-05` that resolves only once. Two resolutions must produce two account reads.
        """
        account = _account(factory)
        token = SessionService(SqlSessionStore(factory), lifetime=LIFETIME).create(
            account, now=NOW
        )

        reads = 0
        accounts = SqlAccountStore(factory)
        original = accounts.get_account

        def counting(account_id: str):
            nonlocal reads
            reads += 1
            return original(account_id)

        accounts.get_account = counting  # type: ignore[method-assign]
        from khepri.rca.lifecycle import LifecycleService

        resolver = ActorResolver(
            SessionService(SqlSessionStore(factory), lifetime=LIFETIME),
            LifecycleService(accounts, SqlOrganizationStore(factory)),
        )
        resolver.resolve_actor(token, now=NOW)
        resolver.resolve_actor(token, now=NOW)
        assert reads == 2, "account state was cached across resolutions"


class TestNoBearerMaterialAtRest:
    def test_the_stored_identifier_is_a_hash(self, factory: sessionmaker) -> None:
        """`KHEPRI-DEC-015` §5, `R3-01` §9."""
        sessions = SessionService(SqlSessionStore(factory), lifetime=LIFETIME)
        token = sessions.create(_account(factory), now=NOW)
        with factory() as database:
            stored = [row.session_id_hash for row in database.query(SessionRow).all()]
        assert stored == [hash_session_id(token)]
        assert token not in stored

    def test_no_column_holds_bearer_shaped_material(self, factory: sessionmaker) -> None:
        """No column may hold anything shaped like a raw token -- not merely *this* token.

        **Asserted on shape rather than on the known string, and the difference is not academic.**
        An earlier version searched the row for the token it had just created. Mutation testing
        showed that version passing while a column held a raw-token-shaped value: searching for
        one known needle cannot find a different one. The property required is "no bearer material
        at rest", so the test looks for the prefix that marks bearer material.
        """
        sessions = SessionService(SqlSessionStore(factory), lifetime=LIFETIME)
        token = sessions.create(_account(factory), now=NOW)
        with factory() as database:
            row = database.query(SessionRow).one()
            values = {
                column.key: str(getattr(row, column.key))
                for column in sqla_inspect(SessionRow).columns
            }
        assert token not in values.values()
        for name, value in values.items():
            assert SESSION_ID_PREFIX not in value, f"`{name}` holds bearer-shaped material"


class TestTheCommercialBoundaryHolds:
    def test_no_session_module_imports_rra(self) -> None:
        """`FR-036`. Verified on the syntax tree, not by text: an import inside a function or
        under a conditional is still an import, and a substring search for `khepri.rra` also
        matches the docstrings that discuss RRA as a counter-example."""
        for module_name in SESSION_MODULES:
            imported = _imported_modules(_rca_source(module_name))
            offending = {name for name in imported if name.startswith("khepri.rra")}
            assert not offending, f"{module_name} imports {sorted(offending)}"

    def test_the_session_path_logs_nothing(self) -> None:
        """`FR-040`. A log statement here would echo identifiers no requirement permits.

        **Read from the AST, not by substring.** A text search for `logging` also matches the
        prose in `session_service`'s docstring about *logging the user out*, and a search for
        `print(` would match `pprint(`. Worse in the other direction: text matching cannot tell an
        import from a mention, so it is equally capable of missing a real one behind an alias.
        """
        for module_name in SESSION_MODULES:
            source = _rca_source(module_name)
            assert "logging" not in _imported_modules(source), f"{module_name} imports logging"
            assert "print" not in _called_names(source), f"{module_name} calls print"


class TestTheAbsencesAreLoadBearing:
    def test_the_session_service_still_holds_no_account_store(self) -> None:
        """`R3-04`'s boundary survives `R3-05`.

        The chokepoint was added to `ActorResolver`, not folded into `SessionService`. Keeping
        them separate is what lets a session be resolved for revocation or sweeping without an
        account store in hand -- and it is why `R3-04`'s suite can prove the session half alone.
        """
        source = inspect.getsource(SessionService)
        assert "assert_account_active" not in source
        assert "AccountStore" not in source

    def test_the_chokepoint_has_exactly_the_three_governed_production_callers(self) -> None:
        """One chokepoint, three governed callers. A fourth is a place to forget it.

        `R3-01` §4 names RRA's four-call-site expiry predicate as the counter-example; this is the
        same failure mode applied to the `FR-008` guard. Actor resolution checks every protected
        action; external authentication revalidates immediately before minting a Khepri session;
        provider-owned recovery independently revalidates before recording its Khepri consequence.
        All three are governed boundaries, and no other path may bypass them.

        **Counts calls, not mentions.** `session_service.py` names the chokepoint in its docstring
        to explain why it deliberately does not call it, and `R3-04`'s boundary test asserts that
        absence. A substring search counts that explanation as a call site.
        """
        callers = sorted(
            path.name
            for path in pathlib.Path("src/khepri").rglob("*.py")
            if path.name != "lifecycle.py"
            and "assert_account_active" in _attribute_calls(path.read_text(encoding="utf-8"))
        )
        assert callers == [
            "actor_resolution.py",
            "external_auth_api.py",
            "recovery_security.py",
        ]
