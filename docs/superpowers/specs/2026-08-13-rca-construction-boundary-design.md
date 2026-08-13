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

Mechanism: each record keeps `@dataclass(frozen=True, slots=True)` and gains

```python
_token: object = field(kw_only=True, compare=False, repr=False, default=None)
```

with a `__post_init__` that raises `TypeError` unless `_token` is the module-private sentinel.
`kw_only=True` sidesteps the default/non-default field-ordering rule; `compare=False` and
`repr=False` keep the sentinel out of `__eq__`, `__hash__`, and `__repr__`.

All of this was validated empirically before any refactor
(scratch probe, 2026-08-13, all eleven checks passing): sentinel excluded from equality and
repr, records still hashable, `kw_only` ordering legal, direct construction rejected,
`create()` refusing an `owner_id` argument, and `_from_storage` preserving a stored key.

### What this is not

`object.__setattr__` still bypasses `frozen`, and any module can import a name beginning with
an underscore. **Python has no private construction.** The guarantee is that a bypass must be
*deliberate and conspicuous*, not that it is impossible.

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
restore it. A guard whose test still passes when the guard is removed is not a guard.

New coverage: direct construction of each of the four records raises; `create()` signatures
exclude stored-only fields; `_from_storage` round-trips verbatim; a store rejects a record that
did not come through a door; `Verifier.derive` never yields a digest equal to the encoded
credential (finding 2, asserted directly).

## Judgment calls made without the owner

The owner authorized unattended execution after selecting Q1–Q6 and went offline. These were
decided during implementation and are flagged for audit:

- **Sentinel over `__init_subclass__`, metaclasses, or a separate builder class.** Smallest
  change that closes both findings; keeps records as plain dataclasses.
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
