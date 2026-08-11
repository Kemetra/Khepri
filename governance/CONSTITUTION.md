# Khepri Constitution

Version: 2.0.0

Effective when merged to `main`

Authority: Ahmed Shaaban, sole repository owner

## I. Sole authority

Ahmed Shaaban is Khepri's sole decision authority. Automation checks facts and consistency; it
does not approve changes or act as a separate authority.

## II. Merge is approval

A change is proposed while it exists only on a branch or pull request. It becomes approved and
governing when the sole owner merges it to `main`. The Git record supplies the approval identity,
content, and time; Khepri maintains no parallel approval ledger.

## III. One registry

`governance/registry.yaml` is authoritative for governed artifact type, identity, state, document,
dependencies, and supersession. Markdown explains intent but cannot override the registry.
External and predecessor material is reference only and grants no authority.

## IV. Specification before product code

Product code is admitted only in small, independently verifiable slices linked to an active
specification. A slice does not widen its specification, privacy boundary, runtime boundary, or
data use. Material boundary changes require the owner to merge an updated or new artifact first.

## V. Fail closed

Unknown schemas, artifact types, states, documents, dependencies, cycles, family relationships,
and supersession references block validation. Automation reports ambiguity instead of inferring
missing authority or intent.

## Lifecycle

- `active`: governing on `main`.
- `retired`: retained for context but not governing.

Retired artifacts may name one active successor through `superseded_by`. Drafts and proposals live
on branches and pull requests, not in the authoritative lifecycle.
