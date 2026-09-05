"""`W1-05` (first PR) -- Overview and the Data surface (`RCA-005` `FR-120`, `FR-121`, `FR-122`).

**The line this slice draws, stated before building, as the `G3-04` plan asks.** `FR-120` forbids
a KPI, chart or business figure on Overview, and the plan names the risk: a "summary number" that
is really a count of retained rows. This slice puts *every* number on the wrong side of that line.
Overview renders one row for the latest analysis, one row for the latest data, one row per item
needing attention, and a retention notice -- and no count of anything, not even "3 analyses". The
only digits on the surface are inside `<time>` elements. `test_overview_carries_no_figure` asserts
that literally: the body with its `<time>` elements removed contains no digit.

**Templates present; they do not compute.** The plan's acceptance is "a scan proves no template
computes, rounds or sums". Every row is shaped in Python from the records the reader returned, in
the reader's order, and the template iterates. `test_no_shell_template_computes` reads every
expression in every shell template and refuses arithmetic and the aggregating filters.

**A link ships with its surface.** `FR-121` and `RCA-002` `FR-049`. The Overview and Data links
appear only when a reader is wired, and the two surfaces answer `unavailable` when it is not, so a
shell configured without the workspace has no half-built destination. The Analyses link is the
next PR's and is asserted absent here.

**No surface may say content expires on its own.** `KHEPRI-DEC-033` §5: until `W1-07` ships the
sweep, no surface may tell a customer that content expires automatically. The retention notice is
asserted against that, in both languages, on the copy itself.

**Customer vocabulary.** Blueprint §7.2: rows do not lead with digests, mapping versions or
internal identifiers, and `DatasetVersion` does not appear on screen. Here none of them appears at
all -- contextual evidence is `W1-06`'s -- and the words are *data*, not *dataset version*.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from html import unescape
from importlib.resources import files

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.errors import SCOPE_FAILURE, ScopeAccessDenied
from khepri.rca.organizations import Organization
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rca.workspace.contracts import (
    RUN_COMPLETED,
    RUN_FAILED,
    RUN_STARTED,
    AdmittedSource,
    AnalysisRun,
    DatasetVersion,
    RunOutcome,
    RunSubject,
    VersionLifecycle,
)
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes
from khepri.runtime.shell_copy import SHELL_COPY
from khepri.runtime.shell_workspace import moment

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
EARLIER = datetime(2026, 9, 4, 9, 30, tzinfo=UTC)
EARLIEST = datetime(2026, 9, 3, 8, 0, tzinfo=UTC)

#: Identifiers carry no digits, so a digit anywhere outside a `<time>` element is a figure the
#: surface rendered and not an identifier it echoed.
ORGANIZATION = "org-acme"
OTHER_ORGANIZATION = "org-other"
#: What the isolation door returns for the session's organization. Distinct from the organization
#: identifier on purpose: the store is keyed by this and not by that (`FR-031`), which is the
#: defect review on `#373` found.
SCOPE = "scope-acme"
DIGEST = "d" * 64
MAPPING_VERSION = "mapping-v-alpha"


@dataclass
class _Context:
    account_id: str
    organization_id: str | None
    role: str | None = "owner"

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"


class _StubResolver:
    def __init__(self, context: _Context) -> None:
        self._context = context

    def for_request(self, token: str, *, organization_id: str | None, now: object) -> _Context:
        return self._context

    def require_owner(self, token: str, *, organization_id: str, now: object) -> _Context:
        return self._context


class _StubOrganizations:
    def organizations_for_account(self, account_id: str) -> list[Organization]:
        return [
            Organization._from_storage(organization_id=ORGANIZATION, name="Acme", created_at=NOW)
        ]

    def memberships_for_organization(self, organization_id: str) -> list[object]:
        return []


@dataclass
class _StubIsolation:
    """The one scope door, recording what it was asked and answering one scope for one pair."""

    asked: list[tuple[str, str]] = field(default_factory=list)
    refuse: bool = False

    def resolve_scope(self, account_id: str, organization_id: str) -> str:
        self.asked.append((account_id, organization_id))
        if self.refuse:
            raise ScopeAccessDenied(SCOPE_FAILURE)
        return SCOPE if organization_id == ORGANIZATION else f"scope-{organization_id}"


class _StubBridge:
    def open(self, *, account_id: str, organization_id: str, now: object) -> object:
        raise AssertionError("the surface cases drive GETs only")  # pragma: no cover


@dataclass
class _StubRecords:
    """A reader that returns what it was given and records which scope it was asked about."""

    versions: tuple[DatasetVersion, ...] = ()
    runs: tuple[AnalysisRun, ...] = ()
    asked: list[str] = field(default_factory=list)

    def dataset_versions_for_scope(self, owner_id: str) -> tuple[DatasetVersion, ...]:
        self.asked.append(owner_id)
        return self.versions

    def analysis_runs_for_scope(self, owner_id: str) -> tuple[AnalysisRun, ...]:
        self.asked.append(owner_id)
        return self.runs


def _version(
    version_id: str, *, created_at: datetime, sealed_at: datetime | None = None
) -> DatasetVersion:
    return DatasetVersion._from_storage(
        version_id=version_id,
        owner_id=ORGANIZATION,
        source=AdmittedSource(
            plaintext_digest=DIGEST,
            ciphertext_digest=DIGEST,
            size_bytes=4096,
            media_type="text/csv",
            manifest_digest=DIGEST,
            mapping_version=MAPPING_VERSION,
            admission_outcome="admitted",
        ),
        lifecycle=VersionLifecycle(created_at=created_at, sealed_at=sealed_at),
    )


def _run(run_id: str, version_id: str, *, state: str, started_at: datetime) -> AnalysisRun:
    outcome = (
        RunOutcome(
            state=state,
            package_digest=DIGEST,
            package_version="package-v-alpha",
            formula_version="formula-v-alpha",
            completed_at=started_at,
        )
        if state == RUN_COMPLETED
        else RunOutcome(state=state)
    )
    return AnalysisRun._from_storage(
        subject=RunSubject(run_id=run_id, owner_id=ORGANIZATION, version_id=version_id),
        outcome=outcome,
        started_at=started_at,
    )


def _shell(
    records: _StubRecords | None,
    *,
    bridge: bool = False,
    context: _Context | None = None,
    isolation: _StubIsolation | None | str = "default",
) -> TestClient:
    """`isolation` defaults to a stub whenever a reader is given, so the ordinary case is the
    fully wired one; pass `None` to build a shell with a reader and no scope door."""
    if isolation == "default":
        isolation = _StubIsolation() if records is not None else None
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=_StubResolver(context or _Context("acct-a", ORGANIZATION)),
            organizations=_StubOrganizations(),
            bridge=_StubBridge() if bridge else None,
            records=records,
            isolation=isolation,
        ),
        clock=lambda: NOW,
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


def _nav(html: str) -> str:
    """The frame's destination landmark and nothing else, so an assertion about the navigation
    is not satisfied by a link in the body."""
    start = html.index('class="frame-surfaces"')
    return html[start : html.index("</nav>", start)]


def _body(html: str) -> str:
    return html.split("<body", 1)[1]


def _link(language: str, surface: str) -> str:
    return f'href="{SHELL_PREFIX}/{language}/{ORGANIZATION}/{surface}"'


# --- navigation: a link ships with its surface ---------------------------------------------


class TestTheLinkShipsWithItsSurface:
    """`FR-121`, `FR-049`."""

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_frame_offers_overview_data_and_team_in_that_order(self, language: str) -> None:
        nav = _nav(
            _shell(_StubRecords()).get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/team").text
        )

        positions = [
            nav.index(_link(language, surface)) for surface in ("overview", "data", "team")
        ]
        assert positions == sorted(positions)
        assert _link(language, "analyses") not in nav

    def test_the_labels_are_the_reconciled_set(self) -> None:
        """Design language §3.5: Overview · Data · Analyses · Team, and `DatasetVersion` never."""
        for language in ("en", "ar"):
            nav = _nav(
                _shell(_StubRecords()).get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/team").text
            )

            assert SHELL_COPY[language]["overview_title"] in nav
            assert SHELL_COPY[language]["data_title"] in nav
            assert SHELL_COPY[language]["team_title"] in nav
            assert "dataset" not in nav.lower()

    def test_without_a_reader_the_links_are_absent_and_the_surfaces_unavailable(self) -> None:
        shell = _shell(None)

        nav = _nav(shell.get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/team").text)
        assert _link("en", "overview") not in nav
        assert _link("en", "data") not in nav
        assert _link("en", "team") in nav
        for surface in ("overview", "data"):
            response = shell.get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/{surface}")
            assert response.status_code == 404
            assert SHELL_COPY["en"]["unavailable_title"] in response.text

    def test_the_landmark_is_named_for_what_it_is(self) -> None:
        """The `nav` was labelled `Team` when Team was its only entry; with three it is not."""
        for language in ("en", "ar"):
            nav = _nav(
                _shell(_StubRecords()).get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/team").text
            )

            assert f'aria-label="{SHELL_COPY[language]["frame_surfaces_label"]}"' in nav
            assert f'aria-label="{SHELL_COPY[language]["team_title"]}"' not in nav

    @pytest.mark.parametrize("surface", ["overview", "data", "team"])
    def test_the_current_surface_is_marked(self, surface: str) -> None:
        nav = _nav(_shell(_StubRecords()).get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/{surface}").text)

        current = re.findall(r'<a href="([^"]+)"[^>]*aria-current="page"', nav)
        assert current == [f"{SHELL_PREFIX}/en/{ORGANIZATION}/{surface}"]

    def test_the_chooser_row_leads_to_overview(self) -> None:
        """Blueprint §7.1: Overview is the orientation surface, so it is where an organization
        opens. Without a reader the row keeps leading to Team, the one surface that exists."""
        with_reader = _shell(_StubRecords()).get(f"{SHELL_PREFIX}/en/").text
        without = _shell(None).get(f"{SHELL_PREFIX}/en/").text

        assert _link("en", "overview") in with_reader
        assert _link("en", "team") not in with_reader
        assert _link("en", "team") in without

    @pytest.mark.parametrize("language", ["en", "ar"])
    @pytest.mark.parametrize("surface", ["overview", "data"])
    def test_the_language_control_keeps_the_surface(self, surface: str, language: str) -> None:
        """`FR-047` scenario 11, extended to the two new surfaces."""
        alternate = "ar" if language == "en" else "en"
        html = (
            _shell(_StubRecords()).get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/{surface}").text
        )

        assert f'href="{SHELL_PREFIX}/{alternate}/{ORGANIZATION}/{surface}"' in html


# --- overview --------------------------------------------------------------------------------


def _worked_scope() -> _StubRecords:
    """Two data versions and three runs, newest first, as the store returns them."""
    return _StubRecords(
        versions=(
            _version("ver-b", created_at=EARLIER, sealed_at=NOW),
            _version("ver-a", created_at=EARLIEST, sealed_at=EARLIER),
        ),
        runs=(
            _run("run-c", "ver-b", state=RUN_STARTED, started_at=NOW),
            _run("run-b", "ver-b", state=RUN_FAILED, started_at=EARLIER),
            _run("run-a", "ver-a", state=RUN_COMPLETED, started_at=EARLIEST),
        ),
    )


class TestOverview:
    """`FR-120`: latest work, data state, items needing attention; no KPI, chart or figure."""

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_it_shows_the_latest_analysis_once(self, language: str) -> None:
        html = (
            _shell(_worked_scope()).get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/overview").text
        )

        assert html.count('class="latest-work"') == 1
        assert SHELL_COPY[language]["run_state_started"] in html
        assert SHELL_COPY[language]["run_state_completed"] not in html

    def test_the_latest_analysis_is_the_first_the_reader_returned(self) -> None:
        """The template does not re-order: the store already returns newest first (`FR-117`)."""
        records = _worked_scope()
        reversed_records = _StubRecords(versions=records.versions, runs=records.runs[::-1])

        html = _shell(reversed_records).get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/overview").text

        assert SHELL_COPY["en"]["run_state_completed"] in html
        assert SHELL_COPY["en"]["run_state_started"] not in html

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_it_shows_the_latest_data_state(self, language: str) -> None:
        html = (
            _shell(_worked_scope()).get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/overview").text
        )

        assert html.count('class="latest-data"') == 1
        assert SHELL_COPY[language]["data_admitted"] in html
        assert SHELL_COPY[language]["data_in_use"] in html

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_an_empty_scope_says_so_rather_than_rendering_nothing(self, language: str) -> None:
        html = _shell(_StubRecords()).get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/overview").text

        assert SHELL_COPY[language]["overview_no_work"] in html
        assert SHELL_COPY[language]["overview_no_data"] in html
        assert 'class="latest-work"' not in html

    def test_attention_is_rendered_only_when_something_needs_it(self) -> None:
        """Blueprint §7.1: an always-present "no issues" panel is decoration, not reassurance."""
        quiet = _StubRecords(
            versions=_worked_scope().versions,
            runs=(_run("run-a", "ver-a", state=RUN_COMPLETED, started_at=EARLIEST),),
        )

        loud = _shell(_worked_scope()).get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/overview").text
        calm = _shell(quiet).get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/overview").text

        assert SHELL_COPY["en"]["attention_title"] in loud
        assert loud.count('class="attention-item"') == 1
        assert SHELL_COPY["en"]["attention_title"] not in calm
        assert "attention-item" not in calm

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_overview_carries_no_figure(self, language: str) -> None:
        """`FR-120`, `M3-U5`. The visible text with its `<time>` elements removed has no digit at
        all: no count, no percentage, no total. Nothing drawn either."""
        html = (
            _shell(_worked_scope()).get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/overview").text
        )
        body = re.sub(r"<time\b[^>]*>.*?</time>", "", _body(html), flags=re.DOTALL)
        text = unescape(re.sub(r"<[^>]+>", "", body))

        assert re.search(r"\d", text) is None, text
        assert "<canvas" not in body and "<svg" not in body and "<table" not in body
        assert "%" not in text

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_retention_notice_makes_no_expiry_claim(self, language: str) -> None:
        """`KHEPRI-DEC-033` §5: no surface may say content expires automatically until `W1-07`."""
        html = (
            _shell(_worked_scope()).get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/overview").text
        )
        notice = SHELL_COPY[language]["retention_notice"]

        assert notice in html
        for forbidden in ("expire", "automatic", "تنتهي", "تلقائي", "ينتهي"):
            assert forbidden not in notice.lower(), forbidden

    def test_the_one_action_is_offered_where_it_can_succeed(self) -> None:
        """One dominant action, `New analysis`, posting to `R8-06`'s route -- and only when a
        bridge is wired, because a form whose every submission is refused reads as a fault."""
        action = f'action="{SHELL_PREFIX}/en/{ORGANIZATION}/analyses"'

        with_bridge = (
            _shell(_worked_scope(), bridge=True)
            .get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/overview")
            .text
        )
        without = _shell(_worked_scope()).get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/overview").text

        assert with_bridge.count(action) == 1
        assert SHELL_COPY["en"]["new_analysis"] in with_bridge
        assert action not in without


# --- data -------------------------------------------------------------------------------------


class TestData:
    """Blueprint §7.2 with `FR-117`'s row vocabulary and `FR-122`."""

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_every_version_is_a_row_in_the_readers_order(self, language: str) -> None:
        html = _shell(_worked_scope()).get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/data").text

        assert html.count('class="data-item"') == 2
        first = html.index('datetime="2026-09-04')
        second = html.index('datetime="2026-09-03')
        assert first < second

    def test_the_template_does_not_reorder_what_it_was_given(self) -> None:
        records = _worked_scope()
        reversed_records = _StubRecords(versions=records.versions[::-1], runs=records.runs)

        html = _shell(reversed_records).get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/data").text

        assert html.index('datetime="2026-09-03') < html.index('datetime="2026-09-04')

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_a_row_states_what_the_blueprint_asks(self, language: str) -> None:
        """When submitted, whether admitted, whether in use, its retention state, in words."""
        records = _StubRecords(
            versions=(
                _version("ver-b", created_at=EARLIER),
                _version("ver-a", created_at=EARLIEST, sealed_at=EARLIER),
            )
        )
        html = _shell(records).get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/data").text
        copy = SHELL_COPY[language]

        assert copy["data_admitted"] in html
        assert copy["data_awaiting"] in html
        assert copy["data_in_use"] in html
        assert copy["retention_kept"] in html
        assert "text/csv" in html

    @pytest.mark.parametrize("language", ["en", "ar"])
    @pytest.mark.parametrize("state", [RUN_STARTED, RUN_FAILED])
    def test_an_unsealed_version_with_a_run_says_the_analysis_started(
        self, state: str, language: str
    ) -> None:
        """Sealing happens on the first completion, so a version whose only run started or failed
        is unsealed while that run is listed beneath it. "Awaiting its first analysis" over a row
        that says "Processing" was the contradiction review on `#373` found."""
        records = _StubRecords(
            versions=(_version("ver-b", created_at=EARLIER),),
            runs=(_run("run-c", "ver-b", state=state, started_at=NOW),),
        )
        copy = SHELL_COPY[language]

        data = _shell(records).get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/data").text
        overview = _shell(records).get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/overview").text

        for html in (data, overview):
            assert copy["data_analysis_started"] in html
            assert copy["data_awaiting"] not in html
            assert copy["data_in_use"] not in html

    def test_no_row_leads_with_an_internal_identifier(self) -> None:
        """§7.2: digests, mapping versions and contract identifiers belong to audit detail, which
        is `W1-06`'s. Here they do not appear at all, and neither does the domain term."""
        html = _shell(_worked_scope()).get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/data").text

        assert DIGEST not in html
        assert MAPPING_VERSION not in html
        assert "package-v-alpha" not in html
        assert "ver-a" not in html and "run-a" not in html
        assert "dataset" not in html.lower()

    def test_the_analyses_that_used_a_version_sit_under_it(self) -> None:
        """Grouping happens in Python from `version_id`, and the template never filters."""
        html = _shell(_worked_scope()).get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/data").text
        rows = html.split('<li class="data-item"')[1:]

        assert len(rows) == 2
        newer, older = rows
        assert newer.count('class="data-use"') == 2
        assert older.count('class="data-use"') == 1
        assert SHELL_COPY["en"]["run_state_completed"] in older
        assert SHELL_COPY["en"]["run_state_completed"] not in newer

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_an_empty_scope_says_so(self, language: str) -> None:
        html = _shell(_StubRecords()).get(f"{SHELL_PREFIX}/{language}/{ORGANIZATION}/data").text

        assert SHELL_COPY[language]["data_empty"] in html
        assert "data-item" not in html

    def test_a_time_is_machine_readable_and_isolated(self) -> None:
        """`FR-122`/`FR-055`: a timestamp is a Latin run; inside Arabic prose it carries `ltr`."""
        html = _shell(_worked_scope()).get(f"{SHELL_PREFIX}/ar/{ORGANIZATION}/data").text

        assert re.search(r'<time datetime="2026-09-04T09:30:00\+00:00"[^>]*dir="ltr"', html)


