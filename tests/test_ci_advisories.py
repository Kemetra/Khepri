"""SCRUM-41: CI fails on an actionable High or Critical advisory, and exceptions expire.

`.github/scripts/advisory_gate.py` reads osv-scanner's report of `uv.lock` and decides what
blocks; `.github/scripts/advisory_exceptions.py` refuses an exception with no reason or no
expiry. The workflow also runs the gate on `.github/advisories/known-vulnerable.uv.lock` and
requires it to block, so a gate that cannot fail is caught in CI, not here.
"""

from __future__ import annotations

import json
import sys
import tomllib
from datetime import date
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".github" / "scripts"
ADVISORIES = ROOT / ".github" / "advisories"
sys.path.insert(0, str(SCRIPTS))

import advisory_exceptions  # noqa: E402
import advisory_gate  # noqa: E402

TODAY = date(2026, 10, 10)


def _advisory(vid: str, package: str, *fixed: str) -> dict:
    events = [{"introduced": "0"}, *({"fixed": f} for f in fixed)]
    return {
        "id": vid,
        "affected": [
            {"package": {"name": package, "ecosystem": "PyPI"}, "ranges": [{"events": events}]}
        ],
    }


def _report(*packages: dict) -> dict:
    return {"results": [{"source": {"path": "/repo/uv.lock"}, "packages": list(packages)}]}


def _package(name: str, version: str, *advisories: tuple[str, str, tuple[str, ...]]) -> dict:
    """`advisories` are (id, max_severity, fixed versions)."""
    return {
        "package": {"name": name, "version": version, "ecosystem": "PyPI"},
        "groups": [{"ids": [vid], "max_severity": score} for vid, score, _ in advisories],
        "vulnerabilities": [_advisory(vid, name, *fixed) for vid, _, fixed in advisories],
    }


def _gate(report: dict) -> list[advisory_gate.Finding]:
    _, findings = advisory_gate.read_report(report)
    return findings


# --- what blocks -------------------------------------------------------------------------------


@pytest.mark.parametrize("score", ["7.0", "8.2", "9.1"])
def test_a_high_or_critical_advisory_with_a_fix_blocks(score: str) -> None:
    (finding,) = _gate(_report(_package("pyjwt", "2.13.0", ("GHSA-a", score, ("2.14.0",)))))

    assert finding.blocking
    assert finding.fixed == ("2.14.0",)


def test_a_medium_advisory_with_a_fix_is_reported_not_gated() -> None:
    (finding,) = _gate(_report(_package("mako", "1.3.12", ("GHSA-m", "6.9", ("1.4.2",)))))

    assert not finding.blocking
    assert finding.gate == "reported: below High"


def test_a_high_advisory_with_no_fix_is_reported_not_gated() -> None:
    """Nothing can be done about it yet, so it must stay visible without blocking every PR."""
    (finding,) = _gate(_report(_package("pyjwt", "2.13.0", ("GHSA-n", "8.0", ()))))

    assert not finding.blocking
    assert finding.gate == "reported: no fix"


def test_an_unscored_advisory_with_a_fix_blocks() -> None:
    """Fail closed: no score is not a low score."""
    (finding,) = _gate(_report(_package("x", "1.0", ("PYSEC-u", "", ("1.1",)))))

    assert finding.score is None
    assert finding.blocking


def test_a_fix_published_for_another_package_is_not_this_ones() -> None:
    report = _report(_package("httpx2", "2.9.1", ("GHSA-h", "8.1", ("2.10.0",))))
    vuln = report["results"][0]["packages"][0]["vulnerabilities"][0]
    vuln["affected"][0]["package"]["name"] = "httpcore2"

    (finding,) = _gate(report)

    assert finding.fixed == ()
    assert not finding.blocking


def test_package_names_match_however_they_are_spelled() -> None:
    report = _report(_package("Py_JWT", "2.13.0", ("GHSA-s", "7.4", ("2.14.0",))))
    report["results"][0]["packages"][0]["vulnerabilities"][0]["affected"][0]["package"]["name"] = (
        "py-jwt"
    )

    (finding,) = _gate(report)

    assert finding.blocking


