# M3 roadmap reconciliation — disposition record

**Baseline:** `main` @ `739d474`, 2026-08-26.
**Artifacts reconciled:** `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`,
`docs/product/KHEPRI_PRODUCT_UX_BLUEPRINT.md`, `governance/registry.yaml`.
**Grants no implementation authority.** This record changes no LOCKED decision, resolves no
CONFLICT-BLOCKED item, and introduces no decision ID. D4 observes that `CONFLICT-BLOCKED` is itself
undefined in the blueprint and recommends defining it — that is a documentation fix, and it resolves
no item marked with it.

## What this is, and what it deliberately is not

This reconciles the two M3-bearing product documents against each other and against registry
state. It reports a **disposition per divergence**: correct as recorded, fixable drift, or
requiring owner authority.

It does **not** resolve the navigation-scope conflict. Under the blueprint's own precedence chain
(§1) the roadmap governs, and narrowing `W1-05` is a roadmap amendment the blueprint states it
cannot perform (§8). Performing it here would grant authority no registry artifact confers.

**Not machine-checked.** No test parses either document. Verified two ways, because a grep for the
filenames alone would miss a path built from parts: `tests/` contains exactly one construction of a
path into `docs/` — `test_rca001_authorization_matrix.py:167,170`, which opens the `r6-01` design
note — and the only `.md` files any test reads are that note, `STATUS.md`, and files under
`governance/`. `tests/test_rca001_status_consistency.py` is scoped to
`specs/001-rca-001-commercial-identity/STATUS.md` alone.

Every claim below was derived by hand at the baseline above and will drift. Treat it as a dated
snapshot, not a gate. Adding that gate is a reasonable follow-up and is deliberately **not** done
here: a scanner over these two documents is its own slice with its own self-tested-scanner
obligation (the idiom `test_rca001_status_consistency.py` establishes), not a rider on a
disposition record.

## Registry state of every program M3 cites

The finding that shapes this record. `governance/registry.yaml` (`schema_version: 2`) admits
`family`, `specification`, and `decision`. Searched for each program the blueprint names as an
authority dependency:

| Program | Cited as | In `governance/registry.yaml` |
|---|---|---|
| `W1` (`W1-01`…`W1-11`) | required contracts | **absent** |
| `G2` (`G2-01`…`G2-03`) | retention authority | **absent** |
| `G3` (`G3-01`…`G3-04`) | workspace authority | **absent** |
| `G4`/`C1` | comparison authority | **absent** |
| `T1` (`T1-01`…`T1-08`) | metric/quality contracts | **absent** |
| `RCA-002` | shipped-shell authority | `state: active` |
| `RRA-006`, `RRA-009` | report/evidence authority | `state: active` |

`grep -rE '\b(W1|G2|G3|G4|T1)(-[0-9]+)?\b' governance/` returns nothing. These are roadmap
*programs* (roadmap §7 lists `G2/G3/W1` as "New retention and RCA workspace authority" — authority
that does not yet exist), not registered artifacts. Every M3 slice therefore depends on authority
with **no registry entry in any state**.

This makes the blueprint's blocked labels correct. One label — `T1`'s, and only `T1`'s — understates
the block by naming a state the registry does not hold: see D1.

## Dispositions

### Correct as recorded — no action

| Item | Where | Why it is right |
|---|---|---|
| `M3-U1`…`M3-U5`, `M3-U8` CONTRACT-BLOCKED | blueprint §19 | Each names a `W1` prerequisite; `W1` is unregistered. |
| `M3-U6`, `M3-U7` AUTHORITY-BLOCKED | blueprint §19 | `G2`/`G3` unregistered; U7 additionally requires "a **registered** artifact", which is the precise condition. |
| §18 CONTRACT-BLOCKED / AUTHORITY-BLOCKED rows | blueprint §18 | Consistent with the table above. |
| Three SHIPPED rows' **cited authority** | blueprint §18 | Commercial shell + Team and Organization chooser cite `RCA-002`; Report / evidence surfaces cites `RRA-006`, `RRA-009`. All `state: active`. Evidence detail is **partly SHIPPED** with metric detail CONTRACT-BLOCKED on `T1` — correct, since `T1` is unregistered. *Scope: the authority citation only. Whether each row is still SHIPPED at the current tip is D2.* |
| Navigation-scope conflict, roadmap governing | blueprint §8, §21 | Precedence applied correctly; the needed amendment is named and correctly left unperformed. |
| `FR-049` slice-ordering constraint | blueprint §19 | `FR-049` verified in `governance/specifications/RCA-002.md:47`; `RCA-002` is `active`. Correctly labelled a constraint, not a preference. |
| `W1-05` citation `roadmap:746` | blueprint §8 | Line 746 is the `W1-05` row and does name six surfaces. Citation exact. |

### D1 — DRIFT, fixable: `T1` labelled `PROPOSED` as if it were registry state

**Where:** all three occurrences of `PROPOSED` in the blueprint, and they are the only three —
`:623` (§18 Quality summary row), `:631` (§18 prose, "`T1` is `PROPOSED`"), and `:705` (§21
quality-summary row). No other program is labelled this way, so the defect is `T1`-specific rather
than systemic.

`T1` has no registry entry, so it has no registry state. `PROPOSED` is a roadmap program label.
`governance/README.md:23` — "Markdown explains intent but cannot override registry state" — makes
the distinction load-bearing: an **unregistered** program is a *stronger* block than a proposed one,
because there is no artifact to activate.

