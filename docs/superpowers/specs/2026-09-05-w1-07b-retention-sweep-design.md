# `W1-07b` — The retention sweep, with a caller in the built wheel

**Date:** 2026-09-05
**Requirements:** `KHEPRI-DEC-033` §5; `RCA-005` `FR-124`, `FR-125`
**Status:** design, pending the owner's review
**Measured against:** `main` at `4d79692` (`W1-07a` merged)

## 1. The obligation, and what discharges it

`KHEPRI-DEC-033` §5 states, in the decision rather than only in its evidence, that **no retention
horizon is enforced**: every sweeper's only caller is `khepri.local.cli`, which the wheel excludes.
It names what discharges the obligation, and the two halves are separate acceptance criteria:

> `W1-07` … must ship a retention sweep with **a caller present in the shipped image**, and
> **evidence that each horizon in §2 is honoured**.

Re-measured on `4d79692` while writing this design, and still true:

- `pyproject.toml:78` — `exclude = ["src/khepri/local"]`
- `rca/invitation_retention.py:40` — `INVITATION_HORIZON_IS_UNENFORCED = True`
- Five retention sweepers under `khepri.rca` (`invitation_retention`, `lifecycle` ×2,
  `recovery_security`, `session_retention`), plus `LocalSweeper._expire_sessions` for `RRA`
  content. The sixth `sweep` method is `local/sweeper.py`'s, which is the *composition* of the
  others; it and `local/wiring.py` are both excluded from the wheel.

`W1-07a` shipped the customer-triggered half (`#382`). This slice is the time-triggered half, and
it is the last thing standing between §2's thirteen rows and the deployed image.

### 1.1 What §2 actually requires a sweeper for

The second half of §5 — *evidence that each horizon in §2 is honoured* — reads at first like
thirteen sweepers. It is not. Measured row by row:

| §2 rows | Horizon | State on `4d79692` |
|---|---|---|
| Dataset version, analysis run, mapping/manifest, fact package, report artifacts, narrative, provenance record, source profile | **No inactivity expiry** (`OD-3`) | **Correctly swept by nothing.** A sweeper here would be the silently-shortening history blueprint §7.3 forbids, and `OD-3` records that an inactivity sweep "would need a notification capability no active artifact grants" |
| Raw upload, normalized events | 7 days after sealing | `LocalSweeper._expire_sessions` exists; unreachable from the wheel |
| Account, membership event, commercial session, invitation, recovery evidence | 12–24 months (`KHEPRI-DEC-015`) | Five sweepers exist; unreachable from the wheel |
| **Deletion evidence** | **12 months** | **No implementation anywhere** |
| **Retention/lifecycle audit event** | **12 months** | **No implementation anywhere** |
| Retail content under a disabled organization | 24 months | No implementation; **out of scope** (§6) |
| Backups | 14 days | The runtime's own lifecycle mechanism, not code in this repository |

So eight of thirteen rows need no sweeper *by decision*. What this slice owes is a caller for the
work that exists, and an implementation for the two horizons that have none.

## 2. The caller

### 2.1 Where the composition lives

`LocalSweeper` and `RetentionPasses` move from `khepri/local/sweeper.py` to
`khepri/runtime/retention_sweep.py`, and a console script is added:

```toml
khepri-retention-sweep = "khepri.runtime.retention_sweep:main"
```

This follows a precedent already recorded in `pyproject.toml:45`, for `khepri-clerk-hard-stop`, in
these words: *"`khepri.runtime` rather than `khepri.local` deliberately: the wheel excludes
`src/khepri/local`, so a command there would be absent from the image that actually needs to run
it."* The same sentence is the whole argument here.

**`khepri.local` imports the moved composition; it does not keep a copy.** `LocalSweeper` has
exactly one production consumer (`local/wiring.py:32`, `:134`, `:316`) and one test consumer
(`tests/test_local_sweeper.py:50`, whose `StubSweeper` subclasses it). Leaving a second
composition behind would be the "second deletion implementation to keep correct" that
`local/sweeper.py`'s own docstring warns against, and this repository has recorded the same trap
as *compose and config must share one source*.

**What moves, exactly.** The whole of `local/sweeper.py`'s public surface — `LocalSweeper`,
`RetentionPasses`, `RetentionCounts`, `SweepReport`, `REASON_EXPIRED` and the `build_local_sweeper`
factory (a pass-through, `sweeper.py:225`). `local/sweeper.py` becomes a re-export so
`local/wiring.py` and `tests/test_local_sweeper.py` keep their import paths, or those two callers
are repointed; the implementation plan picks one and applies it consistently. Nothing is
reimplemented either way.

