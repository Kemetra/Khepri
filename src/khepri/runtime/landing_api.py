"""The public product landing surface (`LAND1-01`, RCA-004).

One bilingual, non-authenticated marketing page. It explains existing governed behavior and
demonstrates the trust model with a labelled synthetic specimen. It holds no customer state and
reaches no service, so this registrar takes no service argument and cannot resolve a session.

Three boundaries are load-bearing and each is asserted by a test rather than left to review:

`FR-085` — governed vocabulary has one source. The specimen's metric names and its refusal text
are read from `khepri.rra.rendering.wording` at import, never retyped here. Marketing narration
that has no governed counterpart lives in `landing_copy`.

`FR-086` — the landing links only to a legal destination that actually publishes. `LEGAL_LINKS`
is resolved from `legal_api`'s own publication decision, so a page that regresses to unpublished
leaves the footer instead of becoming a dead link, and the landing never joins `LEGAL_PAGES`.

`FR-087`/`FR-088` — no CTA renders. No request-access destination exists in the runtime and no
active specification authorizes one: `contact-us` is unpublished, `/beta` is the invitation-gated
private journey, and RCA-001 and RCA-002 both exclude public self-serve signup. `FR-087` permits
a CTA only where its destination already exists, so the page closes on its thesis instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files

from fastapi import FastAPI, HTTPException, Response
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from khepri.rra.journey.security import SECURITY_HEADERS
from khepri.rra.rendering.fonts import load_report_fonts
from khepri.rra.rendering.wording import (
    caveat_message,
    metric_business_name,
    refusal_message,
)
from khepri.runtime.landing_copy import LANDING_COPY, LANDING_DIRECTIONS
from khepri.runtime.legal_api import LEGAL_PREFIX, published_pages

LANDING_PREFIX = "/landing"
LANDING_ASSETS = f"{LANDING_PREFIX}/assets"

#: The one public marketing surface RCA-004 `FR-081` authorizes. A second entry here is a
#: specification change, not an implementation detail, which is what the inventory test guards.
LANDING_PAGES = frozenset({"index"})

_ASSETS = {"landing.css": "text/css; charset=utf-8"}
_TYPEFACES = {face.file_name: face for face in load_report_fonts()}
_PUBLIC_HEADERS = {**SECURITY_HEADERS, "Cache-Control": "public, max-age=0, must-revalidate"}

#: The refusal the specimen demonstrates. `prior_window_absent` is a section-scope reason in
#: `REASON_SCOPES`, so it is read at section scope; asking for it at result scope raises.
_SPECIMEN_REASON = "prior_window_absent"
_SPECIMEN_REASON_SCOPE = "section"

#: The caveat the specimen qualifies with, read from the same catalog as the refusal.
#:
#: An earlier draft narrated a missing-category caveat in marketing prose. The runtime cannot
#: produce that outcome — `basket` refuses an incomplete dimension with
#: `dimension_values_incomplete` rather than caveating it, and no missing-category caveat code
#: exists — so the page advertised
#: behavior the product does not have and defined a caveat meaning of its own, which is exactly
#: what `FR-085` excludes. This code is a real caveat with the right shape: the figure is reported,
#: and the qualification travels with it.
_SPECIMEN_CAVEAT = "rows_without_time_field_excluded"


@dataclass(frozen=True, slots=True)
class SpecimenCourse:
    """One line of the synthetic specimen, named by the governed catalog.

    `term` is never authored here: it is `metric_business_name` for a governed metric code, so a
    catalog rename reaches this page instead of drifting from it.
    """

    metric: str
    value: str
    state: str


#: The synthetic specimen. Values are illustrative and labelled as such in the template; the
#: metric codes are governed and resolve to governed names at render time.
_SPECIMEN_COURSES = (
    SpecimenCourse(metric="revenue", value="4,182,600 EGP", state="proven"),
    SpecimenCourse(metric="transactions", value="61,244", state="proven"),
    SpecimenCourse(metric="average_order_value", value="68.29 EGP", state="proven"),
)

_ARABIC_SPECIMEN_VALUES = {
    "revenue": "٤٬١٨٢٬٦٠٠ ج.م",
    "transactions": "٦١٬٢٤٤",
    "average_order_value": "٦٨٫٢٩ ج.م",
}


def landing_environment() -> Environment:
    """Render only the landing templates, with an undefined value treated as a failure."""
    return Environment(
        loader=PackageLoader("khepri.runtime", "landing_templates"),
        autoescape=select_autoescape(default=True, default_for_string=True),
        undefined=StrictUndefined,
    )


def specimen(language: str) -> tuple[dict[str, str], ...]:
    """The specimen's courses, named by the governed catalog in the requested language."""
    values = _ARABIC_SPECIMEN_VALUES if language == "ar" else None
    return tuple(
        {
            "term": metric_business_name(course.metric, language),
            "value": values[course.metric] if values else course.value,
            "state": course.state,
        }
        for course in _SPECIMEN_COURSES
    )


