"""`R4-02` -- the invitation domain and its hashed secret.

Scope, following `R3-02`'s: domain types only. Persistence, the `CHECK` constraints, the sweeper,
issuance, revocation, and redemption are `R4-03`...`R4-06`. Nothing here touches a database.

Two tests here exist because of a gap found while reading `R4-01`, not because the design note
listed them; both are marked where they appear.
"""

from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest

from khepri.rca.authorization import AuthorizationContext
from khepri.rca.credentials import KDF_DKLEN, SALT_BYTES, KdfParams, Verifier, hash_credential
from khepri.rca.invitations import (
    INVITATION_ID_PREFIX,
    INVITATION_KDF,
    TOKEN_PREFIX,
    Invitation,
    InvitationLifecycle,
    InvitationOffer,
    InvitationSecret,
    StoredInvitationSecret,
    issue_secret,
    parse_token,
    verify_secret,
)
from khepri.rca.organizations import MEMBER_ROLE, OWNER_ROLE, ROLES

ORG = "org_acme"
ACTOR = "acc_owner"
TARGET = "invitee@example.com"
NOW = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(days=7)


def _offer(role: str = MEMBER_ROLE) -> InvitationOffer:
    return InvitationOffer(
        organization_id=ORG, intended_role=role, target_identity=TARGET, issued_by=ACTOR
    )


def _open(
    *, role: str = MEMBER_ROLE, expires_at: datetime = LATER, issued_at: datetime | None = None
) -> Invitation:
    """An open invitation, or -- with `expires_at` in the past -- one that has since expired.

    `issued_at` defaults to just before `expires_at` rather than to a fixed `NOW`, because the
    creation door requires `expires_at > issued_at`: an expired invitation is one that was validly
    issued and then outlived its horizon, never one minted already expired.
    """
    return Invitation.create(
        _offer(role),
        secret=issue_secret(),
        expires_at=expires_at,
        issued_at=issued_at if issued_at is not None else expires_at - timedelta(days=1),
    )


# --- generation: shape, not values (section 4) ----------------------------------------------


def test_the_secret_and_salt_are_generated_at_the_stated_sizes() -> None:
    """`R4-01` section 4 owes a test on the sizes rather than on the values.

    A CSPRNG secret is not assertable against a known value, so the evidence is shape. Section 4
    fixes `secrets.token_urlsafe(32)` for the secret and `secrets.token_bytes(16)` for the salt;
    the urlsafe encoding is base64 of 32 bytes, so the decoded entropy is what is asserted rather
    than a string length that base64 padding would make an implementation detail.
    """
    secret = issue_secret()

    assert len(secret.verifier.salt) == SALT_BYTES
    assert len(secret.verifier.digest) == KDF_DKLEN
    # token_urlsafe(32) is 32 bytes of entropy rendered as 43 base64 characters.
    assert len(secret.secret) == 43
    assert secret.invitation_id.startswith(INVITATION_ID_PREFIX)


def test_two_successive_issuances_differ_in_every_generated_field() -> None:
    """The other half of section 4's shape evidence: a fixed secret or a fixed salt satisfies
    every length assertion above while destroying the entropy `FR-016` requires."""
    first, second = issue_secret(), issue_secret()

    assert first.secret != second.secret
    assert first.invitation_id != second.invitation_id
    assert first.verifier.salt != second.verifier.salt
    assert first.verifier.digest != second.verifier.digest


def test_the_digest_is_scrypt_over_the_secret_and_its_salt() -> None:
    """The stored verifier is derived, not the secret encoded -- `FR-016`'s "persisted only as a
    strong salted hash". Recomputed independently rather than trusted, so a generator that stored
    `secret.encode()` fails here."""
    secret = issue_secret()

    expected = hash_credential(secret.secret, secret.verifier.salt, INVITATION_KDF)
    assert secret.verifier.digest == expected


def test_the_invitation_verifier_uses_the_rra_work_factor_not_the_credential_default() -> None:
    """Section 4 pins `n=2**14`, matching `rra/sessions.py:108`, deliberately *below*
    `credentials.DEFAULT_KDF`'s `2**15`.

    Asserted because the two constants are one character apart and `Verifier.derive` -- the FR-002
    credential path -- pins the higher one with no parameter. A future edit that routed invitation
    secrets through `Verifier.derive` would silently change the stored work factor of every
    invitation, and the KDF parameters are persisted per row precisely so that cannot happen
    unnoticed.
    """
    assert INVITATION_KDF.n == 2**14
    assert issue_secret().verifier.kdf == INVITATION_KDF


