# RCA construction-boundary stance

Design for issue #151. Decided 2026-08-13. Owner selected the options recorded under
"Decisions"; every subsequent judgment call made while implementing unattended is recorded
under "Judgment calls made without the owner".

## Problem

`khepri.rca`'s records are inconsistent about who guards their invariants. PR #148 ran four
consecutive review rounds, each fixing the previous round's finding and surfacing the next:

| Round | Finding | Fix | What it produced |
|---|---|---|---|
| 1 | service validated the isolation key, store did not | validate in service | store callers bypass the service |
| 2 | a store caller could persist `owner@example.test` as the key | validate the key's shape | shape ≠ provenance |
| 3 | shape cannot establish CSPRNG provenance | type allocates its own key; add `restore` | `restore` is itself a bypass |
| 4 | `IsolationScope.restore("org", "owner@example.test")` reaches the store | — | *(stopped here)* |

Round 3's fix produced round 4's finding. The loop does not terminate by local fixes, because
each one answers "who validates?" for one record while leaving the others open.

Two findings remain open from #148, both valid as stated:

1. **`IsolationScope.restore` is a public reconstruction bypass** (`src/khepri/rca/organizations.py`).
2. **Credential material is accepted verbatim at the store** (`src/khepri/rca/persistence.py`) —
   an `Account` with `credential_digest=credential.encode()` and an empty salt commits,
   retaining a recoverable credential in violation of FR-002.

Neither is reachable today. Verified on `c98d04e` by grep across `src/`: there are **zero**
references to `AccountStore`, `OrganizationStore`, `SqlAccountStore`, `SqlOrganizationStore`,
`add_account`, or `create_organization` outside `src/khepri/rca/`. Both findings describe
hardening against a hypothetical in-process caller, not a defect in shipped behaviour.

## Decisions

Owner selected, 2026-08-13:

| # | Question | Decision |
|---|---|---|
| Q1 | Who may call the store protocols? | **Internal to `khepri.rca` only** |
| Q2 | Construction stance | **Sealed value objects (two doors)** |
| Q3 | Scope | **RCA now; RRA tracked as a follow-up issue** |
| Q4 | `hash_credential` visibility | **Public, but moved to a `credentials` module** |
| Q5 | Sequencing | **#151 first, then #149, then #150** |
| Q6 | Issue #43 | **Close as obsolete, with a pointer to governance v2** |

Q1=A and Q2=B are not in tension. Even with stores internal, the sealed form is worth taking
because `IsolationScope` is *already* half-sealed, and the half-measure is what generated
rounds 3 and 4. Reverting to anemic records would re-open a hole we have already found.

## Architecture: the two-door rule

Every record in `khepri.rca` — `Account`, `Organization`, `Membership`, `IsolationScope` —
exposes exactly two construction doors.

| Door | Name | Caller | Guarantee |
|---|---|---|---|
| Creation | `Record.create(...)` | service layer | allocates identifiers, validates invariants, derives verifiers |
| Reconstruction | `Record._from_storage(...)` | `persistence.py` only | preserves stored values verbatim, asserts nothing |

Mechanism: **the capability belongs to the call, not to the object.** Each record keeps
`@dataclass(frozen=True, slots=True)`, subclasses `Sealed`, and builds instances inside a
`through_door()` context manager. `Sealed.__post_init__` raises `TypeError` unless a door is
open on the current thread (a re-entrant depth counter on a `threading.local`, so nested
construction works and one thread cannot authorize another).

### Round five: why the capability is not a field

The first implementation made it an instance field holding a module-private sentinel, with
`compare=False, repr=False, kw_only=True`. Independent review of that commit (`fca3252`) found
a third door, and the exploit was reproduced end to end before the fix:

```python
forged = dataclasses.replace(IsolationScope.create(org), owner_id="own_VictimPharmacyInc000000")
store.create_organization(org, membership, forged)   # returns True, commits
isolation.resolve_scope(...)                          # -> "own_VictimPharmacyInc000000"
```

`dataclasses.replace` rebuilds an instance by reading every field the caller did not override
and calling `cls(**fields)` — so it copied the sentinel forward onto a record whose isolation
key had just been substituted. That is **verbatim the round-2 defect from #148** (an
organization name inside the "opaque" key), reachable again through one idiomatic stdlib call.

The error was certifying *"this object came through a door"* when what needs certifying is
*"this call is a door"*. A field is per-instance state, and `replace` copies per-instance
state. Moving the capability into the call stack leaves nothing to copy forward.

This also removed a trap the field design had set for the next two slices: on a frozen
dataclass, `dataclasses.replace(account, verifier=None)` is the obvious way to write #149's
verifier destruction, and `dataclasses.replace(membership, role="owner")` the obvious way to
write #150's role transition. Both produced sealed, store-acceptable records. Both are now
refused, which forces those slices to express a change as an operation rather than a field
assignment — the correct shape for them anyway.

