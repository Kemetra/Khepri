"""Bind a fact package's profile to the package's own scope (#432, `RRA-001`).

`RRA-001` binds every fact package to its opaque owner and session. `rra_fact_packages` had two
independent foreign keys for that: `(owner_id, session_id)` onto the session and `profile_id` onto
the profile. Each was checked separately, so a package in scope A could cite scope B's profile and
still satisfy both. The workspace closed the same hole with composite keys in `20260904_0021`, and
this revision does the same here.

**The key carries all three columns.** `fk_package_profile_scope` references
`(owner_id, session_id, profile_id)`. `(owner_id, profile_id)` alone would still let a package cite
another session's profile under the same owner, and `RRA-001` fails such cross-session access
closed. `packages.py` builds every package from the scope and profile of one session, so the
stronger form refuses nothing the product writes. `uq_profile_scope` exists only as the reference
target, because `profile_id` is already unique as the primary key.

**It replaces `fk_package_profile` instead of sitting beside it.** The composite key implies the
single-column one, and two keys stating one fact are how they come to disagree.

**`RESTRICT`, as before.** `deletion_persistence.py` deletes packages before profiles, which the
single-column key already required.

**An upgrade over a cross-scope row fails.** PostgreSQL validates existing rows when the key is
added, so a database that already holds such a package refuses to upgrade. That is intended: the
row is the defect, and `RRA-002`'s deletion path is how content leaves.

**Deferred, not forgotten.** A key from `rra_beta_sessions.owner_id` onto `rca_isolation_scopes`
would refuse every invitation-redeemed session, because those carry a design-partner scope that has
no scope row. The plan at `docs/superpowers/plans/2026-09-25-432-tenant-schema-plan.md` records
this and the other deferrals.

Constraint names are spelled literally rather than imported from the model, so a later edit to the
model cannot rewrite what this revision did.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260925_0031"
down_revision: str | None = "20260915_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PACKAGES = "rra_fact_packages"
_PROFILES = "rra_dataset_profiles"
_SCOPE = ["owner_id", "session_id", "profile_id"]
_TARGET = "uq_profile_scope"
_COMPOSITE = "fk_package_profile_scope"
_LEGACY = "fk_package_profile"


def upgrade() -> None:
    with op.batch_alter_table(_PROFILES) as profiles:
        profiles.create_unique_constraint(_TARGET, _SCOPE)
    with op.batch_alter_table(_PACKAGES) as packages:
        packages.drop_constraint(_LEGACY, type_="foreignkey")
        packages.create_foreign_key(_COMPOSITE, _PROFILES, _SCOPE, _SCOPE, ondelete="RESTRICT")


def downgrade() -> None:
    with op.batch_alter_table(_PACKAGES) as packages:
        packages.drop_constraint(_COMPOSITE, type_="foreignkey")
        packages.create_foreign_key(
            _LEGACY, _PROFILES, ["profile_id"], ["profile_id"], ondelete="RESTRICT"
        )
    with op.batch_alter_table(_PROFILES) as profiles:
        profiles.drop_constraint(_TARGET, type_="unique")
