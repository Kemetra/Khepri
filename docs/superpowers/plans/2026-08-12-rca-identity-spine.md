# RCA-001 Commercial Identity Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the durable account, organization, and stable opaque isolation-scope mapping that
`RCA-001` requires, so that an organization resolves to a stable `owner_id` from which no
commercial identifier is derivable.

**Architecture:** A new `src/khepri/rca/` package mirroring the existing `rra` layout — frozen
dataclasses for records, `Protocol` classes for stores, a separate SQLAlchemy module for local
Postgres persistence. The isolation scope is a random opaque token **allocated once per
organization and stored**, never derived from organization data. Scope resolution returns
`owner_id` only; it does not construct a `SessionScope` and creates no sessions.

**Tech Stack:** Python 3.13, `hashlib.scrypt` + `hmac.compare_digest`, SQLAlchemy 2.x
(`DeclarativeBase`, `Mapped`, `mapped_column`), pytest.

## Global Constraints

- **Design authority:** `docs/superpowers/specs/2026-08-12-rca-identity-spine-design.md` (commit `f7cf884`).
- **Governance:** implementation is authorized only as a bounded slice linked to `RCA-001`. Do not
  edit anything under `governance/`, and do not edit `src/khepri_gov/`.
- **Import direction:** `khepri.rca` may import from `khepri.rra`. **No module under
  `src/khepri/rra/` may import from `khepri.rca`** (FR-039). Asserted by a test in Task 6.
- **Do not modify `src/khepri/rra/*` in this slice.** Not one line.
- **Do not write to any `rra_*` table.** All new tables are prefixed `rca_`.
- **Never derive the isolation scope** from an email, organization name, slug, account identifier,
  or any human-readable identifier (FR-032). Allocate with `secrets.token_urlsafe(18)`.
- **Credential KDF:** `hashlib.scrypt(n=2**15, r=8, p=1, dklen=32)` with a 16-byte
  `secrets.token_bytes(16)` salt. Store `n`, `r`, `p` alongside each digest.
- **Uniform refusals:** one module-level message constant per refusal class; identical message
  regardless of which check failed (FR-004, FR-025, FR-034).
- **Content-free logging:** never log an email, organization name, or credential material (FR-040).
- **Python interpreter:** `./.venv/Scripts/python.exe`. The `python` on PATH lacks the package.
- **Line length 100** (`[tool.ruff]` in `pyproject.toml`). `target-version = "py313"`.
- **Every module starts with** `from __future__ import annotations`.
- **Do NOT run `ruff format`.** CI has no format gate and the local ruff is version-skewed;
  running it would churn ~86 unrelated files.
- **Test naming:** `tests/test_rca001_<topic>.py`, matching the existing `test_rra001_*` convention.
- **Test fakes:** declare `Memory*Store` classes inside the test file that uses them. There is no
  `tests/conftest.py` and this plan does not add one.
- **Branch:** `feat/rca-identity-spine`. Do not commit to `main`.
- **Commits:** `git commit --no-gpg-sign` (signing is blocked on this machine). Multi-line messages
  via `git commit -F <file>`, never a here-string.

## File Structure

| File | Responsibility |
|---|---|
| `src/khepri/rca/__init__.py` | Package marker. Empty. |
| `src/khepri/rca/errors.py` | Refusal exceptions + their single message constants. |
| `src/khepri/rca/stores.py` | `Protocol` definitions: `AccountStore`, `OrganizationStore`. |
| `src/khepri/rca/accounts.py` | `Account` record, `AccountService`: create / authenticate / disable. |
| `src/khepri/rca/organizations.py` | `Organization`, `Membership`, `IsolationScope` records; `OrganizationService`: create-with-owner atomically. |
| `src/khepri/rca/isolation.py` | `IsolationService.resolve_scope` — the FR-031 choke point. |
| `src/khepri/rca/persistence.py` | SQLAlchemy rows (`rca_*` tables) + store implementations. |
| `tests/test_rca001_accounts.py` | FR-001, FR-002, FR-004 (Task 2). |
| `tests/test_rca001_organizations.py` | FR-009, FR-010, FR-014 (Task 3). |
| `tests/test_rca001_isolation.py` | FR-031, FR-032, FR-033, FR-034, FR-035 (Task 4). |
| `tests/test_rca001_persistence.py` | Store round-trip + atomicity (Task 5). |
| `tests/test_rca001_boundary.py` | FR-039 import direction + RRA independence (Task 6). |

Task order is dependency order: errors → accounts → organizations → isolation → persistence →
boundary. Tasks 2, 3, 4 use in-memory fakes only, so they need no database.

---

### Task 1: Package skeleton and uniform refusals

**Files:**
- Create: `src/khepri/rca/__init__.py`
- Create: `src/khepri/rca/errors.py`
- Create: `src/khepri/rca/stores.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `AuthenticationFailed`, `OrganizationCreationFailed`, `ScopeAccessDenied`,
  `_AUTHENTICATION_FAILURE`, `_SCOPE_FAILURE`; `AccountStore` and `OrganizationStore` protocols
  (their methods are fully specified in Tasks 2 and 3).

- [ ] **Step 1: Create the package marker**

```bash
mkdir -p src/khepri/rca
```

Create `src/khepri/rca/__init__.py` as an empty file (0 bytes).

- [ ] **Step 2: Write `errors.py`**

```python
from __future__ import annotations

