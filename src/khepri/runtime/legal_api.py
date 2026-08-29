"""Public legal/trust route framework (`LEGAL1-01`, RCA-003 FR-062--FR-080)."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.resources import files

from fastapi import FastAPI, HTTPException, Response
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from khepri.rra.journey.security import SECURITY_HEADERS
from khepri.runtime.legal_copy import DIRECTIONS, LEGAL_COPY, LEGAL_PAGE_TITLES

LEGAL_PREFIX = "/legal"
LEGAL_ASSETS = f"{LEGAL_PREFIX}/assets"
LEGAL_PAGES = frozenset(LEGAL_PAGE_TITLES["en"])


@dataclass(frozen=True, slots=True)
class LegalPublication:
    """A proposed public document and the verified inputs it relies on.

    Keeping publication state next to the public renderer makes the fail-closed
    boundary durable when later LEGAL1 slices add substantive copy.
    """

    content: dict[str, tuple[str, ...]] = field(default_factory=dict)
    verified_inputs: frozenset[str] = frozenset()


LEGAL_PUBLICATIONS = {page: LegalPublication() for page in LEGAL_PAGES}
_REQUIRED_PUBLICATION_INPUTS = {
    "privacy-policy": frozenset({"operator_identity", "privacy_contact", "effective_date"}),
    "terms-and-conditions": frozenset(
        {
            "operator_identity",
            "support_contact",
            "governing_law",
            "dispute_process",
            "effective_date",
        }
    ),
    "contact-us": frozenset({"operator_identity", "support_contact", "effective_date"}),
}
_PLACEHOLDER_MARKER = "[PLACEHOLDER]"

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


def _published_content(language: str, page: str) -> tuple[str, ...] | None:
    """Return one verified language variant only when bilingual publication is complete."""
    publication = LEGAL_PUBLICATIONS[page]
    if set(publication.content) != set(DIRECTIONS):
        return None
    content = publication.content[language]
    if not content or any(
        _PLACEHOLDER_MARKER in paragraph
        for language_content in publication.content.values()
        for paragraph in language_content
    ):
        return None
    if not _REQUIRED_PUBLICATION_INPUTS.get(page, frozenset()).issubset(
        publication.verified_inputs
    ):
        return None
    return content


def _legal_response(environment: Environment, *, language: str, page: str) -> Response:
    """Render only a verified document; unresolved publication remains unavailable."""
    publication_content = _published_content(language, page)
    body = environment.get_template("legal_page.html.j2").render(
        language=language,
        direction=DIRECTIONS[language],
        alternate="ar" if language == "en" else "en",
        page=page,
        page_title=LEGAL_PAGE_TITLES[language][page],
        copy=LEGAL_COPY[language],
        assets=LEGAL_ASSETS,
        prefix=LEGAL_PREFIX,
        publication_content=publication_content,
    )
    return Response(
        content=body,
        status_code=200 if publication_content is not None else 503,
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
    "LEGAL_PUBLICATIONS",
    "LegalPublication",
    "add_legal_routes",
    "legal_environment",
]
