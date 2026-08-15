"""The `IdentityProvider` seam and its verified-identity type (`R3-10`).

**Vendor containment, not a provider-switching framework.** `KHEPRI-DEC-018` §6 requires that
provider concepts not spread into Khepri's domain, authorization, organization, membership, or
isolation logic, and that a narrow internal seam contain them. That is the whole purpose; the
narrowness *is* the containment, so every addition here weakens it.

**What the seam exposes, exhaustively:** whether a request carries a verified identity, and the
stable provider subject with the provider that issued it. §6: "It exposes nothing else. Khepri
business authority is not expressible through it, so a provider cannot assert authority even in
error."

That last clause is a structural claim rather than a promise about behavior. A seam that *could*
carry a role is a seam where a future adapter eventually puts one, whatever the reviewing intent —
so `VerifiedIdentity` has exactly two fields and the protocol exactly one method.

**Where this sits in the request path** (`R3-09` §2.1):

```
provider verifies identity                     <- R3-11 adapter, behind this seam
        |
stable provider subject                        <- this module: (provider, subject) only
        |
(provider, provider_subject) -> account_id     <- local lookup, no provider call (R3-04)
        |
Khepri mints its own session                   <- R3-04, cse_ cookie
        |
   [R3-01 §4 steps 2-5, unchanged]
```

Everything external identity adds happens *before* step 1 of the resolution path. From the cookie
onward the path is identical whether the actor authenticated through `FR-002` credentials or an
admitted provider, which is why this slice changes no existing module.

**No adapter here, and no vendor named.** `R3-11` owns any concrete provider and cannot start until
one is admitted under §5 — the merged Clerk evaluation records four outstanding vendor-evidence
gates. Naming a vendor now would make the seam that vendor's shape before any gate was cleared,
the same way `khepri.infra` encodes platform limits and never `KHEPRI-DEC-007`'s chosen values.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    """One authenticated actor as an admitted provider reports them, and nothing more.

    **Not a `Sealed` record, deliberately.** `records.py`'s two-door rule governs records Khepri
    *mints*: creation allocates and validates, reconstruction preserves stored values. This is
    neither — it is an inbound fact an adapter reports, carrying no invariant Khepri allocates.
    Sealing it would add ceremony with no protected invariant and would imply this package
    constructs provider identities. `StoredSession` is the precedent.

    **What is deliberately absent.** No organization, role, permission, membership, `can_act`, or
    resource ownership: `KHEPRI-DEC-018` §4 requires Khepri to refuse those claims for any
    authorization purpose, and a field here is how one would arrive anyway. Providers commonly
    emit them; the prohibition is on reading them, and the cheapest way to guarantee that is to
    have nowhere to put them.

    **No `account_id` either.** The seam stops at the provider's own vocabulary. Mapping
    `(provider, provider_subject)` to a Khepri account is a local lookup owned by `R3-04`, and
    `R3-09` §2.1 requires it stay local so a provider outage cannot make an already-authenticated
    request unresolvable.
    """

    #: Which provider issued this identity. Populated by the adapter with its own name, so a
    #: subject is never ambiguous between two providers that both mint opaque subject strings.
    provider: str
    #: The provider's stable identifier for this actor -- the verified token's `sub`, per the
    #: merged provider evaluation. Never a portability anchor such as an `external_id`: those
    #: change hands during migrations, and a per-request subject that can move is an account
    #: takeover waiting for one.
    provider_subject: str


@runtime_checkable
class IdentityProvider(Protocol):
    """The one question Khepri may ask an identity provider.

    **Structural rather than nominal**, following `AccountStore` and `OrganizationStore` in
    `stores.py`. An adapter satisfies this by shape, so `R3-11`'s vendor code never imports from
    `khepri.rca` and the dependency points one way only — which is what keeps vendor types from
    reaching back across the boundary §6 draws.

    **One method, and the count is load-bearing.** A second is a second thing a provider could be
    asked, and every question widens the surface a provider's answer can influence.
    """

    def verify(self, credential: str) -> VerifiedIdentity | None:
        """The verified identity behind a provider credential, or `None` if there is not one.

        `None` is the "whether the request carries a verified identity" half of §6, and the
        return type is the whole vocabulary: a richer one is how a provider's refused claims
        would arrive despite §4.

        **Refuses rather than raises for an invalid credential.** An absent, expired, malformed,
        or forged credential are one answer here, matching the uniform-refusal rule `FR-004` and
        `FR-022` impose one layer up: a caller able to distinguish them learns which credentials
        exist. An adapter may still raise for a *transport* failure — a provider being
        unreachable is not a statement about the credential.

        **Synchronous, and this is the one shape decision not fixed by an artifact.** No provider
        is admitted, so nothing constrains it; a synchronous contract matches every existing store
        and service in this package, and `R3-09` §2.1 keeps per-request resolution local, so the
        hot path makes no provider call at all. `R3-11` is the task that would know better, and
        changing this before an adapter exists costs one signature.
        """
        ...


__all__ = ["IdentityProvider", "VerifiedIdentity"]
