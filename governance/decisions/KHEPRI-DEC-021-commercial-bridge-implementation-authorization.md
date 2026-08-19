# KHEPRI-DEC-021: Authorization to implement the commercial bridge and the RRA scoped-session entry point

> Active. **Supersedes `KHEPRI-DEC-020`**, which is retired by this record. Stands beside
> `KHEPRI-DEC-014` and `KHEPRI-DEC-018`.
>
> `active` is the only non-retired state the registry admits (`validator.py:15`), and a branch is a
> proposal until the owner merges it (`AGENTS.md`). This record is therefore written in its merged
> form and is **not governing until that merge** — the header states the state it will hold, not a
> claim that it already holds it. `R7-07` may not begin before the merge.

## Context

`KHEPRI-DEC-020` (`2c9e0c1`) admitted the bridge's shape and authorized the schema change it
required, and `R7-02` delivered that migration (`20260817_0017`, `#205`). Its §3 then withheld
authorization for the code, in terms:

> **No product code beyond the migration and its ORM change.** No bridge service and no entry-point
> implementation are authorized here. `R7-02` and later slices remain separately reviewable.

That bullet is the only thing blocking `R7-07`. The roadmap records the same reading: *"it is
blocked on governance rather than on code: `KHEPRI-DEC-020` §1 re-enacts the admitted shape, so the
design is settled, but §3 withholds authorization for the code. Lifting that needs a successor
record, which is the owner's to make."*

**Supersession is the only available instrument, and this is the third time it has been.**
`KHEPRI-DEC-017` makes supersession whole-document; editing `KHEPRI-DEC-020` to admit what it
forbids would rewrite history rather than correct it, and its own Consequences state that a
superseded document *"remains in place as history and must not be edited to match this one."* The
same applies to it now.

**Why this record does more than lift one bullet.** Probing the seam before authorizing it — the
method `KHEPRI-DEC-020`'s own closing lesson asks for — surfaced three things the admitted shape
does not cover, each of which would otherwise be decided by whoever implements `R7-07`:

1. **There is no invitation-free session insert.** `SessionStore`'s Protocol
   (`src/khepri/rra/sessions.py:56-70`) exposes `add_invitation`, `get_invitation`,
   `redeem_invitation`, `update_session`, and `get_session`. `BetaSessionRow` is written in exactly
   one place — inside `redeem_invitation` (`src/khepri/rra/persistence.py:381-392`), behind the
   invitation guard at `:373-379`. `update_session` only mutates consent and deletion fields on a
   row that already exists. So the entry point `KHEPRI-DEC-019` §2 admitted has **nowhere to
   persist**, and authorizing it without its store path would authorize a function that cannot
   work.
2. **Resume needs a query that does not exist, and nothing settles what it selects.**
   `get_session` is keyed by `session_id` (`sessions.py:~60`) and `BetaSessionRow`'s primary key is
   `session_id` (`rra/persistence.py:73`), so `R7-01` §4's create-once/resume-thereafter shape needs
   a new query. But `owner_id` is deliberately non-unique after `20260817_0017`, and `R7-01` §4 says
   only that the bridge "looks up an existing session" — so *which* session a resume selects is
   unspecified in every merged document. §2 settles it.
3. **Two merged documents disagree about where the bridge lives**, and neither can override the
   other. `R7-01` §3 evaluates three locations and recommends `khepri.local`; the roadmap's `R7-07`
   disposition frames the discipline as *"no `rra_` import inside `src/khepri/rca/`"*, which
   presumes an RCA-side bridge. This is not cosmetic: it decides whether the boundary test `R7-07`
   owes is a flat prohibition or an allowlist.

## Decision

### 1. Everything `KHEPRI-DEC-020` decided is carried forward unchanged

This record re-enacts, without modification of substance:

- **`KHEPRI-DEC-020` §1**, which itself re-enacts `KHEPRI-DEC-019`'s §1 governing principle ("The
  organization's scope is the analysis scope. `RRA` never learns whose it is."), §2 admitted shape,
  §3 `FR-037` analysis, and §4's five obligations. All of it stands as written.
- **`KHEPRI-DEC-020` §2**, the migration on `rra_beta_sessions` and its ORM change. Already
  implemented and merged; re-enacted so that retiring the record does not unsettle what it
  authorized.

`KHEPRI-DEC-019` §4's five obligations are load-bearing for what follows and are restated for the
implementer rather than left one document away: `RRA`'s existing tests pass **unmodified**; `RRA`
remains independently testable with no account, organization, or membership (`FR-039`); the beta
path is unchanged; **the caller resolves the scope and never receives one**; and
`allocate_owner_id` remains the single minting site.