Low severity and conservative in the safe direction: it never overstates readiness. Worth fixing
because it reads as a governance state and invites a planner to look for a `T1` entry.

**Fix, when a slice next touches these sections:** cite the label's source in prose rather than
restating it as state — "`T1` is a roadmap program and has no registry entry". The row's own status
stays CONTRACT-BLOCKED. No registry change, no decision ID.

Deliberately *not* a new bracketed token, but **not because the vocabulary is closed** — D4 shows it
is not. The reason is narrower and survives that: a token is a claim about *status*, and "`T1` is
unregistered" is a claim about the **registry**, which §1's vocabulary does not describe. Prose
keeps the two kinds of statement apart; a token would fuse them, which is the confusion D1 is
correcting in the first place.

### D2 — DRIFT, fixable: both baselines are stale

| Document | States | Verified | Status |
|---|---|---|---|
| Blueprint §head | `df9f1d1` (`origin/main`), 2026-08-26 | real commit, ancestor of `origin/main` | **3 commits behind** `739d474` |
| Roadmap §head | `main` @ `f865079…`, 2026-08-24 | real commit, ancestor of `origin/main` | **14 commits behind** `739d474` |

Both are valid ancestors — neither is a false or topic-branch baseline. But the blueprint defines
SHIPPED as "verified in the current implementation at the baseline SHA" (§1), so its three SHIPPED
rows are verified against a tip three commits old. One of those three commits (`739d474`) is the
blueprint's own.

**Fix:** restamp each baseline in the slice that next revises the document, after re-verifying the
SHIPPED rows. Restamping without re-verifying converts a stale-but-honest claim into a false one.

### D3 — OWNER DECISION REQUIRED: navigation scope

**Already recorded** in blueprint §8 and §21 (Navigation scope row, CONFLICT-BLOCKED). Restated
here only to confirm the disposition survives a registry check — it does, and the conflict is
narrower than it appears.

| | Blueprint (§8, LOCKED-as-written) | Roadmap `W1-05` (`:746`) |
|---|---|---|
| Surfaces | Overview, Data, Analyses, Team | Workspace Overview, Datasets, Analyses, **Reports**, **Metrics**, **Activity** |

Four blueprint rows contradict `W1-05` directly: Reports, Activity, Metrics, and the "Workspace"
label. Blueprint locked decisions 1, 2, 4, 19, 20 all carry the CONFLICT-BLOCKED marker.

**Not urgent, and that is a finding.** `W1-05` depends on `stable W1 API, U1`, and `W1-01` requires
an **active `G3`** — unregistered. The conflict cannot be reached by implementation until `G2`/`G3`
authority exists, so it is not blocking any admissible slice today.

**The option space is the one blueprint §8 already defines** — accept the direction and amend
`W1-05`, or keep `W1-05` and unlock the four blueprint rows. Recording a third option here would
widen a settled question; this record does not.

### D4 — DRIFT, fixable: `CONFLICT-BLOCKED` is used as a status but defined nowhere

**Where:** blueprint `:271`, `:279`, `:662`, `:663`, `:665`, `:680`, `:681`, `:712` — eight
occurrences. §1's status vocabulary table (`:33`–`:39`) does not contain it.

It is a real status in use, not prose. At `:712` it sits in the **status column** of §21's register,
in the same position as PROVISIONAL, CONTRACT-BLOCKED, and AUTHORITY-BLOCKED. At `:279` the document
writes "**CONFLICT-BLOCKED**, not LOCKED", contrasting it directly with a defined token — which is
only meaningful if both are the same kind of thing.

For precision, §1's table has **five rows** defining **six tokens**: row two, `PROVISIONAL /
CONTRACT-BLOCKED`, pairs two that are each used standalone (PROVISIONAL at `:312`, `:703`, `:718`,
`:719`; CONTRACT-BLOCKED throughout). `CONFLICT-BLOCKED` is a **seventh**, and the only one with no
definition.

**Severity:** higher than D1, because §8's precedence reasoning and five of §20's locked decisions
all rest on it. A reader cannot check whether "CONFLICT-BLOCKED" means "blocked until an owner
chooses" or "blocked until the roadmap is amended" — §8 implies the latter, but nothing states it.

**Fix:** add a row to §1's table defining it. That is a documentation edit to the blueprint, not a
governance change — the token already carries its meaning consistently in all eight uses, so
defining it records existing practice rather than deciding anything. No decision ID.

**Found by adversarial review of this record**, which is worth recording: this document's first
draft asserted the vocabulary was "a closed set of six" and used that as the reason for a fix in D1.
The premise was false and the reasoning rested on it. D1 now rests on the distinction between a
status claim and a registry claim, which holds regardless.

## Summary

Dispositions are named rather than counted. A count stated here and derived from a table above is
the same defect `tests/test_rca001_status_consistency.py` exists to catch — one fact in two places,
where editing a row leaves the total superficially plausible. Nothing enforces agreement in this
document, so it states each disposition once.

| Disposition | Items | Action |
|---|---|---|
| Correct as recorded | every row of the table above, each named there | none |
| Fixable drift | **D1** (`T1` labelled as registry state), **D2** (both baselines stale), **D4** (`CONFLICT-BLOCKED` undefined) | fold into the next slice touching those sections |
| Owner decision required | **D3** (navigation scope) | already registered in blueprint §21; not blocking |

**No M3 divergence requires action before implementation can proceed**, because no M3 slice is
admissible: every one depends on `W1`/`G2`/`G3`/`T1`, none of which is registered. The blueprint's
own conclusion (§18) — "Design may proceed; production code may not" — is confirmed.
