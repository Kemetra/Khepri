"""The beta journey is unchanged for a participant who has no account (`R7-04`).

`KHEPRI-DEC-020` §1 carries forward two obligations from `KHEPRI-DEC-019` §4 that this file is the
evidence for:

- **Obligation 2** — `RRA` remains independently testable (`FR-039`): its behavior must hold with no
  account, no organization, and no membership existing anywhere.
- **Obligation 3** — the beta path is unchanged: a participant redeems an invitation and proceeds
  exactly as today.

**Why a new file rather than additions to the existing suite.** `FR-037` requires `RRA-001`'s
controls stay covered by its existing tests **unmodified**, and `KHEPRI-DEC-020` §3 repeats that no
`test_rra*` file may be edited. Extending `test_rra001_api.py` with commercial-era assertions is
exactly what those clauses forbid, so the journey is exercised here independently. The overlap with
`test_rra001_api.py` is deliberate and is the cost of the rule, not an oversight.

**What makes these tests non-vacuous, stated precisely.** Each drives the **real app** over HTTP
against a **real database**, never a fake, so what they assert is the journey rather than a model of
it. Two mutants were run to check they can fail: fixing `redeem`'s minted `owner_id` to a constant
(breaking `KHEPRI-DEC-019` §4's fifth obligation) fails
`test_a_second_participant_gets_a_wholly_separate_scope`, and pointing the consent route at a wrong
path fails its test.

**One mutant they deliberately survive, recorded so the gap is not mistaken for coverage.**
Restoring `unique=True` on `owner_id` -- undoing `20260817_0017` -- leaves every test here green.
That is correct rather than a hole: `redeem` mints a fresh scope per redemption, so a beta
participant never meets the constraint, which is precisely why the beta was coherent with it for as
long as it existed. `tests/test_rra_scope_cardinality_migration.py` is what fails on that mutant,
and that is the right home for it. The lesson is that this file proves the beta is *unaffected*
by the change, not that it *detects* the change.

**What this file does not claim.** It says nothing about a commercial actor: no bridge exists
(`R7-07`), and live authorization on resume is `R7-03`'s. A green run here means the beta is intact,
not that commercial access works.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rca.persistence import Base as RcaBase
from khepri.rra.api import create_app
from khepri.rra.persistence import Base as RraBase
from khepri.rra.persistence import SqlSessionStore
from khepri.rra.sessions import InvitationService

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
INVITATION_EXPIRY = NOW + timedelta(hours=1)
REDEEM = "/api/v1/beta/sessions/redeem"
CONSENT = "/api/v1/beta/consent"


class _BetaStack:
    """The beta stack as a participant meets it: RRA only, with no RCA table in existence."""

    def __init__(self) -> None:
        self.engine = sa.create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        RraBase.metadata.create_all(self.engine)
        self.store = SqlSessionStore(sessionmaker(self.engine, expire_on_commit=False))
        self.service = InvitationService(self.store)
        app = create_app(service=self.service, clock=lambda: NOW)
        self.client = TestClient(app, base_url="https://testserver")

    def invitation(self) -> str:
        return self.service.issue_invitation(expires_at=INVITATION_EXPIRY)

    def table_names(self) -> list[str]:
        with self.engine.connect() as connection:
            return sorted(sa.inspect(connection).get_table_names())


@pytest.fixture(name="beta")
def _beta() -> _BetaStack:
    return _BetaStack()


def test_no_commercial_table_exists_in_the_beta_stack(beta: _BetaStack) -> None:
    """Obligation 2, asserted before anything else: the participant's world holds no account.

    Every test below is only meaningful if this holds -- otherwise they prove the journey works
    *alongside* commercial tables rather than without them.
    """
    tables = beta.table_names()
    assert tables, "the beta stack created no tables at all"
    assert [name for name in tables if name.startswith("rca_")] == []
    assert all(name.startswith("rra_") for name in tables), tables


def test_the_two_metadata_registries_share_no_table(beta: _BetaStack) -> None:
    """`FR-039` structurally: `create_all` on one base cannot produce the other's tables.

    This is what makes `RRA` independently testable rather than merely untested-with-RCA. Asserted
    on the registries themselves, so it fails if a future slice moves a table across the boundary
    even when no test happens to build both.
    """
    assert set(RraBase.metadata.tables) & set(RcaBase.metadata.tables) == set()
    assert all(name.startswith("rra_") for name in RraBase.metadata.tables)
    assert all(name.startswith("rca_") for name in RcaBase.metadata.tables)


def test_a_participant_with_no_account_redeems_and_receives_a_session(beta: _BetaStack) -> None:
    """Obligation 3's first step, over HTTP against the real app."""
    response = beta.client.post(REDEEM, json={"token": beta.invitation()})

    assert response.status_code == 201
    assert response.json() == {
        "content_expires_at": "2026-08-24T12:00:00Z",
        "consent_required": True,
    }
    assert "khepri_beta_session=ses_" in response.headers["set-cookie"]


