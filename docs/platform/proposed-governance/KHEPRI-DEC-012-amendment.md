# Draft amendment to `KHEPRI-DEC-012`

**Draft for owner review. Not applied.** Target:
`governance/decisions/KHEPRI-DEC-012-transformation-and-orchestration-boundary.md`.
No registry change — `KHEPRI-DEC-012` stays `proposed`.

---

## Why this is an amendment and not a supersession

`KHEPRI-DEC-012` is `proposed` in `governance/registries/decisions.yaml`. Its own closing line:

> This decision remains proposed until its registry entry contains explicit approval evidence.

An unaccepted decision is a draft. Editing it is a review, not a governed change. Once it is
accepted, the same edit becomes a supersession requiring a new decision and a new approval
package — and `APP-013`'s treatment of `KHEPRI-DEC-005` shows what that costs: the document is
pinned by `document_sha256` and `khepri-gov validate` fails closed on any edit.

**Roadmap §10 Phase 0 places this at item 3, after the boundary decisions. That order is more
expensive.** Amend first.

## What DEC-012 actually decided, stated fairly

It refused **dbt and Dagster adoption into Khepri**, on evidence that remains correct:

- dbt without a warehouse has no relation to compile against, and `KHEPRI-DEC-005:36` excludes
  a data warehouse;
- a Dagster daemon with its own run storage is the microservice boundary the same clause
  excludes;
- Khepri's job layer already provides every Dagster capability it needs, and per-stage retry
  is architecturally forbidden by the lease-safety argument at `KHEPRI-DEC-012:28-34`;
- Seshat-BI's adapters are CLIs over a developer checkout holding a repository-root lock —
  "Neither is a library Khepri could import, and neither is a service Khepri could call."

**None of that is disturbed.** The amendment does not reopen dbt or Dagster.

## What it did not decide

It never considered a **headless analytical contract**, because none was proposed. Its
Consequences line —

> Seshat-BI is unaffected. Its adapters remain correctly placed over a medallion warehouse that
> actually exists. No cross-repository dependency is created in either direction.

— is an observation about what refusing dbt and Dagster *does*. Read as a general prohibition
it would settle a question the decision never examined, on evidence it never gathered. That
reading is available today, and roadmap §10 Phase 0 item 3 shows a reader taking it.

## The proposed edit

Insert as a new subsection under **Consequences**, immediately after the "Seshat-BI is
unaffected" bullet:

> ### What this decision does not decide about Seshat-BI
>
> This decision refuses two **tooling runtime** dependencies: a dbt binary compiling against a
> warehouse, and a Dagster daemon with its own run storage. Its evidence is about runtimes —
> a separately provisioned interpreter, a repository-root filesystem lock, a `dbt-core==1.12.0`
> pin against Khepri's `jinja2>=3.1,<4`, `requires-python >=3.13` against Khepri's
> `>=3.13,<3.14`, and a wheel that deliberately excludes `src/khepri/local` from the image that
> runs web and worker.
>
> A dependency on a **versioned analytical contract** — a published schema package with
> fixtures and a compatibility manifest, carrying no numerical library, no CLI, no workspace
> root, and no adapter — is a different question with different evidence. This decision does
> not reach it, and the sentence "No cross-repository dependency is created in either
> direction" describes the effect of refusing dbt and Dagster, not a standing prohibition on
> every form of cross-repository dependency.
>
> That question is `[DEC-BOUNDARY]`'s. If `[DEC-BOUNDARY]` authorizes a contract dependency, it
> does so on its own evidence and supersedes nothing here.
>
> The following stay refused by this decision and are not reopened by `[DEC-BOUNDARY]`:
>
> ```text
> Khepri -> dbt runtime
> Khepri -> Dagster runtime
> Khepri -> Power BI runtime
> Khepri -> a Seshat-BI repository checkout or workspace root
> Khepri -> the Seshat-BI CLI
> Khepri -> co-installation of the seshat-bi distribution
> ```

## Two smaller corrections in the same edit

**1. The prompting observation is now answered.** `KHEPRI-DEC-012:209-214` says it does not
address the observation that prompted it and that "They are the roadmap's subject, and they
begin with a family charter." Both `docs/khepri-commercial-roadmap.md` (2026-08-04) and the
owner's master roadmap (2026-08-05) now exist. Add a pointer so a reader is not sent looking
for a document that has since been written twice.

**2. The catalog gap has a candidate owner.** `KHEPRI-DEC-012:202-205` leaves open that Khepri
has no browsable catalog of governed facts, formulas, and citations. The Phase 1 design package
(`docs/reporting/`) resolves the *customer-facing* half by separating business and audit
layers, and explicitly keeps the governed-fact catalog "as an internal product and
specification asset." Cross-reference it; the gap is narrower than DEC-012 recorded.

## What the amendment does not do

- Does not accept `KHEPRI-DEC-012`. Approval is the owner's, under Constitution II.
- Does not authorize a Seshat dependency. That is `[DEC-BOUNDARY]`.
- Does not touch `governance/registries/decisions.yaml`.
- Does not reopen dbt or Dagster.

## If the owner prefers to accept DEC-012 unamended

Legitimate, with a stated cost: `[DEC-BOUNDARY]` then opens against an accepted decision whose
Consequences read as a general prohibition, and must either supersede that section or argue it
was never general. The second is weaker — a decision's plain text is what a later reader has.
Amending a draft is cheaper than arguing about an accepted one.
