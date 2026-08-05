# Proposed governance drafts

**None of these is a governed artifact.** They are drafts for owner review. No file under
`governance/` was created or modified; no registry entry exists; no identifier is allocated;
no approval state changed. `uv run khepri-gov validate` passes unchanged.

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

`KHEPRI-DEC-012` is cited by its real identifier throughout, because it already exists. The
amendment draft edits an existing artifact and allocates nothing.

## Contents

| Draft | Intended target | Purpose |
|---|---|---|
| [`identifier-survey.md`](identifier-survey.md) | — | What the registries hold, and what a next value *would* be if derived. Provisional candidates only; nothing reserved. |
| [`KHEPRI-DEC-012-amendment.md`](KHEPRI-DEC-012-amendment.md) | `governance/decisions/KHEPRI-DEC-012-…md` (edit) | Adds the tooling-runtime vs analytical-contract distinction **before** DEC-012 is accepted |
| [`decision-draft-seshat-boundary.md`](decision-draft-seshat-boundary.md) | `governance/decisions/<derived-id>-seshat-analytical-boundary.md` | `[DEC-BOUNDARY]` — dependency shape, analytical ownership, the no-package source of truth, and the metric-authority precondition |
| [`family-charter-draft-commercial.md`](family-charter-draft-commercial.md) | `governance/families/<CODE>.md` | `[FAM-COMMERCIAL]` charter, plus the `RRA.md` re-scope it forces |

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
