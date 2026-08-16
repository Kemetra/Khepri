# KHEPRI-DEC-019: Commercial attachment to the opaque analysis scope

> Active. Stands beside `KHEPRI-DEC-014` and `KHEPRI-DEC-018`; supersedes nothing.
>
> `active` is the only non-retired state the registry admits (`validator.py:15`), and a branch is a
> proposal until the owner merges it (`AGENTS.md`). This record is therefore written in its merged
> form and is **not governing until that merge** — the header states the state it will hold, not a
> claim that it already holds it.

## Context

`R6` is merged (`#192`…`#195`, `#197`…`#200`). An authenticated actor resolves to an
`AuthorizationContext` carrying an account, an active organization, and a live role, and
`IsolationService.resolve_scope` maps an organization to its stable opaque `owner_id`
(`FR-031`, `FR-035`).

`R7` must connect that scope to an RRA analysis session, and the `R7-01` design note
(`docs/superpowers/specs/2026-08-16-r7-01-commercial-bridge-design.md`) establishes that it cannot,
because of a structural fact verified in the code rather than assumed.

### The structural fact

Four `RRA` content tables declare composite foreign keys onto
`rra_beta_sessions(owner_id, session_id)` (`persistence.py:109`, `:149`, `:202`, `:246`), so a row
in that table is the precondition for any retail content existing. Exactly one code path writes
one — `InvitationService.redeem` (`sessions.py:125`) — and it mints its own scope:

```python
owner_id=f"own_{secrets.token_urlsafe(18)}"      # sessions.py:126 — fresh, per redemption
```

`FR-035` requires **one organization to resolve to a stable scope across sessions**, and
`allocate_owner_id` (`organizations.py:151`) already mints exactly one per organization. A
commercial actor redeeming an invitation would therefore hold two unrelated scopes, and content
written under the session would be invisible to the organization that owns it.

`R7-01` §2 closes the two alternatives. `RCA` cannot write the `rra_` row: `FR-039` requires `RRA`
to remain independently testable and `test_rca_declares_no_rra_table_dependency` asserts every
`RCA` table is `rca_`-prefixed — `isolation.py:14-17` already records this reasoning verbatim. And
a commercial actor cannot redeem a beta invitation, because that breaks `FR-035` and makes
commercial access depend on the invitation secrets `FR-016`…`FR-020` place under `R4`.

### What already constrains the answer, and reframes it

`RRA-001` anticipated this case. Its Requirements section reads:

> "Preserve the opaque owner ID as **the only future attachment point for separately approved
> commercial authentication**."

That clause does two things. It reserves the `owner_id` as the attachment point for exactly this
purpose, and it requires that reaching it be **separately approved**. This decision is that
approval. The commercial bridge is therefore not a widening of `RRA-001` but the use of a mechanism
`RRA-001` set aside for it, which is why this record admits a shape rather than amending a
specification.

**A note on `RRA-001`'s footer, because a reader checking the citation will hit it.** `RRA-001`
ends "This specification is draft and does not authorize product implementation," and ten
specifications carry that line while `governance/registry.yaml` marks them `active` and their code
is merged and shipping. `AGENTS.md` resolves the conflict: the registry "is authoritative for
artifact type, identity, state," and "Markdown rationale cannot override it." The registry records
`RRA-001` as `active`, so it governs and the footer is stale prose. The staleness is reported here,
not corrected — a decision record is not the vehicle for a specification's prose pass.

### Why this is not a specification question

`RRA-001` already permits the attachment at requirement level, exactly as `RCA-001`'s assumption
`A-4` permitted external identity at plan level before `KHEPRI-DEC-018`. What a specification
cannot do is authorize the boundary change itself. This decision supplies the missing authority and
nothing more. No `RRA-001` amendment is made and none is required.

## Decision

### 1. The governing principle

> **The organization's scope is the analysis scope. `RRA` never learns whose it is.**

`RCA` decides *which* opaque key a request acts under. `RRA` decides everything about the analysis
performed under it. Exactly one value crosses the boundary, and it carries no commercial meaning.

### 2. What is admitted

`RRA` may grow **one additive entry point** that creates an analysis session against a
caller-supplied opaque `owner_id`, rather than minting one.

Its shape, fixed here so `R7-02` implements rather than re-decides:

- It is a **new function**, sibling to `redeem`. `redeem` is not modified, not parameterised, and
  not called by it.
- It accepts an opaque `owner_id` and mints its own `session_id`. `session_id` remains `RRA`'s to
  allocate: it is per-analysis, not per-organization, and `FR-035` says nothing about it.
- It accepts **nothing else** that identifies a caller. No account, no organization, no email, no
  name, no slug.
