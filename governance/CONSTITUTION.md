# Khepri Constitution

Version: 3.0.0

Effective when merged to `main`

Authority: Ahmed Shaaban, sole repository owner

## I. Sole authority

Ahmed Shaaban is Khepri's sole decision authority. Automation checks facts and consistency; it
does not approve changes or act as a separate authority.

## II. Approval has one home per artifact

Product decisions and specifications created after this version takes effect are approved when
the sole owner records them as **Approved** on a canonical Confluence page in space KHEPRI:
explicit, attributed, dated, and naming any record they supersede. A Draft or Proposed page, and
any edit made by an agent, carries no authority.

Every change to this repository (code, executable contracts, tests, CI, and the artifacts
`governance/registry.yaml` lists) is proposed while it exists only on a branch or pull request, and is accepted
into `main` when the sole owner merges it. The merge approves that change. It never approves a
product decision or specification whose home is Confluence. The Git record supplies the approval
identity, content, and time for repository changes; Khepri maintains no parallel approval ledger.

Artifacts that `governance/registry.yaml` lists at the effective date keep their repository home
and stay approved as merged. Only a later change merged by the owner retires or amends them. A
decision or specification first listed after that date admits no product code, unless it only
retires or amends a listed artifact; KHEPRI-DEC-036 is the one decision added with this version.

## III. One registry

`governance/registry.yaml` is authoritative for the type, identity, state, document,
dependencies, and supersession of the artifacts it lists. Markdown explains intent but cannot
override the registry. The registry lists no Confluence record, and no Confluence page approves
or retires a listed artifact. `governance/ATLASSIAN-TRANSITION.md` records where each listed
identifier's authority lives. External and predecessor material is reference only and grants no
authority.

## IV. Specification before product code

Product code is admitted only in small, independently verifiable slices linked to a primary
Approved specification that the pull request names, plus any others it relies on: the active
registry specification that governs the behavior, or, where none does, an Approved Confluence
specification cited by page and version.
Where both would apply, the registry specification governs until the owner merges its
retirement. Automation cannot read Confluence; the owner checks the cited record at merge, and a
slice with no citable Approved specification is not admitted. A slice does not widen its
specification, privacy boundary, runtime boundary, or data use. Material boundary changes require
the owner to approve an updated or new artifact at its Article II home first.

## V. Fail closed

Unknown schemas, artifact types, states, documents, dependencies, cycles, family relationships,
and supersession references block validation. Automation reports ambiguity instead of inferring
missing authority or intent.

## VII. Privacy and least data

Khepri defaults to collecting, retaining, exposing, and processing the least data necessary.
New data use requires an explicit purpose, owner, boundary, retention decision, and approval.
Approval here is Article II's, at the artifact's home.

## Lifecycle

- `active`: governing on `main`.
- `retired`: retained for context but not governing.

Retired artifacts may name one active successor through `superseded_by`. Drafts and proposals live
on branches and pull requests, or as Draft or Proposed Confluence pages, not in the authoritative
lifecycle.