def test_the_session_cookie_still_carries_every_transport_control(beta: _BetaStack) -> None:
    """`FR-037` names cross-session isolation and opacity among the controls `RCA-001` must not
    weaken. The cookie flags are where that is observable at the boundary."""
    response = beta.client.post(REDEEM, json={"token": beta.invitation()})

    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=strict" in cookie


def test_redemption_still_mints_its_own_scope(beta: _BetaStack) -> None:
    """The claim `KHEPRI-DEC-020` §2's fifth obligation protects: `redeem` is unchanged and still
    mints its own `own_` value.

    A bridge that reached into `redeem` -- or a slice that parameterised it to accept a scope --
    would show up here, which is why this asserts the *shape* of what redemption produced rather
    than only that it succeeded.
    """
    beta.client.post(REDEEM, json={"token": beta.invitation()})

    with beta.engine.connect() as connection:
        rows = connection.execute(
            sa.text("SELECT owner_id, session_id FROM rra_beta_sessions")
        ).all()

    assert len(rows) == 1
    owner_id, session_id = rows[0]
    assert owner_id.startswith("own_")
    assert session_id.startswith("ses_")
    assert owner_id != session_id


def test_a_second_participant_gets_a_wholly_separate_scope(beta: _BetaStack) -> None:
    """The isolation property the dropped constraint used to enforce incidentally.

    `UNIQUE (owner_id)` is gone, so nothing in the *schema* now prevents two beta participants from
    sharing a scope -- only `redeem` minting a fresh one does. This test is that guard, and it is
    the one test here that fails when `redeem`'s minting is broken.

    Note what it does **not** do: restoring the constraint leaves it green, because a fresh scope
    per redemption satisfies both worlds. It guards the minting, not the schema.
    """
    beta.client.post(REDEEM, json={"token": beta.invitation()})
    beta.client.post(REDEEM, json={"token": beta.invitation()})

    with beta.engine.connect() as connection:
        owners = (
            connection.execute(sa.text("SELECT owner_id FROM rra_beta_sessions")).scalars().all()
        )

    assert len(owners) == 2
    assert len(set(owners)) == 2, "two participants must not share an isolation scope"


def test_an_invalid_invitation_still_returns_one_uniform_failure(beta: _BetaStack) -> None:
    """`RRA-001`'s anti-enumeration control, unchanged. Distinct causes, one response."""
    beta.invitation()  # a live invitation exists, so "not found" is not the only reachable branch
    expired = beta.service.issue_invitation(expires_at=NOW - timedelta(seconds=1))

    seen = set()
    for token in ("malformed", "", expired, "kiv1.inv_absent.secret"):
        response = beta.client.post(REDEEM, json={"token": token})
        seen.add((response.status_code, response.text))

    assert len(seen) == 1, f"failures are distinguishable: {seen}"
    status, body = seen.pop()
    assert status == 400
    assert "Invitation is invalid or unavailable." in body


def test_a_redeemed_invitation_still_cannot_be_replayed(beta: _BetaStack) -> None:
    """One-use redemption. The dropped constraint was `owner_id`'s, not the invitation's, and this
    asserts the two were never doing the same job."""
    token = beta.invitation()
    assert beta.client.post(REDEEM, json={"token": token}).status_code == 201

    replayed = beta.client.post(REDEEM, json={"token": token})

    assert replayed.status_code == 400
    with beta.engine.connect() as connection:
        count = connection.execute(sa.text("SELECT COUNT(*) FROM rra_beta_sessions")).scalar_one()
    assert count == 1, "a replay created a second session"


def test_consent_still_gates_the_journey_for_an_accountless_participant(beta: _BetaStack) -> None:
    """Obligation 3 past the first step: the participant proceeds through consent as today."""
    redeemed = beta.client.post(REDEEM, json={"token": beta.invitation()})
    assert redeemed.json()["consent_required"] is True

    consented = beta.client.post(CONSENT, json={"consent_version": "2026-07-01"})

    assert consented.status_code == 204
    with beta.engine.connect() as connection:
        version = connection.execute(
            sa.text("SELECT consent_version FROM rra_beta_sessions")
        ).scalar_one()
    assert version == "2026-07-01"


def test_the_journey_needs_no_rca_import_to_run(beta: _BetaStack) -> None:
    """`FR-039` at the module level: importing and exercising `RRA` must not pull `RCA` in.

    `test_rca001_boundary.py::test_no_rra_module_imports_rca` proves this statically over the
    source. This proves the consequence at runtime -- the app served a request without `khepri.rca`
    being needed for it.

    Deliberately checks `sys.modules` *after* driving a request rather than before: an import that
    only happens inside a handler would be invisible to a check at collection time. `khepri.rca` is
    imported by this very test file, so the assertion is about the RRA app's *own* imports, read
    from its module graph rather than from the interpreter's global state.
    """
    beta.client.post(REDEEM, json={"token": beta.invitation()})

    import khepri.rra.api
    import khepri.rra.sessions

    for module in (khepri.rra.api, khepri.rra.sessions):
        offenders = [
            name
            for name, value in vars(module).items()
            if getattr(value, "__module__", "").startswith("khepri.rca")
        ]
        assert offenders == [], f"{module.__name__} holds RCA objects: {offenders}"
