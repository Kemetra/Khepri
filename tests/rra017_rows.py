"""One scope's rows in every `khepri.rra` table, for RRA-017's policy tests (`#595`).

Each builder returns the column values of one valid row: every CHECK and every foreign key holds
when `chain(scope)` is inserted in order. The order is the foreign-key order, so a prefix of it
(`before(scope, table)`) is every parent a row of `table` needs and none of its dependants.

The rows are written as the migration owner, which crosses the policies (`FR-270`). A test that
asks whether a runtime role may write a row names one of these and attempts the insert itself.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from khepri.rra.sessions import SessionScope, object_prefix

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
HOUR = timedelta(hours=1)
WEEK = timedelta(days=7)


def digest(seed: str) -> str:
    """A 64-character hex digest, distinct per seed, for every `length(...) = 64` CHECK."""
    return hashlib.sha256(seed.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class Scope:
    """One owner's identifiers. `tag` keeps two chains under one owner apart."""

    owner_id: str
    tag: str

    def ident(self, kind: str) -> str:
        return f"{kind}_{self.tag}"

    @property
    def session_id(self) -> str:
        return self.ident("ses")

    @property
    def job_id(self) -> str:
        return self.ident("job")

    @property
    def bundle_id(self) -> str:
        return digest(f"bundle-{self.tag}")


Row = dict[str, Any]


def _session(s: Scope) -> Row:
    return {
        "session_id": s.session_id,
        "owner_id": s.owner_id,
        "created_at": NOW - HOUR,
        "content_expires_at": NOW + WEEK,
        "consent_version": None,
        "consented_at": None,
        "deletion_requested_at": None,
        "content_deleted_at": None,
    }


def _envelope(s: Scope, kind: str) -> Row:
    return {
        "owner_id": s.owner_id,
        "session_id": s.session_id,
        "object_key": object_prefix(SessionScope(s.owner_id, s.session_id)) + kind,
        "size_bytes": 10,
        "sha256_hex": digest(f"{kind}-plain-{s.tag}"),
        "created_at": NOW - HOUR,
        "expires_at": NOW + WEEK,
        "encryption_algorithm": "AES-256-GCM",
        "envelope_version": 2,
        "ciphertext_sha256_hex": digest(f"{kind}-cipher-{s.tag}"),
    }


def _upload(s: Scope) -> Row:
    return {"upload_id": s.ident("upl"), "media_type": "text/csv", **_envelope(s, "upload")}


def _profile(s: Scope) -> Row:
    return {
        "profile_id": s.ident("prf"),
        "owner_id": s.owner_id,
        "session_id": s.session_id,
        "upload_id": s.ident("upl"),
        "profile_version": "v1",
        "mapping_version": "v1",
        "source_sha256_hex": digest(f"source-{s.tag}"),
        "profile_digest": digest(f"profile-{s.tag}"),
        "row_count": 1,
        "column_count": 1,
        "admissible": True,
        "created_at": NOW - HOUR,
        "document": {},
    }


def _package(s: Scope) -> Row:
    return {
        "package_id": s.ident("pkg"),
        "owner_id": s.owner_id,
        "session_id": s.session_id,
        "profile_id": s.ident("prf"),
        "package_version": "v1",
        "formula_version": "v1",
        "mapping_version": "v1",
        "profile_document_digest": digest(f"profile-document-{s.tag}"),
        "source_sha256_hex": digest(f"source-{s.tag}"),
        "package_digest": digest(f"package-{s.tag}"),
        "row_count": 1,
        "created_at": NOW - HOUR,
        "document": {},
    }


def _job(s: Scope) -> Row:
    return {
        "job_id": s.job_id,
        "owner_id": s.owner_id,
        "session_id": s.session_id,
        "idempotency_key": digest(f"idempotency-{s.tag}"),
        "state": "queued",
        "queued_at": NOW - HOUR,
        "available_at": NOW - HOUR,
        "attempt_count": 0,
        "max_attempts": 3,
        "lease_owner": None,
        "lease_expires_at": None,
        "completed_at": None,
        "dead_letter_reason": None,
    }


def _job_attempt(s: Scope) -> Row:
    return {
        "job_id": s.job_id,
        "attempt_number": 1,
        "session_id": s.session_id,
        "released_at": NOW - HOUR / 2,
        "disposition": "retry_scheduled",
        "available_at": NOW - HOUR / 2,
    }


def _operational_event(s: Scope) -> Row:
    return {
        "event_id": s.ident("evt"),
        "session_id": s.session_id,
        "job_id": s.job_id,
        "fact_package_id": None,
        "report_bundle_id": None,
        "stage": "profiling",
        "transition": "started",
        "attempt_number": 1,
        "recorded_at": NOW - HOUR,
        "duration_ms": None,
        "queue_time_ms": None,
        "provider_latency_ms": None,
        "dataset_size_band": None,
        "output_size_bytes": None,
    }


def _delivery(s: Scope) -> Row:
    return {
        "job_id": s.job_id,
        "owner_id": s.owner_id,
        "session_id": s.session_id,
        "bundle_id": s.bundle_id,
        "package_version": "v1",
        "narrative_state": "omitted",
        "generated_at": NOW - HOUR,
        "expires_at": NOW + WEEK,
    }


def _delivery_surface(s: Scope) -> Row:
    return {
        "job_id": s.job_id,
        "surface": "web",
        "bundle_id": s.bundle_id,
        "content_digest": digest(f"surface-{s.tag}"),
    }


