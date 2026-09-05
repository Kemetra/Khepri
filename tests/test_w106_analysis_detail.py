"""`W1-06` -- Analysis detail, the Analysis Passport, the artifact handoff, and the Analyses
destination that `#374` withheld (`RCA-005` `FR-117`, `FR-118`, `FR-119`, `FR-121`; `RCA-002`
`FR-046`, `FR-049`; blueprint §7.3, §7.4, §10).

Every run here was admitted, derived, queued and delivered through the deployed routes and the real
worker (`tests/w104b_support.py`), then read back through the shell as `build_shell_services`
composes it. Nothing here calls a workspace action or fabricates a record.

What the surfaces must hold:

- the Analyses destination and its rows ship together with detail, the "next valid action" `#374`
  waited for; a row's trust state is the report's own quality summary, worded through the report's
  component chrome (`RRA-012`) and its section headings (`RRA-011`), never through words this shell
  coins;
- detail leads with the Passport -- period, data reference, coverage, scale, timestamp, methodology
  and version context -- and keeps every digest and machine identifier inside contextual audit
  detail (`FR-119`, §10);
- artifacts are reached from detail and nowhere else (`FR-118`), through a handoff that resumes
  the run's own analysis session (`R7-03`) and hands the browser the beta cookie the report API
  reads;
- every refusal is the one uniform `unavailable` surface (`FR-050`).
"""

from __future__ import annotations

import re
from datetime import timedelta
from importlib.resources import files

import pytest

from khepri.rra.rendering.wording import COMPONENT_CHROME, SECTION_HEADINGS
from khepri.rra.session_cookie import SESSION_COOKIE as BETA_COOKIE
from khepri.runtime.shell_api import SHELL_PREFIX
from khepri.runtime.shell_copy import SHELL_COPY
from tests.w104_support import member
from tests.w104b_support import journey
from tests.w106_support import (
    analyses_address,
    completed_run,
    detail_address,
    handoff_address,
    page,
    shell_over,
    started_run,
)

EN = SHELL_COPY["en"]
AR = SHELL_COPY["ar"]