def test_a_commit_hash_is_not_a_fixed_version() -> None:
    """An advisory fixed only in a `GIT` range has no version to lock, so it is not actionable."""
    report = _report(_package("urllib3", "1.26.4", ("GHSA-g", "8.1", ("1.26.17",))))
    affected = report["results"][0]["packages"][0]["vulnerabilities"][0]["affected"][0]
    affected["ranges"][0]["type"] = "ECOSYSTEM"
    affected["ranges"].append({"type": "GIT", "events": [{"introduced": "0"}, {"fixed": "0122"}]})

    (finding,) = _gate(report)
    assert finding.fixed == ("1.26.17",)

    affected["ranges"].pop(0)
    (finding,) = _gate(report)
    assert finding.fixed == ()
    assert not finding.blocking


# --- refusing a report that proves nothing -----------------------------------------------------


def test_a_report_that_scanned_no_packages_is_refused() -> None:
    with pytest.raises(advisory_gate.RefusedReport, match="no packages"):
        advisory_gate.read_report({"results": []})


@pytest.mark.parametrize(
    "report",
    [None, [], {}, {"results": [{"packages": []}]}, {"results": [{"source": {}, "packages": 1}]}],
)
def test_a_malformed_report_is_refused(report: object) -> None:
    with pytest.raises(advisory_gate.RefusedReport):
        advisory_gate.read_report(report)


# --- what the job prints and returns -----------------------------------------------------------


def test_the_table_names_package_advisory_severity_and_fix() -> None:
    clean = _package("alembic", "1.16.4")
    risky = _package("urllib3", "2.7.0", ("GHSA-u", "8.9", ("2.8.0",)))
    scanned, findings = advisory_gate.read_report(_report(clean, risky))

    text = advisory_gate.render(scanned, findings)

    assert "2 locked packages scanned; 1 advisories; 1 blocking" in text
    assert "| **BLOCKING** | urllib3 | 2.7.0 | GHSA-u | 8.9 HIGH | 2.8.0 | uv.lock |" in text


@pytest.mark.parametrize(
    ("advisory", "expected"),
    [
        (None, advisory_gate.PASS),
        (("GHSA-m", "5.0", ("2.0",)), advisory_gate.PASS),
        (("GHSA-h", "7.5", ("2.0",)), advisory_gate.BLOCKED),
    ],
)
def test_main_exits_by_what_blocks(tmp_path: Path, advisory: tuple | None, expected: int) -> None:
    package = _package("p", "1.0", advisory) if advisory else _package("p", "1.0")
    path = tmp_path / "osv.json"
    path.write_text(json.dumps(_report(package)), encoding="utf-8")

    assert advisory_gate.main([str(path)]) == expected


def test_main_refuses_an_unreadable_report(tmp_path: Path) -> None:
    path = tmp_path / "osv.json"
    path.write_text("not json", encoding="utf-8")

    assert advisory_gate.main([str(path)]) == advisory_gate.REFUSED
    assert advisory_gate.main([str(tmp_path / "missing.json")]) == advisory_gate.REFUSED


def test_the_canary_is_not_named_like_a_lockfile() -> None:
    """A file called `uv.lock` would be picked up as Khepri's own by any lockfile scanner."""
    canary = ADVISORIES / "known-vulnerable.uv.lock"
    lock = tomllib.loads(canary.read_text(encoding="utf-8"))

    assert canary.name != "uv.lock"
    assert {p["name"]: p["version"] for p in lock["package"]}["urllib3"] == "1.26.4"


# --- exceptions --------------------------------------------------------------------------------


def _osv(**entry: object) -> list[str]:
    return advisory_exceptions.osv_errors({"IgnoredVulns": [entry]}, today=TODAY)


def _trivy(**entry: object) -> list[str]:
    return advisory_exceptions.trivy_errors({"vulnerabilities": [entry]}, today=TODAY)


def test_a_reasoned_expiring_exception_is_accepted() -> None:
    assert (
        _osv(id="GHSA-a", reason="not reachable: HMAC unused", ignoreUntil=date(2026, 12, 1)) == []
    )
    assert _trivy(id="CVE-1", statement="no fix in noble yet", expired_at=date(2026, 12, 1)) == []


