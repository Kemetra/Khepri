"""Organization invitations: the domain and its hashed secret (`R4-02`).

**Scope.** Domain types only, following `R3-02`'s fence. Persistence, the `CHECK` constraints and
the sweeper are `R4-03`; issuance and revocation are `R4-04`; the `FR-020` and purge cascades are
`R4-06`; redemption and its uniform-failure path are `R4-05`. Nothing here touches a database, a
request, or a clock -- every moment is a parameter.

Designed by `docs/superpowers/specs/2026-08-17-r4-01-invitation-design.md`. Records follow the
two-door rule in `records.py`.

## What this module deliberately does not do

`FR-017` requires six distinct redemption failures -- malformed token, unknown identifier, wrong
secret, expired, revoked, already redeemed -- to be indistinguishable by message *and by timing*.
`parse_token` and `verify_secret` here raise and return ordinarily, because timing uniformity is a
property of the path that sequences them and cannot be established by either one alone: the design
note's section 6 requires a dummy lookup *and* a dummy scrypt on the malformed-token path, which is
earlier than any call here. `R4-05` owns that path. A caller that treats these two functions as the
whole of `FR-017` compliance will leak existence through timing, which the note names as the place a
`R4` implementation is most likely to be accidentally non-compliant "because the fast path looks
like an optimization".
"""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime

from khepri.rca.credentials import SALT_BYTES, KdfParams, Verifier, hash_credential
from khepri.rca.organizations import ROLES
from khepri.rca.records import Sealed, register_sealed, through_door

#: `kci1.<invitation_id>.<secret>`, mirroring RRA's `kiv1.` with a distinct prefix so a beta token
#: and a commercial token can never be confused at a boundary that accepts both. `R3-01` section
#: 2.1 established that reasoning for session keys.
TOKEN_PREFIX = "kci1"

#: Shared with `rra/sessions.py:78` as the design note spells it. The prefixes above are what
#: disambiguate the two families: RRA reaches `get_invitation` only after its own `parse_token` has
#: dispatched on `kiv1`, so no bare-identifier path crosses the boundary and the shared identifier
#: prefix discloses nothing.
INVITATION_ID_PREFIX = "inv_"

#: One message for every parse failure, so the four refusals below are already indistinguishable by
#: text before `R4-05` makes them indistinguishable by timing. Following `_INVITATION_FAILURE` and
#: `SCOPE_FAILURE`: a single constant cannot drift into four subtly different strings.
_MALFORMED = "malformed invitation token"

#: 18 bytes of CSPRNG output, matching every other opaque identifier in this package.
_ID_BYTES = 18

#: 32 bytes of CSPRNG entropy, rendered as 43 urlsafe base64 characters.
_SECRET_BYTES = 32

#: RRA's scrypt parameters (`rra/sessions.py:105-112`), matched rather than chosen anew: two
#: hashing schemes in one codebase means one of them is unreviewed.
#:
#: **Deliberately below `credentials.DEFAULT_KDF`'s `n=2**15`, and that is not an oversight.** The
#: two work factors protect different things. A credential is chosen by a person and may be
#: low-entropy, so its KDF cost is what stands between a stolen digest and the password; an
#: invitation secret is 32 CSPRNG bytes, where there is nothing to guess and the KDF only bounds the
#: value of a stolen digest before expiry. The parameters are persisted per row (`KdfParams`) so
#: this can be raised later without invalidating existing invitations.
INVITATION_KDF = KdfParams(n=2**14, r=8, p=1)


