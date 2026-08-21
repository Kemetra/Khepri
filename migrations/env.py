from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from khepri.rca.persistence import Base as RcaBase
from khepri.rca.recovery_security_persistence import RecoverySecurityEventRow
from khepri.rra.delivery_persistence import ReportDeliveryRow
from khepri.rra.job_persistence import ReportJobRow
from khepri.rra.persistence import Base
from khepri.rra.telemetry_persistence import OperationalEventRow

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.environ.get("KHEPRI_DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

_RRA_ROWS = (
    ("Report job", ReportJobRow),
    ("Operational event", OperationalEventRow),
    ("Report delivery", ReportDeliveryRow),
)

# Imported explicitly because the row lives outside the already-large RCA persistence module.
_RCA_ROWS = (("Recovery security event", RecoverySecurityEventRow),)


def _verify_rra_rows_share_one_base() -> None:
    for label, row in _RRA_ROWS:
        if row.metadata is not Base.metadata:
            raise RuntimeError(f"{label} metadata is not registered with the RRA base.")


def _verify_rca_base_is_separate() -> None:
    """RCA declares its own DeclarativeBase rather than joining RRA's (FR-039)."""
    if RcaBase.metadata is Base.metadata:
        raise RuntimeError("RCA metadata must stay separate from the RRA base (FR-039).")
    if any(name.startswith("rra_") for name in RcaBase.metadata.tables):
        raise RuntimeError("RCA metadata must not declare rra_* tables.")
    for label, row in _RCA_ROWS:
        if row.metadata is not RcaBase.metadata:
            raise RuntimeError(f"{label} metadata is not registered with the RCA base.")


_verify_rra_rows_share_one_base()
_verify_rca_base_is_separate()

# Both metadata objects, as a list, so autogenerate sees every table without merging bases.
target_metadata = [Base.metadata, RcaBase.metadata]


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