_AUTHENTICATION_FAILURE = "Credentials are invalid or unavailable."
_SCOPE_FAILURE = "Scope is invalid or unavailable."
_ORGANIZATION_FAILURE = "Organization could not be created."


class AuthenticationFailed(PermissionError):
    pass


class ScopeAccessDenied(PermissionError):
    pass


class OrganizationCreationFailed(ValueError):
    pass
```

Note: `AuthenticationFailed` and `ScopeAccessDenied` subclass `PermissionError`, matching
`CrossSessionAccessDenied` in `src/khepri/rra/sessions.py:25`.

- [ ] **Step 3: Write `stores.py`**

```python
from __future__ import annotations

from typing import Protocol

from khepri.rca.accounts import Account
from khepri.rca.organizations import IsolationScope, Membership, Organization


class AccountStore(Protocol):
    def add_account(self, account: Account) -> bool: ...

    def get_account_by_email(self, email: str) -> Account | None: ...

    def get_account(self, account_id: str) -> Account | None: ...

    def update_account(self, account: Account) -> None: ...


class OrganizationStore(Protocol):
    def create_organization(
        self,
        organization: Organization,
        membership: Membership,
        scope: IsolationScope,
    ) -> bool: ...

    def get_membership(self, organization_id: str, account_id: str) -> Membership | None: ...

    def get_scope(self, organization_id: str) -> IsolationScope | None: ...
```

`create_organization` takes all three records because FR-010 requires them to be written
atomically. `add_account` returns `bool` (False on duplicate email) rather than raising, so the
caller controls the uniform refusal.

- [ ] **Step 4: Verify it imports**

Run: `./.venv/Scripts/python.exe -c "import khepri.rca.errors"`
Expected: no output, exit 0. (`stores.py` will not import until Tasks 2–3 create `accounts.py` and
`organizations.py`; that is expected and is resolved in Task 3.)

- [ ] **Step 5: Commit**

```bash
git add src/khepri/rca/
git commit --no-gpg-sign -m "feat(rca): add package skeleton and uniform refusal errors"
```

---

### Task 2: Accounts — durable identity, hashed credentials, uniform failure

**Files:**
- Create: `src/khepri/rca/accounts.py`
- Test: `tests/test_rca001_accounts.py`

**Interfaces:**
- Consumes: `AuthenticationFailed`, `_AUTHENTICATION_FAILURE` from `khepri.rca.errors`.
- Produces:
  - `Account` frozen dataclass: `account_id: str`, `email: str`, `credential_salt: bytes`,
    `credential_digest: bytes`, `kdf_n: int`, `kdf_r: int`, `kdf_p: int`, `disabled: bool = False`
  - `hash_credential(credential: str, salt: bytes, *, n: int, r: int, p: int) -> bytes`
  - `AccountService(store: AccountStore)` with
    `create_account(email: str, credential: str) -> Account`,
    `authenticate(email: str, credential: str) -> Account` (raises `AuthenticationFailed`),
    `disable_account(account_id: str) -> None`
  - Constants `KDF_N = 2**15`, `KDF_R = 8`, `KDF_P = 1`, `KDF_DKLEN = 32`, `SALT_BYTES = 16`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_rca001_accounts.py`:

```python
from __future__ import annotations

import pytest

from khepri.rca.accounts import Account, AccountService, hash_credential
from khepri.rca.errors import AuthenticationFailed

EMAIL = "owner@example.test"
CREDENTIAL = "correct horse battery staple"


class MemoryAccountStore:
    def __init__(self) -> None:
        self.accounts: dict[str, Account] = {}

    def add_account(self, account: Account) -> bool:
        if any(existing.email == account.email for existing in self.accounts.values()):
            return False
        self.accounts[account.account_id] = account
        return True

    def get_account_by_email(self, email: str) -> Account | None:
        for account in self.accounts.values():
            if account.email == email:
                return account
        return None

    def get_account(self, account_id: str) -> Account | None:
        return self.accounts.get(account_id)

    def update_account(self, account: Account) -> None:
        self.accounts[account.account_id] = account


def _service() -> AccountService:
    return AccountService(MemoryAccountStore())


def test_create_account_establishes_durable_identity() -> None:
    service = _service()
    account = service.create_account(EMAIL, CREDENTIAL)
    assert account.account_id.startswith("acc_")
    assert account.email == EMAIL
    assert account.disabled is False


def test_credential_is_never_stored_in_recoverable_form() -> None:
    service = _service()
    account = service.create_account(EMAIL, CREDENTIAL)
    blob = repr(account).encode() + account.credential_digest + account.credential_salt
    assert CREDENTIAL.encode() not in blob


def test_credential_digest_records_its_work_factor() -> None:
    service = _service()
    account = service.create_account(EMAIL, CREDENTIAL)
    assert (account.kdf_n, account.kdf_r, account.kdf_p) == (2**15, 8, 1)
    assert len(account.credential_salt) == 16
    assert len(account.credential_digest) == 32


def test_same_credential_yields_distinct_digests_across_accounts() -> None:
    service = _service()
    first = service.create_account("a@example.test", CREDENTIAL)
    second = service.create_account("b@example.test", CREDENTIAL)
    assert first.credential_digest != second.credential_digest


def test_authenticate_succeeds_with_correct_credential() -> None:
    service = _service()
    created = service.create_account(EMAIL, CREDENTIAL)
    assert service.authenticate(EMAIL, CREDENTIAL).account_id == created.account_id


def test_authentication_failures_are_uniform() -> None:
    service = _service()
    service.create_account(EMAIL, CREDENTIAL)
    disabled = service.create_account("off@example.test", CREDENTIAL)
    service.disable_account(disabled.account_id)

    messages = []
    for email, credential in (
        ("missing@example.test", CREDENTIAL),
        (EMAIL, "wrong credential"),
        ("off@example.test", CREDENTIAL),
    ):
        with pytest.raises(AuthenticationFailed) as caught:
            service.authenticate(email, credential)
        messages.append(str(caught.value))

    assert len(set(messages)) == 1


def test_duplicate_email_is_refused_uniformly() -> None:
    service = _service()
    service.create_account(EMAIL, CREDENTIAL)
    with pytest.raises(AuthenticationFailed):
        service.create_account(EMAIL, "another credential")


def test_hash_credential_is_deterministic_for_a_fixed_salt() -> None:
    salt = b"0123456789abcdef"
    first = hash_credential(CREDENTIAL, salt, n=2**14, r=8, p=1)
    second = hash_credential(CREDENTIAL, salt, n=2**14, r=8, p=1)
    assert first == second
    assert hash_credential("other", salt, n=2**14, r=8, p=1) != first
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca001_accounts.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'khepri.rca.accounts'`.

- [ ] **Step 3: Write the implementation**

Create `src/khepri/rca/accounts.py`:

```python
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from khepri.rca.errors import AuthenticationFailed, _AUTHENTICATION_FAILURE

if TYPE_CHECKING:
    from khepri.rca.stores import AccountStore

KDF_N = 2**15
KDF_R = 8
KDF_P = 1
KDF_DKLEN = 32
SALT_BYTES = 16


@dataclass(frozen=True, slots=True)
class Account:
    account_id: str
    email: str
    credential_salt: bytes
    credential_digest: bytes
    kdf_n: int
    kdf_r: int
    kdf_p: int
    disabled: bool = False


def hash_credential(credential: str, salt: bytes, *, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        credential.encode(),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=KDF_DKLEN,
    )


class AccountService:
    def __init__(self, store: AccountStore) -> None:
        self._store = store

    def create_account(self, email: str, credential: str) -> Account:
        salt = secrets.token_bytes(SALT_BYTES)
        account = Account(
            account_id=f"acc_{secrets.token_urlsafe(18)}",
            email=email,
            credential_salt=salt,
            credential_digest=hash_credential(credential, salt, n=KDF_N, r=KDF_R, p=KDF_P),
            kdf_n=KDF_N,
            kdf_r=KDF_R,
            kdf_p=KDF_P,
        )
        if not self._store.add_account(account):
            raise AuthenticationFailed(_AUTHENTICATION_FAILURE)
        return account

    def authenticate(self, email: str, credential: str) -> Account:
        account = self._store.get_account_by_email(email)
        if account is None:
            self._reject()
        candidate = hash_credential(
            credential,
            account.credential_salt,
            n=account.kdf_n,
            r=account.kdf_r,
            p=account.kdf_p,
        )
        if not hmac.compare_digest(candidate, account.credential_digest):
            self._reject()
        if account.disabled:
            self._reject()
        return account

    def disable_account(self, account_id: str) -> None:
        account = self._store.get_account(account_id)
        if account is None:
            return
        self._store.update_account(replace(account, disabled=True))

    @staticmethod
    def _reject() -> None:
        raise AuthenticationFailed(_AUTHENTICATION_FAILURE)
```

