# KHEPRI-DEC-020: Commercial attachment to the opaque analysis scope, with the schema change it requires

> Active. **Supersedes `KHEPRI-DEC-019`**, which is retired by this record. Stands beside
> `KHEPRI-DEC-014` and `KHEPRI-DEC-018`.
>
> `active` is the only non-retired state the registry admits (`validator.py:15`), and a branch is a
> proposal until the owner merges it (`AGENTS.md`). This record is therefore written in its merged
> form and is **not governing until that merge** — the header states the state it will hold, not a
> claim that it already holds it.

## Context

`KHEPRI-DEC-019` (`00e0f47`) admitted an additive `RRA` entry point creating an analysis session
against a caller-supplied opaque `owner_id`. `R7-02` then found, before writing the bridge, that the
record contradicts itself, and recorded the finding rather than resolving it
(`docs/superpowers/specs/2026-08-17-r7-02-schema-cardinality-finding.md`, `9bfae82`).

**This record exists to resolve that contradiction, and supersession is the only available
instrument.** `KHEPRI-DEC-019` cannot be amended in place: supersession under `KHEPRI-DEC-017` is
whole-document, and editing a governing record to admit what it forbids would rewrite history rather
than correct it. The owner selected **Option A** from the finding's §5 on 2026-08-17.

### The contradiction, stated exactly

`KHEPRI-DEC-019` §2 admits an entry point that creates a session against a supplied `owner_id`. Its
§5 forbids "No schema or migration, in either package."

Both cannot hold. `rra_beta_sessions.owner_id` carries a `UNIQUE` constraint, so one `owner_id`
backs **exactly one session, ever**, while a commercial organization holds one stable `owner_id` for
its lifetime (`FR-035`). The admitted entry point can be written; its second call raises
`IntegrityError`.

**`KHEPRI-DEC-019` §5 was therefore wrong as written** — it forbade the change its own §2 required.
That is a defect in the record, not in `RRA`, not in `RCA-001`, and not in the implementer who found
it. `RRA`'s single-analysis-per-scope shape is coherent for a private beta and was never a defect;
it is a beta assumption encoded as a database invariant, which `RRA-001`'s "only future attachment
point for separately approved commercial authentication" clause did not anticipate.

### The evidence, re-verified for this record

Probed against live ORM metadata rather than read from the migration, because a schema claim
deserves the same standard as a test claim:

```
rra_beta_sessions   UNIQUE (owner_id)              anonymous — from column unique=True
rra_beta_sessions   UNIQUE (owner_id, session_id)  named uq_session_owner_scope
rra_uploads         UNIQUE (session_id)
```

Two constraints on one table disagree about what is unique. `uq_session_owner_scope` says a scope
may hold many sessions and each pairing is distinct; the anonymous column-level constraint says it
may hold one. The composite one already expresses the real invariant.

**A detail that governs the migration.** The constraint to be dropped is **anonymous** in both the
ORM (`persistence.py:74`, `unique=True` on the column) and the emitted DDL — it has no name in
`__table_args__`. PostgreSQL will have auto-assigned one. That name was **not verified for this
record**: `KHEPRI_TEST_DATABASE_URL` is unset in this environment and no PostgreSQL is reachable, so
47 tests skip. The implementing slice must read the name from the live catalogue rather than assume
the conventional `rra_beta_sessions_owner_id_key`, and must not hardcode a name it has not observed.

## Decision

### 1. Everything `KHEPRI-DEC-019` decided is carried forward unchanged

This record re-enacts, without modification of substance, `KHEPRI-DEC-019`'s:

- **§1 governing principle** — "The organization's scope is the analysis scope. `RRA` never learns
  whose it is." `RCA` decides which opaque key a request acts under; `RRA` decides everything about
  the analysis performed under it. Exactly one value crosses, carrying no commercial meaning.
- **§2 admitted shape** — one additive entry point, sibling to `redeem`, accepting an opaque
  `owner_id` and minting its own `session_id`, accepting nothing else that identifies a caller, and
  performing no authorization. `redeem` is not modified, not parameterised, and not called by it.
- **§3 `FR-037` analysis** — the control named is opacity, not provenance, and both minting sites are
  the same construction character for character. `allocate_owner_id` takes no argument, so `FR-032`
  and `FR-033` are satisfied by construction.
- **§4 obligations**, all five, unweakened: `RRA`'s existing tests pass unmodified; `RRA` remains
  independently testable with no account, organization, or membership; the beta path is unchanged;
  the caller resolves the scope and never receives one; and `allocate_owner_id` remains the single
  minting site.

The reasoning in `KHEPRI-DEC-019`'s Context — why this is not a specification question, why `RCA`
cannot write the `rra_` row, why a commercial actor cannot redeem a beta invitation, and the note on
`RRA-001`'s stale draft footer — stands as written and is not restated here.

### 2. What this record additionally authorizes

**One migration on `rra_beta_sessions`, dropping the anonymous `UNIQUE (owner_id)` constraint and
nothing else.**

Fixed here so the implementing slice implements rather than re-decides:

- `UNIQUE (owner_id, session_id)` (`uq_session_owner_scope`) is **retained**. It is the constraint
  that expresses the real invariant, and dropping both would leave the scope-session pairing
  unconstrained.