def _text(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def _nav(html: str) -> str:
    start = html.index('class="frame-surfaces"')
    return html[start : html.index("</nav>", start)]


def _audit(html: str) -> str:
    """The contextual audit detail's markup, and nothing outside it."""
    start = html.index('class="audit-detail"')
    return html[start : html.index("</details>", start)]


def _outside_audit(html: str) -> str:
    start = html.index('class="audit-detail"')
    end = html.index("</details>", start)
    return html[:start] + html[end:]


# --- FR-121: the Analyses destination ships with detail -----------------------------------------


@pytest.mark.parametrize("language", ["en", "ar"])
def test_the_four_destinations_ship_in_order_once_detail_exists(language: str) -> None:
    j = journey()
    who = member(j.w)

    nav = _nav(page(j, who, "team", language=language))

    links = [
        f'href="{SHELL_PREFIX}/{language}/{who.organization_id}/{surface}"'
        for surface in ("overview", "data", "analyses", "team")
    ]
    positions = [nav.index(link) for link in links]
    assert positions == sorted(positions)
    assert SHELL_COPY[language]["analyses_title"] in nav


@pytest.mark.parametrize("wiring", [{"with_provenance": False}, {"with_bridge": False}])
def test_analyses_is_withheld_when_its_provenance_or_handoff_is_unwired(wiring: dict) -> None:
    """`FR-049`: a row's trust state needs the provenance read and its artifacts need the handoff.
    Without either the destination does not exist, rather than existing and refusing."""
    j = journey()
    who = member(j.w)
    run, _job, _session = completed_run(j, who)
    shell = shell_over(j, who, **wiring)

    assert f'href="{analyses_address(who)}"' not in _nav(
        shell.get(f"{SHELL_PREFIX}/en/{who.organization_id}/team").text
    )
    assert shell.get(analyses_address(who)).status_code == 404
    assert shell.get(detail_address(who, run.run_id)).status_code == 404


def test_the_analyses_address_renders_the_spine() -> None:
    j = journey()
    who = member(j.w)
    completed_run(j, who)

    response = shell_over(j, who).get(analyses_address(who))

    assert response.status_code == 200
    assert 'class="spine-list"' in response.text
    assert EN["analyses_empty"] not in response.text


# --- FR-117: rows link to their detail and state their trust --------------------------------------


def test_a_live_row_links_to_its_detail_and_a_completed_one_states_its_quality() -> None:
    j = journey()
    who = member(j.w)
    run, _job, _session = completed_run(j, who)

    html = page(j, who, "analyses")

    assert f'href="{detail_address(who, run.run_id)}"' in html
    start = html.index('class="spine-trust"')
    trust = html[start : html.index("</p>", start)]
    chrome = COMPONENT_CHROME["en"]
    assert chrome["quality_answered"] in trust or chrome["quality_refused"] in trust
    # Section names are the report's own headings, never words of this shell's.
    assert any(heading in trust for heading in SECTION_HEADINGS["en"].values())
    assert run.run_id not in _text(html)


def test_a_started_row_states_no_quality_yet() -> None:
    j = journey()
    who = member(j.w)
    run, _job, _session = started_run(j, who)

    html = page(j, who, "analyses")

    assert f'href="{detail_address(who, run.run_id)}"' in html
    assert 'class="spine-trust"' not in html
    for word in COMPONENT_CHROME["en"].values():
        assert word not in _text(html)


# --- FR-119: the Passport leads, digests sit behind audit detail ----------------------------------


def test_detail_leads_with_the_passport_and_keeps_digests_in_audit_detail() -> None:
    j = journey()
    who = member(j.w)
    run, _job, _session = completed_run(j, who)
    (version,) = j.w.store.dataset_versions_for_scope(who.owner_id)

    html = page(j, who, f"analyses/{run.run_id}")

    # Order: period, data reference, coverage, scale, timestamp, then methodology context.
    labels = [
        EN["passport_period"],
        EN["passport_data"],
        EN["passport_scope"],
        EN["passport_rows"],
        EN["passport_ran"],
        EN["passport_methodology"],
    ]
    passport_region = html[html.index('class="passport"') :]
    positions = [passport_region.index(f"<dt>{label}</dt>") for label in labels]
    assert positions == sorted(positions)
    assert html.index(EN["passport_title"]) < html.index(EN["audit_title"])
    # The period is the attested coverage, stated as dates.
    assert "2026-01-05" in html and "2026-01-07" in html
    # The data reference follows to the Data row, and the scale is the admitted row count.
    anchor = f'href="{SHELL_PREFIX}/en/{who.organization_id}/data#data-{version.version_id}"'
    assert anchor in html
    assert ">4<" in html
    # Digests and identifiers: inside the audit detail, and only there.
    outside = _text(_outside_audit(html))
    for token in (
        run.package_digest,
        version.manifest_digest,
        version.upload_plaintext_digest,
        run.run_id,
        version.version_id,
    ):
        assert token in _audit(html), token
        assert token not in outside, token
    # Methodology and version context is in the Passport, as `FR-119` puts it.
    passport = html[html.index('class="passport"') : html.index('class="audit-detail"')]
    for token in (version.mapping_version, run.package_version, run.formula_version):
        assert token in passport, token


def test_detail_states_the_quality_summary_through_the_reports_words() -> None:
    j = journey()
    who = member(j.w)
    run, _job, _session = completed_run(j, who)

    html = page(j, who, f"analyses/{run.run_id}")

    start = html.index('class="quality"')
    quality = html[start : html.index("</dl>", start)]
    chrome = COMPONENT_CHROME["en"]
    assert chrome["quality_summary"] in html
    assert any(chrome[key] in quality for key in ("quality_answered", "quality_refused"))
    assert any(heading in quality for heading in SECTION_HEADINGS["en"].values())
    # Availability, never certainty: no percent sign and no score anywhere on the page.
    assert "%" not in _text(html)


@pytest.mark.parametrize("language", ["en", "ar"])
def test_detail_renders_in_both_languages(language: str) -> None:
    j = journey()
    who = member(j.w)
    run, _job, _session = completed_run(j, who)

    html = page(j, who, f"analyses/{run.run_id}", language=language)

    copy = SHELL_COPY[language]
    for key in ("analysis_title", "passport_title", "artifacts_title", "audit_title"):
        assert copy[key] in html, key
    assert COMPONENT_CHROME[language]["quality_summary"] in html


# --- FR-118: artifacts are reached from detail, through the handoff, and from nowhere else --------


def test_a_completed_run_offers_each_artifact_as_a_handoff_from_detail() -> None:
    j = journey()
    who = member(j.w)
    run, _job, _session = completed_run(j, who)

    html = page(j, who, f"analyses/{run.run_id}")

    for kind in ("web", "evidence", "pdf", "excel"):
        assert f'action="{handoff_address(who, run.run_id, kind)}"' in html, kind
    for key in ("artifact_web", "artifact_evidence", "artifact_pdf", "artifact_excel"):
        assert EN[key] in html, key
    # The report API's addresses are built in Python at handoff time, never in a template.
    assert "/api/v1/beta" not in html


def test_a_started_run_offers_no_artifact_and_says_the_report_is_not_ready() -> None:
    j = journey()
    who = member(j.w)
    run, _job, _session = started_run(j, who)

    html = page(j, who, f"analyses/{run.run_id}")

    assert "<form" not in html
    assert EN["artifacts_not_yet"] in html
    assert EN["run_state_started"] in html


def test_a_failed_run_offers_no_artifact_and_says_none_was_produced() -> None:
    from tests.w104b_support import RETRY_DELAY, BrokenHandler

    j = journey()
    who = member(j.w)
    run, job_id, _session = started_run(j, who)
    for _attempt in range(3):
        j.run_job(job_id, handler=BrokenHandler())
        j.clock.advance(RETRY_DELAY * 2)

    html = page(j, who, f"analyses/{run.run_id}")

    assert "<form" not in html
    assert EN["artifacts_none"] in html
    assert EN["run_state_failed"] in html


@pytest.mark.parametrize(
    ("kind", "target"),
    [
        ("web", "/api/v1/beta/reports/{job}/surfaces/web/en"),
        ("evidence", "/api/v1/beta/reports/{job}/surfaces/evidence/en"),
        ("pdf", "/api/v1/beta/reports/{job}/surfaces/pdf/en"),
        ("excel", "/api/v1/beta/reports/{job}/surfaces/excel"),
    ],
)
def test_the_handoff_resumes_the_runs_session_and_sends_the_browser_to_the_artifact(
    kind: str, target: str
) -> None:
    """`R7-03`: the session is resumed through the bridge -- re-authorized, in scope -- and the
    beta cookie the report API reads is set exactly as the journey entry sets it (`R8-06`)."""
    j = journey()
    who = member(j.w)
    run, job_id, session_id = completed_run(j, who)

    response = shell_over(j, who).post(
        handoff_address(who, run.run_id, kind), follow_redirects=False
    )

    assert response.status_code == 303
    assert response.headers["location"] == target.format(job=job_id)
    cookie = response.headers["set-cookie"]
    assert f"{BETA_COOKIE}={session_id}" in cookie
    assert "Path=/api/v1/beta" in cookie and "HttpOnly" in cookie and "Secure" in cookie


def test_the_handoff_follows_the_address_language() -> None:
    j = journey()
    who = member(j.w)
    run, job_id, _session = completed_run(j, who)

    response = shell_over(j, who).post(
        handoff_address(who, run.run_id, "web", language="ar"), follow_redirects=False
    )

    assert response.headers["location"] == f"/api/v1/beta/reports/{job_id}/surfaces/web/ar"


def test_the_handoff_refuses_a_run_with_no_report_and_sets_no_cookie() -> None:
    j = journey()
    who = member(j.w)
    run, _job, _session = started_run(j, who)

    response = shell_over(j, who).post(
        handoff_address(who, run.run_id, "web"), follow_redirects=False
    )

    assert response.status_code == 404
    assert "set-cookie" not in response.headers
    assert EN["unavailable_title"] in response.text


def test_the_handoff_refuses_an_unknown_kind() -> None:
    j = journey()
    who = member(j.w)
    run, _job, _session = completed_run(j, who)

    response = shell_over(j, who).post(
        handoff_address(who, run.run_id, "json"), follow_redirects=False
    )

    assert response.status_code == 404
    assert "set-cookie" not in response.headers


# --- FR-042 / FR-046 / FR-050: scope, exactness, and the uniform refusal --------------------------


def test_another_organizations_run_is_unavailable_to_read_and_to_hand_off() -> None:
    j = journey()
    who = member(j.w)
    other = member(j.w, email="other@example.test", name="Other")
    run, _job, _session = completed_run(j, who)
    shell = shell_over(j, other)

    read = shell.get(detail_address(other, run.run_id))
    handoff = shell.post(handoff_address(other, run.run_id, "web"), follow_redirects=False)

    assert read.status_code == 404 and EN["unavailable_title"] in read.text
    assert handoff.status_code == 404 and "set-cookie" not in handoff.headers
    assert run.run_id not in read.text


@pytest.mark.parametrize("tail", ["analyses/run_no_such", "analyses/{run}/", "analyses/{run}/more"])
def test_an_inexact_or_unknown_detail_address_is_unavailable(tail: str) -> None:
    """`FR-046`: `/analyses/{run}` with one tolerated trailing slash is the address; a tail past it,
    or an identifier no run answers to, reaches `unavailable` and never a surface that guesses."""
    j = journey()
    who = member(j.w)
    run, _job, _session = completed_run(j, who)
    address = tail.format(run=run.run_id)

    response = shell_over(j, who).get(f"{SHELL_PREFIX}/en/{who.organization_id}/{address}")

    if address.endswith("/") and address.count("/") == 2:
        assert response.status_code == 200
    else:
        assert response.status_code == 404
        assert EN["unavailable_title"] in response.text


def test_a_run_whose_journey_content_has_expired_keeps_its_passport_but_not_its_handoff() -> None:
    """`KHEPRI-DEC-033` §2: the provenance record lives with the run, so eight days on the
    Passport still reads -- period, scale, outcomes. The analysis session's content is gone, so
    no artifact is offered and the page says the report can no longer be opened rather than
    offering a handoff that would refuse (`FR-049`; `W1-07` reconciles artifact retention)."""
    j = journey()
    who = member(j.w)
    run, _job, _session = completed_run(j, who)
    j.clock.advance(timedelta(days=8))

    html = page(j, who, f"analyses/{run.run_id}")

    assert EN["passport_period"] in html and "2026-01-05" in html and ">4<" in html
    assert EN["passport_unavailable"] not in html
    assert "<form" not in html
    assert EN["artifacts_unreachable"] in html
    assert EN["run_state_completed"] in html


# --- No second index -----------------------------------------------------------------------------


def test_no_template_but_detail_offers_an_artifact_and_none_names_the_report_api() -> None:
    """`FR-118`: one place discovers deliverables. Every other shell template carries no artifact
    form and no report address; the handoff's targets live in Python, tested above."""
    directory = files("khepri.runtime").joinpath("shell_templates")
    for entry in directory.iterdir():
        source = entry.read_text(encoding="utf-8")
        assert "/api/v1/beta" not in source, entry.name
        if entry.name != "analysis.html.j2":
            assert "artifacts/" not in source, entry.name


# --- The quality groups, over a summary with every kind of outcome --------------------------------


def test_the_groups_are_answered_without_caveat_then_caveated_then_refused() -> None:
    """A caveated analysis was still answered, so it appears in the caveated group and not in the
    plain one; a refused analysis appears in the refused group and nowhere else. The codes are
    `KHEPRI-DEC-033` §3's, retained with the run; the words are the report's own, in both
    languages."""
    from khepri.rca.workspace.tombstones import SectionStates
    from khepri.runtime.shell_analysis import trust_groups

    sections = SectionStates(
        overview="answered",
        comparison="refused",
        concentration="answered",
        growth="answered",
        basket="caveated",
    )

    for language in ("en", "ar"):
        chrome = COMPONENT_CHROME[language]
        headings = SECTION_HEADINGS[language]
        groups = {group.label: group.sections for group in trust_groups(sections, language)}
        assert groups == {
            chrome["quality_answered"]: tuple(
                headings[s] for s in ("overview", "concentration", "growth")
            ),
            chrome["quality_caveated"]: (headings["basket"],),
            chrome["quality_refused"]: (headings["comparison"],),
        }


def test_the_handoff_sets_no_cookie_when_the_bridge_will_not_resume() -> None:
    """`R7-03`: the bridge re-authorizes before it resumes, and refuses a member whose standing is
    gone. That refusal is the uniform surface with no `Set-Cookie` -- a cookie beside a refusal
    would hand a session to a reader who was just denied one."""
    from dataclasses import replace as replace_services

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from khepri.rca.session_cookie import SESSION_COOKIE
    from khepri.runtime.shell_api import add_shell_routes
    from tests.w106_support import HTTPS, services_over

    class _RefusingBridge:
        def open(self, **kwargs):  # pragma: no cover -- the handoff never opens
            raise AssertionError

        def resume(self, **kwargs):
            return None

    j = journey()
    who = member(j.w)
    run, _job, _session = completed_run(j, who)
    app = FastAPI()
    add_shell_routes(
        app,
        services=replace_services(services_over(j, who), bridge=_RefusingBridge()),
        clock=j.clock,
    )
    client = TestClient(app, base_url=HTTPS)
    client.cookies.set(SESSION_COOKIE, "a-session-token")

    response = client.post(handoff_address(who, run.run_id, "web"), follow_redirects=False)

    assert response.status_code == 404
    assert "set-cookie" not in response.headers
    assert EN["unavailable_title"] in response.text


def test_the_handoff_refuses_a_run_whose_content_has_expired_and_sets_no_cookie() -> None:
    """The handoff's rule is detail's rule: what the page will not offer, the route will not hand
    off, so a stale address cannot resume a session whose content has ended (`FR-049`)."""
    j = journey()
    who = member(j.w)
    run, _job, _session = completed_run(j, who)
    j.clock.advance(timedelta(days=8))

    response = shell_over(j, who).post(
        handoff_address(who, run.run_id, "web"), follow_redirects=False
    )

    assert response.status_code == 404
    assert "set-cookie" not in response.headers
    assert EN["unavailable_title"] in response.text


def test_the_handoff_redirect_carries_the_shells_security_headers() -> None:
    """`FR-043`/`FR-045`: every shell response carries the security headers, and the handoff's
    redirect is one -- the same set the journey entry's redirect carries (review on `#376`)."""
    from khepri.rra.journey.security import SECURITY_HEADERS

    j = journey()
    who = member(j.w)
    run, _job, _session = completed_run(j, who)

    response = shell_over(j, who).post(
        handoff_address(who, run.run_id, "web"), follow_redirects=False
    )

    assert response.status_code == 303
    for header, value in SECURITY_HEADERS.items():
        assert response.headers[header] == value, header