Note on `_reject`: the credential comparison runs **before** the disabled check so that a disabled
account costs the same work as an enabled one. The missing-account branch returns early without
hashing, which is a known timing difference; closing it requires a dummy hash and is deferred to
the session slice where login is actually exposed. Record this in the commit body.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca001_accounts.py -q`
Expected: 8 passed.

- [ ] **Step 5: Lint**

Run: `./.venv/Scripts/python.exe -m ruff check src/khepri/rca/ tests/test_rca001_accounts.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/khepri/rca/accounts.py tests/test_rca001_accounts.py
git commit --no-gpg-sign -m "feat(rca): add durable accounts with scrypt credentials (FR-001, FR-002, FR-004)"
```

---

### Task 3: Organizations — atomic create-with-owner and FR-014 attribution

**Files:**
- Create: `src/khepri/rca/organizations.py`
- Test: `tests/test_rca001_organizations.py`

**Interfaces:**
- Consumes: `OrganizationCreationFailed`, `_ORGANIZATION_FAILURE` from `khepri.rca.errors`;
  `OrganizationStore` from `khepri.rca.stores`.
- Produces:
  - `Organization` frozen dataclass: `organization_id: str`, `name: str`, `created_at: datetime`
  - `Membership` frozen dataclass: `organization_id: str`, `account_id: str`, `role: str`,
    `changed_by: str`, `changed_at: datetime`
  - `IsolationScope` frozen dataclass: `organization_id: str`, `owner_id: str`
  - `OWNER_ROLE = "owner"`
  - `allocate_owner_id() -> str`
  - `OrganizationService(store: OrganizationStore)` with
    `create_organization(name: str, creator_account_id: str, *, now: datetime) -> Organization`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_rca001_organizations.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from khepri.rca.errors import OrganizationCreationFailed
from khepri.rca.organizations import (
    OWNER_ROLE,
    IsolationScope,
    Membership,
    Organization,
    OrganizationService,
    allocate_owner_id,
)

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
ACCOUNT = "acc_creator"


class MemoryOrganizationStore:
    def __init__(self, *, fail_on_create: bool = False) -> None:
        self.organizations: dict[str, Organization] = {}
        self.memberships: dict[tuple[str, str], Membership] = {}
        self.scopes: dict[str, IsolationScope] = {}
        self.fail_on_create = fail_on_create

    def create_organization(
        self,
        organization: Organization,
        membership: Membership,
        scope: IsolationScope,
    ) -> bool:
        if self.fail_on_create:
            return False
        self.organizations[organization.organization_id] = organization
        self.memberships[(membership.organization_id, membership.account_id)] = membership
        self.scopes[scope.organization_id] = scope
        return True

    def get_membership(self, organization_id: str, account_id: str) -> Membership | None:
        return self.memberships.get((organization_id, account_id))

    def get_scope(self, organization_id: str) -> IsolationScope | None:
        return self.scopes.get(organization_id)


def test_creating_an_organization_makes_the_creator_an_owner() -> None:
    store = MemoryOrganizationStore()
    service = OrganizationService(store)
    organization = service.create_organization("Acme Pharmacy", ACCOUNT, now=NOW)

    membership = store.get_membership(organization.organization_id, ACCOUNT)
    assert membership is not None
    assert membership.role == OWNER_ROLE


def test_membership_creation_is_attributable() -> None:
    store = MemoryOrganizationStore()
    service = OrganizationService(store)
    organization = service.create_organization("Acme Pharmacy", ACCOUNT, now=NOW)

    membership = store.get_membership(organization.organization_id, ACCOUNT)
    assert membership is not None
    assert membership.changed_by == ACCOUNT
    assert membership.changed_at == NOW


def test_creation_allocates_an_isolation_scope() -> None:
    store = MemoryOrganizationStore()
    service = OrganizationService(store)
    organization = service.create_organization("Acme Pharmacy", ACCOUNT, now=NOW)

    scope = store.get_scope(organization.organization_id)
    assert scope is not None
    assert scope.owner_id.startswith("own_")


def test_failed_creation_leaves_nothing_behind() -> None:
    store = MemoryOrganizationStore(fail_on_create=True)
    service = OrganizationService(store)
    with pytest.raises(OrganizationCreationFailed):
        service.create_organization("Acme Pharmacy", ACCOUNT, now=NOW)

    assert store.organizations == {}
    assert store.memberships == {}
    assert store.scopes == {}


def test_allocated_owner_ids_are_distinct() -> None:
    assert len({allocate_owner_id() for _ in range(200)}) == 200


def test_owner_id_shape_matches_the_rra_beta_shape() -> None:
    owner_id = allocate_owner_id()
    assert owner_id.startswith("own_")
    assert len(owner_id) == len("own_") + 24
```

Note on the last test: `secrets.token_urlsafe(18)` yields 24 characters, matching
`src/khepri/rra/sessions.py:126`, so RCA-minted and beta-minted scopes are indistinguishable.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca001_organizations.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'khepri.rca.organizations'`.

- [ ] **Step 3: Write the implementation**

Create `src/khepri/rca/organizations.py`:

```python
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from khepri.rca.errors import OrganizationCreationFailed, _ORGANIZATION_FAILURE

if TYPE_CHECKING:
    from khepri.rca.stores import OrganizationStore

OWNER_ROLE = "owner"


@dataclass(frozen=True, slots=True)
class Organization:
    organization_id: str
    name: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Membership:
    organization_id: str
    account_id: str
    role: str
    changed_by: str
    changed_at: datetime


@dataclass(frozen=True, slots=True)
class IsolationScope:
    organization_id: str
    owner_id: str


def allocate_owner_id() -> str:
    """Allocate a fresh opaque isolation key.

    The key is drawn from a CSPRNG and is never derived from organization data, so no
    commercial identifier can appear in it or be recovered from it (FR-032, FR-033).
    """
    return f"own_{secrets.token_urlsafe(18)}"