def test_the_secret_is_returned_once_and_is_not_reachable_from_the_record() -> None:
    """Section 4: "The secret is returned once and never stored." The plaintext lives on the
    transient carrier, and the record that will be persisted holds only the verifier."""
    secret = issue_secret()
    invitation = _open()

    assert not any(
        secret.secret == getattr(invitation, field, None) for field in Invitation.__slots__
    )
    assert "secret" not in Invitation.__slots__


def test_a_hand_built_carrier_cannot_create_an_invitation_at_all() -> None:
    """**Found in review on #215, twice.** The first fix checked `verifier.kdf == INVITATION_KDF`,
    which a caller defeats by passing the right parameters with an arbitrary digest --
    `credentials.py:9-13` makes exactly that argument about its own case: "A digest cannot be
    distinguished from an arbitrary 32-byte string by inspection, so shape checking cannot establish
    that a real KDF produced it."

    So the guarantee is provenance, not shape: `InvitationSecret` is sealed, `issue_secret` is its
    only door, and `create` calls `assert_sealed`. A caller cannot assemble one at any work factor,
    with any digest, or with a chosen identifier or secret.
    """
    weak = Verifier._from_storage(
        salt=b"x" * SALT_BYTES,
        digest=b"not-a-real-digest".ljust(KDF_DKLEN, b"0"),
        kdf=KdfParams(n=2, r=1, p=1),
    )

    # The carrier itself is unconstructible outside the door -- this is the load-bearing line.
    with pytest.raises(TypeError):
        InvitationSecret(invitation_id="inv_x", secret="chosen", verifier=weak)


def test_object_new_is_not_claimed_to_be_refused_and_is_covered_elsewhere() -> None:
    """**A test written, run, and deleted -- recorded so it is not written again.**

    It asserted that `create` refuses an `InvitationSecret` built with `object.__new__`. It
    does not, and it cannot: `assert_sealed` compares `type(record)` against the declared set, and
    `object.__new__(InvitationSecret)` produces exactly that type. `records.py` says so directly --
    `object.__new__`, `object.__setattr__` and `through_door` are the three bypasses it names as
    permanently open, because "a guard against `object.__setattr__` is itself removable by
    `object.__setattr__`; this is the language's design, not a gap in this module."

    What separates those three from the four that were fixed is intent: nobody writes
    `object.__new__` while trying to do the right thing. The defense is therefore *static*, and it
    already exists -- `test_rca001_resolver_chokepoint.py` asserts that no module in any production
    package calls `object.__new__` or `object.__setattr__`, repo-wide, and self-tests its scanner.

    This test asserts the boundary rather than the bypass: `assert_sealed` in `create` is what
    refuses a *different* sealed type or a subclass, which is the reachable case.
    """
    # An unsealed stand-in with exactly the right attributes. `assert_sealed` compares the
    # declared type rather than the shape, so this is refused where a duck-typed check would
    # accept it -- and before any attribute is read, which is the ordering that was wrong once.
    class Lookalike:
        invitation_id = "inv_chosen"
        secret = "chosen-by-caller"
        # A *genuine* verifier, so the refusal has to come from the carrier's own type. Written
        # first with `verifier = None`, which `assert_sealed(verifier)` rejected instead -- the
        # test passed while `assert_sealed(secret)` was removable, and only mutating that line
        # exposed it. The mutant is what found this, not the assertion.
        verifier = issue_secret().verifier

    with pytest.raises(TypeError):
        Invitation.create(
            _offer(),
            secret=Lookalike(),  # type: ignore[arg-type]
            expires_at=LATER,
            issued_at=NOW,
        )


@pytest.mark.parametrize("expires_at", [NOW, NOW - timedelta(days=1)])
def test_an_invitation_cannot_expire_at_or_before_its_issuance(expires_at: datetime) -> None:
    """**Found in review on #215.** The design note's section 3 requires
    `CHECK expires_at > issued_at`, following `ck_session_expiry_after_creation`. Without the same
    rule at the door, creation mints an invitation already expired at issuance -- an initial state
    the four-state table cannot express -- which circulates through domain code until persistence
    rejects it. The boundary is `<=` for the same reason `is_expired_at` is."""
    with pytest.raises(ValueError):
        Invitation.create(
            _offer(), secret=issue_secret(), expires_at=expires_at, issued_at=NOW
        )