- `owner_id` remains `NOT NULL`. **No replacement index is required, and the slice must not add
  one** — `uq_session_owner_scope` is `UNIQUE (owner_id, session_id)` and `owner_id` is its
  **leading column**, so its backing index already serves `owner_id`-only lookups after the drop.
  Verified by probe: the table's only explicit index is
  `ix_rra_beta_sessions_content_expires_at`, and `owner_id` carries no `index=` flag, so today its
  lookups ride on the constraint being dropped. `artifact_persistence.py:427-433` queries
  `owner_id` under `SELECT … FOR UPDATE`, which is why this was checked rather than assumed. The
  retained composite constraint is what makes the drop safe, and is a second reason not to drop
  both.
- The ORM changes correspondingly: `unique=True` comes off `persistence.py:74`. A migration that
  changes the database while leaving the ORM asserting uniqueness would leave two sources disagreeing
  about one fact.
- The migration is **reversible**. Its `downgrade` restores the constraint, and will fail if
  commercial rows already violate it — which is correct, and must be stated in the migration's
  docstring rather than worked around.
- The constraint name is **read from the live catalogue**, not assumed. See the note above.

### 3. What this record still does not authorize

Every exclusion in `KHEPRI-DEC-019` §5 other than the schema clause is carried forward intact:

- **No product code beyond the migration and its ORM change.** No bridge service and no
  entry-point implementation are authorized here. `R7-02` and later slices remain separately
  reviewable.
- **No endpoint.** `R7-05`'s HTTP surface is not settled, proposed, or implied.
- **No further schema change.** `rra_uploads.UNIQUE (session_id)` stands — that is the finding's
  Option B, and it is **not** taken. `R7-01` §4's create-once/resume-thereafter shape does not
  require it, and one session per analysis is `RRA`'s design rather than an accident.
- **No `RRA-001`, `RRA-002`, or `RCA-001` amendment.**
- **No change to `redeem`**, its signature, its behavior, or the invitation lifecycle.
- **No authorization inside `RRA`.**
- **No commercial identifier crossing the boundary.** `FR-032` and `FR-033` unaffected.
- **No public signup, billing, durable report history, or changed content retention.**
- **No relocation of authoritative retail calculation into `RCA`** (`FR-036`).
- **No `test_rra*` edit.** `FR-037` requires `RRA`'s controls remain covered by its existing tests
  **unmodified**, and §4's first obligation is unchanged. No existing test asserts
  `UNIQUE (owner_id)` — verified by search — so dropping it breaks none, which is itself evidence the
  constraint was an unexamined beta default rather than a defended invariant. **If implementing the
  migration requires editing any `test_rra*` file, that is a conflict with this decision and must be
  recorded, not resolved by editing the test.**

## Consequences

- **`KHEPRI-DEC-019` is retired and superseded by this record.** Registry state is authoritative;
  its document remains in place as history and must not be edited to match this one.
- `R7-02` is **unblocked** and may proceed once this record is merged, implementing §2's migration
  and then `KHEPRI-DEC-019` §2's shape. It remains a separately reviewed slice.
- `R7-03`, `R7-05`, and `R7-06` remain blocked on `R7-02` rather than on governance. `R7-03` tests
  the resume path, which needs `R7-02`'s persistence — the roadmap table's `Depends on: R3, R6`
  understates it, and `R7-01` §4 is the governing description.
- **`R7-04` was never blocked** and is unaffected by this record. It is regression-only and asserts
  the beta journey holds for a participant with no account, which must remain true under this
  decision as under `KHEPRI-DEC-019`.
- **`R6-08`'s `test_the_resolver_has_no_production_consumer_yet` will fail** when `R7-05` wires a
  consumer. Its docstring instructs its own replacement; relaxing it instead would discard the
  chokepoint evidence that slice exists to provide.
- **`R6-05`'s `test_every_protected_action_in_the_design_has_a_matrix_class` will fail** if `R7` adds
  a row to `R6-01` §3.1. Add the row and the `ACTION_COVERAGE` entry in the same slice; that coupling
  is the point.
- Two carried gaps in `specs/001-rca-001-commercial-identity/STATUS.md` become closable by `R7`:
  `resolve_scope`'s unauthenticated matrix cell gains an authenticated boundary, and `FR-023`'s
  object-level half gains an object-level path to test.
- Twelve `RCA-001` requirements — `FR-008`, `FR-009`, `FR-021` … `FR-026`, `FR-028`, `FR-031`,
  `FR-034`, `FR-038` — move together when `R7-05` routes a production path through
  `AuthorizationResolver`, and not before. That is why `R7` is the critical path rather than `R4` or
  `R5`.
- **A lesson recorded, because the method matters more than the outcome.** `KHEPRI-DEC-019` was
  reviewed and merged carrying a self-contradiction that one probe against live metadata exposed
  within the hour. The contradiction was invisible on the record's face because both clauses were
  individually reasonable; only the database's constraints made them incompatible. A decision that
  admits a shape touching an existing table should state which constraints on that table it has
  checked.
- `KHEPRI-DEC-008`, `KHEPRI-DEC-014`, `KHEPRI-DEC-015`, `KHEPRI-DEC-017`, and `KHEPRI-DEC-018` are
  unaffected and not superseded.
- The commercial thesis behind the phase ordering remains an untested assumption, as
  `KHEPRI-DEC-014` records. This decision does not change that.

---

Identity, state, document, dependencies, and supersession are authoritative in
`governance/registry.yaml`.
