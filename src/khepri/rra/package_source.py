"""Rebuilding a published fact package for the job that will report on it.

**Why the rebuild is not a constructor on `FactPackage`.** `build_fact_package`
re-derives the profile, the mapping and the admissibility decision from the
bytes and refuses anything that does not match, which is what makes a package
trustworthy. A `from_document` classmethod beside it would be a second
constructor that trusts its input completely, sitting one line away from the one
that trusts nothing. It lives here instead, next to the only thing that makes it
safe: the recomputed content address. A document that does not hash back to the
address it was stored under is refused rather than reported.

**What this module does not re-check.** Whether a stored package may be *served*
at all -- the session exists, consent stands, the content has not expired, the
governed versions have not advanced, the provenance still matches the profile it
cites -- is `FactPackageService._assert_current` and its callers, which
`packages.py` documents as the single test of that question. Restating those
checks here is how the RRA-004 read path once came to be missing several of
them, so this module asks a reader that already applies them.

**Why a clock reaches this module.** `pipeline.py` has none deliberately: a
generation timestamp belongs to the record that stores a report, not to the
bundle's identity. Reading a package is a different question -- expiry and
consent are decided as of a moment -- and the governed reader takes that moment
as an argument. So the source holds the clock the pipeline refuses to.

**Why the whole job, and not a session identifier.** The reader selects on the
session alone. A job carries the owner too, and the owner is what makes the
isolation boundary checkable, so the source compares the scope the job was
leased under against the scope the package was published under.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, runtime_checkable

from khepri.rra.aggregates import Bucket, Comparison, Series
from khepri.rra.facts import (
    Fact,
    FactComparison,
    FactPackage,
    FactSeries,
    RefusedResult,
)
from khepri.rra.jobs import ReportJob
from khepri.rra.packages import FactPackageRecord, PackageCorrupted
from khepri.rra.sessions import SessionScope, assert_same_scope


@runtime_checkable
class SessionPackageReader(Protocol):
    """A reader of the package a session published, under the governed checks.

    `FactPackageService` is the implementation; this names the one method of it
    that a report run needs, so the source depends on the question rather than
    on the whole publication service.
    """

    def get_session_package(
        self,
        *,
        session_id: str,
        now: datetime,
    ) -> FactPackageRecord | None: ...


class SessionFactPackageSource:
    """The fact package for a leased job, rebuilt from what was published."""

    def __init__(
        self,
        *,
        packages: SessionPackageReader,
        now: Callable[[], datetime],
    ) -> None:
        self._packages = packages
        self._now = now

    def load(self, job: ReportJob) -> FactPackage | None:
        """The one package this job may report on, or nothing published yet.

        `None` means no package was published for this session, which the
        pipeline records as a missing package. Every other unhappy answer --
        an unavailable session, a superseded version, a package that no longer
        matches its profile or its own digest -- raises, because reporting any
        of them as an absence would turn a refused read into a routine one.
        """
        record = self._packages.get_session_package(
            session_id=job.session_id,
            now=self._now(),
        )
        if record is None:
            return None
        assert_same_scope(
            SessionScope(owner_id=job.owner_id, session_id=job.session_id),
            record.scope,
        )
        package = rebuild_fact_package(record.document)
        if package.digest != record.package_digest:
            # Recomputed from the rebuilt package rather than from the stored
            # text, so this proves two things at once: the document is intact,
            # and nothing was lost or invented in rebuilding it.
            raise PackageCorrupted("Rebuilt fact package does not match its digest.")
        return package


def rebuild_fact_package(document: Mapping[str, Any]) -> FactPackage:
    """The package a stored canonical document describes, field by field.

    Enumerated rather than unpacked, so a document carrying an unexpected field
    cannot smuggle it into a governed object, and a governed field that is
    absent is refused instead of defaulted.
    """
    return FactPackage(
        package_version=_text(document, "package_version"),
        formula_version=_text(document, "formula_version"),
        mapping_version=_text(document, "mapping_version"),
        profile_digest=_text(document, "profile_digest"),
        source_sha256_hex=_text(document, "source_sha256_hex"),
        row_count=_count(document, "row_count"),
        monetary_precision=_count(document, "monetary_precision"),
        facts=tuple(_fact(entry) for entry in _entries(document, "facts")),
        series=tuple(_series(entry) for entry in _entries(document, "series")),
        comparisons=tuple(_comparison(entry) for entry in _entries(document, "comparisons")),
        refusals=tuple(_refusal(entry) for entry in _entries(document, "refusals")),
        caveats=_labels(document, "caveats"),
    )


def _fact(entry: Mapping[str, Any]) -> Fact:
    return Fact(
        fact_id=_text(entry, "fact_id"),
        citation_id=_text(entry, "citation_id"),
        metric=_text(entry, "metric"),
        value=_text(entry, "value"),
        precision=_count(entry, "precision"),
        unit_kind=_text(entry, "unit_kind"),
        inputs=_labels(entry, "inputs"),
        caveats=_labels(entry, "caveats"),
    )


def _series(entry: Mapping[str, Any]) -> FactSeries:
    return FactSeries(
        fact_id=_text(entry, "fact_id"),
        citation_id=_text(entry, "citation_id"),
        metric=_text(entry, "metric"),
        measure=_text(entry, "measure"),
        precision=_count(entry, "precision"),
        unit_kind=_text(entry, "unit_kind"),
        series=Series(
            granularity=_text(entry, "granularity"),
            buckets=tuple(_bucket(point) for point in _entries(entry, "points")),
        ),
        caveats=_labels(entry, "caveats"),
    )


def _comparison(entry: Mapping[str, Any]) -> FactComparison:
    return FactComparison(
        fact_id=_text(entry, "fact_id"),
        citation_id=_text(entry, "citation_id"),
        metric=_text(entry, "metric"),
        measure=_text(entry, "measure"),
        precision=_count(entry, "precision"),
        unit_kind=_text(entry, "unit_kind"),
        comparison=Comparison(
            dimension=_text(entry, "dimension"),
            buckets=tuple(_bucket(cell) for cell in _entries(entry, "buckets")),
            distinct_values=_count(entry, "distinct_values"),
            truncated_values=_count(entry, "truncated_values"),
            redacted_values=_count(entry, "redacted_values"),
        ),
        caveats=_labels(entry, "caveats"),
    )


def _bucket(entry: Mapping[str, Any]) -> Bucket:
    return Bucket(
        label=_text(entry, "label"),
        value=_value(entry, "value"),
        rows=_count(entry, "rows"),
    )


def _refusal(entry: Mapping[str, Any]) -> RefusedResult:
    return RefusedResult(metric=_text(entry, "metric"), reason=_text(entry, "reason"))


def _text(document: Mapping[str, Any], name: str) -> str:
    value = _required(document, name)
    if not isinstance(value, str):
        raise PackageCorrupted(f"Stored fact package states no {name}.")
    return value


def _count(document: Mapping[str, Any], name: str) -> int:
    value = _required(document, name)
    if not _is_count(value):
        raise PackageCorrupted(f"Stored fact package states no {name}.")
    return value


def _is_count(value: Any) -> bool:
    """Whether a stored value is a whole non-negative count."""
    if isinstance(value, bool):
        # `bool` is an `int`, and `True` is not a row count.
        return False
    if not isinstance(value, int):
        return False
    return value >= 0


def _value(document: Mapping[str, Any], name: str) -> Decimal | None:
    """A bucket's measure, which a withheld value leaves absent rather than zero."""
    value = _required(document, name, optional=True)
    if value is None:
        return None
    if not isinstance(value, str):
        raise PackageCorrupted(f"Stored fact package states no {name}.")
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise PackageCorrupted(f"Stored fact package states no {name}.") from error


