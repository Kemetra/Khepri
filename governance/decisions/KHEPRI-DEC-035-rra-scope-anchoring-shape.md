# KHEPRI-DEC-035: Anchoring the RRA scope in the database — the admissible shape, and the interim acceptance

> Active when merged to `main`.

## Context

`#432` records that tenant isolation for `khepri.rra` is enforced by one Python call and nothing
beneath it. `rra_beta_sessions.owner_id` is an unconstrained string
(`src/khepri/rra/persistence.py:80`). No foreign key anchors it and no row-level security exists, so
the database will attach any `owner_id` a caller hands it. Every RRA content table binds
`(owner_id, session_id)` compositely to that session row, so the exposure is exactly one level deep:
**forge the session row, and everything beneath it validates.**

`S1-02` (`docs/superpowers/plans/2026-09-15-s1-02-store-seam-triage.md` §1) ranked this seam first,
the only one where the database can represent a cross-scope row. It named three shapes and said that
choosing among them is the owner's, not a slice's:

1. a cross-package foreign key onto `rca_isolation_scopes.owner_id`;
2. a CHECK or trigger local to `khepri.rra`;
3. row-level security with a tenant role and `SET LOCAL`.

`#578` closed `#432`'s two other schema holes and deferred this one with its reason. The roadmap
therefore keeps `S1-03` and `S1-05` open, and `#152` with them, until this seam is "addressed or
explicitly accepted". This decision does both halves of that sentence: it names the one admissible
shape, and it accepts the gap explicitly and with a bound until that shape ships.

## Decision

### 1. Row-level security is the only admissible shape

Anchoring the RRA scope in the database means **PostgreSQL row-level security**, enforced against a
runtime role that does not own the tables and is not a superuser, with the scope set per unit of work
by `SET LOCAL`. The two other shapes are not admissible, for these reasons:

- **Shape 1, a foreign key onto `rca_isolation_scopes`, is refused.**
  - It refuses legitimate writes. Invitation-redeemed sessions carry an `own_…` scope with no
    `rca_isolation_scopes` row (`redeem` mints one per redemption, `src/khepri/rra/sessions.py:198`), so the key would refuse
    every beta redemption, the path `KHEPRI-DEC-023` keeps unchanged.
  - It breaks `RCA-001` `FR-039`: RRA's own tests would need an RCA record before they could open a
    session. It also couples two `DeclarativeBase` metadata trees that are deliberately separate.
  - It does not stop the attack `#432` names. Another organization's `owner_id` is a real scope
    row, so a forged session naming it satisfies the key.
- **Shape 2, a CHECK or trigger local to `khepri.rra`, is refused.** A CHECK cannot consult another
  table. A trigger that does reads `rca_isolation_scopes` from the RRA connection. That is the same
  boundary crossing as shape 1, performed in procedural code, and it gives the same existence-only
  guarantee.

Row-level security is the only shape that states the property `#432` is about: *a unit of work
acting for one scope cannot read or write another scope's rows.* It needs no RCA row and no
cross-package key. It therefore keeps `FR-039` and the separate metadata trees intact.

### 2. What row-level security must cover when it ships

- **Tables.** Every table in `khepri.rra`'s metadata that carries an `owner_id` column. The set is
  defined by that property, not by a list, so a table added later is covered or its omission fails a
  test.
- **Policy.** Both `USING` and `WITH CHECK` compare `owner_id` with the unit of work's scope setting.
  An unset **or empty** setting must match nothing (Constitution V). The property is what binds, not
  a mechanism: on a pooled connection that earlier ran `SET LOCAL`, the missing-setting read returns
  an empty string rather than `NULL`, so a policy relying on `NULL` comparison alone does not satisfy
  this clause.
- **Role.** The application connects as a role that neither owns the tables nor bypasses RLS, and
  `FORCE ROW LEVEL SECURITY` applies to every covered table. Migrations and the deletion and
  retention sweeps that must cross scopes run under a separately named role, and each such use is
  enumerated in the implementing slice.
- **Verification.** Against PostgreSQL, not SQLite, as that role:
  - a unit of work scoped to A reads none of B's rows;
  - inserting a session or child row whose `owner_id` differs from the setting fails at the database;
  - a unit of work with no setting reads zero rows, including on a pooled connection reused after
    an earlier scoped transaction.

  These run in the `concurrency`-marked PostgreSQL job, where a skip fails the build.