Note that a `__replace__` method would **not** have fixed this: `dataclasses.replace` calls
`cls(**changes)` directly and never consults `obj.__replace__`, so defining one blocks
`copy.replace` while leaving `dataclasses.replace` exactly as open. Verified.

### Substitution is blocked; faithful duplication is not

`copy.copy`, `copy.deepcopy`, and `pickle` are deliberately **not** blocked. On a slotted
dataclass they allocate via `__class__.__new__` and restore state through `__reduce_ex__`,
never calling `__init__`, so no check applies — blocking them would mean fighting the pickle
protocol. It is also unnecessary: they reproduce every field verbatim and expose no parameter
through which a caller's value can enter, so a copy of a legitimate record is a legitimate
record. The property that matters is that **substitution** is refused, not duplication. A test
pins this distinction so a future change making a copy protocol field-substitutable fails.

### `Verifier` is sealed too

Review also found that sealing the records was not enough while `Verifier` stayed open.
`Account._from_storage` accepts whatever `Verifier` it is handed without re-deriving — it must,
since a stored digest is the only thing a candidate can be compared against — so an unsealed
`Verifier` let an in-package caller choose credential material for an account whose own
provenance check then passed. The two-door rule has to reach the material, not only the record
that carries it.

### What this is not

`object.__setattr__` still bypasses `frozen`, and any module can call `through_door()` itself.
**Python has no private construction.** The guarantee is that a bypass must be *deliberate and
conspicuous*, not that it is impossible.

`dataclasses.replace` was precisely the opposite — an accidental, idiomatic bypass — which is
what made it worth a redesign rather than a documented caveat. That is the line: a mechanism
that a careful engineer could trip over while writing ordinary code is a defect; one that
requires reaching for `object.__setattr__` is a documented limit.

Docstrings must therefore say "unmistakable", never "unbypassable". The existing docstring at
`organizations.py:56-57` — "no layer can construct a scope carrying an untrusted key" — is an
overclaim of exactly this kind, and overclaiming is part of what let #148's rounds continue:
each round trusted the previous round's docstring instead of the code.

### Why `restore` is replaced rather than renamed

The current `restore` (`organizations.py:66-78`) calls `cls(organization_id=...)`, which runs
`__post_init__` and allocates a fresh CSPRNG key, then immediately overwrites it via
`object.__setattr__`. Every read from storage burns a `secrets.token_urlsafe(18)` draw and
discards it. `_from_storage` sets the field directly through the normal constructor path: no
wasted draw, and no "construct then clobber" idiom to mislead the next reader.

## Components

### `khepri/rca/credentials.py` (new, Q4=C)

Owns credential material end to end, so "make a verifier" and "destroy a verifier" are one
trusted operation each rather than field assignments scattered across layers.

Moved from `accounts.py`: `KDF_N`, `KDF_R`, `KDF_P`, `KDF_DKLEN`, `SALT_BYTES`, `_DUMMY_SALT`,
`KdfParams`, `DEFAULT_KDF`, `hash_credential`. Added: `Verifier` (a frozen record of
`salt`/`digest`/`kdf`) and `Verifier.derive(credential)`, which allocates the salt itself.

`Account.create` then takes `(email, credential)` and calls `Verifier.derive` — closing finding
2, because there is no path that accepts a caller-supplied digest for a *new* account.
`Account._from_storage` still takes the three stored columns verbatim, since a stored verifier
must round-trip unchanged.

This also gives #149 a home for non-recoverable verifier destruction (`KHEPRI-DEC-015`) instead
of forcing that slice to invent one.

### `khepri/rca/organizations.py`

`IsolationScope` loses `field(init=False)`, `__post_init__`'s allocation, and `restore`. It
gains `create(organization_id)` — which has **no `owner_id` parameter**, so an untrusted key is
not merely rejected but unexpressible — and `_from_storage(organization_id, owner_id)`.
`allocate_owner_id` stays public: it is a pure function, tested directly for distinctness, and
carries no invariant to protect.

`Organization` and `Membership` take the same two doors. `Organization.create(name, now)`
allocates the `org_` identifier; `Membership.create(...)` takes the role explicitly.

### `khepri/rca/persistence.py`

`_account_from_row`, `_membership_from_row`, and `_scope_from_row` switch to `_from_storage`.
`add_account` and `create_organization` gain an assertion that their inputs carry the sentinel,
turning "documented as internal" into a runtime check. The existing aggregate-identity checks
in `create_organization` are unchanged.

### `khepri/rca/stores.py`, `accounts.py`, `isolation.py`

Protocols unchanged. `AccountService.create_account` and `OrganizationService.create_organization`
delegate allocation to `create()` instead of building records inline. `isolation.py` is untouched
by this slice — `resolve_scope`'s failure to refuse a disabled account is #149's, because
disablement does not exist yet.

## Data flow

```
create:   Service ── Record.create(domain args) ──▶ record ──▶ Store.add/create ──▶ row
read:     row ──▶ Record._from_storage(columns) ──▶ record ──▶ Service ──▶ caller
```

