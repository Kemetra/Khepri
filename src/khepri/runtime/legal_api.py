"""Public legal/trust route framework (`LEGAL1-01`, RCA-003 FR-062--FR-080)."""

from __future__ import annotations

from importlib.resources import files

from fastapi import FastAPI, HTTPException, Response
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from khepri.rra.journey.security import SECURITY_HEADERS
from khepri.runtime.legal_copy import DIRECTIONS, LEGAL_COPY, LEGAL_PAGE_TITLES

LEGAL_PREFIX = "/legal"
LEGAL_ASSETS = f"{LEGAL_PREFIX}/assets"
LEGAL_PAGES = frozenset(LEGAL_PAGE_TITLES["en"])

_ASSETS = {
    "shell.css": "text/css; charset=utf-8",
    "shell-components.css": "text/css; charset=utf-8",
}
_PUBLIC_HEADERS = {**SECURITY_HEADERS, "Cache-Control": "public, max-age=0, must-revalidate"}


def legal_environment() -> Environment:
    """Render only the public legal templates with undefined values treated as failures."""
    return Environment(
        loader=PackageLoader("khepri.runtime", "legal_templates"),
        autoescape=select_autoescape(default=True, default_for_string=True),
        undefined=StrictUndefined,
    )


def _legal_response(environment: Environment, *, language: str, page: str) -> Response:
    """Render an unpublished legal destination without customer or legally operative content."""
    body = environment.get_template("legal_page.html.j2").render(
        language=language,
        direction=DIRECTIONS[language],
        alternate="ar" if language == "en" else "en",
        page=page,
        page_title=LEGAL_PAGE_TITLES[language][page],
        copy=LEGAL_COPY[language],
        assets=LEGAL_ASSETS,
        prefix=LEGAL_PREFIX,
    )
    return Response(
        content=body,
        status_code=503,
        media_type="text/html; charset=utf-8",
        headers=dict(_PUBLIC_HEADERS),
    )


def add_legal_routes(app: FastAPI) -> None:
    """Register the closed, unauthenticated legal framework on every web application.

    The individual destinations deliberately render a shared unpublished state. RCA-003 blocks
    substantive Privacy, Terms, and Contact publication until verified legal inputs exist; later
    LEGAL1 slices may replace only their authorized page state after satisfying those preconditions.
    This registrar has no service argument, so it cannot resolve a session or organization.
    """
    environment = legal_environment()

    @app.get(f"{LEGAL_ASSETS}/{{name}}")
    def legal_asset(name: str) -> Response:
        """Serve the two existing local presentation sheets through an exact allowlist."""
        media_type = _ASSETS.get(name)
        if media_type is None:
            raise HTTPException(status_code=404)
        content = files("khepri.rra.journey").joinpath("assets", name).read_bytes()
        return Response(content=content, media_type=media_type, headers=dict(_PUBLIC_HEADERS))

    @app.get(f"{LEGAL_PREFIX}/{{language}}/{{page}}")
    def legal_page(language: str, page: str) -> Response:
        """Address only the bilingual, authority-limited legal page inventory."""
        if language not in LEGAL_COPY or page not in LEGAL_PAGES:
            raise HTTPException(status_code=404)
        return _legal_response(environment, language=language, page=page)


__all__ = [
    "LEGAL_ASSETS",
    "LEGAL_PAGES",
    "LEGAL_PREFIX",
    "add_legal_routes",
    "legal_environment",
]
