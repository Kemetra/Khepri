# Identifier survey

**No identifier is allocated, claimed, or reserved by this planning pass.** This document
surveys what the registries currently contain and derives what the *next* value in each
sequence would be **if** an artifact were drafted. A derived value is a **provisional
candidate**: it is re-derived at drafting time against the registry as it stands then, and any
intervening artifact displaces it.

Surveyed at Khepri `c7d78b2` and Seshat-BI `157ef43`.

---

## A. Planning placeholders used across this package

Prose in this package refers to proposed artifacts by **non-numeric placeholder**, never by a
number. The placeholder is the stable name; the identifier is derived later.

| Placeholder | What it would be | Repository |
|---|---|---|
| `[DEC-BOUNDARY]` | The decision governing Khepri's relationship with Seshat-BI | Khepri |
| `[DEC-COMMERCIAL]` | The decision superseding `KHEPRI-DEC-003`'s beta boundary | Khepri |
| `[FAM-COMMERCIAL]` | The commercial product family | Khepri |
| `[SPEC-REPORT]` | The business-first report and separated audit evidence specification | Khepri |
| `[PKG-GOV]` | The approval package carrying the governance set | Khepri |
| `[PKG-RRA-RENEWAL]` | The renewal package required to change `RRA.md` | Khepri |
| `[SESHAT-ADR-BOUNDARY]` | The headless-engine and consumer-isolation decision | Seshat-BI |
| `[SESHAT-SPEC-CONTRACTS]` | Analysis/evidence schema definitions | Seshat-BI |
| `[SESHAT-SPEC-ENGINE]` | Repo-root-free analytical API | Seshat-BI |
| `[SESHAT-SPEC-CONSUMER]` | Consumer compatibility suite | Seshat-BI |

Identifiers that already exist — `KHEPRI-DEC-003`, `-005`, `-006`, `-008`, `-012`, `FND-001`
through `-003`, `RRA-001` through `-008`, `APP-002`, `APP-013`, Seshat `ADR-0008`, Seshat specs
`137` and `138` — are cited by their real values throughout, because they are allocated facts.

---

## B. Khepri — what the registries contain

### Decisions — `governance/registries/decisions.yaml`

`KHEPRI-DEC-001` … `KHEPRI-DEC-012`, no gaps.
States: `accepted` ×9 (001–007, 010, 011) · `proposed` ×2 (008, 012) · `rejected` ×1 (009).

*Provisional candidate for the next decision drafted: `KHEPRI-DEC-013`.* Two decisions are
contemplated in this package (`[DEC-BOUNDARY]`, `[DEC-COMMERCIAL]`), so a second would derive
`-014` **only if both are drafted and neither is displaced.** Neither is reserved.

### Families — `governance/registries/families.yaml`

`FND` (active, `APP-001`) · `RRA` (active, `APP-002`). Three-letter codes, not numbered.

`[FAM-COMMERCIAL]` would need a new code. `docs/khepri-commercial-roadmap.md` proposes **RCA**
(Retail Commercial Analysis) and argues for it against widening `RRA.md`. No registry constrains
the letters; the code is a naming choice at the drafting moment, not an allocation.

### Specifications — `governance/registries/specifications.yaml`

`FND-001` verified · `FND-002`, `FND-003` implemented · `RRA-001` … `RRA-008` approved.

*Provisional candidates: `FND-004`, `RRA-009`, and `<FAMILY>-001` under any new family.*
`[SPEC-REPORT]` is **recommended** under `RRA` — a session direction, not an approved route, and
placement under the commercial family remains live. On the recommended route its provisional
candidate is `RRA-009`.

### Approval packages — `governance/approvals/`

`APP-001` … `APP-008`, `APP-010` … `APP-014`. Format pinned:
`PACKAGE_ID_PATTERN = re.compile(r"^APP-[0-9]{3}$")` (`src/khepri_gov/approval_packages.py:72`).

*Provisional candidate for the next package: `APP-015`.* Whether `[PKG-GOV]` and
`[PKG-RRA-RENEWAL]` are one package or two is a mechanics question for whoever drafts them.
**No number is set aside for either.**

