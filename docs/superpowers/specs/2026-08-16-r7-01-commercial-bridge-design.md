# R7-01 — how a commercial authorization context opens or resumes an RRA analysis session

**Task:** `R7-01` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`.
**Status:** design note. No code. One question for the owner in §6.

---

## 1. The state this note describes, stated first

`R6` is merged through `R6-08` (`#192`…`#195`, `#197`…`#200`). An authenticated actor now resolves
to an `AuthorizationContext` carrying `account_id`, the active `organization_id`, and a live role,
and `IsolationService.resolve_scope` maps an organization to its stable opaque `owner_id`.

What does *not* exist is any path from that scope to an RRA analysis session. This note defines
that path, and its central finding is that **the path cannot be built without a decision only the
owner can take**, because the obvious implementations each violate a requirement.

Everything below was verified against the code rather than taken from the roadmap.

## 2. The seam, and why it is not a matter of wiring

`RRA-001`'s content tables — four of them — declare composite foreign keys onto
`rra_beta_sessions(owner_id, session_id)` (`persistence.py:109`, `:149`, `:202`, `:246`). A row in
that table is therefore the precondition for *any* retail content existing.

Exactly one code path writes such a row: `InvitationService.redeem` (`sessions.py:125`), reached
through `POST /api/v1/beta/sessions/redeem` (`api.py:160`). And it mints its own scope:

```python
session = BetaSession(
    owner_id=f"own_{secrets.token_urlsafe(18)}",     # sessions.py:126 — fresh, per redemption
    session_id=f"ses_{secrets.token_urlsafe(18)}",
    ...
)
```

That is the whole problem in two lines. `FR-035` requires **one organization to resolve to a stable
scope across sessions**, and `allocate_owner_id()` (`organizations.py:145`) already mints exactly
one stable `owner_id` per organization at creation. A commercial actor redeeming an invitation
would get a *second*, unrelated `owner_id` — the organization's scope and the session's scope would
disagree, and content written under the session would be invisible to the organization that owns
it.

**The three ways out, and why two are closed:**

| Approach | Verdict |
|---|---|
| RCA writes the `rra_beta_sessions` row itself, carrying the organization's `owner_id` | **Closed.** `FR-039` requires RRA to remain independently testable, and `test_rca_declares_no_rra_table_dependency` asserts every RCA table starts with `rca_`. `isolation.py:14-17` already records this: a session identifier minted in RCA "could not satisfy [the FKs] without writing into RRA's tables, which `FR-039` forbids." |
| A commercial actor redeems a beta invitation like anyone else | **Closed.** It mints a fresh `owner_id` per redemption, breaking `FR-035`'s stability clause, and it makes commercial access depend on an invitation secret that `FR-016`…`FR-020` place under `R4`. |
| **RRA grows an additive entry point accepting a caller-supplied `owner_id`** | **The only remaining shape.** §6 is the owner's decision on whether to take it. |

## 3. Where the bridge may live, settled here rather than assumed

`test_rca001_boundary.py::test_no_rra_module_imports_rca` forbids `khepri.rra` → `khepri.rca`.
**The reverse direction is unasserted** — verified by reading all four tests in that file; only
`test_rca_declares_no_rra_table_dependency` constrains RCA, and it constrains *tables*, not imports.
`STATUS.md`'s `FR-036` row records the same absence.

So three locations are available, and this note recommends the third:

| Location | Assessment |
|---|---|
| `khepri.rra` | **Refused.** Would import `khepri.rca` and fail `test_no_rra_module_imports_rca`. Also wrong on `FR-039`: RRA must not know accounts exist. |
| `khepri.rca` | Permitted today, but it makes every RCA test transitively depend on RRA and quietly spends the one-directional import budget. `FR-036` forbids authoritative retail calculation in RCA; an import is not a calculation, but this is the direction that drift takes. |
| **`khepri.local` (the existing composition root)** | **Recommended.** `wiring.py` already imports both packages (`:34`-`:46`) and is where the two halves are assembled today. A bridge here needs no new import direction at all, and keeps both packages ignorant of each other. |

**A test this note recommends `R7-02` add**: assert the RCA→RRA import direction explicitly, in
whichever direction the owner settles. It is currently unasserted in both directions, which is how a
boundary erodes without anyone deciding to erode it.

## 4. The contract, assuming §6 is answered "yes"

Stated so `R7-02` can implement without re-deriving it, and so the owner can see what they are
approving.

**Opening.** A commercial actor with a resolved `AuthorizationContext`:

1. `IsolationService.resolve_scope(account_id, organization_id)` → the organization's stable
   `owner_id`. This already exists and already refuses non-members and disabled accounts.
2. The bridge calls RRA's new entry point with that `owner_id`, receiving a `BetaSession` whose
   `owner_id` **is** the organization's. `session_id` stays RRA's to mint — it is per-analysis, not
   per-organization, and `FR-035` says nothing about it.
3. The actor proceeds through the existing journey unchanged.

**Resuming.** Identical, except the bridge looks up an existing session rather than creating one.
The authorization step is *not* skipped on resume: `FR-030` requires a membership change to take
effect for decisions made after it, so a resumed session re-resolves the context, exactly as
`R6-07`'s scenario-20 tests require. This is what `R7-03` tests.

**What the bridge must never do**, each traceable to a requirement:

- Pass an `organization_id`, name, slug, or email to RRA (`FR-032`, `FR-033`). Only the opaque
  `owner_id` crosses.
- Accept an `owner_id` from the caller instead of resolving it (`R6-01` §5's critical rule: object
  identifiers never grant authority).
- Mint an `owner_id` of its own. `allocate_owner_id` is the single definition, and a second minting
  site is how `FR-035`'s stability breaks.
