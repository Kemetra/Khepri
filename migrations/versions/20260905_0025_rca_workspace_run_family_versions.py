"""Retain each `RRA-008` family's version with the run that ran under it (`W1-08`, `RCA-005`
`FR-116`).

`FR-116` names `rra008.*` beside `rra003.mapping.*` and `rra004.*` among the governed versions a
Methodology Change Notice must present. `20260905_0024` retained the mapping, package and core
formula identifiers, but not the four family versions, so a run whose comparison or basket analysis
moved reported no change and the differing identifier was unreachable (review on `#377`).

**Not derivable, so retained.** `versions.ADMITTED_FAMILY_PAIRS` records which
`(formula, family)` pairings are *authorized*; it never records which one a given run used, and it
gains a row whenever a family lands. Reading a run's family version out of that table would answer
a different question than "what did this run run under", and would answer it ambiguously the first
time one formula admits two versions of one family. Only the run's own record can say.

**Nullable, and read as absence.** A run completed before this migration retained no family
version, and Analysis detail must still render its Passport and its Notice. Null therefore means
"not recorded" and never "a version that changed": the Notice states a family only where both runs
recorded one and the two differ. A run completed since retains all four.

**`down_revision` is `20260905_0024`**, `W1-06`'s provenance record, the head this slice inherits.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_0025"
down_revision: str | None = "20260905_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: One per `RRA-008` family. `overview` is the package's own summary and stamps no family version.
#: Spelled literally here as `20260905_0024` spells its section columns; the drift test compares
#: these against `schema.FAMILY_VERSION_COLUMNS`.
_FAMILY_VERSION_COLUMNS = (
    "family_comparison_version",
    "family_concentration_version",
    "family_growth_version",
    "family_basket_version",
)


def upgrade() -> None:
    with op.batch_alter_table("rca_workspace_run_provenance") as batch:
        for column in _FAMILY_VERSION_COLUMNS:
            batch.add_column(sa.Column(column, sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("rca_workspace_run_provenance") as batch:
        for column in reversed(_FAMILY_VERSION_COLUMNS):
            batch.drop_column(column)
