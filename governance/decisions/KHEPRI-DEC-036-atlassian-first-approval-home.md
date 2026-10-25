# KHEPRI-DEC-036: Atlassian-First Approval Home

## Context

KHEPRI-DEC-017 made the owner's merge to `main` the approval for every governed artifact, and
`registry.yaml` the index of all of them. That put product decisions and specifications in the
same repository as the code, so a change to product direction needed a code-style pull request.

On 2026-10-24 the owner approved the Atlassian-first direction recorded on the Confluence page
[Khepri - Atlassian-First Governance - Owner Decision - 2026-10-24](https://rahmaqanater.atlassian.net/wiki/spaces/KHEPRI/pages/55345155)
(page 55345155). That page states that the repository rules stay in force until a reviewed
transition pull request is merged by the owner, and that no repository safeguard is weakened.
Jira execution moved from project `SCRUM` to `KH`; this change is tracked as KH-43.

## Decision

Approval has one home per artifact (Constitution 3.0.0, Article II):

- Product decisions and specifications created after this decision takes effect are approved when
  the owner marks them **Approved** on a canonical Confluence page in space KHEPRI.
- Every repository change, and every artifact listed in `registry.yaml` at the effective date,
  keeps the owner's merge to `main` as its approval and its repository home.
- The registry lists no Confluence record. No Confluence page approves, amends, or retires a
  listed artifact; only a later owner-merged change does.
- Product code is admitted against one Approved specification named in the pull request: the
  active registry specification that governs the behavior or, where none does, an Approved
  Confluence specification cited by page and version. If both apply, the registry specification
  governs.
- Jira `KH` tracks execution only. GitHub proves what was built.

This decision narrows the approval bullet of KHEPRI-DEC-017 (the owner's merge is approval) to
repository changes and registry-listed artifacts, and reads the registry-authority bullet of
FND-001 the same way. KHEPRI-DEC-017 and FND-001 stay active with their bodies unchanged, and the
registry's active/retired lifecycle is unchanged.

## Retained guarantees

- The validator, `registry.yaml` schema, and every CI check are unchanged and still fail closed
  (Constitution V). Automation cannot read Confluence, so it neither grants nor checks Approved
  status; the owner checks the cited record when merging.
- Privacy, runtime, security, and data boundaries are unchanged; Article VII's substance is
  unchanged and only its approval pointer is generalized. No product behavior changes.
- A decision or specification first listed in the registry after this change admits no product
  code unless it only retires or amends a listed artifact (Constitution II).
- No identifier is renumbered, reused, or deleted. `governance/ATLASSIAN-TRANSITION.md` maps each
  legacy identifier to the home of its authority.

## Consequences

- A legacy artifact cannot yet be retired in favor of a Confluence record, because
  `superseded_by` names only an active registry artifact of the same type. Until a later
  validator change, a legacy artifact is retired or amended only by an owner-merged repository
  change.
- Where a legacy requirement has no Confluence record, its current guard stays. Nothing here
  converts a legacy specification into a Confluence one.
- The repository roadmap, Khepri Operating System, Decisions index, and space guidance are
  reconciled after this change merges, under KH-22 and the owner decision page. This decision does
  not declare them reconciled.
- Out of scope: product features, hosted rollout, spending, AWS migration, AI on customer data,
  production or security approval, and deleting registry history.

## Verification

The repository must pass:

```text
uv run khepri-gov validate
uv run ruff check .
uv run pytest
```