**The class is renamed `RetentionSweeper`.** `LocalSweeper` names the thing it is ceasing to be:
once it lives in `khepri.runtime` and ships in the wheel, it is *the* sweeper, and a name saying
"local" would misdescribe the deployed artifact to the next reader — which is how a later slice
comes to write a second one for "real" deployments. `build_local_sweeper` becomes
`build_retention_sweeper` on the same reasoning.

`sweep()`'s `getattr(self, "_retention", None)` is inherited as-is. It exists because those test
stubs skip `__init__`; changing it is not this slice's work.

### 2.2 Why a console script is "a caller present in the shipped image"

Stated here because a reviewer will otherwise reconstruct it, and may reconstruct it wrongly.

§5's words are *a caller present in the shipped image* — not *a scheduler*. A console script in the
wheel is reachable from the deployed image by an operator or by whatever the runtime schedules;
that is what `khepri-clerk-hard-stop` established, for a procedure `KHEPRI-DEC-025` §4 calls a
"hard stop" precisely because someone must be able to invoke it.

Choosing a **cadence** is an operational decision this repository does not hold: `local/sweeper.py`
already records that *"a local loop that invented one would be modelling a deployment nobody has
authorized."* `DEC-033` decides no cadence anywhere in §2 or §4.

The distinction that matters: `#240`'s defect was a procedure with **no way to invoke it at all**.
A command in the wheel is invocable. An unscheduled command is a deployment question; an absent one
is a product defect.

### 2.3 Rejected alternatives

- **Including `khepri/local` in the wheel.** `pyproject.toml:70-76` records that it carries local
  database credentials which "have no business in a published artifact", and that shipping it would
  hand the image "exactly the two entry points that discipline withholds".
- **A worker-loop tick.** §5 says explicitly that the worker's per-claim sweep is *lease recovery,
  not retention*. Coupling the two would blur exactly the distinction the decision draws.

## 3. The acceptance test, and why the obvious one is worthless

§5's obligation is discharged by evidence **against the built wheel**, not the source tree. A
source-tree assertion would pass today and prove nothing, since every sweeper already exists in
source. That much the `W1-07` design already said. What it did not say is that the *obvious* wheel
test is also worthless.

**Measured, not assumed.** A wheel was built from a `pyproject.toml` carrying
`khepri-phantom = "khepri.local.cli:main"` while `exclude = ["src/khepri/local"]` stood unchanged:

```
[console_scripts]
khepri-clerk-hard-stop = khepri.runtime.clerk_hard_stop:main
khepri-gov = khepri_gov.cli:main
khepri-phantom = khepri.local.cli:main      <- declared

khepri/local packaged: False                 <- absent
```

`entry_points.txt` is generated from `[project.scripts]` metadata; `[tool.hatch.build.targets.wheel]
exclude` governs which *files* are packaged. **The two are independent.** A test that reads
`entry_points.txt` therefore passes over a command that crashes on invocation — which is the
unreachable-procedure shape §5 exists to close, reproduced inside the test meant to prove it closed.

**So the test resolves the entry point's target against the wheel's own contents** — it reads the
declared `module:function`, then confirms that module is present in the wheel and importable from
it, rather than trusting the declaration.

Two mutants must kill it, and both are required:

1. **Point the script at an excluded module** (or add the new module to `exclude`) → must fail.
   This proves the test sees the packaging, not just the manifest.
2. **Add `import khepri.local` to `khepri/runtime/retention_sweep.py`** → must fail. This proves the
   test sees a **transitive** leak — a module that ships but crashes at import because it reaches
   into the excluded package. Without this mutant, only the manifest has been tested.

The second mutant is the one that matters. It is the difference between "the command is declared"
and "the command runs".

## 4. The two purges that have no implementation

Both are twelve-month and content-free. They live in different packages because their tables do,
and `R7-01` §3 forbids either package importing the other, so they meet in `khepri.runtime` —
the seam `W1-04b` established and `W1-07a` used.

| Purge | Package | Table | Anchor |
|---|---|---|---|
| Workspace audit events | `khepri.rca.workspace` | `rca_workspace_audit_events` | `KHEPRI-DEC-015` §2a |
| Deletion evidence | `khepri.rra` | `rra_deletion_evidence` | `KHEPRI-DEC-033` §2, `OD-2` |

Each reuses `MEMBERSHIP_EVENT_RETENTION_MONTHS` and `_months_before` rather than re-deriving
twelve, exactly as `invitation_retention.py:80` already does — §2's own words are that this horizon
is *"adopted rather than re-derived"*, and two literals for one decided number is how they come to
disagree.

Neither store has a purge verb today: `SqlWorkspaceAuditStore` has `record` and `events_for_scope`;
the `RRA` side has `list_evidence`. Each gains one, following
`purge_sessions_dead_before`'s shape — a horizon instant in, a count out.

