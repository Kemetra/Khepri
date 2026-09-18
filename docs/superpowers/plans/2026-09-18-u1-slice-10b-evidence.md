# `U1` slice 10b / `U1-07` — Visual regression, commercial shell surfaces: the evidence

**Authority:** active `RCA-010` `FR-204`–`FR-205`.
**Plan:** `docs/superpowers/plans/2026-09-18-u1-slice-10b-execution-plan.md`.
**Allocation:** `docs/superpowers/plans/2026-09-17-u1-shell-allocation-plan.md` §Slice 10b.
**Design:** `docs/product/KHEPRI_UI_UX_MASTER_SPEC.md` §17, §16.3, §16.4.
**Base:** `0322f7c` (`#487`).

**No production file changed.** One new test module, 13 cases, plus this record and the plan.

---

## The findings, stated before the passes

### Finding 1 — §16.4's refusal reference has no reachable subject

`§16.4` records **#9 refusal** as independently covered by the approved pack, so it reads like a
usable representative. It is not. Measured across all ten shell surfaces:

```
shell surfaces rendering .decision-refusal, .decision-unsupported or .compare-refusal: NONE
```

Naming #9 a representative would have built a run that can only produce the null case — `#486`'s
Finding 2, repeated one slice later. **It is excluded from `_REPRESENTATIVES` and pinned** by
`test_the_refusal_reference_is_recorded_as_unreachable_not_covered`, which fails the day a shell
surface renders a refusal — which is exactly when #9 becomes usable and belongs in the set.

**This is not a product defect.** The pack covers a state the shell does not currently reach.

### Finding 2 — nine of thirteen cases do not run in CI

Measured under CI's own invocation:

```
$ PLAYWRIGHT_BROWSERS_PATH=/nonexistent uv run pytest tests/test_r812_shell_visual_regression.py -q
4 passed, 9 skipped in 14.92s
```

The four that run are the `FR-205` scan, its pack-presence check, and the two representative-set
assertions. **Every measured dimension skips**, because a rendered box tree needs a browser and CI
installs none.

This is `#486` **Finding 1** again, unchanged and still not closable here: `.github/` is outside
`RCA-010` §Scope. Recorded rather than reported as a green run.

### Finding 3 — the shell declares no base `font-family`

> **CLOSED.** Fixed by the follow-on slice this finding called for — `body { font-family:
> var(--font-body) }` in `shell-components.css`. See
> `docs/superpowers/plans/2026-09-18-shell-base-typeface-evidence.md`. Applying the real
> typeface then exposed a latent `FR-200` defect: a member email overflowed `team` at 200%,
> which `#487`'s `break-word` could not break. The account below stays as written.

`FR-204` names **typography** as a comparison dimension. Measured on `overview`, body text resolves
to `"Times New Roman"` — the browser default. No sheet sets a family on `body` or `:root`;
`workspace.css` uses `var(--font-mono, monospace)` and `var(--font-sans, inherit)` in seven places,
but nothing establishes the base.

**Not fixed here.** This slice changes no production file, and the fix belongs to the slice owning
the sheet — the rule `#486` followed into `#487`. The typography dimension is therefore asserted
against **what the shell declares** (the `--text-*` scale and the 4px spacing rhythm) rather than
against a resolved family.

---

## Decision 1 — computed measurement, not stored images

Both architectures were built and measured before choosing.

**Screenshots are byte-stable here.** The same surface captured twice gave identical SHA-256
digests on `decision` and `overview`, so determinism did **not** decide it. Three other things did:

| | Pixel digest | Computed measurement |
|---|---|---|
| Stored artifact | a committed PNG — the "hosted baseline store" `FR-204` excludes | none |
| Names the drifted dimension | **no** — 1px padding and a font swap both changed the hash, and it distinguished neither | **yes** — `spacing_rhythm.padding 16px→17px`; `typography.family→Georgia` |
| Expresses "pixel-identical equality is not required" | no — any legitimate responsive adaptation breaks it | yes — each dimension is asserted on its own terms |
| Deterministic across two runs | yes | yes |