- It performs **no authorization**. The caller has already been authorized; a second check inside
  `RRA` would put one rule in two places, which is the drift `R6-04` and `R2` both took care to
  avoid.

### 3. Why this does not weaken `FR-037`

`FR-037` requires that `RCA-001` not weaken `RRA-001`'s or `RRA-002`'s controls, naming them:
opaque identifiers, cross-session isolation failing closed, encryption in transit and at rest,
isolated object namespaces, immediate idempotent deletion, and content-free logging.

The control named is **opacity**, not provenance, and opacity is untouched — the two minting sites
are the same construction character for character:

```python
f"own_{secrets.token_urlsafe(18)}"     # sessions.py:126   (RRA, per redemption)
f"{_OWNER_ID_PREFIX}{secrets.token_urlsafe(18)}"   # organizations.py:151  (RCA, per organization)
```

Eighteen CSPRNG bytes rendered as twenty-four URL-safe characters, in both cases. Further,
`allocate_owner_id` takes **no argument at all**, so it cannot encode a commercial identifier even
by mistake — `FR-032` and `FR-033` are satisfied by construction rather than by review.

Every other control in `FR-037`'s list is a property of what happens *after* a session exists, and
is unaffected by which function created it.

### 4. The obligations this decision imposes

Each is testable, and `R7` does not satisfy this decision by assertion:

1. **`RRA`'s existing tests pass unmodified.** `FR-037` requires its controls remain "covered by its
   existing tests, unmodified". `redeem` has exactly one production caller (`api.py:166`) and its
   tests call it directly, so an additive sibling leaves all of it untouched. **If implementing `R7`
   requires editing any `test_rra*` file, that is a conflict with this decision and must be
   recorded, not resolved by editing the test.**
2. **`RRA` remains independently testable** (`FR-039`): its tests must pass with no account, no
   organization, and no membership existing. The new entry point is never reached by them.
3. **The beta path is unchanged.** A participant with no account redeems an invitation and proceeds
   exactly as today. `R7-04` is the regression evidence.
4. **The caller resolves the scope; it never receives one.** `owner_id` reaches the entry point only
   from `IsolationService.resolve_scope`, never from a request parameter — `R6-01` §5's critical
   rule, that object identifiers never grant authority, applies unchanged.
5. **No second minting site.** `allocate_owner_id` remains the single definition of an
   organization's scope. A bridge that minted its own would break `FR-035`'s stability clause, and
   the identical construction in §3 makes that mistake easy to write and hard to see.

### 5. What this decision does not authorize

- **No product code.** No bridge service, no entry-point implementation, no `R7-02` or later slice
  is authorized here. This admits a shape; slices remain separately reviewable.
- **No endpoint.** `R7-05`'s HTTP surface is not settled, proposed, or implied.
- **No schema or migration**, in either package.
- **No `RRA-001`, `RRA-002`, or `RCA-001` amendment.** See "Why this is not a specification
  question".
- **No change to `redeem`**, its signature, its behavior, or the invitation lifecycle.
- **No authorization inside `RRA`.** `RRA` gains no ability to decide who may act; it gains one
  parameter it does not interpret.
- **No commercial identifier crossing the boundary.** `FR-032` and `FR-033` are unaffected and
  unweakened.
- **No public signup, billing, durable report history, or changed content retention** — `R7`'s
  non-goals are untouched.
- **No relocation of authoritative retail calculation into `RCA`** (`FR-036`).

## Consequences

- `R7-02` may proceed once this record is merged, implementing §2's shape and satisfying §4's
  obligations. It remains a separately reviewed slice.
- `R7-01` §6's open question is answered. Its §2 table's third row is the admitted shape, and the
  note's framing of it as a reluctant last resort is superseded by `RRA-001`'s own reservation
  clause.
- **`R6-08`'s `test_the_resolver_has_no_production_consumer_yet` will fail** when `R7-05` wires a
  consumer. Its docstring instructs its own replacement; relaxing it instead would discard the
  chokepoint evidence that slice exists to provide.
- Two carried gaps in `specs/001-rca-001-commercial-identity/STATUS.md` become closable by `R7`:
  `resolve_scope`'s unauthenticated matrix cell gains an authenticated boundary, and `FR-023`'s
  object-level half gains an object-level path to test.
- `KHEPRI-DEC-008`, `KHEPRI-DEC-014`, `KHEPRI-DEC-015`, `KHEPRI-DEC-017`, and `KHEPRI-DEC-018` are
  unaffected and not superseded.
- The commercial thesis behind the phase ordering remains an untested assumption, as
  `KHEPRI-DEC-014` records. This decision does not change that.

---

Identity, state, document, dependencies, and supersession are authoritative in
`governance/registry.yaml`.
