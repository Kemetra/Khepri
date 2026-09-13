# Product adversarial review — 2026-09-12

**Status.** This document grants no implementation authority. It does not replace
`governance/registry.yaml`, an active specification, or an active decision. It is a durable
record of a review run plus a verification pass against the working tree. It applies no fixes.

| Field | Value |
|---|---|
| Date | 2026-09-12 |
| Layer | product (whole Kemetra/Khepri repo, not one slice) |
| Skill | `.grok/skills/khepri-adversarial-review/` |
| Method | two isolated general-purpose judges, same three claims; then a separate verification pass against the working tree |
| Tree | `origin/main` at `b28b97e`; working tree HEAD was `9a35ea8` / `plan/d1-06-report-workspace`; no product-code delta in that tree |
| Combined verdict | **REVISE** (both judges REVISE; santa-method requires both PASS) |

## Method

Two isolated general-purpose judges scored the same three product claims. A separate verification
pass then checked each finding against the working tree. The findings table below is the source of
truth after that check — not two judge copies plus a third ledger. Weakened items are not promoted
back to CRITICAL.

## Governing artifacts (active in `governance/registry.yaml`)

Judges confirmed these as active:

- **Families:** FND, RRA, RCA
- **Specs:** FND-001, RRA-001 through RRA-014, RCA-001 through RCA-008
- **Decisions:** KHEPRI-DEC-001, 012, 014, 015, 017, 023, 025, 026, 028–034
- **Also read:** `governance/CONSTITUTION.md` v2.1.0, `PRODUCT.md` (not a registry row)

Retired artifacts grant nothing.

## Claims

| # | Claim | Score |
|---|---|---|
| 1 | Every customer-visible number is selected from a governed, version-pinned semantic view (or an explicit named refusal); templates, controllers, dashboards, APIs, and AI do not recalculate. | FAIL |
| 2 | Ambiguous identity, organization, scope, privacy, retention, or runtime is refused, not inferred; an operator cannot read another organization's facts. | FAIL |
| 3 | Product code exists only inside active-specification scope; `registry.yaml` is the sole authority; Seshat catalogs/specs/application code are not copied. | PASS |

## Findings (source of truth after verification)

| ID | Original | After check | Disposition | Finding | Evidence | Why the check landed there | What would close it |
|---|---|---|---|---|---|---|---|
| K1 | HIGH (both) | HIGH | keep | D1 HTTP isolation tests are stubbed. | `tests/test_d104_breakdowns_and_limits.py:597-607` `_StubDecisions` returns `"700.00"` for any request; `:652-656` `test_an_address_naming_another_organization_gets_the_uniform_refusal` only mismatches path org vs session, never a foreign `run_id`. `RCA-008.md:191` Verification requires "cross-organization isolation on every surface". | Not a demonstrated HTTP leak. Production `SemanticQueryActions` passes `owner_id` (`queries.py:130-149`). | Two real orgs, two real completed runs, `GET /app/{lang}/{own_org}/decisions/{other_org_run_id}` through real `SemanticQueryActions` + adapter; assert uniform unavailable body and no figure. |
| K2 | HIGH (judge B) | HIGH | keep | English machine status on Arabic decision pages. | `shell_templates/decision.html.j2:72` prints `{{ card.status }}`; `card.py:80-87` `STATUS_VERIFIED="verified"` etc.; `tests/test_d103_metric_card.py:311-319` asserts equal status strings across en/ar. Landing has bilingual names (`landing_copy.py:68-81` en Proven/Caveated/Withheld; `:171-183` ar مثبت / متحفَّظ عليه / ممتنع). | FR-162 names those four English tokens as the states; rendering them as visible page text is the miss. `data-status` as a machine attribute is fine; the visible span is not. | Governed bilingual status prose, asserted as different words with the same meaning. |
| K3 | HIGH (A) / MED (B) | HIGH | keep | `get_analysis_run(..., owner_id=None)` fails open. | `workspace/store.py:85-100` `_visible_in`: "A None owner_id means the caller is not narrowing by scope"; `:577-582` `get_analysis_run` defaults `owner_id` to None. Contrast `rra/persistence.py:654-660` `owner_id` required. RCA-001 FR-023: possession of an identifier confers no authority. | API hygiene, not a proven exploit. Production `src/` figure path always passes `owner_id`. Unscoped calls exist in W1 tests (`test_w102_*`, `test_w104_*`). | Require `owner_id: str` with no default; update W1 tests that read unscoped. |
| K4 | CRITICAL (judge B) | HIGH | keep | Decision card value is `CitedFigure.value` (Decimal); template stringifies it; tests inject preformatted strings. | `projection.py:248-250` `_value` returns `figure.value`; FR-139 requires typed Decimal with no re-rounding (`RRA-014.md:69-71`; `projection.py:13-18`). `decision.html.j2:71` `{{ card.value }}`. `card.py:227-230` `MetricCard.value=cell["value"]`. D1 tests inject `"700.00"` (`test_d104_breakdowns_and_limits.py:605-606`). Reports copy renderings (`bundle.py:822-827`, `html.py:3-9`). | Display/parity + test gap, not a second calculation. FR-057 (`RCA-002.md:81-83`) governs "report content in the shell", not D1 cards. RCA-008 Exclusions bar D1 from changing RRA-014, so "project renderings" is a spec successor, not a D1 patch. | Owner chooses RRA-014 successor that projects renderings, or D1 keeps Decimal and stops showing English digits as if they were governed bilingual text; drive tests with a real `CitedFigure`. |
| K5 | HIGH (judge B) | MED | keep | View filters match `CitedFigure.label` and ignore the dimension name. | `projection.py:306-319` `_matches` is `all(figure.label == member for _dimension, member in filters)`. | Recorded limit of admitted shape; collision possible. Two different dimensions on one figure match nothing (fail closed). A product named the same as a category would collide. | RRA-014 successor matches a governed dimension identity, or refuses filters the admitted shape cannot apply. D1 cannot invent a dimension the bundle does not state. |
| W1 | CRITICAL (A) / MED (B) | MED | weaken | Two live figure paths: delivered RRA-006 artifact vs RCA-007 re-running `ReportBundle.of` / `family.derive` at read time. | `semantic_view_adapter.py:16-23` and `:185-188` return `ReportBundle.of(package)`. `RCA-007.md:58,84-107` names the derivation, states no test compares a projected figure to a delivered surface, and says merging the document is the ruling (lines 93-123). `PRODUCT.md:39-40` "they may not recalculate them" is product prose; RCA-007 is the active spec. | True, already ruled by merging RCA-007. Residual is surface-equality evidence, not a silent D1 fix. | Persist a projection or add surface-equality evidence. Owner reading / successor. |
| W2 | HIGH (both) | MED | weaken | `population` column is always None. | `registry.py:109` `ExecutiveOverviewView` `output_field_order` includes `population`; `projection.py:268-276` `_unstated` returns None; `tests/test_sv105_propagation.py:258-272` asserts None. FR-162 requires the card expose `population`; exposing None meets the letter. `decision.html.j2:73` prints it. `RenderableBundle` has no population qualifier. | FR-140 reading, frozen in test. Owner item. | Owner chooses widen the bundle, drop the column, or refuse the view. D1 must not invent a qualifier. |
| W3 | HIGH (judge A) | claim-scope | weaken | Product-wide "every number comes from a semantic view" claim. | `RCA-008.md:29-45` Scope is D1 paths; FR-159 (lines 95-98) binds those surfaces. RRA-006 grants report figures from the fact-package bundle (`html.py:3-8`). RCA-004 FR-084 grants labelled synthetic landing numbers. Landing specimen figures in `landing_api.py` are granted as specimens. | Ungranted as a product-wide rule. Not a `/beta` report defect. | Retract the product-wide claim in `PRODUCT.md`, or an owner artifact that routes every customer number through a pinned view. |
| R1 | MED | MED | residual | Two `_member_or_none` copies. | `shell_decisions.py:38-46` and `:797-821`; `shell_comparison.py:156-169`. RCA-008 forbids editing `shell_comparison.py`. Gates match today. | Intentional duplication under current scope. | Only if an RCA-002 successor owns a shared gate. |
| R2 | MED | MED | residual | Landing Proven/Withheld vs D1 verified/caveated/refused/unavailable. | `landing_copy.py:68-85` says illustrative, not customer data, and also "product's governed vocabulary". `PRODUCT.md:90-92` still lists trust-state vocabulary as undecided. FR-162 already named D1's four states. | Product-doc drift. Registry over prose. | Update `PRODUCT.md`. |
| R3 | LOW | LOW | residual | Constitution jumps Article V to Article VII. | `CONSTITUTION.md:32-42`. DEC-017 retired delegation articles. | Cosmetic. | None required for product correctness. |
| R4 | LOW | LOW | residual | `PRODUCT.md` still calls owner-only deletion undecided. | RCA-005 FR-123 already requires owner-only deletion. | Stale prose. | Update `PRODUCT.md`. |