@dataclass(frozen=True, slots=True)
class StoredInvitationSecret:
    """The secret material as a row holds it: an identifier, a horizon, and a destructible verifier.

    **Deliberately not `InvitationSecret`.** That carrier holds the *plaintext* secret, and a row
    has none -- it was returned once at issuance and never stored. Reconstruction cannot produce
    one and must not appear able to, which is why the two groups are separate types rather than one
    with an optional field: an optional plaintext would be a field a store could fill.

    `verifier` is `None` for a redeemed, revoked, or touched-after-expiry invitation. That is the
    terminal shape, not a defect.
    """

    invitation_id: str
    verifier: Verifier | None
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class InvitationLifecycle:
    """The two terminal timestamps, as stored.

    Exists for the reconstruction door only. `create` has no parameter for either -- a created
    invitation is open by definition -- so grouping them keeps that asymmetry visible in the
    signatures rather than leaving it as two arguments one door happens not to take.

    Both default to `None`, the open shape, so a store reading a row need not name what is absent.
    Expiry is deliberately not here: it is derived from `expires_at` and has no column; giving
    it one would put two fields on one fact.
    """

    redeemed_at: datetime | None = None
    revoked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class InvitationOffer:
    """What is being offered, to whom, by whom -- the three values an owner supplies.

    **Not sealed, because it carries no invariant and grants nothing.** These are inputs on their
    way to `Invitation.create`, which is where `intended_role` is validated; sealing them would put
    a construction boundary around a value object whose forgery buys an attacker nothing they
    could not achieve by calling `create` directly. The record that results *is* sealed.

    `issued_by` is the actor account, for `FR-014`-style attribution. `R4-04` supplies it from what
    the gate resolved rather than from a caller's claim -- section 4's asymmetry with redemption.
    """

    organization_id: str
    intended_role: str
    target_identity: str
    issued_by: str


@dataclass(frozen=True, slots=True)
class InvitationSecret:
    """The plaintext secret and the record material derived from it, returned once.

    **Not sealed, and not persisted.** This is the carrier that crosses from generation to the
    caller who delivers the token, and it exists so that "the secret is returned once and never
    stored" is unexpressible rather than merely forbidden: `Invitation` has no field the plaintext
    could occupy, so a store cannot write it even by mistake. `Verifier` -- the half that *is*
    stored -- is sealed on its own account.
    """

    invitation_id: str
    secret: str
    verifier: Verifier

    @property
    def token(self) -> str:
        """The single string handed to the invitee. Assembled rather than stored, so there is no
        second representation of the secret to forget to destroy."""
        return f"{TOKEN_PREFIX}.{self.invitation_id}.{self.secret}"


def issue_secret() -> InvitationSecret:
    """Generate an invitation identifier, its secret, and the verifier that will be stored.

    **A free function rather than a `Verifier.derive(kdf=...)` overload, deliberately.** `derive` is
    the FR-002 chokepoint whose guarantee is that no caller supplies credential material, and a
    caller-chosen cost factor is caller-supplied material: a `kdf` parameter there would let any
    call site weaken a *credential* to `n=2**10`. So the lower invitation factor is pinned here, on
    a path that produces invitation secrets and nothing else, and `derive` keeps having no
    parameters at all.

    The CSPRNG constructions match `rra/sessions.py:78-80` so there is one generation scheme in the
    codebase rather than two. Stated in the design note because the rest of its section 4 does not
    imply it: fixing the token encoding, the KDF parameters, and the salt *length* still leaves
    generation unspecified, and `scrypt` cannot add entropy a bearer token never had.
    """
    invitation_id = f"{INVITATION_ID_PREFIX}{secrets.token_urlsafe(_ID_BYTES)}"
    secret = secrets.token_urlsafe(_SECRET_BYTES)
    salt = secrets.token_bytes(SALT_BYTES)
    # Hash before opening the door, following `Verifier.derive`: a door authorizes construction for
    # anything on this thread while open, and scrypt is by far the longest call in the package.
    digest = hash_credential(secret, salt, INVITATION_KDF)
    with through_door():
        verifier = Verifier(salt=salt, digest=digest, kdf=INVITATION_KDF)
    return InvitationSecret(invitation_id=invitation_id, secret=secret, verifier=verifier)


