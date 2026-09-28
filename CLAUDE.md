# Khepri — Claude Code operating model

How Claude Code works in Khepri: which system holds which truth, and how one unit of work moves
from inspection to merge. This file governs behavior; it does not document Khepri. The
repository-wide agent rules apply first and are not restated here:

@AGENTS.md

`governance/CONSTITUTION.md`, `governance/registry.yaml`, and active specifications outrank this
file. If a rule here conflicts with them, follow the governance and report the conflict.

## Authority

When sources conflict, trust them in this order:

1. **The owner's current explicit decision.** It steers execution within existing authority. A
   decision that changes a governed boundary (scope, privacy, runtime, data use) governs only once
   the owner merges the artifact that records it (Constitution II, IV). Until then, report the gap
   and do not implement ahead of it.
2. **Active governance and specifications**: registry state first, then the spec's §Scope. They
   say what may be built.
3. **Current `main` and repository evidence**: `git log`, tests, merged PRs. They say what exists.
4. **Jira execution scope** (project `SCRUM`).
5. **Confluence, Atlassian Projects and Goals.**
6. **Prototypes, design handoffs, historical notes, old comments, predecessor repositories.**

Never implement stale Jira or Confluence scope when GitHub authority has moved. Do not reopen a
settled owner decision unless new evidence materially invalidates it; then present the evidence,
not a fresh option list.

## Which system holds which truth

| System | Holds | Is not |
|---|---|---|
| GitHub | Code, specs/governance, tests, technical issues, PRs, merged state | — |
| Jira `SCRUM` | Executable work, priority/order, execution status, blockers, bounded slices | A mirror of every GitHub issue |
| Confluence | Current State, roadmap summaries, decisions, risks/readiness, diagrams | A home for technical specs; link to GitHub |
| Atlassian Projects/Goals | Milestone health, phase, major outcomes, success measures, major risks | Technical evidence |
| ChatGPT | Coordination: reconciles GitHub vs Atlassian, finds drift, picks next work, prepares handoffs | Implementation |
| Claude Code | Implementation of one bounded Jira item or GitHub slice | Licence to expand into adjacent work |

Technical completion requires GitHub evidence. A Confluence decision page is context; a governed
decision exists only in `registry.yaml`.

Jira statuses: **To Do** = valid future work; **In Progress** = actively being implemented;
**In Review** = implementation complete and under review; **Done** = merged or accepted, with
repository evidence. Documentation that says work is complete is not evidence.

## Workflow

inspect → decide → Jira scope (when needed) → implement → validate → review → PR → merge →
reconcile

Before adding a plan, Jira item, document, decision, diagram, review, or governance artifact, ask:
does it unblock implementation, is it required by governance, or does it materially reduce risk?
If all three answers are no, skip it. Once work is implementation-ready, execute.

**Before non-trivial implementation:**

1. Check `git status`, the current branch, and `main` against `origin/main`.
2. Check open PRs that overlap the slice, when relevant.
3. Read the Jira item, when the work is Jira-backed.
4. Read the active specs and governance for the files you will touch (registry state, not the
   spec header).
5. Reconcile Jira scope with GitHub authority. If Jira is stale, report the discrepancy first and
   do not build the stale scope.
6. Name the smallest complete executable slice.

Small technical fixes may stay GitHub-only when a Jira item adds no execution value. Product code
still needs an active specification (Constitution IV).

## Scope

Implement only the requested slice. Do not silently add neighboring Jira work, opportunistic
refactors or cleanup, speculative architecture, dependency upgrades, schema or migration changes,
CI changes, unrelated documentation, or UI redesigns. Record adjacent findings separately instead.
Prefer small but complete PRs; do not split tightly coupled work into micro-PRs.

## Git and execution boundaries

- Stage named files only. Never `git add -A` or `git add .`. Never stage, discard, or rewrite
  unrelated local changes.
- Give each parallel write-capable agent its own worktree.
- The boundaries are implementation, validation, commit, push + PR, post-PR fixes, merge
  preparation, and merge. Cross only the ones requested. "Implement" does not mean commit, and
  "open a PR" does not mean merge.
- **Merge is approval** (Constitution II). Claude merges only under an explicit owner grant for
  that PR or session; a grant never carries into a later session. Merges that change governed
  artifacts (constitution, registry, decisions, families, specifications) go back to the owner.
- Stop and report on unexpected modified files, merge conflicts, material unrelated failures, or
  scope creep.
- Never claim tests or CI passed unless you observed it. Read the counts line; a skipped browser
  test is not a pass.
- Beyond the `AGENTS.md` gates, fill in the PR template's claims table and run
  `coderabbit review --agent` locally before the first push.

## Completion and reconciliation

Work is technically complete after code → tests → validation → review → merged PR. After a merge,
reconcile only what actually changed:

1. Verify that `main` contains the merge.
2. Update or close the GitHub issue, if one is relevant.
3. Move the Jira item to Done.
4. Update the parent Epic only if its real state changed.
5. Update Confluence only if durable project context changed.
6. Update Projects/Goals only for milestone-level change.

Trivial commits need no Atlassian update.

## Status and "what next?"

Triggers include "check", "update", "راجع", "وضعنا إيه؟", "what next?", and "راجع المشروع". Do
not answer from memory or stale summaries; roadmap tables and plan checkboxes drift. Inspect
enough current GitHub (`main`, open PRs, issues, registry) and Atlassian (Jira `SCRUM`, Confluence
Current State) evidence to detect drift:

- merged work still pending in Jira;
- stale blockers;
- closed GitHub issues shown as active;
- Jira scope contradicted by current specs;
- stale Confluence priorities;
- Project/Goal status inconsistent with execution;
- overlapping open PRs.

For "what next?": identify the highest-priority executable Jira item or bounded technical slice,
separate executable from deferred work, name the actual blockers, and recommend **one** concrete
next action rather than a wishlist.

State a blocker as: what is blocked → exact reason → minimum unblocker → what becomes executable
afterwards. A future production gate does not block current local implementation.

## UI work

Load the `khepri-ui` skill. It holds the UI authority chain, the prototype-is-evidence rule,
Arabic/English parity, RTL, accessibility, and the refusal, caveat, and evidence semantics. It
also forbids generic SaaS redesigns. In addition: keep presentation changes distinct from
backend or product capability, do not rerun design review on unchanged work, and once the visual
direction is settled, implement.

## Owner control

The owner decides product direction, irreversible architecture, production exposure,
consequential security decisions, major priority changes, and every merge that constitutes
approval. Do not escalate routine implementation or coordination choices that an active spec,
repository evidence, or an earlier explicit owner decision already settles. Raise real owner items
briefly, each with a recommendation.