# --- scope ------------------------------------------------------------------------------------


class TestScopeComesFromTheSession:
    """`RCA-002` `FR-042`: the address names a surface and a language, never the scope."""

    @pytest.mark.parametrize("surface", ["overview", "data"])
    def test_the_reader_is_asked_about_the_sessions_scope(self, surface: str) -> None:
        """The store is keyed by the opaque scope. It is asked about the scope the isolation door
        returned for the *session's* account and organization -- never the organization
        identifier itself, and never the one in the address."""
        records = _StubRecords()
        isolation = _StubIsolation()

        _shell(records, isolation=isolation).get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/{surface}")

        assert isolation.asked == [("acct-a", ORGANIZATION)]
        assert records.asked, "the reader was never consulted"
        assert set(records.asked) == {SCOPE}
        assert ORGANIZATION not in records.asked

    @pytest.mark.parametrize("surface", ["overview", "data"])
    def test_an_address_naming_another_organization_fails_closed(self, surface: str) -> None:
        """`FR-042` scenario 3. The reader and the scope door are never consulted: a disagreement
        is refused before any read, so nothing about the session's organization is rendered under
        another's address (`#373` review)."""
        records = _worked_scope()
        isolation = _StubIsolation()

        response = _shell(records, isolation=isolation).get(
            f"{SHELL_PREFIX}/en/{OTHER_ORGANIZATION}/{surface}"
        )

        assert response.status_code == 404
        assert SHELL_COPY["en"]["unavailable_title"] in response.text
        assert records.asked == [] and isolation.asked == []

    @pytest.mark.parametrize("tail", ["/extra", "/no-such-object", "/x/y", "//", "///", "/extra/"])
    @pytest.mark.parametrize("surface", ["overview", "data"])
    def test_a_surface_is_an_exact_address(self, surface: str, tail: str) -> None:
        """`FR-046`: `/data/no-such-object` is an unknown path, not the Data surface (`#373`
        review). The trailing slash is the one tolerated tail, as on the chooser."""
        shell = _shell(_worked_scope())

        assert shell.get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/{surface}{tail}").status_code == 404
        assert shell.get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/{surface}/").status_code == 200

    @pytest.mark.parametrize("surface", ["overview", "data"])
    def test_a_refused_scope_reaches_the_uniform_refusal(self, surface: str) -> None:
        """`FR-050`: the isolation door refusing -- a disabled account, a membership gone since
        the session resolved -- is one more collapsed cause, not a 500 and not an empty page."""
        shell = _shell(_worked_scope(), isolation=_StubIsolation(refuse=True))

        response = shell.get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/{surface}")

        assert response.status_code == 404
        assert SHELL_COPY["en"]["unavailable_title"] in response.text
        assert SHELL_COPY["en"]["run_state_started"] not in response.text

    def test_a_reader_without_a_scope_door_offers_nothing(self) -> None:
        """Half a wiring is no wiring (`FR-049`): a reader with no way to resolve the scope could
        only be asked the wrong question, so the surfaces and their links are absent."""
        shell = _shell(_worked_scope(), isolation=None)

        nav = _nav(shell.get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/team").text)
        assert _link("en", "overview") not in nav and _link("en", "data") not in nav
        assert shell.get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/overview").status_code == 404

    @pytest.mark.parametrize("surface", ["overview", "data"])
    def test_a_session_with_no_active_organization_reaches_the_refusal(self, surface: str) -> None:
        shell = _shell(_StubRecords(), context=_Context("acct-a", None))

        response = shell.get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/{surface}")

        assert response.status_code == 404

    @pytest.mark.parametrize("outcome", ["refused", "ADMITTED", "admitted "])
    def test_an_unknown_admission_outcome_refuses_the_surface(self, outcome: str) -> None:
        """The column accepts any string and `W1-04` only ever writes the admitting code, so any
        other value is a corrupt or foreign row. It is not read as "Not admitted" -- a word the
        record did not say (review on `#373`) -- and not as a blank: the surface refuses, the way
        `RRA-012` `FR-094` has a component refuse a code it cannot word."""
        odd = DatasetVersion._from_storage(
            version_id="ver-r",
            owner_id=ORGANIZATION,
            source=AdmittedSource(
                plaintext_digest=DIGEST,
                ciphertext_digest=DIGEST,
                size_bytes=4096,
                media_type="application/vnd.ms-excel",
                manifest_digest=DIGEST,
                mapping_version=MAPPING_VERSION,
                admission_outcome=outcome,
            ),
            lifecycle=VersionLifecycle(created_at=EARLIER),
        )
        shell = _shell(_StubRecords(versions=(odd,)))

        for surface in ("data", "overview"):
            response = shell.get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/{surface}")

            assert response.status_code == 404, surface
            assert SHELL_COPY["en"]["unavailable_title"] in response.text
            assert "application/vnd.ms-excel" not in response.text
            assert "admitted" not in response.text.lower()


class TestTheWorkspaceSheetLivesInTheRuntime:
    """`RCA-005` names `src/khepri/rra/journey/` as not in its scope, so `W1-05`'s rules may not
    live in the shell stylesheets that `R8-01`/`R8-07` placed there (review on `#373`)."""

    def test_the_sheet_is_served_by_the_shell_and_linked_by_the_frame(self) -> None:
        shell = _shell(_StubRecords())

        sheet = shell.get(f"{SHELL_PREFIX}/assets/workspace.css")
        html = shell.get(f"{SHELL_PREFIX}/en/{ORGANIZATION}/overview").text

        assert sheet.status_code == 200
        assert sheet.headers["content-type"].startswith("text/css")
        assert ".data-item" in sheet.text and ".retention-notice" in sheet.text
        assert f'href="{SHELL_PREFIX}/assets/workspace.css"' in html

    def test_the_journeys_tree_carries_none_of_this_slices_rules(self) -> None:
        components = (
            files("khepri.rra.journey")
            .joinpath("assets", "shell-components.css")
            .read_text(encoding="utf-8")
        )

        for selector in (".data-", ".region-label", ".latest-", ".attention-", ".retention-"):
            assert selector not in components, selector

    def test_the_sheet_keeps_the_component_layers_discipline(self) -> None:
        """No colour of its own, no external reference, logical properties only."""
        sheet = files("khepri.runtime").joinpath("shell_assets", "workspace.css").read_text("utf-8")
        rules = re.sub(r"/\*.*?\*/", "", sheet, flags=re.DOTALL)

        assert "@import" not in rules and "url(" not in rules
        assert re.search(r"#[0-9a-fA-F]{3,8}\b|rgb\(|hsl\(", rules) is None
        for physical in (
            "margin-left",
            "margin-right",
            "padding-left",
            "padding-right",
            "left:",
            "right:",
        ):
            assert physical not in rules, physical


class TestMoments:
    """A stored instant is stated in UTC whatever offset it arrived with, and a naive value is
    read as UTC rather than guessed to be local."""

    def test_an_offset_instant_is_restated_in_utc(self) -> None:
        cairo = datetime(2026, 9, 4, 12, 30, tzinfo=timezone(timedelta(hours=3)))

        stated = moment(cairo)

        assert stated.at == "2026-09-04T09:30:00+00:00"
        assert stated.text == "2026-09-04 09:30 UTC"

    def test_a_naive_instant_is_read_as_utc(self) -> None:
        stated = moment(datetime(2026, 9, 4, 9, 30))

        assert stated.at == "2026-09-04T09:30:00+00:00"


# --- templates do not compute -----------------------------------------------------------------

_AGGREGATING_FILTERS = (
    "round",
    "sum",
    "length",
    "count",
    "sort",
    "max",
    "min",
    "int",
    "float",
    "abs",
)
_ARITHMETIC = re.compile(r"\s[-+*/%]\s|\*\*|//")
_EXPRESSIONS = re.compile(r"\{\{(.*?)\}\}|\{%-?(.*?)-?%\}", re.DOTALL)


def test_no_shell_template_computes() -> None:
    """The `G3-04` acceptance for this slice: a scan proves no template computes, rounds or sums.

    Every `{{ }}` and `{% %}` expression in every shell template is read. Arithmetic between
    operands and the aggregating filters are refused; a template that needs a number gets it from
    Python, where it can be tested, and Overview gets none at all.
    """
    directory = files("khepri.runtime").joinpath("shell_templates")
    templates = [entry for entry in directory.iterdir() if entry.name.endswith(".html.j2")]
    assert {"overview.html.j2", "data.html.j2"} <= {entry.name for entry in templates}

    for entry in templates:
        for match in _EXPRESSIONS.finditer(entry.read_text(encoding="utf-8")):
            expression = match.group(1) or match.group(2) or ""
            assert not _ARITHMETIC.search(expression), (entry.name, expression)
            for name in _AGGREGATING_FILTERS:
                assert not re.search(rf"\|\s*{name}\b", expression), (entry.name, expression)