class OrganizationService:
    def __init__(self, store: OrganizationStore) -> None:
        self._store = store

    def create_organization(
        self,
        name: str,
        creator_account_id: str,
        *,
        now: datetime,
    ) -> Organization:
        organization = Organization(
            organization_id=f"org_{secrets.token_urlsafe(18)}",
            name=name,
            created_at=now,
        )
        membership = Membership(
            organization_id=organization.organization_id,
            account_id=creator_account_id,
            role=OWNER_ROLE,
            changed_by=creator_account_id,
            changed_at=now,
        )
        scope = IsolationScope(
            organization_id=organization.organization_id,
            owner_id=allocate_owner_id(),
        )
        if not self._store.create_organization(organization, membership, scope):
            raise OrganizationCreationFailed(_ORGANIZATION_FAILURE)
        return organization
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca001_organizations.py -q`
Expected: 6 passed.

- [ ] **Step 5: Verify `stores.py` now imports**

Run: `./.venv/Scripts/python.exe -c "import khepri.rca.stores"`
Expected: no output, exit 0. (Task 1 left this module unimportable; it resolves here.)

- [ ] **Step 6: Lint**

Run: `./.venv/Scripts/python.exe -m ruff check src/khepri/rca/ tests/test_rca001_organizations.py`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add src/khepri/rca/organizations.py tests/test_rca001_organizations.py
git commit --no-gpg-sign -m "feat(rca): add organizations with atomic owner membership (FR-009, FR-010, FR-014)"
```

---

### Task 4: The isolation bridge — FR-031 choke point and its invariants

**Files:**
- Create: `src/khepri/rca/isolation.py`
- Test: `tests/test_rca001_isolation.py`

**Interfaces:**
- Consumes: `ScopeAccessDenied`, `_SCOPE_FAILURE` from `khepri.rca.errors`;
  `OrganizationStore` from `khepri.rca.stores`; `OrganizationService` from
  `khepri.rca.organizations`.
- Produces: `IsolationService(store: OrganizationStore)` with
  `resolve_scope(account_id: str, organization_id: str) -> str`.

**This is the task the slice exists for.** `resolve_scope` returns the durable `owner_id` **and
nothing else** — it does not construct a `SessionScope`. RRA content tables declare composite
foreign keys onto `rra_beta_sessions(owner_id, session_id)`
(`src/khepri/rra/persistence.py:102`), so minting a `session_id` here would require writing into
RRA's own tables, which FR-039 forbids.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_rca001_isolation.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from khepri.rca.errors import ScopeAccessDenied
from khepri.rca.isolation import IsolationService
from khepri.rca.organizations import IsolationScope, Membership, Organization, OrganizationService

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
ACCOUNT = "acc_creator"
OTHER_ACCOUNT = "acc_stranger"

ADVERSARIAL_NAMES = [
    "Acme Pharmacy",
    "own_predictable",
    "owner@example.test",
    "acme-pharmacy",
    "ACME PHARMACY",
    "",
    "a" * 200,
]


class MemoryOrganizationStore:
    def __init__(self) -> None:
        self.organizations: dict[str, Organization] = {}
        self.memberships: dict[tuple[str, str], Membership] = {}
        self.scopes: dict[str, IsolationScope] = {}

    def create_organization(
        self,
        organization: Organization,
        membership: Membership,
        scope: IsolationScope,
    ) -> bool:
        self.organizations[organization.organization_id] = organization
        self.memberships[(membership.organization_id, membership.account_id)] = membership
        self.scopes[scope.organization_id] = scope
        return True

    def get_membership(self, organization_id: str, account_id: str) -> Membership | None:
        return self.memberships.get((organization_id, account_id))

    def get_scope(self, organization_id: str) -> IsolationScope | None:
        return self.scopes.get(organization_id)


def _fixture() -> tuple[MemoryOrganizationStore, OrganizationService, IsolationService]:
    store = MemoryOrganizationStore()
    return store, OrganizationService(store), IsolationService(store)


def test_resolve_scope_returns_the_stored_owner_id() -> None:
    store, organizations, isolation = _fixture()
    organization = organizations.create_organization("Acme", ACCOUNT, now=NOW)

    owner_id = isolation.resolve_scope(ACCOUNT, organization.organization_id)
    stored = store.get_scope(organization.organization_id)
    assert stored is not None
    assert owner_id == stored.owner_id


def test_resolve_scope_returns_a_string_not_a_session_scope() -> None:
    _, organizations, isolation = _fixture()
    organization = organizations.create_organization("Acme", ACCOUNT, now=NOW)

    owner_id = isolation.resolve_scope(ACCOUNT, organization.organization_id)
    assert isinstance(owner_id, str)
    assert not hasattr(owner_id, "session_id")


def test_scope_is_stable_across_repeated_resolutions() -> None:
    _, organizations, isolation = _fixture()
    organization = organizations.create_organization("Acme", ACCOUNT, now=NOW)

    resolutions = {
        isolation.resolve_scope(ACCOUNT, organization.organization_id) for _ in range(5)
    }
    assert len(resolutions) == 1


def test_distinct_organizations_resolve_to_distinct_scopes() -> None:
    _, organizations, isolation = _fixture()
    first = organizations.create_organization("Acme", ACCOUNT, now=NOW)
    second = organizations.create_organization("Acme", ACCOUNT, now=NOW)

    assert first.organization_id != second.organization_id
    assert isolation.resolve_scope(ACCOUNT, first.organization_id) != isolation.resolve_scope(
        ACCOUNT, second.organization_id
    )