### 3. The interim gap is accepted, and bounded

Until §2 ships, the absence of a database-level scope backstop on RRA tables is **accepted** for the
conditions `KHEPRI-DEC-031` establishes: local-only rehearsal, internal, no external participant.
The acceptance rests on those conditions, not on the store being sealed. It is not sealed: the
store still resolves sessions, uploads, profiles and packages by `session_id` alone
(`get_session`, `get_upload_for_session`, `get_profile_for_session`, `get_package_for_session`),
and those lookups are `#152`'s to address (§5). What makes the gap tolerable is that under
`KHEPRI-DEC-031` there is one operator, fixture data, and in practice one scope, so no row exists
that another scope could be shown.

The acceptance **ends** at the earliest of:

- any external participant receiving access, a report, an artifact, or a link. This is
  `KHEPRI-DEC-031` §2's bound, and at that point the hosted half of `M2` governs;
- any hosted environment holding data that is not fixture data;
- a second real organization's data existing in any database the runtime connects to.

### 4. A gate added before beta authorization

§2, implemented and verified, is **a precondition of beta authorization**, in addition to every gate
`KHEPRI-DEC-030` §6 lists. It adds to that list and removes nothing from it. `KHEPRI-DEC-030` is not
amended. `#581`, the hosted-readiness checklist, is to carry this gate as one of its tracked
items.

### 5. What this decision does not authorize

- **No implementation today.** Constitution IV admits product code only against an active
  specification. The slice that implements §2 first lands the requirement it builds against, in
  `RRA-001` or a successor. This decision selects the shape and does not stand in for that
  requirement.
- **No foreign key and no trigger** onto `rca_isolation_scopes` from any RRA table, under §1.
- **No closure of `#152`.** This discharges `S1-02` rank 1 and rank 3 for `S1-05`'s accounting:
  rank 3 folds into rank 1, and rank 2 merged in `#463`. `#578` also routed the unscoped
  `session_id` store lookups to `#152`, and those remain its own to address.
- **No reading about RCA's identity tables.** `#432` also observes that one unscoped query would
  return commercial identity rows. Whether RCA tables take the same policy is not decided here, and
  nothing here excludes it.

## Alternatives not selected

- **Ship shape 1 now as a partial wall.** Refused under §1. It breaks beta redemption and `FR-039`,
  and it does not stop the named attack.
- **Leave the seam unaccepted until RLS ships.** This keeps `S1-05` and `#152` open indefinitely on a
  risk that does not exist under `KHEPRI-DEC-031`'s conditions. It also leaves no recorded point at
  which the risk stops being tolerable. §3 records that point.
- **Build RLS now.** This decision authorizes no implementation (§5), and the local rehearsal has one
  scope in practice. §4 makes RLS a gate on the event that creates the risk: external data from a
  second tenant.

## Consequences

- `S1-03` for rank 1 is resolved: the shape is named. `S1-05` can account for rank 1 as accepted
  under §3.
- Beta authorization gains one gate (§4). Hosted work under `KHEPRI-DEC-030` §3, the provisional
  bootstrap, is not gated by this decision. §3's second bullet ends the acceptance before real data
  arrives there.
- The implementing slice must change the connection model: a non-owner role, and `SET LOCAL` on
  every unit of work. That is an operations change as well as a schema change, and it belongs with
  `OPS1`'s environment work, not in `S1` alone.

## Evidence

- `#432`: the finding, its 2026-09-20 audit re-verification, and its list of the unscoped
  `session_id` lookups §3 names.
- `#578`: the disposition table recording why an unconditional foreign key refuses beta
  redemptions.
- `docs/superpowers/plans/2026-09-15-s1-02-store-seam-triage.md` §1 and §3: the ranking and the
  three shapes.
- `src/khepri/rra/persistence.py`: `owner_id` is unconstrained at `:80`, and the composite child keys
  bind to it.
- Owner instruction in session, 2026-09-26: "go", in response to a recommendation to accept the gap
  now and require row-level security before hosted or second-organization use. The owner approved
  the recommendation and did not author it; the merge of this document is the approval
  (Constitution II).
