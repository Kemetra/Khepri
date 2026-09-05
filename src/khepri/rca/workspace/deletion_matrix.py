"""Which ending each workspace class gets when a customer deletes (`KHEPRI-DEC-033` §2).

§2's matrix is authoritative and assigns every class an ending. This restates it as **data**, and
the form is the point. A hand-written cascade is a scope that disarms itself: a class added later
that the sequence does not mention ends nothing, while every existing test still passes. A table
can be checked for *extent* -- `test_every_workspace_table_has_exactly_one_stated_ending` compares
it against `Base.metadata`, so a new workspace table cannot appear without a decision about what a
deletion does to it.

**This is an assertion, not the walk.** `store.set_retention_state` already tombstones a version and
cascades to its runs, and `DeletionService.delete_session_content` already ends the `RRA` content.
Re-implementing either here would be the second implementation `local/sweeper.py` warns against.
What this adds is that the decision each table's ending rests on is written down and checkable.

**Restated rather than imported**, as `TOMBSTONE_SECTIONS` is: `R7-01` §3 forbids `khepri.rca`
importing `khepri.rra`, and half of §2's classes live over there.
"""

from __future__ import annotations

#: The row is replaced by a tombstone: §3's allowlist survives, the rest is gone.
ENDING_TOMBSTONE = "tombstone"
#: The rows are removed outright; nothing of them survives the ending.
ENDING_PURGE = "purge"
#: Ended because a row it names ended -- §1's *named cascade*, evidenced as part of the parent's
#: deletion rather than as an act of its own.
ENDING_CASCADE = "cascade"
#: **Not** ended by a customer's deletion: this is what records that one happened. Ending it with
#: the object would erase the evidence that the object ended. Each such class carries its own
#: twelve-month horizon (`KHEPRI-DEC-015` §2a), which `W1-07b`'s retention sweep enforces.
ENDING_SURVIVES = "survives"

#: One entry per `rca_workspace_*` table, each citing the `KHEPRI-DEC-033` §2 row it comes from.
ENDINGS: dict[str, str] = {
    # "Dataset version ... **Tombstone, by allowlist** (§3) ... Immediate, cascading to every
    # derivative below; evidence recorded". The object a customer's deletion names.
    "rca_workspace_dataset_versions": ENDING_TOMBSTONE,
    # "Analysis run ... **Tombstone** as above; the row remains so history does not silently
    # shorten". Reached because its version ended: §1's named cascade.
    "rca_workspace_analysis_runs": ENDING_CASCADE,
    # "Report bundle artifacts ... **Purged** -- the run's tombstone is the only trace".
    "rca_workspace_artifact_bindings": ENDING_CASCADE,
    # "Provenance record ... Digests and version identifiers survive in the tombstone; nothing
    # else". Ends with its run.
    "rca_workspace_run_provenance": ENDING_CASCADE,
    # The run-to-report link is provenance of the same ending, and ends with the run it links.
    "rca_workspace_run_reports": ENDING_CASCADE,
    # "Reusable source profile ... **Purged** ... deleting a profile deletes no dataset version".
    # A customer may delete one directly, and it names no parent -- so purge, never cascade.
    "rca_workspace_source_profiles": ENDING_PURGE,
    # What survives: the tombstone is §3's record of the ending, the audit event is `FR-125`'s
    # account of who performed it, and the revocation entry is `FR-126`'s guard against a restore
    # undoing it. None may be ended by the deletion it records.
    "rca_workspace_tombstones": ENDING_SURVIVES,
    "rca_workspace_audit_events": ENDING_SURVIVES,
    "rca_workspace_revocations": ENDING_SURVIVES,
}

__all__ = [
    "ENDINGS",
    "ENDING_CASCADE",
    "ENDING_PURGE",
    "ENDING_SURVIVES",
    "ENDING_TOMBSTONE",
]
