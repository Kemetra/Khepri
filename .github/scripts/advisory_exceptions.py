"""Refuse an advisory exception that is unexplained or permanent (SCRUM-41).

Both scanners accept exceptions natively, and both accept them without a reason or an end date:

* osv-scanner reads `[[IgnoredVulns]]` from `.github/advisories/osv-scanner.toml`
  (`id`, `reason`, `ignoreUntil`);
* Trivy reads `vulnerabilities:` from `.github/advisories/trivyignore.yaml`
  (`id`, `statement`, `expired_at`).

An exception is a decision, and a decision is reviewed in the pull request that adds it and
approved by the owner's merge (Constitution II). So every entry must say why, and must expire
within `MAX_DAYS`: an advisory that is still unfixed after that is decided again, not carried.
When an entry expires, the scanner stops honouring it and the gate fails again, which is the
point. Anything this cannot read is refused rather than skipped (Constitution V).

`python advisory_exceptions.py <osv-scanner.toml> <trivyignore.yaml>` exits 0 or 1.
"""

from __future__ import annotations

import sys
import tomllib
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml

#: The longest an exception may run before it is decided again.
MAX_DAYS = 90

_TRIVY_SECTIONS = {"vulnerabilities"}
_OSV_FIELDS = {"id", "ignoreUntil", "reason"}


def _as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def entry_errors(entry: object, *, reason_key: str, expiry_key: str, today: date) -> list[str]:
    """Why one exception entry is not acceptable. Empty means it is."""
    if not isinstance(entry, dict):
        return [f"not a table of fields: {entry!r}"]
    name = str(entry.get("id") or "").strip()
    errors = [] if name else ["an exception has no `id`"]
    label = name or "?"
    if not str(entry.get(reason_key) or "").strip():
        errors.append(f"{label}: no `{reason_key}` says why it is accepted")
    expiry = _as_date(entry.get(expiry_key))
    if expiry is None:
        errors.append(f"{label}: `{expiry_key}` must be a date; an exception cannot be permanent")
    elif expiry > today + timedelta(days=MAX_DAYS):
        errors.append(f"{label}: `{expiry_key}` {expiry} is more than {MAX_DAYS} days away")
    return errors


def _unknown_fields(entry: object, known: set[str]) -> list[str]:
    if not isinstance(entry, dict):
        return []
    return [f"unknown field `{key}` (only {sorted(known)})" for key in sorted(set(entry) - known)]


def osv_errors(config: dict, *, today: date) -> list[str]:
    """Refuse anything osv-scanner could honour that this check cannot see.

    osv-scanner also honours `[[PackageOverrides]]`, whose `effectiveUntil` is optional (absent
    means permanent), and its TOML decoder matches keys case-insensitively, so `ignoredvulns` or
    `Reason` would be read there and missed here. Only the exact spellings are accepted.
    """
    unknown = sorted(set(config) - {"IgnoredVulns"})
    if unknown:
        return [f"osv-scanner.toml: only `IgnoredVulns` may be excepted, found {unknown}"]
    entries = config.get("IgnoredVulns", [])
    if not isinstance(entries, list):
        return ["`IgnoredVulns` must be an array of tables"]
    return [
        f"osv-scanner.toml: {error}"
        for entry in entries
        for error in _unknown_fields(entry, _OSV_FIELDS)
        + entry_errors(entry, reason_key="reason", expiry_key="ignoreUntil", today=today)
    ]


def trivy_errors(document: object, *, today: date) -> list[str]:
    if document is None:
        return []
    if not isinstance(document, dict):
        return ["trivyignore.yaml: must be a mapping"]
    unknown = sorted(set(document) - _TRIVY_SECTIONS)
    if unknown:
        return [f"trivyignore.yaml: only `vulnerabilities` may be excepted, found {unknown}"]
    entries = document.get("vulnerabilities") or []
    if not isinstance(entries, list):
        return ["trivyignore.yaml: `vulnerabilities` must be a list"]
    return [
        f"trivyignore.yaml: {error}"
        for entry in entries
        for error in entry_errors(
            entry, reason_key="statement", expiry_key="expired_at", today=today
        )
    ]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            "usage: advisory_exceptions.py <osv-scanner.toml> <trivyignore.yaml>", file=sys.stderr
        )
        return 1
    today = datetime.now(UTC).date()
    try:
        osv = tomllib.loads(Path(argv[0]).read_text(encoding="utf-8"))
        trivy = yaml.safe_load(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f"FAIL: cannot read the exception files: {error}", file=sys.stderr)
        return 1
    errors = osv_errors(osv, today=today) + trivy_errors(trivy, today=today)
    for error in errors:
        print(f"FAIL: {error}", file=sys.stderr)
    if not errors:
        print("advisory exceptions: every entry is reasoned and expires")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