### 2. What this record additionally authorizes

**The `R7-07` implementation, in four parts and no more.**

- **The entry point.** One additive function in `khepri.rra`, sibling to `redeem`, accepting an
  opaque `owner_id` and minting its own `session_id`, accepting nothing else that identifies a
  caller, and performing no authorization. This is `KHEPRI-DEC-019` §2's shape unchanged; what is
  new here is permission to write it.
- **Its persistence.** One additive `SessionStore` Protocol method that persists a `BetaSession`
  with no invitation, its `SqlSessionStore` implementation, and any in-memory double the tests
  need. **This is authorized explicitly because the entry point is unimplementable without it**,
  and because `KHEPRI-DEC-019` §4's first obligation guards the surface that a Protocol change
  touches. The obligation is not weakened: an *additive* method leaves every existing signature
  intact, so `RRA`'s existing tests must still pass unmodified. If they do not, that is the
  conflict §4 describes and it is to be **recorded, not resolved by editing the test**.
- **The resume lookup, scoped by `(owner_id, session_id)` and never by `owner_id` alone.** One
  additive read-only query; it adds no column, no constraint, and no index — see §4.

  **The scoping is the decision, and an earlier draft of this record got it wrong.** That draft
  authorized "a resume lookup by `owner_id`", which contradicts §4 of this same record:
  `20260817_0017` dropped `UNIQUE (owner_id)` precisely so one scope may hold many sessions, so
  `owner_id` alone identifies a *set* and cannot say which analysis to resume. A conforming
  implementation would fail on multiple rows or pick an arbitrary or stale one, and the bridge would
  resume the wrong analysis. Found in review on `#216`.

  `R7-01` §4 does not close this either — it says the bridge "looks up an existing session" without
  saying which — so the gap is upstream of this record and is settled here rather than left to
  `R7-07`:

  - **The caller names the analysis it is resuming.** `session_id` is per-analysis and `RRA`'s to
    mint, so a caller resuming holds one from the create call. A resume naming none would be a
    request for "whichever session you have", which is not a behaviour anyone specified.
  - **The lookup is `(owner_id, session_id)`** — exactly `uq_session_owner_scope`, which is why no
    new index is needed and why the pair is the natural key rather than an invention.
  - **It fails closed.** A `session_id` that exists under a *different* `owner_id` returns nothing,
    not that session. This is `FR-023`'s object-identifier rule at the RRA boundary: the caller
    supplies an identifier, and the scope it may act under comes from `resolve_scope` rather than
    from the identifier. Refusing must be indistinguishable from "no such session".
  - **No "current session" invariant is admitted.** A column or convention marking one session
    current per scope would reintroduce, one layer up, the single-session cardinality
    `20260817_0017` removed. `R7-05`'s surface may present a most-recent list; that is a query
    ordering, not a schema fact, and this record authorizes no column for it.
- **The bridge**, calling `IsolationService.resolve_scope(account_id, organization_id)`
  (`src/khepri/rca/isolation.py:30-40`) and passing the resulting opaque `owner_id` to the entry
  point.

### 3. The bridge lives in `khepri.runtime`

Resolving the conflict named in the Context — and rejecting both options the merged documents offered.

`R7-01` §3 evaluated three locations and recommended `khepri.local`, on the ground that
`src/khepri/local/wiring.py` already imports `khepri.rca.*` and roughly fifteen `khepri.rra.*`
modules side by side, so a bridge there needs no new import direction. **An earlier draft of this
record adopted that recommendation. It is wrong, and the reason is packaging rather than layering.**
Found in review on `#216`.

`khepri.local` is not deployed:

- `pyproject.toml:66` — `exclude = ["src/khepri/local"]`, and the comment there states the reason:
  "development wiring… kept OUT of the built wheel, which is what the OCI image installs."
- `src/khepri/local/__init__.py:1` — "Local development wiring. Not governed, not production, not
  evidence… none of it is deployed."
- `Dockerfile:72` validates `khepri.runtime.config, khepri.runtime.wiring, khepri.runtime.worker`.
  It does not import `khepri.local`, because the image does not contain it.

So a bridge in `khepri.local` is unreachable from the deployed web role, and `R7-05` would have to
move or duplicate it — against a binding clause of this record. An authorization naming a location
the product cannot use is not an authorization; it is a defect of the same shape as
`KHEPRI-DEC-019`'s, which admitted an entry point the schema forbade.