### 4.1 The sweep writes what it purges

Two requirements make this unavoidable, and they must be read together:

- **`FR-125`**: *"Every workspace action — create version, run, delete, **sweep**, profile reuse —
  MUST emit one content-free audit event."* `sweep` is named literally.
- **`FR-124`**: *"The first deletion of an object **and every retention-triggered purge** MUST
  record content-free deletion evidence."*
- `DEC-033` §2's audit row states its ending is *"Run by the retention sweep, **recorded as a**
  [content-free record]"*.

So the sweep is a producer of the very classes it purges. Two consequences the implementation must
face rather than discover:

**A migration is required and is not optional.** `AUDIT_ACTIONS` is `CHECK`-constrained and admits
no sweep action. `W1-07a` left the note in `audit.py:46`: *"`W1-07b` adds the sweep when it writes
it — `FR-125` names it — and the migration literal moves in the same commit."* The migration head is
pinned in **three** places, all of which move together:

1. `RCA_REVISIONS` in `tests/test_rca001_migration.py` — whose middle field is the migration
   **file slug**, not a table name
2. the `alembic heads` assertion in `tests/test_rca001_session_persistence.py:434`
3. `Migration head` in `specs/001-rca-001-commercial-identity/STATUS.md:10`

Current head is `20260906_0027`; this slice adds `20260906_0028`. `RCA_TABLES` in the same test
module gains no entry — this migration widens a `CHECK` and creates no table — and the extent
assertion added in `#382` (`test_every_rca_table_in_the_models_is_named_here`) will hold unchanged,
which is the check that this claim is true rather than assumed.

**A sweep event has no object, and the type already allows that.** Corrected while writing the
implementation plan; an earlier draft of this section said `AUDIT_OBJECTS` needed a new kind for
the sweep. It does not. `AuditEntry.subject` is already `AuditSubject | None`, every constructor
takes `subject: AuditSubject | None`, and `WorkspaceAuditEvent` documents the pairing: *"`object_kind`
and `object_id` are `None` together, for a refusal that produced no object"*, pinned by a `CHECK` in
`schema.py`. A sweep acts on a *class* over a horizon, so it passes `None` and writes
`WorkspaceAuditEvent.completed(actor, ACTION_RETENTION_SWEPT, None, now=now)`.

This is better than adding a kind. A sweep subject named `version` would make an evidence consumer
read a class-level purge as an act on one customer's dataset version — a real signal at the wrong
granularity — and a new kind like `class` would admit a subject shape nothing else uses. The
migration therefore widens **only** `AUDIT_ACTIONS`; `AUDIT_OBJECTS` and `AUDIT_OUTCOMES` are
untouched.

**The actor is `system:retention` **, following `ACTOR_PIPELINE = "system:pipeline"` — whose comment
already prescribes it: *"`W1-07`'s retention sweep will name its own actor in the same shape."* The
`system:` prefix keeps it from colliding with, or reading as, an account identifier.

**The pass must not purge its own evidence.** The sweep's audit event and evidence are themselves
subject to the twelve-month horizon the sweep enforces. Since both are written at `now` and the
horizon is twelve months before `now`, no correctly-ordered pass can reach them — but that is a
property to **assert**, not to assume, because it silently becomes false if a later slice moves the
horizon or reorders the pass. One test drives a sweep and asserts its own event survives it.

### 4.2 Ordering

The two new passes are independent of each other and of the existing five, for the reason
`RetentionPasses.run` already records: each evaluates its own predicate against `now`, so running
them in any order over one instant gives one result. They join `RetentionPasses` as two more
optional fields rather than a new mechanism.

## 5. Deleting the unenforced flag needs a replacement guard

§5 says `INVITATION_HORIZON_IS_UNENFORCED`'s deletion "is part of the evidence". Deleting it
naively **removes coverage**:

- `invitation_retention.py:40` defines it and `:103` exports it in `__all__`
- `tests/test_rca001_invitation_retention.py:179` asserts `is True`

Deleting constant, export and assertion together leaves nothing that can fail if the flag returns.
So the evidence gets a shape:

1. **A scan** asserting no `*_IS_UNENFORCED` constant exists anywhere under `src/khepri/`. Written
   as a scan rather than a check on one name, because the defect it guards is *a horizon documented
   as unenforced*, not *this particular constant*. It carries an emptiness assertion for the reason
   `#382` recorded: a scan whose input can be empty passes vacuously.
2. **A reachability test** asserting the wheel-reachable composition actually reaches the invitation
   pass — deleting a flag that says "unenforced" while the pass stays unreached would be worse than
   the flag.

Two comments become false on this merge and are corrected in the same commit:

- `invitation_retention.py:30` — *"`RetentionPasses` is invoked only by the manual `sweep`
  subcommand (`khepri.local.cli`)"*