- Compute any retail fact (`FR-036`).

## 5. What R7's remaining slices inherit

Recorded because three of them will fail tests `R6` merged **by design**, and a future agent seeing
a red suite should not "fix" them:

- **`test_the_resolver_has_no_production_consumer_yet`** (`R6-08`) fails the moment `R7-05` wires
  the resolver into an endpoint. Its docstring instructs its own replacement — replace it with a
  test asserting that consumer's path, do not relax it.
- **`test_every_protected_action_in_the_design_has_a_matrix_class`** (`R6-05`) fails if `R7` adds a
  row to `R6-01` §3.1. Add the row *and* the `ACTION_COVERAGE` entry in the same slice; that
  coupling is the point.
- **`VERB_CALLER_ALLOWLIST`** (`R6-08`) gains an entry if any endpoint reaches a membership verb.
  Adding one is the review conversation the allowlist exists to force, not an obstacle.
- **`R7-02` closes two carried gaps** recorded in `STATUS.md`: `resolve_scope`'s unauthenticated
  cell (it will finally sit behind an authenticated boundary) and `FR-023`'s object-level half.

**`FR-037` is a hard line.** RRA-001's controls must remain "covered by its existing tests,
**unmodified**". If implementing `R7` requires editing any `test_rra*` file, that is a specification
conflict to record, not a refactor to perform. The `R6` slices touched zero of them and `R7` should
be able to say the same.

## 6. Question for the owner

**May `RRA` grow an additive session-creation entry point that accepts a caller-supplied
`owner_id`?**

This is the only remaining shape (§2), and it is a change to a *governed* specification's surface,
which is why it is not mine to take.

What it costs, stated plainly rather than minimised: `RRA-001` currently guarantees that every
`owner_id` is minted by RRA itself, and an entry point taking one from a caller weakens that to
"minted by RRA, or supplied by a caller RRA trusts". `FR-037` says this specification must not
weaken RRA's controls, and a reasonable reading is that this weakens one.

The counter-reading, which is why the question is worth asking rather than self-answering: the
control `FR-037` enumerates is *opacity*, not *provenance* — "opaque identifiers, cross-session
isolation failing closed, …". An `owner_id` from `allocate_owner_id`
(`organizations.py:151`) and one from `redeem` (`sessions.py:126`) are **the same construction,
character for character**: both are `f"own_{secrets.token_urlsafe(18)}"`, 18 CSPRNG bytes rendered
as 24 URL-safe characters. And `FR-032`/`FR-033` — which govern what may appear *in* the key — are
satisfied by construction, because `allocate_owner_id` takes no argument at all and so cannot
encode a commercial identifier even by mistake.

**The vehicle, so the question is actionable rather than open-ended.** This changes a governed
specification's surface, and the precedent is `KHEPRI-DEC-018` (`dcb63da`, `#177`), which admitted
the external identity-provider boundary and added `R3-09`/`R3-10`/`R3-11` to the roadmap. It was
drafted as a document under `governance/decisions/` with a `registry.yaml` entry, and became
governing when the owner merged it — the same convention every slice here follows. So the answer to
this question is most naturally **`KHEPRI-DEC-019`**, the next free number, admitting an additive
scoped-session entry point and pinning which of the three shapes below it authorizes.

An agent may draft that record; only the owner's merge makes it governing. This note does not draft
it, because drafting a decision whose substance is still open would put the recommendation and the
authorization in one artifact — which `governance-integrity-principles` forbids.

Three ways to take it, if the answer is yes:

- **A separate entry point** (`open_scoped_session(owner_id, *, now)`) leaving `redeem` untouched,
  so the beta path keeps its current guarantee verbatim and `FR-039`'s independence is unaffected —
  RRA's existing tests never call the new function. **Recommended.**
- A parameter on `redeem`, which entangles the commercial path with invitation secrets.
- A `SessionStore` write from the bridge, which puts session-shape knowledge outside RRA.

If the answer is **no**, `R7` cannot proceed in its current form and the roadmap needs an
alternative — most plausibly that commercial actors get their own content tables and RRA is reached
only for calculation, which is a much larger change and contradicts `FR-036`'s "every retail fact
must originate from the existing RRA fact package".

## 7. What this note does not settle

- **The bridge service itself.** `R7-02`. This says what it must resolve, never how.
- **Live authorization on resume.** `R7-03` — the contract above requires re-resolution; the tests
  proving a disabled or revoked actor cannot continue are that slice's.
- **HTTP surface.** `R7-05`. No endpoint shape is proposed here, deliberately: `R6-01` §5's rule
  that object identifiers never grant authority constrains it more than any URL design would.
- **Beta-mode preservation.** `R7-04`, which must show the existing journey is unchanged for a
  participant who has no account.
- **Whether `R6-01` §3.1 gains a row** for "open an analysis session". It probably should, and that
  is `R7-05`'s call once the endpoint exists.

## 8. Two stale status rows, reported rather than edited

The roadmap's §15 table still reads:

| Row | Says | Actually |
|---|---|---|
| `R6 Canonical authorization` | `BLOCKED` — "depends on R3 session resolution alone" | `R6-01`…`R6-08` all merged (`#192`…`#195`, `#197`…`#200`) |
| `R7 Commercial RRA bridge` | `BLOCKED` — "Depends on R6" | Its only named blocker is cleared; it is now blocked on §6 instead |

Reported, not corrected: this is a design note, and reconciling roadmap status is a status pass.
It is the same class of staleness `R6-07` corrected for `FR-008`/`FR-030` and flagged for
`FR-027`/`FR-029` — a merged slice leaving a status row untouched, which is why
`khepri-plan-status-blocks-not-checkboxes` says to verify a status against the code rather than
read it.
