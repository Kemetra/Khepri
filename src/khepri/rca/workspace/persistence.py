"""Workspace persistence (`RCA-005` `FR-109`--`FR-113`).

Three tables and one store. `W1-01` wrote the domain contracts and held no persistence; this slice
gives them rows, and nothing else -- no service, no authorization, no computation. `W1-04` takes the
authorized operations.

**Every table is keyed by the opaque isolation scope, with a foreign key that says so.** `FR-109`
and `RCA-001` `FR-033` require the key to carry no commercial meaning and no organization
identifier. A bare `owner_id` column would let a caller write any string; the constraint onto
`rca_isolation_scopes.owner_id` is what makes it a key rather than a label. That target is a
`UNIQUE` column rather than that table's primary key -- `organization_id` is -- which a foreign key
may reference and which is deliberately the column that carries no commercial identifier.

**Retention state lives here and not on the record.** `DatasetVersion`'s docstring in `contracts.py`
commits to this: a version is "immutable once sealed; after that only its retention state changes,
which `W1-02` holds in the store rather than on this record". `FR-112` says the same from the other
side -- append-only, and "only retention state and tombstoning may change a row". So the column is
on the table, the transition is a store operation, and the sealed record read back is unchanged by
it. A retention field on the record would make retention look like content.

**The vocabulary is enforced twice, and neither is decoration.** `RETENTION_STATES` is checked in
the store, which is where a caller gets a content-free refusal rather than a driver error, and again
by a `CHECK` constraint, which is what holds when a row arrives by any other route. `W1-01` closed
exactly this defect in its `RUN_STATES` form: a tuple that only *documents* its values leaves the
constraint with prose and no code path.

This module is now the **public path** for two modules split from it on `#370`: `schema.py`
(rows, constraints, guards) and `store.py` (reads, transitions, locks). It re-exports every name
it previously defined, so nothing that imported from here changed. See each module's docstring.
"""

from __future__ import annotations

from khepri.rca.workspace.locks import live_runs_for_update, run_for_update, version_for_update
from khepri.rca.workspace.run_reports import RunReportRow, SqlRunReportStore
from khepri.rca.workspace.schema import (
    _ROW_GUARDS,  # noqa: F401 -- the guard-shape test asserts this mapping's keys
    APPEND_ONLY_FAILURE,
    COMPLETION_COLUMNS,
    DELETE_FAILURE,
    GOVERNED_SECTION_STATE_CODES,
    MUTABLE_COLUMNS,
    PROFILE_IDENTITY_COLUMNS,
    PROFILE_IDENTITY_FAILURE,
    RECOMPLETE_FAILURE,
    RESEAL_FAILURE,
    RETENTION_ACTIVE,
    RETENTION_STATE_FAILURE,
    RETENTION_STATES,
    RETENTION_TOMBSTONED,
    RUN_TOMBSTONE_COLUMNS,
    SECTION_COLUMNS,
    SECTION_STATE_CODES,
    TOMBSTONE_FAILURE,
    TOMBSTONE_IMMUTABLE_FAILURE,
    TOMBSTONE_SECTIONS,
    TOMBSTONE_SUBJECTS,
    TOMBSTONED_FROZEN_FAILURE,
    VERSION_TOMBSTONE_COLUMNS,
    AnalysisRunRow,
    ArtifactBindingRow,
    DatasetVersionRow,
    SourceProfileRow,
    WorkspaceTombstoneRow,
)
from khepri.rca.workspace.store import SqlWorkspaceRecordStore, WorkspaceHistory

__all__ = [
    "APPEND_ONLY_FAILURE",
    "GOVERNED_SECTION_STATE_CODES",
    "SECTION_COLUMNS",
    "SECTION_STATE_CODES",
    "TOMBSTONE_SECTIONS",
    "TOMBSTONED_FROZEN_FAILURE",
    "VERSION_TOMBSTONE_COLUMNS",
    "TOMBSTONE_IMMUTABLE_FAILURE",
    "RUN_TOMBSTONE_COLUMNS",
    "PROFILE_IDENTITY_FAILURE",
    "PROFILE_IDENTITY_COLUMNS",
    "run_for_update",
    "version_for_update",
    "live_runs_for_update",
    "TOMBSTONE_SUBJECTS",
    "SourceProfileRow",
    "WorkspaceTombstoneRow",
    "WorkspaceHistory",
    "DELETE_FAILURE",
    "COMPLETION_COLUMNS",
    "RECOMPLETE_FAILURE",
    "RESEAL_FAILURE",
    "TOMBSTONE_FAILURE",
    "MUTABLE_COLUMNS",
    "RETENTION_ACTIVE",
    "RETENTION_STATES",
    "RETENTION_STATE_FAILURE",
    "RETENTION_TOMBSTONED",
    "AnalysisRunRow",
    "ArtifactBindingRow",
    "DatasetVersionRow",
    "RunReportRow",
    "SqlRunReportStore",
    "SqlWorkspaceRecordStore",
]
