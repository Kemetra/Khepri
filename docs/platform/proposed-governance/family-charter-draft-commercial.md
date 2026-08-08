# `[FAM-COMMERCIAL]` charter (DRAFT) and the required `RRA.md` re-scope

> **Progress note added 2026-08-08 (`main` @ `04acba3`).** This draft was promoted and approved
> as `APP-017` (2026-08-08). `RCA` — the code this draft argued for and this repository's
> registries adopted — is `active` in `families.yaml`, `depends_on: [FND, RRA]`; `KHEPRI-DEC-014`
> (the decision this draft calls `[DEC-COMMERCIAL]`) is `accepted`; and the `RRA.md` re-scope in
> Part 2 landed as a renewal (`APP-017` superseding `APP-002`'s pin), matching
> [`rra-exclusions-rescope.md`](rra-exclusions-rescope.md)'s staged text verbatim.
>
> **The landed `governance/families/RCA.md` is not byte-identical to Part 1 below.** Two
> differences, found comparing the two texts directly:
>
> - The landed Excludes carries an explicit bullet — "Internal report-job queueing and
>   report-job reliability, which `RRA.md` owns. This family's queueing boundary is the
>   customer-facing kind only" — that Part 1 does not have. This is the same
>   `KHEPRI-DEC-012`-derived qualification `rra-exclusions-rescope.md` applies to `RRA.md`'s
>   own work-queues clause, carried into `RCA.md` for consistency.
> - The landed runtime/provider Excludes bullet reads "Runtime, provider, and deployment
>   selection, which a separately approved architecture decision governs and which remains a
>   distinct gate from anything this charter authorizes," reworded from Part 1's shorter
>   "Runtime, provider, or deployment selection, which `KHEPRI-DEC-008` governs and which
>   remains a separate gate."
>
> Neither difference changes what the family owns. Part 1 below is left as drafted, since it is
> the record of what was proposed; it is not what was approved. Read `governance/families/RCA.md`
> directly for the governed text.
>
> **One defect survives the promotion, unfixed.** `RCA.md`'s closing line still reads "The family
> is proposed" against `families.yaml`'s `state: active` — the exact staleness this draft's Part
> 2 corrected in `RRA.md`. `RCA.md` is now itself digest-pinned by `APP-017`, so this cannot be
> fixed as an edit; it needs its own renewal package, which no one has drafted.
>
> **Draft for owner review. Not a governed artifact. No identifier or family code is allocated.**
> (True when written; superseded by the paragraphs above.)

`[FAM-COMMERCIAL]` and `<CODE>` are **planning placeholders**. `docs/khepri-commercial-roadmap.md`
proposes **RCA** (Retail Commercial Analysis) as the code and argues for it against widening
`RRA.md`; no registry constrains the letters, and the choice is made at drafting time. Nothing
is reserved.

Two documents that must land in **one approval package**, so no moment exists where both family
documents claim the same capability (Constitution I).

Targets on promotion: `governance/families/<CODE>.md` (new) and
`governance/families/RRA.md` (edit).

---

## Part 1 — `governance/families/<CODE>.md`

Follows `governance/templates/family.md` and the phrasing of `FND.md` and `RRA.md`.

> # <CODE>: Retail Commercial Analysis
>
> ## Owns
>
> - Commercial identity: accounts, credentials, authentication, sessions, and recovery.
> - Organizations, membership, and role-based access.
> - Persistent customer workspaces, durable dataset and report history, and the retention
>   decision governing them.
> - Multi-dataset collections within a workspace, governed time alignment, and schema-drift
>   review.
> - Plans, entitlements, quotas, subscriptions, invoicing, and billing-provider integration.
> - Public onboarding, self-serve signup, and abuse controls.
> - Report sharing, download permissions, and delivery scheduling.
> - Agency portfolios, client switching, delegated access, and bounded white labeling.
> - Consumption of governed analytical evidence produced outside this repository, under
>   `[DEC-BOUNDARY]`.
>
> ## Excludes
>
> - Governed retail intake, profiling, admissibility, deterministic facts, comparative
>   analysis, narrative, and report surfaces. Those are RRA's, and this family consumes them
>   rather than reimplementing them.
> - Repository governance, registries, and lifecycle validation. Those are FND's.
> - Forecasting, generic non-retail analysis, customer-authored formulas, arbitrary code
>   execution, and unsupported metrics.
> - Authoritative recalculation of any figure owned by another repository's analytical engine,
>   as bounded by `[DEC-BOUNDARY]`.
> - White labeling that removes or misrepresents mandatory provenance, refusal, or
>   automatic-generation disclosure.
> - Product implementation while this family remains proposed or its specifications remain
>   draft.
>
> Identity, state, owner, dependencies, and approval evidence are authoritative in
> `governance/registries/families.yaml`.

### Registry shape

**No registry entry is created by this planning pass.** Should the owner direct that this be
drafted, the entry would take this shape, with `<CODE>` chosen at that moment:

```yaml
  - id: <CODE>
    name: Retail Commercial Analysis
    state: proposed
    owner: AHMED-SHAABAN
    document: governance/families/<CODE>.md
    depends_on:
      - FND
      - RRA
```

No approval fields — Constitution VI requires them only at `active` or `retired`.

### Three choices worth challenging

**Why a new family rather than widening `RRA.md`.** Deleting RRA's exclusions and putting
commercial capabilities there leaves one document asserting both "invite-bound, pseudonymous
beta sessions" and "commercial multi-tenant service." Constitution I requires one authoritative
representation per governed fact. `docs/khepri-commercial-roadmap.md` reaches the same
conclusion independently.

**Why `depends_on: [FND, RRA]`.** The commercial family consumes RRA's report pipeline directly. A commercial
workspace with no governed report is not a product. Matches how `RRA` already depends on `FND`.

**Why the last Excludes bullet is not boilerplate.** `RRA.md` carries the same line and it is
the clause `AGENTS.md` enforces — "Never implement ahead of an approved specification." Without
it, chartering the family reads as authorizing the work.

---

## Part 2 — the required `RRA.md` re-scope

### The problem

`RRA.md` writes its exclusions as flat prohibitions:

> Commercial authentication, user profiles, persistent customer workspaces, organizations,
> membership roles, billing, subscriptions, scheduling, and public signup.

Once the commercial family is active and owns billing, "billing is excluded" is ambiguous between
excluded-from-RRA and excluded-from-Khepri. Constitution I forbids the ambiguity.

`FND.md` already solves it:

> It excludes customer features, business or domain logic, infrastructure services, and
> **responsibilities of future product families. Those boundaries require separately approved
> families and specifications.**

### The edit

Replace `RRA.md`'s first two Excludes bullets with:

> - Responsibilities of the Retail Commercial Analysis family: commercial authentication, user
>   profiles, persistent customer workspaces, organizations, membership roles, billing,
>   subscriptions, scheduling, public signup, agency portfolios, client switching, delegated
>   access, customer-facing work queues, and white labeling. Those boundaries are owned by
>   the commercial family and require its separately approved specifications.

Keep the remaining bullets unchanged: forecasting and generic analysis stay excluded from both
families.

### Two corrections in the same edit

**1. The prose contradicts the registry.** `RRA.md` closes with "The family is proposed."
`families.yaml` records `state: active`, approved 2026-07-29 under `APP-002`. Constitution I
settles it — the registry wins — but the prose is wrong and a reader may act on it. Replace
with `FND.md`'s formulation: "Identity, state, owner, dependencies, and approval evidence are
authoritative in `governance/registries/families.yaml`."

**2. Two clauses `KHEPRI-DEC-012` already analysed should be recorded, not silently carried.**

- `RRA.md`'s "Runtime or provider selection before a separate architecture decision is
  accepted" — `KHEPRI-DEC-012:94-99` records this exclusion as **lapsed**, because its
  condition is satisfied: `KHEPRI-DEC-005` is accepted. Carrying it forward unchanged invites
  the misreading DEC-012 warned against ("dropping the qualifier that carries its meaning").
- `RRA.md`'s exclusion of `work queues` — `KHEPRI-DEC-012:104-108` records that this means
  *customer-facing* queues, grouped with agency portfolios and white labeling, and that reading
  it platform-wide "would make shipped, approved code unauthorized," since the internal
  report-job queue is owned by "Report-job reliability" and implemented in `jobs.py` and
  `job_persistence.py`. The re-scope above writes "customer-facing work queues" for that
  reason.

### Digest hazard — checked, and it applies

**`RRA.md` is pinned.** `APP-002.yaml` binds it as

```yaml
  - id: RRA
    document: governance/families/RRA.md
    document_sha256: sha256:8a1235a0d6b9e36a6446a1e1cfd3f7ef5db52ca7d9e0ed23bcffb18eded095d2
    from_state: proposed
    to_state: active
```

and the file hashes to exactly that today, so the pin is live and undrifted.

**Consequence: the re-scope is a renewal approval package, not an edit.** Same machinery as
`APP-013`/`KHEPRI-DEC-005`, in `src/khepri_gov/approval_renewals.py`. Attempting it as a plain
edit fails `khepri-gov validate` closed, exactly as the DEC-005 attempt did.

`APP-002` also pins `KHEPRI-DEC-002`, `-003`, `-004`, and `RRA-001` through `RRA-007` by digest.
That matters for item 5 below: superseding `KHEPRI-DEC-003` changes its **registry state**,
which needs no renewal — but adding a `superseded_by` note to the *document* would be an edit
to a pinned artifact and would need one. Record the supersession in the registry, not in the
document body.

---

## Part 3 — what the approval package must contain

Per `KHEPRI-DEC-004` (atomic approval packages) and `governance/templates/approval-package.yaml`,
one package — `[PKG-GOV]` — covering:

1. `governance/families/<CODE>.md` — new, `proposed`.
2. `governance/families/RRA.md` — re-scoped, plus the two corrections.
3. `governance/registries/families.yaml` — the new family entry.
4. Any renewal required by the digest check above.
5. `[DEC-COMMERCIAL]` — the decision superseding `KHEPRI-DEC-003`'s beta boundary, stating which
   privacy controls survive commercialization unchanged (encryption, cross-session isolation,
   isolated object namespaces, immediate idempotent deletion, content-free logging) and which
   are replaced (pseudonymity, seven-day expiry, single-use invitation).

Item 5 is the one that must not be deferred. Chartering a commercial family while
`KHEPRI-DEC-003`'s beta boundary stands accepted leaves two accepted artifacts describing
incompatible products.

## Kill test, carried forward

From `docs/khepri-commercial-roadmap.md` Phase 0B, and worth repeating because it costs nothing:

> Write the pricing page copy before writing the family charter. If you cannot state in three
> sentences why a chain pays monthly for this, the charter is premature.