@pytest.mark.parametrize(
    ("entry", "complaint"),
    [
        ({"id": "GHSA-a", "ignoreUntil": date(2026, 12, 1)}, "no `reason`"),
        ({"id": "GHSA-a", "reason": "  ", "ignoreUntil": date(2026, 12, 1)}, "no `reason`"),
        ({"id": "GHSA-a", "reason": "r"}, "cannot be permanent"),
        ({"id": "GHSA-a", "reason": "r", "ignoreUntil": "someday"}, "cannot be permanent"),
        ({"id": "GHSA-a", "reason": "r", "ignoreUntil": date(2027, 1, 9)}, "more than 90 days"),
        ({"reason": "r", "ignoreUntil": date(2026, 12, 1)}, "no `id`"),
    ],
)
def test_an_unexplained_or_permanent_osv_exception_is_refused(entry: dict, complaint: str) -> None:
    errors = _osv(**entry)

    assert any(complaint in e for e in errors), errors


def test_ninety_days_is_the_last_acceptable_expiry() -> None:
    assert _osv(id="G", reason="r", ignoreUntil=date(2027, 1, 8)) == []
    assert _osv(id="G", reason="r", ignoreUntil=date(2027, 1, 9)) != []


def test_a_trivy_exception_without_a_statement_or_expiry_is_refused() -> None:
    errors = _trivy(id="CVE-1")

    assert any("no `statement`" in e for e in errors)
    assert any("`expired_at` must be a date" in e for e in errors)


def test_trivy_may_except_only_vulnerabilities() -> None:
    errors = advisory_exceptions.trivy_errors({"secrets": [{"id": "aws"}]}, today=TODAY)

    assert errors and "only `vulnerabilities`" in errors[0]


_GOOD = {"id": "G", "reason": "r", "ignoreUntil": date(2026, 12, 1)}


@pytest.mark.parametrize(
    "config",
    [
        # osv-scanner honours these, and an override with no `effectiveUntil` is permanent.
        {"PackageOverrides": [{"name": "pyjwt", "ecosystem": "PyPI", "ignore": True}]},
        {"PackageOverrides": [{"name": "pyjwt", "vulnerability": {"ignore": True}}]},
        # osv-scanner's TOML decoder matches keys case-insensitively, so this is honoured too.
        {"ignoredvulns": [{"id": "GHSA-a"}]},
        {"IgnoredVulns": [_GOOD], "ignoredVulns": [{"id": "GHSA-b"}]},
    ],
)
def test_an_osv_section_other_than_exactly_ignoredvulns_is_refused(config: dict) -> None:
    errors = advisory_exceptions.osv_errors(config, today=TODAY)

    assert any("only `IgnoredVulns`" in e for e in errors), errors


@pytest.mark.parametrize("extra", ["Reason", "ignoreuntil", "effectiveUntil", "ignore"])
def test_an_osv_exception_field_outside_the_known_three_is_refused(extra: str) -> None:
    """A miscased or foreign field may be read by osv-scanner but never by this check."""
    errors = _osv(**_GOOD, **{extra: "x"})

    assert any(f"unknown field `{extra}`" in e for e in errors), errors


def test_the_committed_exception_files_are_valid() -> None:
    osv = tomllib.loads((ADVISORIES / "osv-scanner.toml").read_text(encoding="utf-8"))
    trivy = yaml.safe_load((ADVISORIES / "trivyignore.yaml").read_text(encoding="utf-8"))

    assert advisory_exceptions.osv_errors(osv, today=date.today()) == []
    assert advisory_exceptions.trivy_errors(trivy, today=date.today()) == []


def test_the_exceptions_main_fails_on_a_bad_entry(tmp_path: Path) -> None:
    osv = tmp_path / "osv-scanner.toml"
    osv.write_text('[[IgnoredVulns]]\nid = "GHSA-a"\n', encoding="utf-8")
    trivy = tmp_path / "trivyignore.yaml"
    trivy.write_text("vulnerabilities: []\n", encoding="utf-8")

    assert advisory_exceptions.main([str(osv), str(trivy)]) == 1
    osv.write_text("", encoding="utf-8")
    assert advisory_exceptions.main([str(osv), str(trivy)]) == 0
