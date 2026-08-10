# Tasks: Governance v2

**Feature**: `specs/003-governance-v2/`
**Created**: 2026-08-10
**Status**: Working material — not governed, not approved

Legend: `[ ]` pending · `[~]` blocked on owner · **[P]** parallelisable with siblings

---

## W1 — Digest and drift enforcement

*No owner action. Retires the `APP-018`..`APP-021` defect class.*

- [ ] **T-101** Fixture from the `APP-021` defect: `RCA.md` at its pre-fix bytes, plus a registry
      entry pinning the superseded digest. This is the known-positive; without it W1 is untested.
- [ ] **T-102** `khepri-gov digest-check` — walk registry entries with `document` +
      `document_sha256`, recompute via `digests.py`, compare. Exit non-zero listing artifact,
      expected, actual, path. *Depends: T-101.*
- [ ] **T-103** **[P]** Unit tests: match, mismatch, missing file, entry lacking a pin, multiple
      simultaneous mismatches. *Depends: T-102.*
- [ ] **T-104** **[P]** Wire `digest-check` into the `governance` CI workflow as its own job
      (FR-002). *Depends: T-102.*
- [ ] **T-105** **[P]** Wire into pre-commit (existing config if present, else git hook)
      (FR-001). *Depends: T-102.*
- [ ] **T-106** Corpus survey: catalogue lifecycle-conditioned phrasings across
      `governance/families/*.md` and `governance/specifications/*.md`. **Output is a list, not a
      checker** — measure the false-positive surface before writing the rule.
- [ ] **T-107** Self-disarming rule check (FR-003), scoped to normative sections, honouring
      `<!-- lifecycle-ok: reason -->` and reporting each suppression. *Depends: T-106.*
- [ ] **T-108** **[P]** Tests for T-107: `APP-021` pre-fix text fails; post-fix passes; a
      legitimate lifecycle mention does **not** fire; a suppressed case reports. *Depends: T-107.*
- [ ] **T-109** Full gate run — `validate`, `delegation-guard`, `ruff`, `pytest` (1711 baseline) —
      then PR. *Depends: T-103..T-105, T-108.*

## W2 — Harness autonomy

*No owner action, no governance change. Independent of W1 — may run in parallel.*

- [ ] **T-201** Audit this session's blocked commands as the requirement set: `khepri-gov validate`,
      `git commit` (heredoc), `git push origin main` ×2.
- [ ] **T-202** Draft `.claude/settings.json` allowlist: enumerated verbs only, never bare `git` or
      `gh`. *Depends: T-201.*
- [ ] **T-203** Verify the withheld set stays gated (FR-007): `push --force`, `reset --hard` on
      shared refs, `rebase`, `filter-branch`, `push --delete`, `gh repo delete`, unscoped `rm -rf`.
      *Depends: T-202.*
- [ ] **T-204** Confirm end to end: branch → commit → push → PR → merge with zero prompts
      (SC-001). *Depends: T-202, T-203.*

## W3 — The amendment

*Drafting is instructed. Ratification is the owner's.*

- [ ] **T-301** Re-read `KHEPRI-DEC-011` immediately before drafting and mirror its structure:
      Context → numbered Decision clauses with complete quoted replacement text → Consequences.
- [ ] **T-302** **Resolve the Article V tension in writing** — that Article V forbids a gate acting
      as *approver*, while clause 3 removes the *requirement of an approval act* for reversible
      artifacts, leaving the agent as named authority under Article II with CI as evidence.
      **If this cannot be drawn cleanly, withdraw clause 3 and ship W1+W2 only.** *Depends: T-301.*
      **This is the gate on the whole amendment — do not draft around it.**
- [ ] **T-303** Author `governance/decisions/KHEPRI-DEC-016-governance-v2.md` at `proposed`,
      carrying complete replacement text for Article VIII (FR-009..015). *Depends: T-302.*
- [ ] **T-304** Register `KHEPRI-DEC-016` in `governance/registries/decisions.yaml` at `proposed`.
      *Depends: T-303.*
- [ ] **T-305** Author `governance/approvals/APP-023.yaml` at `state: proposed` with **no approval
      block**. `document_sha256` first, then `manifest_digest`. *Depends: T-303, T-304.*
      **`APP-022` is taken** — W1 consumed it for the RRA charter renewal, and it is the
      authoritative approval evidence in `families.yaml`. Reusing the ID would destroy that
      evidence. Confirm the next unused ID at authoring time rather than trusting this number.
- [ ] **T-306** Gate run, then PR — describing precisely what ratification would authorize.
      *Depends: T-305.*
- [~] **T-307** **OWNER: ratify `APP-023`.** The single blocking item. Cannot be delegated —
      Article VIII reserves the constitution, and an agent-approved amendment shrinking the agent's
      own reserved set is exactly what bootstrap containment prevents. *Depends: T-306.*
- [ ] **T-308** Transcribe DEC-016's quoted text into `CONSTITUTION.md` (v1.2.0) and flip the
      registry entry to `accepted`. **Mechanical only — compose nothing.** *Depends: T-307.*
- [ ] **T-309** Widen `is_reserved_file()` / `reserved_artifact_errors()` to the new categories
      (FR-017). *Depends: T-308.*
- [ ] **T-310** **[P]** Update `delegation.py` tests for the new reserved set. *Depends: T-309.*
- [ ] **T-311** **[P]** Verify FR-015 — every existing approved artifact still validates; no
      historical package invalidated. *Depends: T-309.*
- [ ] **T-312** Final gate run and PR. *Depends: T-309..T-311.*

## Post-amendment

- [ ] **T-401** `DEL-007` expiry warning ahead of 2026-11-08 (FR-016). Independent of W3.
- [ ] **T-402** Measure **SC-007a** at +30 days: zero state-preserving renewal packages
      (`APP-019`/`APP-021` class). The original SC-007 was withdrawn — its 72:58 ratio came from
      `git log --all`; on `main` it is 53:57 and already in product's favour.

---

## Critical path

```
T-101 → T-102 → T-104/T-105 → T-109                 W1 ships
T-201 → T-202 → T-204                                W2 ships
T-301 → T-302 → T-303 → T-305 → T-306 → [T-307 OWNER] → T-308 → T-309 → T-312
```

**W1 and W2 are fully independent of W3.** If ratification never comes, they still deliver
FR-001..008 — which is where the measured friction actually was.

## Two rules that hold regardless

1. **T-307 blocks T-308.** No transcription, no enforcement widening, on the strength of having
   drafted the decision. Drafting is not ratification.
2. **`APP-023` carries no approval block.** If a draft ever grows one, that is the failure mode
   this entire design exists to prevent.
