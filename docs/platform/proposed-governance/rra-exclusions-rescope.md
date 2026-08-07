# Proposed re-scope of `governance/families/RRA.md`

**Status:** staged replacement text for owner approval. Applies nothing. `RRA.md` is unchanged and
remains pinned by `APP-002`.

`KHEPRI-DEC-014` §4 requires this re-scope, and requires it be carried by a renewal package rather
than an edit. `governance/families/RRA.md` is pinned at
`sha256:8a1235a0d6b9e36a6446a1e1cfd3f7ef5db52ca7d9e0ed23bcffb18eded095d2` by
`governance/approvals/APP-002.yaml`, verified still matching on 2026-08-07 with
`uv run khepri-gov document-digest governance/families/RRA.md`. `khepri-gov validate` rejects any
change to it that no renewal authorizes.

## Why the current text cannot stand once RCA is active

`RRA.md`'s Excludes are flat prohibitions: billing, subscriptions, scheduling, and public signup are
*excluded*, full stop. Once `RCA` owns billing, "billing is excluded" reads two ways — excluded from
`RRA`, or excluded from Khepri — and Constitution I requires one authoritative representation per
governed fact.

`FND.md` already solves this correctly, excluding "customer features, business or domain logic,
infrastructure services, and responsibilities of future product families" and stating those
boundaries "require separately approved families and specifications." The re-scope below adopts that
phrasing.

## Two changes, and no others

1. **The Excludes block** is re-expressed as family boundaries rather than prohibitions.
2. **The closing sentence** is corrected. It currently reads "The family is proposed" while
   `governance/registries/families.yaml` records `state: active` — the same stale-closing-sentence
   defect the roadmap records for `KHEPRI-DEC-005`. A pinned document admits no drive-by fix, so it
   is corrected here or not at all.

No line in `## Owns` changes. `RRA` keeps every responsibility it has.

## Replacement text for `## Excludes` and the closing line

> ## Excludes
>
> - Responsibilities of the `RCA — Retail Commercial Analysis` family: commercial authentication,
>   user profiles, persistent customer workspaces, organizations, membership roles, billing,
>   subscriptions, scheduling, public signup, agency portfolios, client switching, delegated access,
>   work queues, and white labeling. Those boundaries require separately approved specifications
>   under that family.
> - Forecasting, generic analysis, customer-authored formulas, and unsupported metrics. These are
>   excluded from Khepri rather than allocated to another family.
> - Runtime or provider selection before a separate architecture decision is accepted.
> - Product implementation while this family's specifications remain draft.
>
> The family's authoritative lifecycle state and approval evidence are recorded in
> `governance/registries/families.yaml`.

## What changed, line by line

| Current | Replacement | Why |
|---|---|---|
| "Commercial authentication, … and public signup." + "Agency portfolios, … and white labeling." (two bullets, flat prohibitions) | One bullet naming `RCA` as the owner and requiring separately approved specifications | Removes the excluded-from-Khepri reading; adopts `FND.md`'s phrasing |
| "Forecasting, generic analysis, customer-authored formulas, and unsupported metrics." | Same list, plus "excluded from Khepri rather than allocated to another family" | Prevents a later reader assuming `RCA` inherited them |
| "Runtime or provider selection before a separate architecture decision is accepted." | Unchanged | `KHEPRI-DEC-008` still governs it and is still `proposed` |
| "Product implementation while this family remains proposed or its specifications remain draft." | "Product implementation while this family's specifications remain draft." | The family is active; the "remains proposed" clause is dead text |
| "The family is proposed. Its authoritative lifecycle state…" | "The family's authoritative lifecycle state…" | Corrects the stale state claim |

### A Seshat boundary bullet is deliberately not added

An earlier draft of this re-scope added "Analytical capabilities owned by `Kemetra/Seshat-BI` under
`KHEPRI-DEC-013`." That bullet is **omitted**, because `KHEPRI-DEC-013` is `proposed` and citing an
unaccepted decision as a governed boundary is the borrowed-authority failure Constitution III
forbids.

If `KHEPRI-DEC-013` is `accepted` before this package is approved, the bullet may be added in the
same renewal. If it is not, `RRA.md` gains no Seshat boundary and nothing is lost — `RCA.md`'s own
Excludes state the boundary in family terms without citing the unaccepted decision.

## Mechanism

`APP-017` carries this as a renewal entry, mirroring `APP-013.yaml`'s renewal of
`KHEPRI-DEC-005`:

```yaml
  - id: RRA
    document: governance/families/RRA.md
    document_sha256: sha256:<digest of RRA.md AFTER the replacement is applied>
    from_state: active
    to_state: active
    supersedes_approval_ref: governance/approvals/APP-002.yaml
```

`from_state` equals `to_state` because the renewal validator raises `renewal must preserve state`
otherwise. The digest is computed from the edited file, so the sequencing at approval time is:

1. apply the replacement text to `governance/families/RRA.md`
2. `uv run khepri-gov document-digest governance/families/RRA.md` → into `APP-017`'s `RRA` entry
3. `uv run khepri-gov approval-digest governance/approvals/APP-017.yaml` → into `manifest_digest`
4. then approve

That order is not optional. A digest taken before the edit pins bytes that no longer exist, and the
validator fails closed on it.