def test_no_commercial_identifier_appears_in_a_resolved_scope() -> None:
    _, organizations, isolation = _fixture()
    for name in ADVERSARIAL_NAMES:
        organization = organizations.create_organization(name, ACCOUNT, now=NOW)
        owner_id = isolation.resolve_scope(ACCOUNT, organization.organization_id)
        body = owner_id.removeprefix("own_")
        assert organization.organization_id not in owner_id
        assert ACCOUNT not in owner_id
        if name:
            assert name.lower() not in body.lower()


def test_scope_is_not_reproducible_from_organization_data() -> None:
    _, organizations, isolation = _fixture()
    first = organizations.create_organization("Identical Name", ACCOUNT, now=NOW)
    second = organizations.create_organization("Identical Name", ACCOUNT, now=NOW)

    assert isolation.resolve_scope(ACCOUNT, first.organization_id) != isolation.resolve_scope(
        ACCOUNT, second.organization_id
    )


def test_scopes_do_not_merge_for_multi_organization_membership() -> None:
    store, organizations, isolation = _fixture()
    first = organizations.create_organization("First", ACCOUNT, now=NOW)
    second = organizations.create_organization("Second", ACCOUNT, now=NOW)
    store.memberships[(second.organization_id, ACCOUNT)] = Membership(
        organization_id=second.organization_id,
        account_id=ACCOUNT,
        role="owner",
        changed_by=ACCOUNT,
        changed_at=NOW,
    )

    assert isolation.resolve_scope(ACCOUNT, first.organization_id) != isolation.resolve_scope(
        ACCOUNT, second.organization_id
    )


def test_non_member_is_refused() -> None:
    _, organizations, isolation = _fixture()
    organization = organizations.create_organization("Acme", ACCOUNT, now=NOW)

    with pytest.raises(ScopeAccessDenied):
        isolation.resolve_scope(OTHER_ACCOUNT, organization.organization_id)


def test_refusals_are_uniform_and_content_free() -> None:
    _, organizations, isolation = _fixture()
    organization = organizations.create_organization("Acme", ACCOUNT, now=NOW)

    messages = []
    for account_id, organization_id in (
        (OTHER_ACCOUNT, organization.organization_id),
        (ACCOUNT, "org_does_not_exist"),
        (OTHER_ACCOUNT, "org_does_not_exist"),
    ):
        with pytest.raises(ScopeAccessDenied) as caught:
            isolation.resolve_scope(account_id, organization_id)
        messages.append(str(caught.value))

    assert len(set(messages)) == 1
    assert "org_does_not_exist" not in messages[0]
    assert "Acme" not in messages[0]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca001_isolation.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'khepri.rca.isolation'`.

- [ ] **Step 3: Write the implementation**

Create `src/khepri/rca/isolation.py`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from khepri.rca.errors import ScopeAccessDenied, _SCOPE_FAILURE

if TYPE_CHECKING:
    from khepri.rca.stores import OrganizationStore


class IsolationService:
    """Resolves an organization to its durable opaque isolation key.

    This is the single choke point for the FR-031 mapping. It returns ``owner_id`` only and
    never constructs a ``SessionScope``: RRA content tables declare composite foreign keys
    onto ``rra_beta_sessions(owner_id, session_id)``, so a session identifier minted here
    could not satisfy them without writing into RRA's tables, which FR-039 forbids.
    """

    def __init__(self, store: OrganizationStore) -> None:
        self._store = store

    def resolve_scope(self, account_id: str, organization_id: str) -> str:
        membership = self._store.get_membership(organization_id, account_id)
        if membership is None:
            raise ScopeAccessDenied(_SCOPE_FAILURE)
        scope = self._store.get_scope(organization_id)
        if scope is None:
            raise ScopeAccessDenied(_SCOPE_FAILURE)
        return scope.owner_id
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca001_isolation.py -q`
Expected: 9 passed.

- [ ] **Step 5: Lint**

Run: `./.venv/Scripts/python.exe -m ruff check src/khepri/rca/ tests/test_rca001_isolation.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/khepri/rca/isolation.py tests/test_rca001_isolation.py
git commit --no-gpg-sign -m "feat(rca): add the isolation bridge (FR-031, FR-032, FR-033, FR-035)"
```

---

### Task 5: Persistence — `rca_*` tables and atomic creation

**Files:**
- Create: `src/khepri/rca/persistence.py`
- Test: `tests/test_rca001_persistence.py`

**Interfaces:**
- Consumes: `Account` from `khepri.rca.accounts`; `Organization`, `Membership`, `IsolationScope`
  from `khepri.rca.organizations`.
- Produces: `Base` (`DeclarativeBase`), `AccountRow`, `OrganizationRow`, `MembershipRow`,
  `IsolationScopeRow`, `SqlAccountStore(sessionmaker)`, `SqlOrganizationStore(sessionmaker)`.