- `session_retention.py:14` — the same claim

## 6. Non-goals, each with its reason

- **Retail content under a disabled organization (24 months).** `DEC-033` §2's last content row and
  `OD-4`. It needs a per-class walk across **both** packages under a frozen-then-purge rule, which
  is close to the second deletion implementation `local/sweeper.py` warns against, and it is the
  one row whose trigger is a *state change* rather than an elapsed timer. No organization has been
  disabled for twenty-four months, so the row cannot yet be violated. Its own slice.

- **The revocation ledger's horizon.** `FR-126` says the ledger is *"bounded by `KHEPRI-DEC-033`'s
  fourteen-day backup horizon plus a margin"*, and `revocation.py` repeats it — but **§2 has no
  revocation-ledger row**, and nothing enforces that bound. It is named here as a non-goal rather
  than left unmentioned, because an unenforced horizon inside the slice that exists to end them is
  exactly the shape §5 describes.

  It is not swept here for two reasons. It cannot take the twelve-month horizon: that is
  `KHEPRI-DEC-015` §2a's audit horizon and this is a different class. And purging at fourteen days
  plus a margin risks **reopening `FR-126`** — if any backup outlives the ledger entry that guards
  it, a restore makes a deleted version readable again, which is the guarantee `W1-07a` shipped.
  Choosing that margin needs the backup topology decision `KHEPRI-DEC-008` leaves open while
  provisioning is frozen — the same decision `#383` already carries. **Recorded, not implemented.**

- **A scheduler or cadence.** §2.2. Operational, and `DEC-033` decides none.

- **Including `khepri/local` in the wheel.** §2.3.

- **Amending `DEC-033` §5 to mark the obligation discharged.** §5 is the clause that *gates* this
  change; editing it to say the change satisfies it is self-authorizing. This repository records
  the rule as *never delete the clause that gates your change*. Evidence goes in the PR body and in
  this spec; marking §5 discharged is the owner's edit.

- **The `_EXPIRY_CLAIMS` copy guard stays.** §5's prohibition on telling customers that content
  expires automatically lapses when this merges, but no `SHELL_COPY` string makes the claim and
  adding such copy is a later slice's work. Deleting a passing guard as cleanup would lose the only
  thing watching that copy. It is proven able to fail by an inverse mutant in both languages.

- **`G2-01` F-2 — plaintext documents.** `rra_dataset_profiles.document` and
  `rra_fact_packages.document` hold customer labels and values as unencrypted JSON. §5 says whether
  to envelope-encrypt them is an `RRA-002` reading and "is not decided here". An at-rest concern,
  not a retention gap. Left to the owner.

## 7. Testing

**The caller**
- The entry point's target module resolves **inside the built wheel** (§3), with both mutants
- The moved composition has exactly one definition — `khepri.local` imports it
- `tests/test_local_sweeper.py` passes unchanged in behaviour after the move and rename: it is the
  existing evidence that the composition works, and this slice must not weaken it while relocating
  it. Its `StubSweeper(LocalSweeper)` follows the class to its new name.

**The two purges**
- One test per horizon: a row past twelve months is purged, one inside it is not
- The sweep emits its own audit event (`FR-125`) and evidence (`FR-124`)
- **The pass does not purge its own evidence** (§4.1)
- The sweep's audit action is admitted by the migrated `CHECK`, and a `.v99` sentinel action is
  refused — a gate test naming the next real value is a no-op the day that value ships

**The flag**
- No `*_IS_UNENFORCED` constant survives under `src/khepri/`, with an emptiness assertion
- The wheel-reachable composition reaches the invitation pass

**Throughout**
- Each guard mutation-tested; a scan mutated **outside** its own scope, since a scan that names its
  scope reproduces the drift it was written to catch
- The full suite before believing any targeted one: this slice moves a module five test files
  import

## 8. Risks

1. **The wheel test proving the manifest rather than the artifact.** The measured failure in §3.
   Mitigated by resolving the target against the wheel's contents and by the transitive-import
   mutant.
2. **Two definitions of the composition.** Mitigated by moving rather than copying, with
   `khepri.local` importing the result (§2.1).
3. **Deleting the flag while the horizon stays unreached.** Mitigated by §5's two replacement
   guards; the flag's deletion is evidence only if something else can fail.
4. **The migration's head pin missed in one of three places.** CI caught exactly this on `#377`.
   Enumerated in §4.1.
5. **A sweep event borrowing an object kind that means something else.** Mitigated by an admitted
   kind of its own (§4.1).
6. **Reading §5 as discharged because this slice merged.** The horizons are enforced when the
   command exists *and* something invokes it. This spec states what ships; it does not state that
   a deployment runs it, and §6 keeps the amendment with the owner.