def _labels(document: Mapping[str, Any], name: str) -> tuple[str, ...]:
    entries = _entries(document, name, of_mappings=False)
    if any(not isinstance(entry, str) for entry in entries):
        raise PackageCorrupted(f"Stored fact package states no {name}.")
    return tuple(entries)


def _entries(
    document: Mapping[str, Any],
    name: str,
    *,
    of_mappings: bool = True,
) -> Sequence[Any]:
    value = _required(document, name)
    if isinstance(value, str):
        # `str` is a sequence, and a document naming one caveat as a bare
        # string would otherwise rebuild as one caveat per character.
        raise PackageCorrupted(f"Stored fact package states no {name}.")
    if not isinstance(value, Sequence):
        raise PackageCorrupted(f"Stored fact package states no {name}.")
    if of_mappings:
        _require_mappings(value, name)
    return value


def _require_mappings(entries: Sequence[Any], name: str) -> None:
    if any(not isinstance(entry, Mapping) for entry in entries):
        raise PackageCorrupted(f"Stored fact package states no {name}.")


def _required(
    document: Mapping[str, Any],
    name: str,
    *,
    optional: bool = False,
) -> Any:
    if name not in document:
        raise PackageCorrupted(f"Stored fact package states no {name}.")
    value = document[name]
    if optional:
        return value
    if value is None:
        raise PackageCorrupted(f"Stored fact package states no {name}.")
    return value


__all__ = [
    "SessionFactPackageSource",
    "SessionPackageReader",
    "rebuild_fact_package",
]