Follow the style of `src/khepri/rra/persistence.py`: a module-local `Base`, `Mapped` /
`mapped_column` declarations, `UniqueConstraint` / `ForeignKeyConstraint` in `__table_args__`.
Tables are prefixed `rca_`. **No foreign key may reference an `rra_*` table.**

- [ ] **Step 1: Write the failing tests**

Create `tests/test_rca001_persistence.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.errors import OrganizationCreationFailed
from khepri.rca.isolation import IsolationService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import Base, SqlAccountStore, SqlOrganizationStore

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
EMAIL = "owner@example.test"
CREDENTIAL = "correct horse battery staple"


@pytest.fixture(name="factory")
def _factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(engine)


def test_account_round_trips(factory) -> None:
    service = AccountService(SqlAccountStore(factory))
    created = service.create_account(EMAIL, CREDENTIAL)
    assert service.authenticate(EMAIL, CREDENTIAL).account_id == created.account_id


def test_duplicate_email_is_rejected_by_the_database(factory) -> None:
    from khepri.rca.errors import AuthenticationFailed

    service = AccountService(SqlAccountStore(factory))
    service.create_account(EMAIL, CREDENTIAL)
    with pytest.raises(AuthenticationFailed):
        service.create_account(EMAIL, "another credential")


def test_organization_creation_round_trips(factory) -> None:
    store = SqlOrganizationStore(factory)
    accounts = AccountService(SqlAccountStore(factory))
    account = accounts.create_account(EMAIL, CREDENTIAL)

    organization = OrganizationService(store).create_organization("Acme", account.account_id, now=NOW)
    owner_id = IsolationService(store).resolve_scope(account.account_id, organization.organization_id)
    assert owner_id.startswith("own_")


def test_scope_survives_a_new_store_instance(factory) -> None:
    accounts = AccountService(SqlAccountStore(factory))
    account = accounts.create_account(EMAIL, CREDENTIAL)
    organization = OrganizationService(SqlOrganizationStore(factory)).create_organization(
        "Acme", account.account_id, now=NOW
    )

    first = IsolationService(SqlOrganizationStore(factory)).resolve_scope(
        account.account_id, organization.organization_id
    )
    second = IsolationService(SqlOrganizationStore(factory)).resolve_scope(
        account.account_id, organization.organization_id
    )
    assert first == second


def test_creation_is_atomic_on_conflict(factory) -> None:
    store = SqlOrganizationStore(factory)
    accounts = AccountService(SqlAccountStore(factory))
    account = accounts.create_account(EMAIL, CREDENTIAL)
    service = OrganizationService(store)
    first = service.create_organization("Acme", account.account_id, now=NOW)

    with pytest.raises(OrganizationCreationFailed):
        store.create_organization_raising_duplicate(first, account.account_id, NOW)

    # The failed attempt left no orphan membership or scope row.
    with factory() as session:
        from khepri.rca.persistence import IsolationScopeRow, MembershipRow

        assert session.query(MembershipRow).count() == 1
        assert session.query(IsolationScopeRow).count() == 1


def test_no_rca_table_references_an_rra_table() -> None:
    for table in Base.metadata.tables.values():
        assert table.name.startswith("rca_")
        for constraint in table.foreign_key_constraints:
            for element in constraint.elements:
                assert not element.target_fullname.startswith("rra_")
```

Note: SQLite is used here for speed and because these tests assert store *semantics*, not
Postgres-specific behaviour. `create_all` builds the schema, so no migration is needed for tests.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca001_persistence.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'khepri.rca.persistence'`.

- [ ] **Step 3: Write the implementation**

Create `src/khepri/rca/persistence.py`. Structure (write the full bodies; this is the shape, and
every method listed must exist):

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from khepri.rca.accounts import Account
from khepri.rca.organizations import IsolationScope, Membership, Organization


class Base(DeclarativeBase):
    pass


class AccountRow(Base):
    __tablename__ = "rca_accounts"
    __table_args__ = (UniqueConstraint("email", name="uq_rca_account_email"),)

    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    credential_salt: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    credential_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    kdf_n: Mapped[int] = mapped_column(Integer, nullable=False)
    kdf_r: Mapped[int] = mapped_column(Integer, nullable=False)
    kdf_p: Mapped[int] = mapped_column(Integer, nullable=False)
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class OrganizationRow(Base):
    __tablename__ = "rca_organizations"

    organization_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MembershipRow(Base):
    __tablename__ = "rca_memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id"],
            ["rca_organizations.organization_id"],
            name="fk_rca_membership_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["account_id"],
            ["rca_accounts.account_id"],
            name="fk_rca_membership_account",
            ondelete="RESTRICT",
        ),
    )

    organization_id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    changed_by: Mapped[str] = mapped_column(String, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IsolationScopeRow(Base):
    __tablename__ = "rca_isolation_scopes"
    __table_args__ = (
        UniqueConstraint("owner_id", name="uq_rca_scope_owner"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["rca_organizations.organization_id"],
            name="fk_rca_scope_organization",
            ondelete="RESTRICT",
        ),
    )

    organization_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False)
```

