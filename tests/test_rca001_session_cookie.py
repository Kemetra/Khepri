"""R3-06: how a commercial session is carried over HTTP, and what an invalid one earns.

`R3-01` §5 fixes three things this suite asserts rather than trusts:

1. **The name must differ from RRA's**, regardless of path. A browser sends cookies by name and
   path, and a name collision on an overlapping path is silent -- any route under a shared prefix
   would read an RCA cookie as a beta `session_id`.
2. **The refusal literal is RCA's own**, not RRA's `SESSION_UNAVAILABLE`. Sharing it would couple
   two refusal vocabularies that are allowed to diverge later.
3. **The cookie carries the lookup handle and nothing else.** An RCA cookie carrying an
   organization or isolation key would be a weaker posture than the beta system beside it, where
   `owner_id` never crosses the wire.
"""

from __future__ import annotations

from datetime import timedelta

from khepri.rca.session_cookie import (
    SESSION_COOKIE,
    SESSION_COOKIE_PATH,
    SESSION_INVALID,
    clear_session_cookie,
    issue_session_cookie,
)
from khepri.rra.session_cookie import SESSION_COOKIE as RRA_COOKIE
from khepri.rra.session_cookie import SESSION_UNAVAILABLE as RRA_REFUSAL

LIFETIME = timedelta(hours=12)
TOKEN = "cse_a_raw_session_token"


class TestTheNameIsDistinct:
    def test_the_cookie_name_differs_from_rra(self) -> None:
        """`R3-01` §5. A collision would be silent and would cross the commercial boundary."""
        assert SESSION_COOKIE != RRA_COOKIE

    def test_the_refusal_literal_differs_from_rra(self) -> None:
        """Two vocabularies allowed to diverge later must not start as one object."""
        assert SESSION_INVALID is not RRA_REFUSAL

    def test_the_refusal_names_no_cause(self) -> None:
        """`FR-004`, `FR-022`: absent, unknown, expired, revoked, and disabled are one answer."""
        lowered = SESSION_INVALID.lower()
        for cause in ("expired", "revoked", "disabled", "unknown", "missing", "not found"):
            assert cause not in lowered


class TestIssuedAttributes:
    def test_the_cookie_reaches_every_commercial_surface(self) -> None:
        """`R3-01` §5 scopes the cookie to "the commercial surface", which is a role.

        It was `/api/v1/commercial` while the API was the only such surface. `RCA-002` adds a
        second one -- the shell -- and a cookie the shell never receives cannot authenticate a page
        render. The path widens; the *name* stays distinct, which is the property `R3-01` requires
        "regardless of path" and the one that keeps an RCA cookie from being read as a beta
        `session_id`.
        """
        assert SESSION_COOKIE_PATH == "/"
        assert issue_session_cookie(TOKEN, lifetime=LIFETIME)["path"] == SESSION_COOKIE_PATH

    def test_the_cookie_reaches_both_the_api_and_the_shell(self) -> None:
        """The consequence stated as the two paths that must be covered, not as one literal.

        Asserting only the literal would pass if a later change scoped the cookie to `/app` alone
        and silently logged every API caller out.
        """
        for surface in ("/api/v1/commercial/analyses", "/app/en/acme/analyses"):
            assert surface.startswith(SESSION_COOKIE_PATH)

    def test_the_cookie_carries_the_token(self) -> None:
        assert issue_session_cookie(TOKEN, lifetime=LIFETIME)["value"] == TOKEN

    def test_the_cookie_is_http_only(self) -> None:
        """Script-readable session material is the defect this flag exists to prevent."""
        assert issue_session_cookie(TOKEN, lifetime=LIFETIME)["httponly"] is True

    def test_the_cookie_is_secure(self) -> None:
        assert issue_session_cookie(TOKEN, lifetime=LIFETIME)["secure"] is True

    def test_the_cookie_is_same_site_strict(self) -> None:
        """`R3-01` §5 names Strict, not Lax. A commercial action reached cross-site is a
        cross-site request forgery, and Lax admits top-level navigations."""
        assert issue_session_cookie(TOKEN, lifetime=LIFETIME)["samesite"] == "strict"

    def test_max_age_mirrors_the_session_horizon(self) -> None:
        """A cookie outliving its session would leave the browser presenting a dead token; a
        cookie expiring first would log the actor out early. Neither is a security hole on its
        own, and both are avoidable by deriving one from the other."""
        issued = issue_session_cookie(TOKEN, lifetime=LIFETIME)
        assert issued["max_age"] == int(LIFETIME.total_seconds())

    def test_the_cookie_carries_nothing_but_the_token(self) -> None:
        """`R3-01` §5: the lookup handle and nothing else. No organization, no isolation key."""
        issued = issue_session_cookie(TOKEN, lifetime=LIFETIME)
        assert issued["value"] == TOKEN
        assert "own_" not in str(issued)


class TestCleared:
    def test_clearing_empties_the_value(self) -> None:
        assert clear_session_cookie()["value"] == ""

    def test_clearing_expires_immediately(self) -> None:
        assert clear_session_cookie()["max_age"] == 0

    def test_a_cleared_cookie_keeps_every_protective_flag(self) -> None:
        """A logout that drops `Secure` or `HttpOnly` would let the empty cookie be set over
        plaintext or read by script -- a downgrade performed at exactly the moment the actor
        asked for more safety, not less."""
        cleared = clear_session_cookie()
        assert cleared["httponly"] is True
        assert cleared["secure"] is True
        assert cleared["samesite"] == "strict"

    def test_clearing_targets_the_same_name_and_path(self) -> None:
        """A clear on a different path leaves the original cookie in place, and the actor stays
        logged in after asking to log out."""
        issued = issue_session_cookie(TOKEN, lifetime=LIFETIME)
        cleared = clear_session_cookie()
        assert cleared["key"] == issued["key"] == SESSION_COOKIE
        assert cleared["path"] == issued["path"]


class TestNoDomainLeakage:
    def test_the_module_defines_no_second_session_predicate(self) -> None:
        """`R3-01` §4 names RRA as the counter-example: its expiry predicate is repeated at four
        call sites. The cookie module transports a token; deciding whether a session is live is
        `R3-04`'s single predicate and must not be duplicated here."""
        import khepri.rca.session_cookie as module

        source = module.__file__
        assert source is not None
        with open(source, encoding="utf-8") as handle:
            text = handle.read()
        for forbidden in ("is_live_at", "is_expired_at", "revoked_at", "hash_session_id"):
            assert forbidden not in text