# --- token format (section 4) ---------------------------------------------------------------


def test_the_token_carries_a_commercial_prefix_distinct_from_the_beta_one() -> None:
    """Section 4: `kci1.<invitation_id>.<secret>`, "so a beta token and a commercial token can
    never be confused at a boundary that accepts both".

    The `inv_` identifier prefix is shared with `rra/sessions.py:78` **as the design spells it**;
    the token prefix is what disambiguates, and RRA reaches `get_invitation` only after its own
    `parse_token` has dispatched on `kiv1`, so no bare-identifier path crosses the boundary.
    """
    secret = issue_secret()

    assert secret.token.startswith(TOKEN_PREFIX + ".")
    assert TOKEN_PREFIX != "kiv1"
    assert parse_token(secret.token) == (secret.invitation_id, secret.secret)


@pytest.mark.parametrize(
    "token",
    [
        "",
        "kci1",
        "kci1.inv_abc",
        "kci1.inv_abc.secret.extra",
        "kiv1.inv_abc.secret",  # a beta token, offered at the commercial boundary
        "kci1..secret",
        "kci1.inv_abc.",
        "kci1.acc_abc.secret",  # right shape, wrong identifier family
    ],
)
def test_a_malformed_token_is_refused(token: str) -> None:
    """Parsing refuses rather than returning a partial result. The uniform-failure discipline and
    the timing half of `FR-017` are `R4-05`'s; what is asserted here is only that a caller cannot
    obtain an identifier from a token that does not carry one."""
    with pytest.raises(ValueError):
        parse_token(token)


def test_verification_compares_against_the_stored_verifier() -> None:
    secret = issue_secret()

    assert verify_secret(secret.secret, secret.verifier)
    assert not verify_secret("not-the-secret", secret.verifier)


def test_verification_of_a_destroyed_verifier_refuses_rather_than_raising() -> None:
    """`None` is the terminal shape of a destroyed verifier (section 3), not a defect. A redeemed
    or revoked invitation must refuse, and refusing is not the same as crashing on the path
    `R4-05` will call."""
    assert not verify_secret("anything", None)


# --- state, discriminated by nullability (section 5) ----------------------------------------


def test_an_open_invitation_is_neither_expired_nor_redeemed_nor_revoked() -> None:
    invitation = _open()

    assert not invitation.is_expired_at(NOW)
    assert invitation.is_open_at(NOW)
    assert invitation.redeemed_at is None
    assert invitation.revoked_at is None


def test_the_expiry_instant_itself_counts_as_expired() -> None:
    """Section 5's correction, fixed explicitly: "open is `expires_at > now`; expired is
    `expires_at <= now`". A `<` boundary fails *open* at exactly one instant, in a state model
    whose whole point is failing closed. Matches `Session.is_expired_at` and RRA's `redeem`."""
    invitation = _open(expires_at=NOW)

    assert invitation.is_expired_at(NOW)
    assert not invitation.is_open_at(NOW)
    assert not invitation.is_expired_at(NOW - timedelta(microseconds=1))


@pytest.mark.parametrize("terminal", ["redeemed", "revoked"])
def test_a_terminal_invitation_is_not_open_even_before_its_horizon(terminal: str) -> None:
    """**Added after a surviving mutant, not from the design note.** Deleting the `revoked_at`
    clause from `is_open_at` -- so a revoked invitation reports itself open -- left all 37 other
    tests green. The state tests above assert the *timestamp* is set after each operation and never
    asked the predicate about the result, so two of its three clauses were unasserted.

    This matters because `is_open_at` is what `R4-05` will gate redemption on: the clause that went
    untested is the one standing between a revoked invitation and a membership.
    """
    invitation = getattr(_open(), terminal)(at=NOW)

    assert not invitation.is_open_at(NOW)
    # Still inside its horizon, so expiry is not what refuses -- the terminal timestamp is.
    assert not invitation.is_expired_at(NOW)