Then the two stores. `SqlAccountStore` implements `add_account` (returning `False` on
`IntegrityError` after `session.rollback()`), `get_account_by_email`, `get_account`,
`update_account`. `SqlOrganizationStore` implements `create_organization` — **all three rows added
inside one `with factory() as session:` block committed once**, returning `False` on
`IntegrityError` — plus `get_membership`, `get_scope`, and the test helper
`create_organization_raising_duplicate(organization, account_id, now)` which attempts to re-insert
an existing organization id and raises `OrganizationCreationFailed`.

Each store method converts rows to the frozen dataclasses from Tasks 2–3; never return a Row.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca001_persistence.py -q`
Expected: 6 passed.

- [ ] **Step 5: Lint**

Run: `./.venv/Scripts/python.exe -m ruff check src/khepri/rca/ tests/test_rca001_persistence.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/khepri/rca/persistence.py tests/test_rca001_persistence.py
git commit --no-gpg-sign -m "feat(rca): persist accounts, organizations, and scopes atomically"
```

---

### Task 6: FR-039 boundary — RRA independence, asserted

**Files:**
- Create: `tests/test_rca001_boundary.py`

**Interfaces:**
- Consumes: nothing at runtime; inspects source files and module metadata.
- Produces: nothing importable.

- [ ] **Step 1: Write the test**

Create `tests/test_rca001_boundary.py`:

```python
from __future__ import annotations

from pathlib import Path

RRA_DIR = Path(__file__).resolve().parents[1] / "src" / "khepri" / "rra"
RCA_DIR = Path(__file__).resolve().parents[1] / "src" / "khepri" / "rca"


def test_no_rra_module_imports_rca() -> None:
    offenders = [
        path.name
        for path in sorted(RRA_DIR.glob("*.py"))
        if "khepri.rca" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_rca_package_exists_and_is_importable() -> None:
    assert (RCA_DIR / "__init__.py").exists()


def test_rca_declares_no_rra_table_dependency() -> None:
    from khepri.rca.persistence import Base

    for table in Base.metadata.tables.values():
        assert table.name.startswith("rca_")
```

- [ ] **Step 2: Run it to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca001_boundary.py -q`
Expected: 3 passed. (This test passes immediately — it guards a property Tasks 1–5 must not have
broken. If it fails, an earlier task violated the import direction.)

- [ ] **Step 3: Run the FR-039 regression — the whole existing suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: **1561 + 32 new = 1593 passed, 9 skipped.** The 1561 pre-existing tests must pass
unmodified. If any previously-passing RRA test now fails, FR-039 is violated — stop and fix.

- [ ] **Step 4: Governance validation and lint**

```bash
./.venv/Scripts/python.exe -m khepri_gov.cli validate
./.venv/Scripts/python.exe -m ruff check src/ tests/
```

Expected: `Governance validation passed.` and `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add tests/test_rca001_boundary.py
git commit --no-gpg-sign -m "test(rca): assert the RCA to RRA import boundary (FR-039)"
```

---

## Verification Gate

Run before opening a PR:

```bash
./.venv/Scripts/python.exe -m khepri_gov.cli validate
./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/python.exe -m ruff check src/ tests/
```

**Do NOT run `ruff format`.** There is no format gate in `.github/workflows/governance.yml` (it
runs `ruff check .` only), and the local ruff is version-skewed against the lockfile pin — running
it would reformat ~86 unrelated files.

CodeScene pre-flight: `git fetch origin` first (a stale `origin/main` makes `analyze_change_set`
return an empty, meaningless pass), then analyze against `origin/main`. Every file in this slice is
new, so all of them will be scored.

## Requirement Coverage

| Requirement | Task |
|---|---|
| FR-001 durable account | 2 |
| FR-002 credential hashed only | 2 |
| FR-004 uniform authentication failure | 2 |
| FR-009 organization is a durable scope | 3 |
| FR-010 creator is owner, atomically | 3, 5 |
| FR-014 membership change is attributable | 3 |
| FR-031 actor + organization maps to the scope | 4 |
| FR-032 no commercial identifier in the key | 3 (allocation), 4 (asserted) |
| FR-033 scope remains opaque | 3, 4 |
| FR-034 cross-scope access fails closed, content-free | 4 (`test_refusals_are_uniform_and_content_free`) |
| FR-035 stable and distinct scopes | 4 |
| FR-037 no weakening of RRA controls | 6 |
| FR-039 RRA independently testable | 6 |
| FR-040 content-free logging | 1 (message constants), 4 (asserted) |

FR-035's "scopes do not merge for an account in two organizations" is scenario 12 and is asserted by
`test_scopes_do_not_merge_for_multi_organization_membership` in Task 4. Note this exercises the
*scope* consequence of multi-organization membership; FR-011's membership mechanics (joining a
second organization through the normal path rather than a direct store write) belong to the
membership slice.

Deferred to later slices, per the design: FR-003 and FR-005–008 (sessions, recovery, disable
semantics on live sessions), FR-011–013 (membership mechanics, revocation, final-owner guard),
FR-015 (role transitions), FR-016–020 (invitations), FR-021–030 (the authorization checkpoint and
active-organization switching), FR-036, FR-038.