def specimen_refusal(language: str) -> str:
    """The governed refusal text the specimen withholds with.

    Read from the catalog rather than authored, so the landing cannot state a refusal the product
    would not state. `FR-085` forbids a duplicate manually maintained truth for reason meanings.
    """
    return refusal_message(
        _SPECIMEN_REASON, context=_SPECIMEN_REASON_SCOPE, language=language
    )


def specimen_caveat(language: str) -> str:
    """The governed caveat text the specimen qualifies with.

    Read from the catalog for the same reason the refusal is: the landing may not state a
    qualification the product would not state, nor invent one it has no code for.
    """
    return caveat_message(_SPECIMEN_CAVEAT, language)


def panel_metric(language: str) -> str:
    """The metric the bilingual panel names, resolved from the catalog.

    The panel labels a displayed figure rather than narrating, so a hard-coded label here would
    be a second maintained truth for a metric name — the drift `FR-085` excludes, and invisible
    until the catalog renamed `revenue` and only the specimen followed.

    Both panels render on both pages, side by side, so each is asked for by its own script rather
    than by the page's language. That is the point of the register: the same fact, twice, neither
    a translation of the other.
    """
    return metric_business_name("revenue", language)


def legal_links(language: str) -> tuple[dict[str, str], ...]:
    """Every legal destination that currently publishes, in the requested language.

    Resolved from `legal_api`'s publication decision rather than from a second list, so a page
    that is not published never becomes a footer link and a page that later publishes joins
    without an edit here.
    """
    return tuple(
        {"href": f"{LEGAL_PREFIX}/{language}/{page}", "title": title}
        for page, title in sorted(published_pages(language))
    )


def add_landing_routes(app: FastAPI) -> None:
    """Register the public landing on a web application.

    No service argument, so the surface cannot resolve a session, an organization, or customer
    content. It renders the same bytes for every visitor.
    """
    environment = landing_environment()

    @app.get(f"{LANDING_ASSETS}/{{name}}")
    def landing_asset(name: str) -> Response:
        """Serve the landing stylesheet and the bundled faces through an exact allowlist."""
        media_type = _ASSETS.get(name)
        if media_type is not None:
            content = files("khepri.runtime").joinpath("landing_assets", name).read_bytes()
            return Response(
                content=content, media_type=media_type, headers=dict(_PUBLIC_HEADERS)
            )
        face = _TYPEFACES.get(name)
        if face is None:
            raise HTTPException(status_code=404)
        return Response(
            content=face.payload,
            media_type=face.media_type,
            headers=dict(_PUBLIC_HEADERS),
        )

    @app.get(f"{LANDING_PREFIX}/{{language}}")
    def landing_page(language: str) -> Response:
        """Render the landing in one language, with a server-computed direction."""
        if language not in LANDING_COPY:
            raise HTTPException(status_code=404)
        copy = LANDING_COPY[language]
        alternate = "ar" if language == "en" else "en"
        html = environment.get_template("landing.html.j2").render(
            language=language,
            direction=LANDING_DIRECTIONS[language],
            alternate=alternate,
            alternate_href=f"{LANDING_PREFIX}/{alternate}",
            copy=copy,
            assets=LANDING_ASSETS,
            faces=tuple(_TYPEFACES.values()),
            courses=specimen(language),
            refusal=specimen_refusal(language),
            caveat=specimen_caveat(language),
            panel_metric_en=panel_metric("en"),
            panel_metric_ar=panel_metric("ar"),
            legal_links=legal_links(language),
        )
        return Response(
            content=html,
            media_type="text/html; charset=utf-8",
            headers=dict(_PUBLIC_HEADERS),
        )


__all__ = [
    "LANDING_ASSETS",
    "LANDING_PAGES",
    "LANDING_PREFIX",
    "SpecimenCourse",
    "add_landing_routes",
    "landing_environment",
    "legal_links",
    "panel_metric",
    "specimen",
    "specimen_caveat",
    "specimen_refusal",
]