## What both judges PASSed

Seshat catalogs/specs/application code are not copied. Sampled `src/khepri/{rra,rca,runtime}/` maps to active specs. The uncommitted D1-06 plan is not product code.

## Ungranted

"Every customer-visible number is selected from a governed semantic view" as a product-wide rule.
Claim 1 fails on that scope; D1 surfaces are bound by RCA-008 / FR-159, not by a repo-wide grant.

## Two-definitions that survive the check

1. Delivered RRA-006 figures vs RCA-007 re-derived view figures (owner-ruled residual).
2. `CitedFigure.renderings` vs `str(CitedFigure.value)` on D1 (open display gap).
3. FactPackage population vs view column None (owner-item).

## Owner items — decided vs still open

| Item | State |
|---|---|
| RCA-007 re-derivation | Merging that spec was the ruling. Residual is surface-equality evidence. |
| population-as-None | Implementer chose absence; SV1-05 froze it. Still the owner's to confirm or reverse. |
| Whether decision status is a machine token or customer copy | Still open. |
| Whether `get_analysis_run` may omit scope | Still open. |

## Not inspected

Union of both judges; do not expand:

RRA-003 mapping internals; RRA-007 benchmark/worker; live Clerk/FRA1; Alembic heads; CodeScene scores; Excel/PDF writers beyond `html.py`'s stated contract; RRA-004/008 formula oracles in full; deletion/retention sweep clocks; CSP on every error surface; live compose image wiring; byte-diff against Seshat at `f206b7f2`; D1-06 plan contents; invitation/recovery HTTP matrices beyond RCA-001 unit files; infra/CDK; `docs/ui/design_handoff_khepri/` (anti-reference).

## Next actions for the owner

No implementation in this file.

1. D1 isolation test with two real orgs and a foreign `run_id` (K1).
2. Bilingual status (and maybe value) on the decision card (K2, K4).
3. Require `owner_id: str` on `get_analysis_run` (K3).
4. RCA-007 residual: persist projection or surface-equality evidence (W1) — owner reading.
5. population / filter-by-label — RRA-014 successor if the bundle must state them (W2, K5).

---

This report applies no fixes. A change becomes governing only when the owner merges it to main.
