# This directory is a historical artifact. Do not follow its instructions.

**Task:** `R0-02` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`.

**Written at:** `main` @ `ebfbe77`, 2026-08-13.

---

## If you are an agent, read this first

`analyze.md`, `checklist.md`, `clarify.md`, `plan.md`, `spec.md`, and `tasks.md` in this directory
were written on **2026-08-08**, when `RCA-001` was a draft and no RCA product code existed. **They
are wrong about the current state of this repository in ways that will cause damage if followed.**

Concretely, an agent following them would:

- believe implementation is forbidden and stop, when `RCA-001` is `active` and three slices are
  merged;
- rebuild code that already exists on `main`;
- rebuild it **incorrectly** — `plan.md:37` specifies "frozen slotted dataclasses", but `#153`
  shipped a sealed two-door construction boundary (`records.py`), so following the plan produces
  unsealed records that violate the merged boundary;
- create tables that were never built and miss one that was (see §3);
- reason from a Constitution that no longer exists (see §2).

**Where to look instead:**

| For | Read |
|---|---|
| What RCA-001 requires | `governance/specifications/RCA-001.md` — the only authoritative source |
| Artifact state, identity, dependencies, supersession | `governance/registry.yaml` — the only authoritative source |
| What is already implemented | `STATUS.md`, next to this file |
| What to build next | `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md` |
| Operating rules | `AGENTS.md`, `governance/CONSTITUTION.md` |

## 1. Why these files are not being corrected in place

Two reasons, and the second is the decisive one.

**They are dated documents.** This repository already treats a dated advisory as a record of what
was believed when it was written — `docs/khepri-commercial-roadmap.md` carries exactly such a
banner, and the master roadmap states the reason: "a dated advisory that is edited to describe a
later state destroys the record of what was believed when it was written."

**More importantly, they cannot be patched into truth.** `analyze.md` §1 and §5 and `clarify.md`'s
precondition section do not merely contain stale *data* — they reason from a governance framework
that was **deleted**, not updated. Rewriting them line by line would produce prose citing articles
and directories that do not exist. Regenerating the directory would be a second requirements
document competing with the governed specification, which is the drift Constitution I forbids and
which `R0`'s acceptance criteria rule out: `governance/specifications/RCA-001.md` remains the only
authoritative RCA-001 requirement source.

So this file records the delta, and the originals stay as written.

## 2. The framework these documents reason against no longer exists

Commit `2fc6c70` ("refactor(governance): simplify single-owner governance") replaced the governance
model. Verified against the working tree at `ebfbe77`:

**The Constitution went from v1.1.0 to v2.0.0, and has five articles, not eight.**

| Cited in these docs as | Current v2.0.0 |
|---|---|
| I — one authoritative representation | I — **Sole authority** |
| II — named human authority | II — **Merge is approval** |
| III — reference is not authority | III — **One registry** |
| IV — no scope smuggled | IV — **Specification before product code** |
| V — fail closed | V — Fail closed (theme survives; quoted wording does not) |
| VII — least data, retention decision | **does not exist** |
| VIII — delegation | **does not exist** |

Citation sites: `analyze.md:19-25`, `:152`, `:156`; `plan.md:27`, `:103`, `:108`;
`clarify.md:69-70`, `:163`, `:174-175`, `:219`, `:223`; `spec.md:19`.

**Three directories were deleted outright** — confirmed absent from disk:
`governance/registries/` (`decisions.yaml`, `families.yaml`, `specifications.yaml`),
`governance/approvals/` (including `APP-017.yaml`), and `governance/delegations/`
(`DEL-001` … `DEL-005`).

Approval packages and delegations were removed as **machinery**. The authority analysis at
`analyze.md:158-163` and `plan.md:27-31` — which concludes that no delegated authority exists
because every `DEL-*` expired — is therefore void as a framework, not merely out of date.
Constitution II is now "Merge is approval".

Dead-path citation sites: `spec.md:17`; `analyze.md:129`, `:131`, `:143`, `:147`, `:149`, `:163`;
`plan.md:29`; `clarify.md:226`.

## 3. The gate in `analyze.md` §5 is fully cleared

`analyze.md:143-166` names three independent blockers and concludes "**No product code may be
written.**" All three are met:

| Precondition, as recorded | Then | Now |
|---|---|---|
| The relevant `RCA` specification is approved (`analyze.md:148`) | "NOT MET — `RCA-001` is `draft`" | **Met** — `registry.yaml` records `RCA-001` `state: active` |
| A separately approved decision settled runtime and provider (`analyze.md:149`) | "NOT MET — `KHEPRI-DEC-008` is `proposed`" | **Met** — `registry.yaml` records `KHEPRI-DEC-008` `state: active` |
| A Constitution VII retention decision (`analyze.md:152`, `:156`) | "NOT MET — does not exist" | **Met** — `KHEPRI-DEC-015` is `active`; and the article that demanded it no longer exists |

