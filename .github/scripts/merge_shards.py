"""Prove the shards ran the whole suite, once, then merge their marker reports (SCRUM-43).

`FND-005` makes the browser and concurrency guards read the outcomes of the **full** suite.
Sharding splits that suite across jobs, so before any guard reads a merged report this
refuses a set of shard reports that:

* is not exactly the expected number of shards (a shard that never reported);
* disagrees about what was collected (the shards ran different code);
* runs a test in two shards, or in none (the split dropped or repeated a file);
* collected nothing at all.

Only then is the merged `marker-report.json` written. A refusal writes nothing, so the guards
that read it fail on a missing report rather than reading a partial one.

`python merge_shards.py <artifact-dir> <expected-shards> <merged-marker-report>`
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

#: How many missing or repeated node ids a refusal names before it summarises.
_NAMED = 10


def partition_errors(reports: list[dict], *, expected: int) -> list[str]:
    """Every way these shard reports fail to add up to one full run. Empty means they do."""
    if len(reports) != expected:
        return [f"expected {expected} shard reports, found {len(reports)}"]
    collected = set(reports[0]["collected"])
    if not collected:
        return ["the shards collected no tests"]
    if any(set(r["collected"]) != collected for r in reports[1:]):
        return ["the shards collected different suites"]
    return _coverage_errors(reports, collected)


def _coverage_errors(reports: list[dict], collected: set[str]) -> list[str]:
    seen: dict[str, str] = {}
    errors = []
    for report in reports:
        for nodeid in report["selected"]:
            if nodeid in seen:
                errors.append(f"{nodeid} ran in shards {seen[nodeid]} and {report['shard']}")
            seen[nodeid] = report["shard"]
    missing = sorted(collected - set(seen))
    if missing:
        named = ", ".join(missing[:_NAMED])
        errors.append(f"{len(missing)} collected tests ran in no shard: {named}")
    return errors


def merge_marker_reports(reports: list[dict]) -> dict[str, dict[str, str]]:
    """One marker report from the shards'. Each test appears in one shard, so this is a union."""
    merged: dict[str, dict[str, str]] = {}
    for report in reports:
        for marker, outcomes in report.items():
            merged.setdefault(marker, {}).update(outcomes)
    return merged


def _read(directory: Path, pattern: str) -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.rglob(pattern))
    ]


def main(argv: list[str]) -> int:
    directory, expected, out = Path(argv[0]), int(argv[1]), Path(argv[2])
    errors = partition_errors(_read(directory, "shard-report-*.json"), expected=expected)
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    merged = merge_marker_reports(_read(directory, "marker-report-*.json"))
    out.write_text(json.dumps(merged, indent=1, sort_keys=True), encoding="utf-8")
    print(f"shards add up: {expected} shards, every collected test ran exactly once")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
