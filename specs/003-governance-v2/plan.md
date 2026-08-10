# Implementation Plan: Governance v2

**Feature**: `specs/003-governance-v2/`
**Created**: 2026-08-10
**Status**: Working material — not governed, not approved

## Sequencing principle

The three workstreams are **ordered by owner dependency, not by importance**. W1 and W2 need
nothing from the owner and carry most of the value; W3 needs one ratification. Doing W1 and W2
first means that if the owner never ratifies W3, the feature still delivers.

This ordering is also a hedge against the amendment being rejected. Nothing in W1 or W2 assumes
W3 lands.

```
W1 digest+drift ──┐
                  ├──> both land without owner action
W2 harness      ──┘
                        W3 amendment ──> requires APP-022 ratification
```

## W1 — Digest and drift enforcement (no owner action)

**Retires the `APP-018`..`APP-021` defect class.**

### W1.1 Registry-pin consistency check

New `khepri-gov digest-check`: walk every registry entry carrying `document` +
`document_sha256`, recompute, compare. Fail listing artifact, expected, actual, and path.

Reuses `digests.py` (14 lines) — this is a walk plus compare, not new crypto.

**Wire into**: `.pre-commit-config.yaml` if present, else a git hook; **and** the `governance`
CI workflow as its own job. FR-002 requires CI so the guarantee does not depend on local setup.

### W1.2 Self-disarming rule detection

Static check over `governance/families/*.md` and `governance/specifications/*.md` for normative
prose conditioned on a lifecycle state — `while this family remains proposed`, `until … is
approved`, `while … remains draft`, and near variants over the Article-VIII vocabularies.

Failure names file, line, and passage, with the `APP-021` remediation: restate against a real
precondition rather than a lifecycle state.

**Risk — false positives.** Legitimate prose describes lifecycle states without being conditioned
on them. Mitigation: match only inside `Excludes`/normative sections, and provide an inline
`<!-- lifecycle-ok: reason -->` escape that the check honours and reports. Tune against the corpus
before enabling; `APP-021`'s pre-fix text is the known-positive fixture.

### W1.3 Pin-update-in-same-commit

`digest-check` in W1.1 already enforces FR-004: editing a pinned document without updating the pin
fails the commit. No separate mechanism.

## W2 — Harness autonomy (no owner action, no governance change)

`.claude/settings.json` allowlist, repository-scoped.

**Allow**: `git add|commit|status|diff|log|branch|checkout|fetch|pull`, `git push` (non-force),
`gh pr create|view|list|comment|merge`, `uv run khepri-gov *`, `uv run ruff *`, `uv run pytest *`.

**Withhold** (FR-007): `push --force`/`--force-with-lease`, `reset --hard` on shared refs,
`rebase`/`filter-branch`/`push --delete`, `gh repo delete`, unscoped `rm -rf`.

**Merge gating** (FR-008) is a *behavioural* rule, not an allowlist rule: `gh pr merge` is
permitted, and the agent must verify all checks green first. The allowlist cannot express
"only when CI passes", so this is spec'd as agent obligation and observable in the PR record.

**Not a governed artifact.** `.claude/settings.json` is harness config; no package, no registry.

## W3 — The amendment (requires owner ratification)

Follows `KHEPRI-DEC-011` exactly: *an accepted decision containing the complete replacement text,
approved by the named human authority in a package, followed by a transcription that changes
nothing the decision did not state.*

### W3.1 `KHEPRI-DEC-016` — the decision

Carries **complete replacement text** for Article VIII so transcription is mechanical. Structure
mirrors DEC-011: Context → Decision (numbered clauses, quoted final text) → Consequences.

Clauses:

1. **Version** → `1.2.0`, `Amended: 2026-08-10 (KHEPRI-DEC-016)`.
2. **Article VIII paragraph 3 replaced** — reserved set restated by consequence (FR-009), adding
   privacy/retention/data-boundary, keeping constitution, authorities registry, delegation records,
   and reserved-set-altering decisions.
3. **Article VIII gains a paragraph** — artifacts outside the reserved set need no approval
   package; agent commit plus green CI is sufficient (FR-010).
4. **Paragraphs 2, 4, 5 unchanged verbatim** — attribution, 90-day cap, revocation, fail-closed
   (FR-011..014).
5. **Articles I–VII unchanged**; Article V keeps full force.
6. **Prospective only** (FR-015) — no historical package invalidated.

**Article V tension, addressed explicitly.** Article V holds that *"a passing technical check is
not approval."* Clause 3 makes green CI sufficient authority for non-reserved artifacts, which
reads as contradiction. It is not, and the decision must say why: Article V forbids treating a gate
as an *approver*. Clause 3 does not promote CI to approver — it removes the *requirement of an
approval act* for artifacts whose consequences are reversible, leaving the agent as the named
authority under Article II with CI as evidence. If this distinction cannot be drawn cleanly in the
final text, clause 3 is withdrawn and the feature ships W1+W2 only.

### W3.2 `APP-022` — the package

- `artifacts:` → `KHEPRI-DEC-016`, `proposed → accepted`
- `state: proposed`, **no `approval:` block**
- `document_sha256` then `manifest_digest`, in that order (the sequence `APP-017` fixed)
- Scope and exclusions naming what does not change

### W3.3 Transcription (only after ratification)

Mechanical application of DEC-016's quoted text to `CONSTITUTION.md`, plus the registry entry.
Nothing composed at this step.

### W3.4 Enforcement follow-through (FR-017)

`is_reserved_file()` and `reserved_artifact_errors()` widen to the new categories; package
validation applies to a smaller set. Deferred until after ratification — code must not anticipate
an unapproved amendment, which is the `KHEPRI-DEC-011` inversion ("implementing enforcement for an
unamended constitution would build machinery the governing document forbids").

## Ordering constraint

W3.1/W3.2 may be *drafted* now — that is what the owner instructed. W3.3/W3.4 execute **only**
after `APP-022` is ratified. The agent must not transcribe or widen enforcement on the strength of
having drafted the decision.

## Verification

Per workstream: `validate`, `delegation-guard`, `ruff`, `pytest` (1711 baseline), and for W1 a new
`digest-check` proving the `APP-021` fixture fails before the fix and passes after.

## Risks

| Risk | Mitigation |
|---|---|
| W1.2 false positives block legitimate prose | Scope to normative sections; `lifecycle-ok` escape; tune on corpus first |
| Article V tension unresolvable in text | Withdraw clause 3; ship W1+W2 |
| Amendment ratified, enforcement lags | Same inconsistency window DEC-011 accepted and documented; state it |
| Allowlist too broad | Enumerate allowed verbs; never allow bare `git`/`gh`; withhold destructive set |
| Owner never ratifies | W1+W2 deliver independently — this is why they run first |