`FR-204` requires comparison on **eight named dimensions** and explicitly does not require
pixel-identical equality. A digest can satisfy neither clause. So visual evidence here is box
geometry, computed styles and element counts, asserted against token-derived expectations.

## Decision 2 — two obligations, two scopes

The allocation block says representatives come from "the full in-scope set, which includes
`legal_templates/`" **and** from "the covered set". No legal page appears in §16.2's twelve
references, so one list cannot satisfy both. The reading that makes both true:

- **Comparison against the approved pack** (`FR-204`'s eight dimensions) → the **covered
  references**, which is `_REPRESENTATIVES`.
- **Visual-regression evidence as such** — the `FR-205` scan and the extent assertions → the
  **full in-scope set**. The `FR-205` scan is scoped to every test module in the repository, which
  is wider than either.

## The representative set

| Reference | Surface | Basis |
|---|---|---|
| §16.4 #8 evidence drawer, #7 composition | `decision` | the only shell surface rendering a drawer |
| §16.4 #6 period comparison | `compare` | **composition only** — it renders chrome and three download actions, no figures, which is what the reference covers |
| §16.4 #4 workspace overview | `overview` | density floor |
| §16.4 #9 refusal | — | **unreachable, Finding 1** |
| §16.4 #10 Arabic RTL | every representative in `ar` | asserted as invariance |

Named as a **reviewed literal**, cross-checked against §16.4 — not derived from the surfaces the
tests happen to drive, which would be the tautology slice 4 ruled out.

---

## Mutation results

Every guard mutated; every restore verified with `git diff` showing zero deletions.

| # | Mutant | Guard | Result |
|---|---|---|---|
| 1 | a probe module reading a pack PNG via `read_bytes` | `FR-205` scan | **FAIL** as required |
| 2 | add `"nonexistent"` to `_REPRESENTATIVES` | representative extent | **FAIL** as required |
| 3 | `.document-card { padding: 17px }` | `spacing_rhythm` | **FAIL** — `['17px']` detected off-rhythm |
| 4 | a language-conditional `<a>` on `overview` | RTL invariance | **FAIL** on `overview` |

**The `FR-205` scan is also proven non-vacuous in two ways** the CWD trap demands: it is anchored
to `__file__`, and it was run with `tests/` as the working directory, giving the same result. It
carries an emptiness assertion on **both** sides — the modules it scans and the pack it guards —
because a scan over an empty list passes while proving nothing.

---

## Gate results

| Gate | Result |
|---|---|
| `tests/test_r812_shell_visual_regression.py` | **13 passed** |
| Same, without a browser (CI's shape) | 4 passed, 9 skipped — Finding 2 |
| `pytest` (whole suite) | see PR — run alone with an isolated `--basetemp` |
| `ruff check .` | passed |
| `khepri-gov validate` | passed |
| CodeScene vs `origin/main` | see PR |

---

## `FR-204` dimension coverage

| Dimension | Where | Runs in CI |
|---|---|---|
| hierarchy | RTL invariance (`h1`/`h2`/landmark counts) | no |
| density | RTL invariance (cards, actions) | no |
| spacing rhythm | 4px rhythm against the token scale | no |
| typography | the `--text-*` scale; **Finding 3** on the base family | no |
| visual states | slice 5's state grammar binds these | **yes** |
| RTL | invariance across `en`/`ar` | no |
| responsive | slice 8's viewport guards and 9b's matrix | no |
| asset fidelity | slice 2b's `FR-206` asset scan — extended, not duplicated | **yes** |

Two dimensions are covered by earlier slices' static guards and run in CI. Six are measured here
and skip in CI (Finding 2).

---

## What this slice did not do

- **It changed no production file** — including the sheet carrying Finding 3.
- **It introduced no visual-testing platform, service, or hosted baseline store** (`FR-204`), and
  committed no reference image.
- **It did not touch `#486`'s Findings 1 or 2**, both still open and both the owner's.
- **It did not address the six §16.2 references the pack does not cover** (#1, #2, #3, #5, #11,
  #12). Those are an asset-production dependency, not code: "silence is not permission to invent."