def parse_token(token: str) -> tuple[str, str]:
    """Split a presented token into its identifier and secret, or refuse.

    Refuses rather than returning a partial result, so a caller cannot obtain an identifier from a
    token that does not carry one. **The uniform-failure and timing obligations are `R4-05`'s** --
    see this module's docstring.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError(_MALFORMED)
    prefix, invitation_id, secret = parts
    # The rules are a tuple rather than a chained `or` or a run of `if`s. `rra/sessions.py:95`
    # writes them as one three-clause conditional, which on a security boundary reads as a single
    # check; a run of separate `if`s says which rule broke but multiplies the branch count. As data
    # the rules are enumerable -- `R4-05` can report *which* one failed while still refusing
    # uniformly to the caller -- and adding a fourth rule adds a row, not a branch.
    rules = (
        prefix == TOKEN_PREFIX,
        invitation_id.startswith(INVITATION_ID_PREFIX),
        bool(secret),
    )
    if not all(rules):
        raise ValueError(_MALFORMED)
    return invitation_id, secret


def verify_secret(secret: str, verifier: Verifier | None) -> bool:
    """Whether a presented secret matches a stored verifier.

    `None` -- a destroyed verifier -- returns `False` rather than raising, because it is the
    terminal shape of a redeemed, revoked, or touched-after-expiry invitation and not a defect.
    `hmac.compare_digest` rather than `==`, matching `rra/sessions.py:101`.

    **This does not pay a dummy cost for a missing invitation**, so it is not on its own sufficient
    for `FR-017`; the caller that sequences lookup and verification owns that, and `R4-05` owes it.
    """
    if verifier is None:
        return False
    candidate = hash_credential(secret, verifier.salt, verifier.kdf)
    return hmac.compare_digest(candidate, verifier.digest)


@register_sealed
@dataclass(frozen=True, slots=True)
class Invitation(Sealed):
    """An offer of one membership in one organization, addressed to one identity.

    **Four states, discriminated by nullability rather than a status column**, following
    `MembershipEvent`: a `status` field could disagree with the timestamps, and then two fields
    would describe one fact.

    | State | `redeemed_at` | `revoked_at` | `expires_at` vs now |
    |---|---|---|---|
    | open | NULL | NULL | `expires_at > now` |
    | expired | NULL | NULL | `expires_at <= now` |
    | redeemed | set | NULL | any |
    | revoked | NULL | set | any |

    Sealed, following `Membership`: a state change is a new instance, never a mutation, so
    `redeemed_at` is set by constructing rather than by assignment. Destroying the verifier is the
    same move -- a new instance carrying `None`.

    **`target_identity`, not `email`.** The two names would collapse two separately governed data
    classes. `KHEPRI-DEC-015` section 2 governs "Login identity (email)" with a fixed horizon --
    while enabled, then 24 months after disablement -- whereas this field is lifecycle-derived and
    purged "when replay refusal no longer needs it". One name for both would make the shorter rule
    invisible, which is the "no single retention horizon is quietly longer than another" discipline
    that decision adopts. An email address is what `R4` will in fact hold, since `FR-019` issues to
    a person before an account exists; the name records the governed class, not the encoding.

    **Purpose limitation carries with the field.** `target_identity` is readable to refuse replay
    and to attribute a resulting membership, and for nothing else. `FR-040`'s content-free logging
    still forbids logging it.

    **The verifier is an optional whole, not five nullable columns.** `credentials.py:77-80` states
    the reasoning and it transfers verbatim: destruction replaces the whole verifier with `None` and
    cannot be done by halves. Held as independently-nullable columns, a half-destroyed verifier --
    salt gone, digest kept -- would be expressible and nothing in the schema would refuse it, which
    is why the invariant lives in the domain type. `R4-03` owes the `CHECK` that keeps the columns
    NULL together at rest.
    """

    organization_id: str
    intended_role: str
    target_identity: str
    verifier: Verifier | None
    invitation_id: str
    expires_at: datetime
    issued_by: str
    issued_at: datetime
    #: NULL means never redeemed. Derived state is never duplicated into a boolean, following
    #: `Account` and `Session`.
    redeemed_at: datetime | None
    revoked_at: datetime | None

    @classmethod
    def create(
        cls,
        offer: InvitationOffer,
        *,
        secret: InvitationSecret,
        expires_at: datetime,
        issued_at: datetime,
    ) -> Invitation:
        """The creation door: a new, open invitation.

        **The parameters are grouped rather than listed flat**, following `ca7c572`'s fix for the
        same shape in `khepri.rra`: ten positional-or-keyword names meant every caller restated the
        record's field list, and adding a column would touch every call site. The grouping is the
        one section 3 already describes -- what is offered to whom (`InvitationOffer`), the secret
        material (`InvitationSecret`, which `issue_secret` returns as one whole), and the two
        moments. It also removes a class of caller error the flat form allowed: an `invitation_id`
        and a `verifier` from *different* `issue_secret` calls could be passed together, producing a
        record whose stored digest verifies no secret anyone holds.

        **`intended_role` is validated here because this is where a caller-supplied role first
        enters the codebase.** Until now no operation took one: `promote_to_owner` and
        `demote_to_member` name their destination in the method name, and `create_organization`
        fixes the founding role at owner -- which is why
        `test_no_role_change_operation_accepts_a_role_from_its_caller` records that the missing
        validation "has never been exploitable: there is no input to validate". This field is that
        input, so the validation arrives with it. `R4-03`'s `CHECK` is not a substitute: a store
        caller that bypasses this door would reintroduce the gap, the same argument the design
        note's constraints rest on.

        There is no `redeemed_at`/`revoked_at` parameter. A created invitation is open by
        definition, and the terminal states are reached through the operations below or rebuilt by
        the reconstruction door -- never named at creation.

        `expires_at` is required and has no default: `FR-016` requires an explicit expiry and does
        not fix a lifetime, so baking one in would put a product decision in the domain.
        """
        if offer.intended_role not in ROLES:
            raise ValueError(
                f"unknown role {offer.intended_role!r}; an invitation may name only {ROLES}"
            )
        with through_door():
            return Invitation(
                organization_id=offer.organization_id,
                intended_role=offer.intended_role,
                target_identity=offer.target_identity,
                verifier=secret.verifier,
                invitation_id=secret.invitation_id,
                expires_at=expires_at,
                issued_by=offer.issued_by,
                issued_at=issued_at,
                redeemed_at=None,
                revoked_at=None,
            )

    @classmethod
    def _from_storage(
        cls,
        offer: InvitationOffer,
        stored: StoredInvitationSecret,
        *,
        issued_at: datetime,
        lifecycle: InvitationLifecycle,
    ) -> Invitation:
        """Rebuild from stored columns, preserving them verbatim.

        Grouped like `create` and for the same reason, with one difference that matters: the secret
        material arrives as a loose `verifier` and `invitation_id` rather than as an
        `InvitationSecret`, because that carrier holds the *plaintext* secret and a row has none --
        it was returned once at issuance and never stored. Reconstruction cannot produce one and
        must not appear able to.

        Asserts nothing about the values -- including the role -- because they came from the
        database and the guarantee is that nothing but `create` could have put them there. A row
        written before `R4-03`'s `CHECK` existed must still be readable: refusing it here would make
        the reader the thing that breaks, and the forgery this prevents is closed at the creation
        door and at the constraint.
        """
        with through_door():
            return Invitation(
                organization_id=offer.organization_id,
                intended_role=offer.intended_role,
                target_identity=offer.target_identity,
                verifier=stored.verifier,
                invitation_id=stored.invitation_id,
                expires_at=stored.expires_at,
                issued_by=offer.issued_by,
                issued_at=issued_at,
                redeemed_at=lifecycle.redeemed_at,
                revoked_at=lifecycle.revoked_at,
            )

    def is_expired_at(self, moment: datetime) -> bool:
        """True once the horizon has elapsed. **The expiry instant itself counts as expired.**

        Stated once here rather than compared inline at each call site, because the boundary was
        expressible two ways and two implementations picking `<` and `<=` would disagree about one
        instant -- and the one picking `<` treats an invitation at its own expiry as still open,
        failing *open* in a state model whose whole point is failing closed. Matches
        `Session.is_expired_at` (`sessions.py:111`) and RRA's `redeem` (`rra/sessions.py:120`).
        """
        return self.expires_at <= moment

    def is_open_at(self, moment: datetime) -> bool:
        """Neither expired, redeemed, nor revoked.

        **Not sufficient to admit a redemption.** At-most-once needs a lock or a conditional update
        at the database, per the design note's section 6.2; this predicate reads one in-memory
        record and two concurrent redeemers would both see it true. `R4-05` owns that control.
        """
        return (
            self.redeemed_at is None
            and self.revoked_at is None
            and not self.is_expired_at(moment)
        )

    def redeemed(self, *, at: datetime) -> Invitation:
        """The redeemed form: the timestamp set and the verifier destroyed, in one operation.

        A door, not a field assignment, following `Membership.promoted` --
        `dataclasses.replace(invitation, redeemed_at=at)` is the obvious way to write this and is
        the exact shape `records.py` refuses.

        **Destruction is in the same operation because `KHEPRI-DEC-015` requires it at the
        trigger.** Section 5 of that decision measures the harm in days of survival, so this is a
        claim about bytes and not only about authority: a redeemed invitation whose verifier
        survived is one whose secret still verifies.
        """
        self._require_open()
        return self._replacing(redeemed_at=at, revoked_at=None)

    def revoked(self, *, at: datetime) -> Invitation:
        """The revoked form, destroying the verifier for the same reason `redeemed` does.

        Revocation is scoped by `(organization_id, invitation_id)` at the store rather than by
        identifier alone -- that is `R4-04`'s obligation, and this record carries the organization
        so the scoped form is expressible.
        """
        self._require_open()
        return self._replacing(redeemed_at=None, revoked_at=at)

    def verifier_destroyed(self) -> Invitation:
        """Destroy the verifier and change nothing else -- the expiry case.

        **Expiry is not a write**: it is `expires_at <= now`, a derived state with no column and no
        event, so nothing fires at the horizon and something else must destroy the bytes. Any path
        that loads an invitation and finds it expired calls this before refusing, which costs
        nothing on a read that was already happening and closes the case that matters most: an
        expired invitation someone is actively presenting is exactly the one whose verifier should
        not still be there. `R4-03`'s sweeper is the backstop for rows nobody presents.

        No timestamp is set. Giving expiry a column would put two fields on one fact, and the state
        table above reads it off `expires_at` alone.
        """
        if self.verifier is None:
            return self
        return self._replacing(redeemed_at=self.redeemed_at, revoked_at=self.revoked_at)

    def _require_open(self) -> None:
        """Refuse a second terminal transition.

        Not the at-most-once guarantee -- that is the database's, per section 6.2 -- but a caller
        should not be able to express the contradiction in memory either. Expiry is deliberately
        not checked here: it depends on a moment, and these operations take the moment of the write
        rather than a separate clock.
        """
        if self.redeemed_at is not None:
            raise ValueError("this invitation is already redeemed")
        if self.revoked_at is not None:
            raise ValueError("this invitation is already revoked")

    def _replacing(
        self, *, redeemed_at: datetime | None, revoked_at: datetime | None
    ) -> Invitation:
        """Rebuild through the door with the verifier destroyed, preserving everything else."""
        with through_door():
            return Invitation(
                organization_id=self.organization_id,
                intended_role=self.intended_role,
                target_identity=self.target_identity,
                verifier=None,
                invitation_id=self.invitation_id,
                expires_at=self.expires_at,
                issued_by=self.issued_by,
                issued_at=self.issued_at,
                redeemed_at=redeemed_at,
                revoked_at=revoked_at,
            )