def test_expiry_is_derived_and_stated_once_rather_than_compared_at_call_sites() -> None:
    """Section 5 owes "an `is_expired_at`-shaped predicate on the record rather than an inline
    comparison at each call site, so the boundary is stated once" -- the whole reason the `<`/`<=`
    split was expressible twice. No status column: the four states are read off nullability."""
    assert not hasattr(_open(), "status")
    assert "is_expired_at" in vars(Invitation)


def test_redemption_and_revocation_destroy_the_verifier_in_the_same_operation() -> None:
    """Section 3: the destruction triggers are writes, and "destroyed at the trigger" is about
    bytes -- `KHEPRI-DEC-015` section 5 measures the harm in days of survival. A state change that
    left the verifier in place would be a redeemed invitation whose secret still verifies."""
    invitation = _open()

    redeemed = invitation.redeemed(at=NOW)
    assert redeemed.redeemed_at == NOW
    assert redeemed.verifier is None
    assert not verify_secret("anything", redeemed.verifier)

    revoked = invitation.revoked(at=NOW)
    assert revoked.revoked_at == NOW
    assert revoked.verifier is None


def test_the_expired_verifier_is_destroyable_without_a_state_change() -> None:
    """Section 3: "Expiry is not a write" -- a derived state fires no event -- so destruction on
    first touch after expiry is what bounds an expired verifier's survival on the read path. The
    timestamps are unchanged: expiry has no column, and inventing one would give two fields for
    one fact."""
    expired = _open(expires_at=NOW)

    touched = expired.verifier_destroyed(at=NOW)

    assert touched.verifier is None
    assert touched.redeemed_at is None
    assert touched.revoked_at is None
    assert touched.expires_at == expired.expires_at


def test_destroying_a_live_invitations_verifier_is_refused() -> None:
    """**Found in review on #215.** Destroying the verifier of an unexpired invitation leaves both
    terminal timestamps unset, so `is_open_at` keeps reporting it open while it can never be
    redeemed -- a state the four-state table does not contain. `R4-03`'s sweeper is the caller that
    matters, and one passing the wrong horizon would otherwise brick live invitations silently."""
    live = _open()

    with pytest.raises(ValueError):
        live.verifier_destroyed(at=NOW)

    assert live.is_open_at(NOW)
    assert live.verifier is not None


def test_destroying_an_already_destroyed_verifier_is_accepted_at_any_moment() -> None:
    """The early return applies before the expiry check: a redeemed or revoked invitation has no
    verifier left to destroy, so the sweeper need not care whether it also expired."""
    redeemed = _open().redeemed(at=NOW)

    assert redeemed.verifier_destroyed(at=NOW) is redeemed


@pytest.mark.parametrize("operation", ["redeemed", "revoked"])
def test_a_terminal_transition_is_refused_on_an_expired_invitation(operation: str) -> None:
    """**Found in review on #215.** `_require_open` checked only the two timestamps, so
    `redeemed(at=...)` on an invitation past its horizon produced a redeemed record -- a redemption
    of an expired invitation, expressed in the domain.

    Its docstring had excluded expiry because it "depends on a moment, and these operations take the
    moment of the write rather than a separate clock". Both callers already receive that moment, so
    the reasoning was false. This is not `FR-017`'s refusal, which needs the uniform failure and the
    dummy work on `R4-05`'s service path; it is the narrower claim that the record cannot represent
    a state its own table excludes.
    """
    expired = _open(expires_at=NOW)

    with pytest.raises(ValueError):
        getattr(expired, operation)(at=NOW)


def test_a_state_change_is_refused_once_the_invitation_is_no_longer_open() -> None:
    """At-most-once is enforced in the database by `R4-05`'s conditional update; the domain
    refusing a second redemption is not that guarantee and does not claim to be. It is asserted so
    a caller cannot express the contradiction in memory."""
    redeemed = _open().redeemed(at=NOW)

    with pytest.raises(ValueError):
        redeemed.redeemed(at=NOW)
    with pytest.raises(ValueError):
        redeemed.revoked(at=NOW)


def test_expires_at_is_a_required_parameter_with_no_default_lifetime() -> None:
    """Section 4: "`expires_at` is a parameter, not a constant." `FR-016` requires an explicit
    expiry and does not fix a lifetime; baking one in would put a product decision in the
    domain."""
    parameter = inspect.signature(Invitation.create).parameters["expires_at"]

    assert parameter.default is inspect.Parameter.empty