Other `KHEPRI-DEC-008`-is-`proposed` claims: `clarify.md:224-227`, `plan.md:108`.

`analyze.md:143` reads from `HEAD = 3da504c`. Current baseline is `ebfbe77`.

## 4. Status claims that are false

| File | Line | Claim |
|---|---|---|
| `spec.md` | 7 | "Status: Draft — not approved, not implementation-authorized" |
| `spec.md` | 17-18 | Enumerates every existing specification and omits `RCA-001`, which now exists and is `active` |
| `spec.md` | 44-46 | "v1.1.0, amended by `KHEPRI-DEC-011`" — now v2.0.0; DEC-011 is `retired`, superseded by `KHEPRI-DEC-017` |
| `analyze.md` | 14 | "No code written; tasks are unexecuted / This run wrote only `.md`" — three slices of product code are merged |
| `analyze.md` | 20 | Cites the registry state as `draft` |
| `analyze.md` | 24 | "retention decision … **not authored**" — authored as `KHEPRI-DEC-015`, now `active` |
| `analyze.md` | 37 | "four implementation conditions … **2 and 3 unmet** — GATE" |
| `analyze.md` | 128-137 | Reports stale prose in `RCA.md:36` reading "The family is proposed" — since fixed; the word appears nowhere in `RCA.md` |
| `plan.md` | 3-4, 19-20 | "not an authorization to implement"; "Spec approved: no"; "Three independent blockers" |
| `plan.md` | 19 | Cites `approved_by`/`approved_at`/`approval_ref` — fields that do not exist in the current registry schema |
| `tasks.md` | 3-5, 7-8 | "**None of these may be executed**: implementation is blocked by three governance preconditions" |
| `checklist.md` | 84-86 | "not approved and not implementation-authorized" |
| `clarify.md` | 219-223, 235 | Records the retention decision and DEC-008 as open preconditions |

`AGENTS.md` line anchors have also drifted (the file is now 24 lines), and its product-code rule now
reads "**active** specification" rather than "approved". The "≤3 constructor arguments" constraint
cited at `analyze.md:17` **no longer appears in `AGENTS.md` at all**.

## 5. Where `tasks.md` disagrees with what shipped

Roughly half of `tasks.md` is merged. Full per-requirement status is in `STATUS.md`; this table
records only where the task list would actively mislead.

| Task | Reality |
|---|---|
| T-001 … T-004 | **Done** — `accounts.py`, `credentials.py`, `organizations.py`, `lifecycle.py` |
| T-006 audit records | **Not done, and the path is wrong** — `src/khepri/rca/audit.py` does not exist; deferred to `#150` |
| T-007 … T-009 invitations | **Not started** — `invitations.py` does not exist |
| T-010 persistence | **Done, both paths wrong** — `tasks.md:120` says "five `rca_*` tables"; migration `0010` created **four**, and `rca_isolation_scopes` is named in neither document. `tasks.md:122` names `2026____0010_rca_commercial_identity.py`; the file is `20260812_0010_rca_identity_spine.py` |
| T-012 auth sessions | **Not started** — `auth_sessions.py` does not exist |
| T-013 recovery | **Not started** — `recovery.py` does not exist |
| T-014/015/017/018 authorization | **Not started** — `authorization.py` does not exist |
| T-019 RRA bridge | **Done differently** — shipped as `isolation.py`, not `bridge.py`, and returns `owner_id` only rather than a `SessionScope`, contradicting `tasks.md:219`/`:224` and `plan.md` §6 |
| T-021 endpoint access | **Not started** — `api.py` does not exist |

**Two merged slices have no task at all**, so following `tasks.md` would omit them and violate
boundaries they establish:

- `#153` — the sealed two-door construction boundary (`records.py`: `Sealed`, `through_door`,
  `assert_sealed`, `register_sealed`);
- `#157` — account lifecycle and retention (`lifecycle.py`: `AccountRetentionSweeper`,
  `PurgeReport`, the `KHEPRI-DEC-015` 24-month horizon, `disabled_at`, nullable email, migration
  `20260813_0011`), with tests `test_rca001_lifecycle.py`, `test_rca001_retention.py`,
  `test_rca001_boundary.py`.

## 6. Verified non-findings

Recorded so they are not re-investigated:

- `tasks.md:227` asserts `src/khepri/rra/sessions.py` is byte-identical to its state at `3da504c`.
  The commit anchor is stale, but `git diff 3da504c HEAD -- src/khepri/rra/sessions.py` is **empty**
  — the assertion still holds and remains satisfiable.
- `clarify.md:19`'s `RCA.md:5-7` anchor still lands correctly.
- `checklist.md` §3's D-1 … D-5 review record is historically accurate as a record of that review
  and needs no correction.
