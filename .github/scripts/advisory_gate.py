"""Fail CI on an actionable High or Critical advisory in an osv-scanner report (SCRUM-41).

osv-scanner exits 1 on *any* advisory, Medium and Low included, so its exit code cannot be the
gate. This reads its JSON report (`--format json --all-packages`) and decides:

* **blocking**: a CVSS score of 7.0 or more (High or Critical) **and** a published fixed version.
  A fix is what makes a finding actionable; one with no fix is reported, not gated.
* **blocking, fail closed**: an advisory with a fix but no CVSS score at all. An unscored
  advisory is not a low one, and Constitution V refuses to infer what is missing.
* **reported only**: everything else, so a Medium or an unfixed High stays visible.

A report that scanned no package at all is refused rather than passed: a lockfile that parsed to
nothing and a lockfile with no advisories look identical from the exit code alone.

Exceptions are not decided here. osv-scanner applies `.github/advisories/osv-scanner.toml`
before writing the report, and `advisory_exceptions.py` checks that every one of them is
reasoned and expires.

`python advisory_gate.py <osv-report.json>` prints a Markdown table and exits 0 (nothing
blocking), 1 (a blocking advisory) or 2 (the report is refused).
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

#: CVSS 7.0 is where High begins; Critical (9.0+) is above it.
THRESHOLD = 7.0

PASS, BLOCKED, REFUSED = 0, 1, 2

_HEADER = (
    "| Gate | Package | Version | Advisory | Severity (CVSS) | Fixed version | Source |\n"
    "|---|---|---|---|---|---|---|"
)


class RefusedReport(ValueError):
    """The report cannot be read as a scan of a real lockfile."""


@dataclass(frozen=True)
class Finding:
    """One advisory group osv-scanner reported against one locked package."""

    source: str
    package: str
    version: str
    ids: tuple[str, ...]
    score: float | None
    fixed: tuple[str, ...]

    @property
    def blocking(self) -> bool:
        if not self.fixed:
            return False
        return self.score is None or self.score >= THRESHOLD

    @property
    def gate(self) -> str:
        if self.blocking:
            return "**BLOCKING**"
        return "reported: no fix" if not self.fixed else "reported: below High"


def severity_label(score: float | None) -> str:
    if score is None:
        return "unscored"
    for floor, name in ((9.0, "CRITICAL"), (7.0, "HIGH"), (4.0, "MEDIUM"), (0.1, "LOW")):
        if score >= floor:
            return f"{score:.1f} {name}"
    return f"{score:.1f} NONE"


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _score(text: object) -> float | None:
    try:
        return float(str(text))
    except ValueError:
        return None


def _range_fixes(window: dict) -> set[str]:
    # A `GIT` range's fix is a commit hash, not a version anyone can lock.
    if window.get("type") == "GIT":
        return set()
    return {event["fixed"] for event in window.get("events", []) if "fixed" in event}


def _affected_fixes(affected: dict, wanted: str) -> set[str]:
    if _normalise(affected.get("package", {}).get("name", "")) != wanted:
        return set()
    return set().union(*(_range_fixes(window) for window in affected.get("ranges", [])))


def fixed_versions(vulnerabilities: list[dict], ids: set[str], package: str) -> tuple[str, ...]:
    """Every version that fixes one of `ids` for `package`, as the advisories publish them."""
    wanted = _normalise(package)
    fixed = set().union(
        *(
            _affected_fixes(affected, wanted)
            for vuln in vulnerabilities
            if vuln.get("id") in ids
            for affected in vuln.get("affected", [])
        )
    )
    return tuple(sorted(fixed))


def _package_findings(source: str, entry: dict) -> list[Finding]:
    package = entry["package"]
    return [
        Finding(
            source=source,
            package=package["name"],
            version=package.get("version", ""),
            ids=tuple(group["ids"]),
            score=_score(group.get("max_severity", "")),
            fixed=fixed_versions(
                entry.get("vulnerabilities", []), set(group["ids"]), package["name"]
            ),
        )
        for group in entry.get("groups", [])
    ]


def read_report(report: object) -> tuple[int, list[Finding]]:
    """The number of packages scanned and every advisory found. Refuses an unreadable report."""
    scanned = 0
    findings: list[Finding] = []
    for result in _results(report):
        count, found = _result_findings(result)
        scanned += count
        findings.extend(found)
    if scanned == 0:
        raise RefusedReport("the scan read no packages; was --all-packages passed?")
    return scanned, findings


def _results(report: object) -> list:
    if not isinstance(report, dict) or not isinstance(report.get("results"), list):
        raise RefusedReport("not an osv-scanner JSON report: no `results` list")
    return report["results"]


def _result_findings(result: dict) -> tuple[int, list[Finding]]:
    try:
        source = Path(result["source"]["path"]).name
        packages = result["packages"]
        return len(packages), [f for entry in packages for f in _package_findings(source, entry)]
    except (KeyError, TypeError) as error:
        raise RefusedReport(f"malformed osv-scanner report: {error!r}") from error


def render(scanned: int, findings: list[Finding]) -> str:
    """A Markdown summary: counts first, then every finding with blocking ones on top."""
    blocking = [f for f in findings if f.blocking]
    lines = [
        f"{scanned} locked packages scanned; {len(findings)} advisories; "
        f"{len(blocking)} blocking (CVSS >= {THRESHOLD} with a fixed version).",
        "",
    ]
    if findings:
        ordered = sorted(findings, key=lambda f: (not f.blocking, -(f.score or 10.0), f.package))
        lines.append(_HEADER)
        lines.extend(_row(f) for f in ordered)
    return "\n".join(lines)


def _row(finding: Finding) -> str:
    cells = (
        finding.gate,
        finding.package,
        finding.version,
        ", ".join(finding.ids),
        severity_label(finding.score),
        ", ".join(finding.fixed) or "none published",
        finding.source,
    )
    return "| " + " | ".join(cells) + " |"


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: advisory_gate.py <osv-report.json>", file=sys.stderr)
        return REFUSED
    try:
        scanned, findings = read_report(json.loads(Path(argv[0]).read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return REFUSED
    print(render(scanned, findings))
    return BLOCKED if any(f.blocking for f in findings) else PASS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