# --- the role, and the guard that was supposed to catch it ----------------------------------


@pytest.mark.parametrize("role", [*ROLES])
def test_either_declared_role_may_be_invited(role: str) -> None:
    """Both roles are storable, so the refusal below rejects forgery rather than rejecting
    everything -- the same reasoning `test_every_declared_role_survives_a_round_trip` states."""
    assert _open(role=role).intended_role == role


@pytest.mark.parametrize("role", ["", "superadmin", "Owner", "OWNER", "admin", "member "])
def test_an_undeclared_intended_role_is_refused_at_construction(role: str) -> None:
    """**Found while reading `R4-01`, not listed by it.** `R4-02` is the slice where a
    caller-supplied role first enters the codebase: section 3 gives `Invitation` an
    `intended_role` "exactly one of ROLES", and until now no operation took a role from its caller
    at all.

    `tests/test_rca001_guard_evidence.py` records that neither the domain nor
    `rca_membership_events` validates roles, and that what prevented forgery was the *absence of an
    input*. That absence ends here, so the validation arrives with the field. The `CHECK`
    constraint is `R4-03`'s and is not a substitute: a store caller that bypasses `create` is the
    same gap section 4's constraints rest on.
    """
    with pytest.raises(ValueError):
        _open(role=role)


def test_the_role_forgery_guard_can_see_the_invitation_surface() -> None:
    """**The guard self-disarms exactly when it should fire, and this is that finding.**

    `test_no_role_change_operation_accepts_a_role_from_its_caller` scans
    `inspect.getmembers(OrganizationService)`, and its docstring names `R4`'s invitation as "the
    obvious candidate" for the slice that makes it fail. It cannot: an invitation type is not a
    member of `OrganizationService`, so the guard stays green through the very change it was
    written to catch. The roadmap's section 16 note inherits the same inaccuracy.

    Rather than edit that test -- it is correct about `OrganizationService`, and `R4-04`'s service
    is not written yet -- the scan is extended here to the surface that now takes a role. Every
    such parameter must be validated against `ROLES` before reaching a record.
    """
    # The scan looks for `intended_role` wherever it is *declared*, not on a fixed class, because
    # this scan has already lost its target twice in one slice: once written with
    # `inspect.isfunction`, which does not see a `classmethod` accessed off the class, and once when
    # the field moved from `create`'s parameter list onto `InvitationOffer`. Both times every
    # assertion below it still passed, and only the emptiness check caught it -- which is the whole
    # argument for keeping that check.
    role_takers = {
        name: hint
        for name, hint in (
            *((f"InvitationOffer.{f}", f) for f in InvitationOffer.__annotations__),
            *(
                (f"Invitation.{n}", p)
                for n, m in inspect.getmembers(Invitation, inspect.isroutine)
                if not n.startswith("__")
                for p in inspect.signature(m).parameters
            ),
        )
        if hint == "intended_role"
    }

    assert role_takers, (
        "nothing in the invitation surface names a role, so this guard is scanning the wrong "
        "place -- the field was renamed or moved and the check silently stopped applying"
    )

    # Whatever declares it, the creation door is what must refuse an undeclared value.
    with pytest.raises(ValueError):
        Invitation.create(
            _offer("superadmin"), secret=issue_secret(), expires_at=LATER, issued_at=NOW
        )


def test_the_guard_scan_checks_against_the_declared_role_set() -> None:
    """The scanner above is self-tested, following
    `test_rca_import_checker_flags_and_clears_expected_cases`: a scan that found nothing would
    pass every assertion in it. Here the known-good case is that `ROLES` is what is validated
    against, so a validation widened to accept any string is caught."""
    assert set(ROLES) == {OWNER_ROLE, MEMBER_ROLE}
    assert "superadmin" not in ROLES


# --- sealed, following Membership and MembershipEvent (section 3) ---------------------------