**The `APP-009` gap is intentional and traced.** Created at `c00c098` ("gov: propose
KHEPRI-DEC-009 standing authorization", #65), withdrawn at `f38ee8f` ("gov: propose
KHEPRI-DEC-010 spoken delegation and withdraw DEC-009", #66). `KHEPRI-DEC-009` is `rejected`;
its rejection was recorded under `APP-010`. No reference to `APP-009` survives anywhere in the
tree. The number is retired, not missing.

### Delegations and benchmarks

`DEL-001` … `DEL-003`, format `^DEL-[0-9]{3}$` (`src/khepri_gov/delegation.py:13`).
`KHEPRI-BMK-001-sizing.yaml`. Note that `KHEPRI-DEC-008` obliges **re-issuing** `BMK-001`, which
may be a renewal of the existing identifier rather than a new one.

---

## C. Khepri — artifacts contemplated, with their gates

Nothing below is drafted, allocated, or authorized. The table records *what would be needed*, so
the shape is visible before deciding whether any of it should exist.

| Placeholder | Would be | State on landing | Gate |
|---|---|---|---|
| *(amendment to `KHEPRI-DEC-012` — no new identifier; the artifact already exists)* | edit to a `proposed` decision | stays `proposed` | Owner review |
| `[DEC-BOUNDARY]` | Seshat-BI analytical dependency and ownership boundary | `proposed` | Owner review |
| `[FAM-COMMERCIAL]` | Commercial product family | `proposed` | Owner approval |
| `[DEC-COMMERCIAL]` | Supersedes `KHEPRI-DEC-003`'s beta boundary | `proposed` | Owner approval |
| `[SPEC-REPORT]` | Business-first report and separated audit evidence | `draft` | Golden-sample approval |
| `[PKG-GOV]` | Approval package for the governance set | — | Owner approval |
| `[PKG-RRA-RENEWAL]` | **Renewal** package for `RRA.md` | — | Owner approval |

**No consumer specification is contemplated.** The owner deferred the Seshat integration on
2026-08-05, and `[DEC-BOUNDARY]` explicitly declines to name one — an identifier for deferred
work would be a governed artifact with no owner and no gate, which is the direction
Constitution V points away from.

**`[PKG-RRA-RENEWAL]` is a renewal, not an ordinary package.** `RRA.md` is pinned by `APP-002`
as `sha256:8a1235a0d6b9e36a6446a1e1cfd3f7ef5db52ca7d9e0ed23bcffb18eded095d2`, and the file
hashes to exactly that today, so `src/khepri_gov/approval_renewals.py` applies. `APP-002` also
pins `KHEPRI-DEC-002`, `-003`, `-004`, and `RRA-001` through `RRA-007` — so
`[DEC-COMMERCIAL]`'s supersession of `KHEPRI-DEC-003` must be recorded **in the registry**,
never by adding a `superseded_by` note to the pinned document body.

**`[SPEC-REPORT]` and `RRA-006`.** `APP-002` pins `RRA-006` by digest. `[SPEC-REPORT]` is a new
specification *depending on* `RRA-006`, not an edit to it, so no renewal is implied — **but
confirm the dependency is additive before scoping the work.** If drafting reveals `RRA-006`'s
text must change, the slice grows into a second renewal.

---

## D. Seshat-BI — what the repository contains

Seshat has **no YAML registry**. Identity lives in directory names and file headers.

### Architecture decisions — `docs/decisions/`

`0001` … `0019`, no gaps. *Provisional candidate: `0020`.* `ADR-0008` records an append-only
allotment convention ("Shipped ADRs 0001-0007 and 0012 are never reused"), so a number, once
used, is permanent — which is a reason to derive it at drafting time rather than early.

### Specifications — `specs/`

132 directories, numbered to `141`. *Provisional candidate: `142`.*

Two conventions from `specs/README.md` that any new directory must respect:

1. **Cite by full slug, never by bare number.** Numbers 044, 067, 087, and 088 are each
   duplicated across two unrelated directories.
2. **A bare "spec NNN" in a commit message guarantees nothing.** Rule AL2 shipped citing "067"
   and matches neither committed 067 directory.

**Because bare numbers are already unreliable here, this package uses role names only.** No
number is set aside for any Seshat artifact.

### Ratification and capacity

`docs/roadmap/proposal-batch-ratification-model.md` (RATIFIED 2026-07-04, `build+PR` reach):
clean specs may proceed to build and open a PR autonomously; the owner still reviews and merges;
in-spec judgment calls always escalate; the agent never self-ratifies.

`CLAUDE.md`: spec 138 is RATIFIED and in implementation, spec 137 awaits ratification, and "At
most ONE of the two may be in implementation at a time (spec 138 FR-026)." The SPECKIT fence
carries exactly one plan path by contract.

**This constrains implementation, not authorship — and the deferral means no Seshat
implementation capacity is requested by this package at all.**

---

## E. Seshat-BI — artifacts contemplated

| Placeholder | Would be | Status |
|---|---|---|
| `[SESHAT-ADR-BOUNDARY]` | Headless-engine product-module boundary and consumer isolation | Contemplated |
| `[SESHAT-SPEC-CONTRACTS]` | Schema definitions, fixtures, versioning, compatibility manifest | **Deferred** |
| `[SESHAT-SPEC-ENGINE]` | Repo-root-free analytical API, injected governance context | **Deferred** |
| `[SESHAT-SPEC-CONSUMER]` | Consumer compatibility suite | **Deferred** |

**One decision, not four.** Roadmap §12.2 suggests four Seshat decisions (headless boundary,
stable public API, contract ownership, consumer isolation). All four answer one question — what
may a non-Seshat consumer reach? — and Seshat's convention is one decision per bounded question.
Splitting them re-litigates the same boundary four times, which is the failure `ADR-0008` was
written to prevent.

---

## F. Cross-reference discipline

The two governance systems cannot approve each other's artifacts. Every cross-repository
reference must be **immutable**:

- Khepri → Seshat: full spec slug or ADR number, **plus a commit SHA**.
- Seshat → Khepri: artifact ID **plus a commit SHA**.
- Neither may cite the other's *approval* as evidence for its own. Khepri Constitution III —
  reference is not authority — applies to Seshat-BI by analogy even though Article III names
  Seshat-Platform.

`Seshat/src/seshat/report/charts.py` already models the correct form: "PORTED from
`Khepri/src/khepri/rra/rendering/charts.py` at commit `7a1e3fd`."

**A placeholder is not a cross-reference.** Until an artifact exists with a real identifier at a
real commit, the other repository's document must name the placeholder and say it is not yet
allocated. Writing a provisional number there would read as a citation to something that does
not exist.
