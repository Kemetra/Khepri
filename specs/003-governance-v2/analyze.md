# Cross-Artifact Analysis: Governance v2

**Feature**: `specs/003-governance-v2/`
**Created**: 2026-08-10
**Status**: Working material — not governed, not approved

## Traceability matrix

| FR | Requirement | Task(s) | Verified by |
|---|---|---|---|
| FR-001 | Pre-commit digest check | T-102, T-105 | T-103 |
| FR-002 | Same check in CI | T-104 | CI job |
| FR-003 | Reject lifecycle-conditioned prose | T-107 | T-108 |
| FR-004 | Pin updated in same commit | T-102 *(same mechanism)* | T-103 |
| FR-005 | Commit/push/PR without prompts | T-202 | T-204 |
| FR-006 | Read-only verification without prompts | T-202 | T-204 |
| FR-007 | Destructive ops stay gated | T-203 | T-203 |
| FR-008 | Merge only on green CI | T-202 *(behavioural)* | T-204 |
| FR-009 | Reserved set by consequence | T-303 | T-306 |
| FR-010 | No package outside reserved set | T-303 cl.3 | **T-302 gate** |
| FR-011 | Attribution verbatim | T-303 cl.4 | T-310 |
| FR-012 | Bootstrap containment verbatim | T-303 cl.4 | T-310 |
| FR-013 | Revocation verbatim | T-303 cl.4 | T-310 |
| FR-014 | 90-day cap verbatim | T-303 cl.4 | T-310 |
| FR-015 | Prospective only | T-303 cl.6 | T-311 |
| FR-016 | Expiry warning | T-401 | — |
| FR-017 | Enforcement shrinks | T-309 | T-310 |

**Gap closed by this pass.** A mechanical grep found FR-004, 005, 006, 008, and 010..014 uncited in
`tasks.md`. All are genuinely covered — FR-004 by the same check as FR-001, FR-011..014 by DEC-016
clause 4 which preserves four paragraphs verbatim — but coverage that only exists in the author's
head is the drift this feature exists to prevent. The matrix above is now the citation.

## Consistency findings

### F-1 — Article V tension is the feature's single point of failure ⚠ **HIGH**

FR-010 says non-reserved artifacts need no approval package. Article V says *"a passing technical
check is not approval."* Read carelessly, clause 3 promotes CI to approver — exactly what Article V
forbids.

The distinction the text must draw: Article V bars a **gate acting as approver**. Clause 3 does not
make CI an approver; it removes the **requirement of an approval act** for artifacts whose
consequences are reversible, leaving `KHEPRI-AGENT` as the named authority under Article II and CI
as evidence rather than authority.

Whether that distinction survives contact with the actual sentence is unknown until T-302 drafts
it. **T-302 is therefore a genuine gate, not a formality.** If it cannot be drawn cleanly, clause 3
is withdrawn and the feature ships W1+W2 — which is most of the measured value anyway.

### F-2 — Spec 002 contradicted spec 003 until amended ✓ **RESOLVED**

002 recorded OOS-001..005 excluding constitutional amendment; 003 includes it. Left unreconciled,
`specs/` would hold two live specs with opposite scope — the duplicated-source-of-truth defect
spec 001's preamble warns against, and the same class as `APP-021`.

Resolved by marking 002 `Superseded by specs/003-governance-v2/` with the reason, per Constitution
VI. 002 is not rewritten; its harness and drift findings carry forward and stay accurate.

### F-3 — Privacy is added to the reserved set, against the feature's direction ✓ **DELIBERATE**

The feature narrows the reserved set, but FR-009 **adds** privacy/retention/data-boundary
decisions, which were previously delegable. This is intentional and worth flagging so it is not
read as an error: Constitution VII governs data minimisation, and a retention decision fails the
reversibility test as hard as a deployment — once data moves, it does not un-move.

A redesign that only ever loosens is a redesign optimising for the author's convenience. This one
tightens where the evidence says it should.

### F-4 — Enforcement code may not shrink as much as FR-017 implies ⚠ **MEDIUM**

FR-017 expects `khepri_gov` to shrink materially since packages apply to fewer artifacts. But most
of the 2,488 lines are lifecycle/transition/renewal validation that applies to **all** artifacts,
package or not — only the package-approval path narrows.

FR-017 is a "should", so this is not a failure. Stated so nobody later reads flat line count as a
broken promise.

### F-5 — The 72:58 commit ratio is suggestive, not damning ⚠ **LOW**

Cited as evidence governance costs more than the product it governs. Fair, but a young repo
front-loads governance legitimately, and the ratio would improve on its own as product work
accelerates.

The load-bearing evidence is not the ratio — it is that **4 of 20 packages exist purely to repair
governance's own drift**, and that class is mechanically preventable. SC-007 keeps the ratio as an
outcome measure, which is the right use of a soft signal.

### F-6 — W1's value does not depend on the amendment ✓ **BY DESIGN**

Worth stating plainly: FR-001..008 need no ratification and address the friction actually measured
this session. If the owner rejects the amendment entirely, the feature still delivers digest
enforcement and harness autonomy.

The sequencing in `plan.md` is a hedge against exactly that.

## Coverage summary

| Dimension | Status |
|---|---|
| Every FR traced to a task | ✓ (via matrix above) |
| Every scenario traced to an FR | ✓ S1→FR-005..008 · S2→FR-009 · S3→FR-001,002 · S4→FR-003 · S5→FR-013,014 |
| Every SC measurable | ✓ SC-001..007 all counted or observed |
| No duplicated source of truth | ✓ after F-2 |
| Owner-blocking items isolated | ✓ T-307 only |

## Open risk carried into execution

**T-302 is the gate.** Everything in W3 downstream of it assumes the Article V distinction can be
written cleanly. If it cannot, W3 stops there — and that is an acceptable outcome, not a failure of
the feature.