def test_the_record_is_frozen_and_refuses_substitution() -> None:
    """`records.py`'s two-door rule: a state change is a new instance, never a mutation, and
    `dataclasses.replace` is named in that module's docstring as the shape that must not work."""
    invitation = _open()

    with pytest.raises(FrozenInstanceError):
        invitation.redeemed_at = NOW  # type: ignore[misc]
    # `TypeError`, not a blind `Exception`: `records.py:206` refuses construction outside a door
    # with one message constant, and a blind assertion here would also pass on a `TypeError` from a
    # renamed field -- which is the substitution succeeding for a different reason.
    with pytest.raises(TypeError):
        replace(invitation, verifier=None)


def test_a_directly_constructed_invitation_is_refused() -> None:
    """Construction outside a door is refused, so `create` and `_from_storage` are the only two
    ways in. Without this, the sealing above is a claim about `replace` alone."""
    with pytest.raises(TypeError):
        Invitation(
            organization_id=ORG,
            intended_role=MEMBER_ROLE,
            target_identity=TARGET,
            verifier=None,
            invitation_id=INVITATION_ID_PREFIX + "x",
            expires_at=LATER,
            issued_by=ACTOR,
            issued_at=NOW,
            redeemed_at=None,
            revoked_at=None,
        )  # noqa: F821 -- the door refuses before any field is read


def test_reconstruction_preserves_stored_values_without_re_deriving() -> None:
    """The reconstruction door asserts nothing about its values: a stored digest is the only thing
    a candidate can be compared against, so reading must not re-derive. Mirrors
    `Verifier._from_storage`'s reasoning."""
    secret = issue_secret()

    restored = Invitation._from_storage(
        _offer(),
        StoredInvitationSecret(
            invitation_id=secret.invitation_id,
            verifier=Verifier._from_storage(
                salt=secret.verifier.salt, digest=secret.verifier.digest, kdf=INVITATION_KDF
            ),
            expires_at=LATER,
        ),
        issued_at=NOW,
        lifecycle=InvitationLifecycle(),
    )

    assert verify_secret(secret.secret, restored.verifier)
    assert restored.invitation_id == secret.invitation_id


def test_reconstruction_accepts_a_role_the_creation_door_refuses() -> None:
    """The doors flow one way each (`records.py`): `_from_storage` "asserts nothing about the
    values, because they came from the database". A row written before `R4-03`'s CHECK existed must
    still be readable -- refusing it would make the reader the thing that breaks, and the forgery
    this prevents is closed at `create` and at the constraint, not here."""
    restored = Invitation._from_storage(
        _offer("legacy"),
        StoredInvitationSecret(
            invitation_id=INVITATION_ID_PREFIX + "x", verifier=None, expires_at=LATER
        ),
        issued_at=NOW,
        lifecycle=InvitationLifecycle(),
    )

    assert restored.intended_role == "legacy"


def test_no_caller_code_runs_while_the_construction_door_is_open() -> None:
    """**A real vulnerability this slice introduced and then closed. Found in review on #215.**

    Grouping `create`'s parameters into `InvitationOffer` turned plain locals into attribute reads,
    and the reads sat *inside* `with through_door():`. `records.py` enumerates "caller code running
    inside an open door" as one of four bypasses it closed, and an attribute read is caller code: an
    offer subclass overriding `__getattribute__` runs arbitrary code while the capability is live.

    Verified before the fix: the block below constructed an `AuthorizationContext` with
    `account_id`, `organization_id` and `role` all set to a chosen value, and `assert_sealed`
    accepted it -- the `R6` authorization door defeated through an invitation parameter object. The
    flat signature it replaced had no such window, so the refactor caused this.

    The fix is that every caller-owned field is snapshotted into a local before the door opens, so
    the door's body is one constructor call. This test is what keeps that true: the defect returns
    the moment someone moves an attribute read back inside, and no static scan in
    `test_rca001_resolver_chokepoint.py` looks for that shape.
    """
    # Every read is attempted, not just the first. An earlier version of this test guarded with
    # `and not forged` and then asserted on `attempts[0]`, which is the read that happens *outside*
    # the door -- so it passed against a form that read one field inside it. The property is that no
    # read at any point succeeds, so the assertion has to be over all of them.
    attempts: list[object] = []

    class Hostile(InvitationOffer):
        def __getattribute__(self, name: str) -> object:
            if name in {"organization_id", "intended_role", "target_identity", "issued_by"}:
                try:
                    attempts.append(
                        AuthorizationContext(
                            **dict.fromkeys(AuthorizationContext.__dataclass_fields__, "FORGED")
                        )
                    )
                except TypeError as refusal:
                    attempts.append(refusal)
            return object.__getattribute__(self, name)

    hostile = Hostile.__new__(Hostile)
    for field, value in (
        ("organization_id", ORG),
        ("intended_role", MEMBER_ROLE),
        ("target_identity", TARGET),
        ("issued_by", ACTOR),
    ):
        object.__setattr__(hostile, field, value)

    invitation = Invitation.create(
        hostile, secret=issue_secret(), expires_at=LATER, issued_at=NOW
    )

    assert invitation.organization_id == ORG
    assert attempts, "the hostile offer never ran, so this test proves nothing about the door"
    succeeded = [a for a in attempts if not isinstance(a, TypeError)]
    assert not succeeded, (
        f"{len(succeeded)} of {len(attempts)} reads constructed a sealed record from inside the "
        f"door: {succeeded[0]!r}"
    )