def _artifact(s: Scope) -> Row:
    return {
        "job_id": s.job_id,
        "artifact_kind": "excel",
        "bundle_id": s.bundle_id,
        "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "file_name": "khepri-report.xlsx",
        **_envelope(s, "artifact"),
    }


def _deletion_job(s: Scope) -> Row:
    return {
        "deletion_id": s.ident("del"),
        "owner_id": s.owner_id,
        "session_id": s.session_id,
        "reason": "immediate",
        "state": "pending",
        "requested_at": NOW - HOUR,
        "attempt_count": 0,
        "last_attempt_at": None,
        "next_retry_at": None,
        "completed_at": None,
    }


def _deletion_evidence(s: Scope) -> Row:
    return {
        "evidence_id": s.ident("evd"),
        "deletion_id": s.ident("del"),
        "target_kind": "input",
        "target_id": s.ident("upl"),
        "location_digest": digest(f"location-{s.tag}"),
        "content_digest": digest(f"content-{s.tag}"),
        "attempted_at": NOW - HOUR,
        "attempt_number": 1,
        "outcome": "deleted",
        "error_code": None,
    }


#: Every scope-reachable `khepri.rra` table, in foreign-key order.
BUILDERS: dict[str, Callable[[Scope], Row]] = {
    "rra_beta_sessions": _session,
    "rra_uploads": _upload,
    "rra_dataset_profiles": _profile,
    "rra_fact_packages": _package,
    "rra_report_jobs": _job,
    "rra_report_job_attempts": _job_attempt,
    "rra_operational_events": _operational_event,
    "rra_report_deliveries": _delivery,
    "rra_report_delivery_surfaces": _delivery_surface,
    "rra_report_artifacts": _artifact,
    "rra_deletion_jobs": _deletion_job,
    "rra_deletion_evidence": _deletion_evidence,
}

#: Each table's primary-key columns, which name one scope's row in it.
PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "rra_beta_sessions": ("session_id",),
    "rra_uploads": ("upload_id",),
    "rra_dataset_profiles": ("profile_id",),
    "rra_fact_packages": ("package_id",),
    "rra_report_jobs": ("job_id",),
    "rra_report_job_attempts": ("job_id", "attempt_number"),
    "rra_operational_events": ("event_id",),
    "rra_report_deliveries": ("job_id",),
    "rra_report_delivery_surfaces": ("job_id", "surface"),
    "rra_report_artifacts": ("job_id", "artifact_kind"),
    "rra_deletion_jobs": ("deletion_id",),
    "rra_deletion_evidence": ("evidence_id",),
}

#: The columns that place a row in its scope: `owner_id` where it has one, else the parent key
#: `FR-269` walls it through. Re-pointing these at another scope is what `Verification 3` refuses.
SCOPE_COLUMNS: dict[str, tuple[str, ...]] = {
    "rra_beta_sessions": ("owner_id",),
    "rra_uploads": ("owner_id", "session_id"),
    "rra_dataset_profiles": ("owner_id", "session_id"),
    "rra_fact_packages": ("owner_id", "session_id"),
    "rra_report_jobs": ("owner_id", "session_id"),
    "rra_report_job_attempts": ("job_id", "session_id"),
    "rra_operational_events": ("job_id", "session_id"),
    "rra_report_deliveries": ("owner_id", "session_id"),
    "rra_report_delivery_surfaces": ("job_id", "bundle_id"),
    "rra_report_artifacts": ("owner_id", "session_id"),
    "rra_deletion_jobs": ("owner_id", "session_id"),
    "rra_deletion_evidence": ("deletion_id",),
}

#: A column every row of the table carries, for a write that changes nothing (`SET c = c`).
TOUCH_COLUMNS: dict[str, str] = {
    "rra_beta_sessions": "content_expires_at",
    "rra_uploads": "expires_at",
    "rra_dataset_profiles": "created_at",
    "rra_fact_packages": "created_at",
    "rra_report_jobs": "available_at",
    "rra_report_job_attempts": "released_at",
    "rra_operational_events": "recorded_at",
    "rra_report_deliveries": "expires_at",
    "rra_report_delivery_surfaces": "content_digest",
    "rra_report_artifacts": "expires_at",
    "rra_deletion_jobs": "requested_at",
    "rra_deletion_evidence": "attempted_at",
}


def row(scope: Scope, table: str, **overrides: Any) -> Row:
    """One row of `table` for `scope`, with any column replaced."""
    return {**BUILDERS[table](scope), **overrides}


def chain(scope: Scope) -> list[tuple[str, Row]]:
    """One row in every table, parents first."""
    return [(table, build(scope)) for table, build in BUILDERS.items()]


def before(scope: Scope, table: str) -> list[tuple[str, Row]]:
    """Every row `chain` writes ahead of `table`: its parents exist, it and its dependants not."""
    rows = chain(scope)
    return rows[: [name for name, _ in rows].index(table)]


def key_of(scope: Scope, table: str) -> tuple[Any, ...]:
    """The primary key of `scope`'s row in `table`."""
    values = BUILDERS[table](scope)
    return tuple(values[column] for column in PRIMARY_KEYS[table])


def repointed(scope: Scope, other: Scope, table: str) -> Row:
    """`table`'s scope columns as `other`'s row carries them."""
    values = BUILDERS[table](other)
    return {column: values[column] for column in SCOPE_COLUMNS[table]}


__all__ = [
    "BUILDERS",
    "HOUR",
    "NOW",
    "PRIMARY_KEYS",
    "SCOPE_COLUMNS",
    "TOUCH_COLUMNS",
    "WEEK",
    "Row",
    "Scope",
    "before",
    "chain",
    "digest",
    "key_of",
    "repointed",
    "row",
]
