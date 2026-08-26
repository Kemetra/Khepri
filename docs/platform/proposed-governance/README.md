# Proposed governance drafts

**None of these is a governed artifact.** They are drafts for owner review. No file under
`governance/` was created or modified; no registry entry exists; no identifier is allocated;
no approval state changed. `uv run khepri-gov validate` passes unchanged.

> **Progress note added 2026-08-22.** `specification-draft-rca-002-commercial-shell.md` has been
> promoted. `RCA-002` now exists at `governance/specifications/RCA-002.md` and is `active` in
> `governance/registry.yaml`, so **that file is no longer a draft and the paragraph above does not
> describe it.** It is retained here as the review record — what was proposed, so a later reader can
> compare it against what landed. Two deliberate differences: the promoted specification drops the
> draft's framing sections (the DRAFT banner, "Placement", "Two placements this specification
> settles", and "Note on scope discipline"), which argued *for* the specification rather than
> stating it; and its registry entry depends on `RRA-006` and `RRA-009` as well as `RCA` and
> `RCA-001`, because `FR-054` and `FR-057`/`FR-058` carry obligations those specifications fix.
>
> **Progress note added 2026-08-08 (`main` @ `04acba3`).** Two of the four drafts below have
> since been promoted and approved. `KHEPRI-DEC-012-amendment.md` and
> `family-charter-draft-commercial.md` are no longer pending: `KHEPRI-DEC-012` was amended then
> accepted (`APP-015`, 2026-08-06), and the commercial charter was approved as `APP-017`
> (2026-08-08), landing `KHEPRI-DEC-014` (accepted), `RCA` (active), and the renewal of `RRA.md`
> in one atomic package — see
> [`khepri-commercial-roadmap.md`](../../khepri-commercial-roadmap.md) Phase 0B and
> [`cross-repository-pr-sequence.md`](../cross-repository-pr-sequence.md) §0 for the gate status
> that package closed. This directory's own text below (the placeholder table, the sequencing
> constraint, the digest hazard example) is left as drafted rather than rewritten, since it
> describes the state before promotion; read it for the reasoning, and the two notes above for
> current status. `decision-draft-seshat-boundary.md` remains an unpromoted draft — no
> `[DEC-BOUNDARY]` decision exists — and `identifier-survey.md` still describes a registry state
> that has since moved (`KHEPRI-DEC-012` is no longer the highest *unaccepted* decision, and
> `RCA`/`KHEPRI-DEC-014` are no longer placeholders); neither is corrected here, per the same
> no-rewrite rule.

Each draft states its intended target path and the exact registry block it would need.
Promoting one is a single owner-directed move.

## No identifier is allocated

Drafts here are named by **planning placeholder**, never by a governed identifier. A file called
`KHEPRI-DEC-013-draft.md` would already be *using* the number it claims not to have taken, which
is why none exists.

| Placeholder | What it would be |
|---|---|
| `[DEC-BOUNDARY]` | The decision governing Khepri's relationship with Seshat-BI |
| `[DEC-COMMERCIAL]` | The decision superseding `KHEPRI-DEC-003`'s beta boundary |
| `[FAM-COMMERCIAL]` / `<CODE>` | The commercial product family and its three-letter code |
| `[PKG-GOV]` | The approval package carrying a governance set |
| `[PKG-RRA-RENEWAL]` | The renewal package required to change `RRA.md` |
| `[RRA-PRESENTATION]` | The narrow `RRA` specification governing beta journey presentation maintenance |

`KHEPRI-DEC-012` is cited by its real identifier throughout, because it already exists. The
amendment draft edits an existing artifact and allocates nothing.

## Contents

| Draft | Intended target | Purpose |
|---|---|---|
| [`identifier-survey.md`](identifier-survey.md) | — | What the registries hold, and what a next value *would* be if derived. Provisional candidates only; nothing reserved. |
| [`KHEPRI-DEC-012-amendment.md`](KHEPRI-DEC-012-amendment.md) | `governance/decisions/KHEPRI-DEC-012-…md` (edit) | Adds the tooling-runtime vs analytical-contract distinction **before** DEC-012 is accepted |
| [`decision-draft-seshat-boundary.md`](decision-draft-seshat-boundary.md) | `governance/decisions/<derived-id>-seshat-analytical-boundary.md` | `[DEC-BOUNDARY]` — dependency shape, analytical ownership, the no-package source of truth, and the metric-authority precondition |
| [`family-charter-draft-commercial.md`](family-charter-draft-commercial.md) | `governance/families/<CODE>.md` | `[FAM-COMMERCIAL]` charter, plus the `RRA.md` re-scope it forces |
| [`specification-draft-rra-beta-journey-presentation.md`](specification-draft-rra-beta-journey-presentation.md) | `governance/specifications/RRA-<assigned>.md` | `[RRA-PRESENTATION]` — the missing presentation authority for the surface `RCA-002:132-135` assigns to `RRA`. Added 2026-08-26 against `main` @ `7327695`. Owner rulings D-1 through D-4 applied; unpromoted, no identifier taken, dependency wiring deferred to activation |

## Sequencing constraint that shapes all of them

`KHEPRI-DEC-012` is **`proposed`**. Its own closing line: "While it remains `proposed` it is
reasoning on the record, not authority."

- Amend it now → an edit to an unaccepted draft. Cost: one review.
- Accept it, then amend → a supersession, a new decision, a new approval package. Cost:
  a governed change to an accepted artifact.

Roadmap §10 Phase 0 lists the amendment as item 3, after the boundary decisions. **That order
is more expensive than it needs to be.** The amendment should land first.

## Digest hazard before editing any governed document

`APP-013.yaml` binds `KHEPRI-DEC-005` by `document_sha256`, and `khepri-gov validate` fails
closed on any edit — confirmed empirically in a prior session, where the edit was attempted,
rejected, and reverted. Before editing `RRA.md` or any accepted decision, check whether an
approval package pins it. If one does, the change needs a **renewal approval package**, not an
edit.

`KHEPRI-DEC-012` is not pinned by any approval package, because it has never been approved.
That is what makes the amendment cheap.