Creation flows one way and reconstruction the other; the two never meet. A record built by
`_from_storage` is never handed to a creation path, and `create()` cannot accept a stored key.

## Error handling

Unchanged and deliberately uniform. `AuthenticationFailed`, `ScopeAccessDenied`, and
`OrganizationCreationFailed` keep their content-free messages (FR-004, FR-034).

Sentinel violations raise `TypeError`, not a domain error. That is correct: reaching a sealed
constructor is a programming error inside `khepri.rca`, not a runtime condition a caller can
handle, and it must never be caught and converted into a content-free refusal — that would hide
a bug behind a security message.

## Testing

The load-bearing risk is **tests that pass for the wrong reason**, which is how #148's findings
survived review. Three specific cases, all identified before the refactor:

1. **`test_rca001_persistence.py:268` would pass vacuously.** It asserts
   `pytest.raises(TypeError)` on `IsolationScope(organization_id="org_1", owner_id=untrusted)`.
   Today that raises because `owner_id` is `init=False`; after the refactor it raises because
   `_token` is missing. Same exception, different reason, and the property under test —
   "an untrusted key cannot enter a scope" — would no longer be exercised at all. Confirmed by
   running the probe. Replace it with a signature assertion: `"owner_id" not in
   inspect.signature(IsolationScope.create).parameters`, plus a check that a created key does
   not contain the untrusted input.

2. **`test_rca001_persistence.py:283`** exercises `IsolationScope.restore`, which is being
   removed. Rewrite against `_from_storage`, keeping the FR-035 stability property it asserts.

3. **`test_rca001_accounts.py:126` monkeypatches `accounts_module.hash_credential`** to count
   scrypt calls, which is how FR-004's uniform-cost property is verified. Moving the function to
   `credentials.py` orphans that patch target: the recorder never fires, `calls` stays empty, and
   `dict.fromkeys(totals, [DEFAULT_KDF])` compares `{} == {}` — green, testing nothing. Repoint
   the patch **and** add an explicit non-empty assertion before each uniformity comparison
   (`:154` and `:262`) so an unfired recorder fails loudly.

Every guard added by this slice is mutation-tested: break the guard, confirm the test goes red,
restore it. A guard whose test still passes when the guard is removed is not a guard. **9/9
mutations caught**, including a deliberate re-introduction of the round-five forgery.

Mutation testing found one real gap on its first run: the partial-verifier guard in
`_verifier_from_row` had no test defending it, because no existing test writes a
partially-populated row. Flipping `any` to `all` left the whole suite green. That is exactly
the guard #149 leans on hardest, so it now has a parametrized test over each way a row can be
half-destroyed.

**Mutation testing cannot find a missing guard**, only an untested one — it perturbs code that
exists. The `dataclasses.replace` hole was invisible to it and was caught by adversarial
review instead. Both were needed; neither would have sufficed.

New coverage: direct construction of each of the four records raises; `create()` signatures
exclude stored-only fields; `_from_storage` round-trips verbatim; a store rejects a record that
did not come through a door; `Verifier.derive` never yields a digest equal to the encoded
credential (finding 2, asserted directly).

## Judgment calls made without the owner

The owner authorized unattended execution after selecting Q1–Q6 and went offline. These were
decided during implementation and are flagged for audit:

- **Call-scoped capability over `__init_subclass__`, metaclasses, or builder classes.**
  Smallest change that closes the findings while keeping records as plain dataclasses. Chosen
  after the instance-field version failed review; see "Round five" above.
- **`threading.local` rather than a module global.** A store may be used from several threads,
  and one thread's construction must not authorize another's.
- **Copy protocols left alone** rather than blocked via `__reduce__`. Reasoned above: they
  cannot substitute a field, so they add no exposure, and overriding them would fight the
  pickle protocol for no security gain.
- **`allocate_owner_id` stays public** while `hash_credential` moves. Asymmetric, but they
  differ: the former protects no invariant and is tested directly for distinctness; the latter
  is the operation finding 2 is about.
- **Stores assert the sentinel rather than re-validating field contents.** Re-validating shape
  is what round 2 already proved insufficient.
- **`isolation.py` untouched.** The disabled-account gap is real but unreachable until
  disablement exists; fixing it here would mean inventing disablement outside its slice, which
  is the #148 failure mode.

## Follow-ups this creates

- **RRA stance (Q3).** File an issue: `khepri.rra` has the same frozen-dataclass + `Protocol`
  shape across ~40 modules. Same reasoning applies; the migration is large and separate.
- **#149** inherits `credentials.py` for verifier destruction and keeps its own four design
  questions (tombstone shape, purge trigger, service placement, revocation ledger) open.
- **#150** inherits the two-door form for `Membership` and the `rca_membership_events`
  redesign.

## Verification

`uv run khepri-gov validate`, `uv run ruff check .`, and `uv run pytest` must pass, plus a
CodeScene pre-flight against a freshly fetched `origin/main` — `credentials.py` is a new file
and every new file is scored.