**`khepri.runtime` is the packaged composition layer**, described by its own `__init__` as "Production
composition roots for the approved RRA web and worker roles", and it is what the Dockerfile
validates. A bridge there is reachable from the role that will serve `R7-05`'s endpoint.

**It does introduce a new import direction, and that is admitted deliberately.** `khepri.runtime`
currently imports no `khepri.rca` module — verified across all four of its modules — so this is the
first RCA import into the production composition layer. That is the correct place for it: composition
roots exist to know about both sides, which is exactly what `khepri.local` does for development. What
`R7-01` §3 was protecting against is a bridge inside **`khepri.rca`**, which would make every RCA test
transitively depend on RRA and, in its words, *"quietly spends the one-directional import budget"*.
That option remains rejected.

**`khepri.local` may wire the same implementation** so the journey stays runnable on a developer's
machine. One implementation, two composition roots — which is the relationship those two packages
already have for every other service.

Two consequences, both binding on `R7-07`:

- **The boundary assertion is a flat prohibition, not an allowlist.** `khepri.rca` imports no
  `khepri.rra` module and `khepri.rra` imports no `khepri.rca` module, mirroring the existing
  one-directional prohibition rather than carving an exception out of it. Both packages stay ignorant
  of each other and `khepri.runtime` knows both, which is what a composition root is for. This is the
  stricter of the two readings and needs no maintenance as the bridge grows.
- **The roadmap's `R7-07` disposition is superseded on this point.** Its phrasing — *"the bridge's
  'no `rra_` import inside `src/khepri/rca/`' discipline rests on prose, not on a guard"* — remains
  correct about the *gap*; its implicit assumption that the bridge sits in `khepri.rca` does not
  survive this record. The roadmap is a planning artifact and does not govern
  (`CONSTITUTION.md`); it should be updated to match, and the mismatch is recorded here rather
  than silently left.

### 4. What was checked before admitting this shape

`KHEPRI-DEC-020`'s closing lesson asks that *"a decision that admits a shape touching an existing
table should state which constraints on that table it has checked."* Applying it to this record:

- **`uq_session_owner_scope`** — `UNIQUE (owner_id, session_id)` on `rra_beta_sessions`
  (`rra/persistence.py:70`) — is **retained and unaffected**. One scope holding many sessions is
  exactly what `20260817_0017` enabled; the composite constraint still forbids the same pair twice.
- **`uq_upload_session`** — `UNIQUE (session_id)` on `rra_uploads` (`rra/persistence.py:111`) — is
  **retained**. One upload per session remains `RRA`'s design. An organization now gets many
  sessions, each with one upload, so nothing about this record pressures it. The finding's Option B
  was refused by `KHEPRI-DEC-020` §3 and stays refused.
- **No new index is required for the resume lookup.** With §2's scoping the lookup *is*
  `uq_session_owner_scope`'s column pair, so that constraint's own backing index serves it
  exactly — a stronger statement than `KHEPRI-DEC-020` §2 needed, which relied on `owner_id`
  merely being the leading column.
- **`BetaSessionRow`'s primary key is `session_id`** (`rra/persistence.py:73`), which is why the
  resume lookup is a new query rather than an existing one reused.

### 5. What this record still does not authorize

Every exclusion in `KHEPRI-DEC-020` §3 other than its first bullet is carried forward intact:

- **No endpoint.** `R7-05`'s HTTP surface is not settled, proposed, or implied. `R7-07` places the
  bridge in `khepri.runtime` so that surface *can* consume it later, and wires nothing to a route.
- **No further schema change.** `rra_uploads.UNIQUE (session_id)` stands.
- **No `RRA-001`, `RRA-002`, or `RCA-001` amendment.**
- **No change to `redeem`**, its signature, its behavior, or the invitation lifecycle. The entry
  point is a sibling; `redeem` is not modified, not parameterised, and not called by it.
- **No authorization inside `RRA`.** The caller has already been authorized; a second check would
  put one rule in two places.
- **No commercial identifier crossing the boundary.** `FR-032` and `FR-033` unaffected: no
  `organization_id`, name, slug, or email reaches `RRA`. Only the opaque `owner_id` crosses.
- **No public signup, billing, durable report history, or changed content retention.**
- **No relocation of authoritative retail calculation into `RCA`** (`FR-036`).
- **No `test_rra*` edit.** Unchanged from `KHEPRI-DEC-020` §3 and `KHEPRI-DEC-019` §4.1: if
  implementing this requires editing any `test_rra*` file, that is a conflict with this decision and
  must be **recorded, not resolved by editing the test**.

Two further exclusions specific to this record:

- **No `owner_id` from a request.** The bridge obtains it from `resolve_scope` and from nowhere
  else. A parameter through which a caller could name a scope would make an object identifier grant
  authority, which `R6-01` §5's critical rule forbids.
- **No skipped re-resolution on resume.** `FR-030` requires a membership change to take effect for
  decisions made after it, so resuming re-resolves the authorization context rather than trusting
  the session. `R7-03` is the evidence slice for this and remains separate.

## Consequences

- **`KHEPRI-DEC-020` is retired and superseded by this record.** Registry state is authoritative;
  its document remains in place as history and **must not be edited to match this one**. Its §2
  migration is already merged and is re-enacted by §1 above, so retiring it unsettles nothing.
- **`KHEPRI-DEC-019`'s `superseded_by` is re-pointed from `KHEPRI-DEC-020` to this record, and that
  is a property of the registry rather than a rewriting of history.** `_validate_successor`
  (`validator.py:348`) requires a successor to be `active`, so the moment `KHEPRI-DEC-020` retires,
  `KHEPRI-DEC-019` naming it becomes invalid — the validator says so directly, and it was the first
  thing to fail when this record was drafted. **The registry therefore models `superseded_by` as a
  pointer to the record that governs the subject matter now, not as a link to the immediate
  predecessor.** The established shape is fan-in: `KHEPRI-DEC-002`, `-004`, `-010`, `-011`, and
  `-016` all name `KHEPRI-DEC-017`. The *sequence* 019 → 020 → 021 is recoverable from these
  documents, which each name what they supersede in prose; it is deliberately not recoverable from
  the registry, which answers "what governs this now?" and only that. A reader tracing lineage reads
  the documents; a tool asking what is authoritative reads the registry. Recorded because the
  re-point looks like an edit to an unrelated record and is not one.
- **`R7-07` is unblocked** and may proceed once this record is merged, implementing §2's four parts
  at §3's location. It remains a separately reviewed slice.
- **`R7-03`, `R7-05`, and `R7-06` remain blocked on `R7-07`**, not on governance. `R7-03` tests the
  resume path and needs the persistence `R7-07` adds; `KHEPRI-DEC-020`'s Consequences said the same
  about `R7-02`, and the dependency simply moves forward one slice. The roadmap's
  `Depends on: R3, R6` cell for `R7-03` continues to understate it, and `R7-01` §4 with this record
  is the governing description.
- **The roadmap's `R7-07` disposition needs updating** for §3's location decision, per that
  section. A planning artifact cannot override this record, but leaving them disagreeing is the
  drift that produced `#214`'s findings.
- **`R6-08`'s `test_the_resolver_has_no_production_consumer_yet` does not fire from `R7-07`
  alone.** It fails when a production module *consumes `AuthorizationResolver`*, which is `R7-05`'s
  endpoint. A bridge wired only into `khepri.local` and reached by no handler leaves it green.
  When `R7-05` lands, its docstring instructs its own replacement; relaxing it instead would
  discard the chokepoint evidence that slice exists to provide.
- **`R6-05`'s `test_every_protected_action_in_the_design_has_a_matrix_class` likewise does not fire
  from `R7-07` alone**, and will if `R7-05` adds a row to `R6-01` §3.1. Add the row and the
  `ACTION_COVERAGE` entry in the same slice; that coupling is the point.
- **`R7-07` owes the RCA→RRA boundary test**, per §3. It is currently unasserted in both
  directions inside `test_rca001_boundary.py`, whose `_TARGET` is hard-coded to `khepri.rca`. The
  existing `find_rca_import_offenses(source, package)` is already parameterised on `package`, so a
  mirror is small — and §3's flat prohibition is what makes it expressible as a mirror rather than
  as an exception list.
- **Twelve `RCA-001` requirements still move together with `R7-05`, not with this record.**
  `FR-008`, `FR-009`, `FR-021` … `FR-026`, `FR-028`, `FR-031`, `FR-034`, and `FR-038` are blocked
  on a production path routing through `AuthorizationResolver`. A bridge with no handler is not
  that path.
- **A lesson carried forward rather than relearned.** `KHEPRI-DEC-019` shipped a self-contradiction
  that one probe exposed within the hour, and `KHEPRI-DEC-020` recorded the rule that followed. This
  record applied it to itself: probing the seam before authorizing it is what found that the
  admitted entry point had nowhere to persist. **An authorization that names a function should state
  where that function writes.** Authorizing the entry point alone would have handed `R7-07` an
  unimplementable scope and left the Protocol question to be decided in a pull request.

---

Identity, state, document, dependencies, and supersession are authoritative in
`governance/registry.yaml`.