def test_the_reconstruction_door_is_closed_to_caller_code_too() -> None:
    """The same window, on the door `R4-03`'s store will call.

    `_from_storage` receives values that came from the database, but the *carriers* are still
    caller-constructed objects, so the `__getattribute__` window is identical -- and this door
    validates nothing by design, which makes it the more attractive of the two. Asserted separately
    because the `create` test above passes unchanged when only this door reads inside itself.
    """
    attempts: list[object] = []

    class Hostile(InvitationLifecycle):
        def __getattribute__(self, name: str) -> object:
            if name in {"redeemed_at", "revoked_at"}:
                try:
                    attempts.append(
                        AuthorizationContext(
                            **dict.fromkeys(AuthorizationContext.__dataclass_fields__, "FORGED")
                        )
                    )
                except TypeError as refusal:
                    attempts.append(refusal)
            return object.__getattribute__(self, name)

    hostile = Hostile.__new__(Hostile)
    object.__setattr__(hostile, "redeemed_at", None)
    object.__setattr__(hostile, "revoked_at", None)

    restored = Invitation._from_storage(
        _offer(),
        StoredInvitationSecret(
            invitation_id=INVITATION_ID_PREFIX + "x", verifier=None, expires_at=LATER
        ),
        issued_at=NOW,
        lifecycle=hostile,
    )

    assert restored.redeemed_at is None
    assert attempts, "the hostile lifecycle never ran, so this test proves nothing"
    succeeded = [a for a in attempts if not isinstance(a, TypeError)]
    assert not succeeded, (
        f"a sealed record was built from inside the reconstruction door: {succeeded[0]!r}"
    )


def test_a_hostile_offer_cannot_change_the_role_between_check_and_use() -> None:
    """The check-versus-use half of the same finding. A `__getattribute__` that returned a declared
    role to the validation and an undeclared one to the constructor would put `"superadmin"` in a
    sealed record past a guard that had just approved `"member"`. Snapshotting reads the field once,
    so the value validated is the value stored."""
    reads: list[str] = []

    class TwoFaced(InvitationOffer):
        def __getattribute__(self, name: str) -> object:
            if name == "intended_role":
                reads.append(name)
                return MEMBER_ROLE if len(reads) == 1 else "superadmin"
            return object.__getattribute__(self, name)

    two_faced = TwoFaced.__new__(TwoFaced)
    for field, value in (
        ("organization_id", ORG),
        ("intended_role", MEMBER_ROLE),
        ("target_identity", TARGET),
        ("issued_by", ACTOR),
    ):
        object.__setattr__(two_faced, field, value)

    invitation = Invitation.create(
        two_faced, secret=issue_secret(), expires_at=LATER, issued_at=NOW
    )

    assert len(reads) == 1, f"the role was read {len(reads)} times, so check and use can diverge"
    assert invitation.intended_role == MEMBER_ROLE


def test_the_target_identity_is_not_named_email() -> None:
    """Section 3: the field is deliberately not `email`, because that name would collapse two
    separately governed data classes -- `KHEPRI-DEC-015` section 2's login identity has a fixed
    24-month horizon, while the invitation's target identity is lifecycle-derived and purged "when
    replay refusal no longer needs it". One name for both makes the shorter rule invisible."""
    assert "target_identity" in Invitation.__slots__
    assert "email" not in Invitation.__slots__
