"""SCRUM-40: the resolved lock stays past the audited advisories and on SQLAlchemy 2.0.

The dependency audit (`docs/audit/2026-10-03-critical-dependency-exit-path-audit.md`, rows 3, 9
and 18) found PyJWT 2.13.0 and urllib3 2.7.0 carrying published advisories, fixed in 2.15.0 and
2.8.0, and a `sqlalchemy<3` range that admits 2.1 on any re-lock. These tests read the lockfile and
the manifest themselves, anchored to this file rather than the working directory, so the image's
`uv sync --frozen` input is what is checked -- not whatever happens to be installed.

A later osv-scanner pass over `uv.lock` found the dev group behind published advisories as well:
pypdf 6.14.2 (fixed by 6.19.0), httpx2 2.9.1 (fixed across 2.10.0-2.12.0) and httpcore2 2.9.1
(fixed in 2.10.0). Their floors sit in the same table.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

_ROOT = Path(__file__).resolve().parents[1]

# The first release that fixes every advisory found, and the release that was locked at the time.
_FLOORS = {
    "httpcore2": (Version("2.10.0"), Version("2.9.1")),
    "httpx2": (Version("2.12.0"), Version("2.9.1")),
    "pyjwt": (Version("2.15.0"), Version("2.13.0")),
    "pypdf": (Version("6.19.0"), Version("6.14.2")),
    "urllib3": (Version("2.8.0"), Version("2.7.0")),
}


def _locked_version(name: str) -> Version:
    lock = tomllib.loads((_ROOT / "uv.lock").read_text(encoding="utf-8"))
    versions = [package["version"] for package in lock["package"] if package["name"] == name]
    assert len(versions) == 1, f"expected exactly one locked {name}, found {versions}"
    return Version(versions[0])


def _declared_requirement(name: str) -> Requirement:
    manifest = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = [Requirement(line) for line in manifest["project"]["dependencies"]]
    matches = [requirement for requirement in requirements if requirement.name == name]
    assert len(matches) == 1, f"expected exactly one declared {name}, found {matches}"
    return matches[0]


@pytest.mark.parametrize("name", sorted(_FLOORS))
def test_the_lock_resolves_past_the_audited_advisories(name: str) -> None:
    floor, audited = _FLOORS[name]
    assert audited < floor, "the audited release must be one the floor refuses"
    assert _locked_version(name) >= floor


def test_sqlalchemy_is_locked_on_the_2_0_series() -> None:
    assert _locked_version("sqlalchemy").release[:2] == (2, 0)


def test_the_manifest_refuses_sqlalchemy_2_1() -> None:
    specifier = _declared_requirement("sqlalchemy").specifier
    assert not specifier.contains(Version("2.1.0"))
    assert specifier.contains(_locked_version("sqlalchemy"))
