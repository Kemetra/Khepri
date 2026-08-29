"""Public legal/trust surfaces (`LEGAL1-01` through `LEGAL1-05`, RCA-003)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib.resources import files

from fastapi import FastAPI, HTTPException, Response
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from khepri.rra.journey.security import SECURITY_HEADERS
from khepri.runtime.legal_copy import (
    DIRECTIONS,
    LEGAL_COPY,
    LEGAL_DOCUMENTS,
    LEGAL_PAGE_TITLES,
)

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
    verified_values: dict[str, dict[str, str]] = field(default_factory=dict)
    verified_evidence: frozenset[str] = frozenset()


LEGAL_PUBLICATIONS = {
    page: LegalPublication(content=LEGAL_DOCUMENTS[page]) for page in LEGAL_PAGES
}
_REQUIRED_PUBLICATION_INPUTS = {
    "privacy-policy": frozenset({"operator_identity", "privacy_contact", "effective_date"}),
    "data-protection": frozenset(
        {"operator_identity", "privacy_contact", "effective_date"}
    ),
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
_CLAIM_PATTERNS = {
    "iso-27001": re.compile(r"\biso[- ]?27001\b", re.IGNORECASE),
    "soc-2": re.compile(r"\bsoc[- ]?2\b", re.IGNORECASE),
    "pci-dss": re.compile(r"\bpci[- ]?dss\b", re.IGNORECASE),
    "gdpr-compliance": re.compile(r"\bgdpr[- ]?(?:compliant|compliance)\b", re.IGNORECASE),
    "pdpl-compliance": re.compile(r"\bpdpl[- ]?(?:compliant|compliance)\b", re.IGNORECASE),
    "generic-certification": re.compile(r"\bcertified\b", re.IGNORECASE),
    "generic-compliance": re.compile(r"\bcompliant\b", re.IGNORECASE),
    "arabic-certification": re.compile(r"حاصل\s+على\s+شهادة"),
    "arabic-compliance": re.compile(r"(?:متوافق(?:ة)?\s+مع|امتثال(?:\s|$))"),
}
_VERIFIED_CLAIM_EVIDENCE: dict[str, frozenset[str]] = {}
_PROHIBITED_CLAIM_PATTERNS = (
    re.compile(r"\b(?:sla|service[- ]level agreement|uptime)\b", re.IGNORECASE),
    re.compile(r"\bself[- ]service (?:deletion|delete|export)\b", re.IGNORECASE),
    re.compile(r"\b(?:training|train)\b.{0,40}\bcustomer[- ]?(?:uploaded )?data\b", re.IGNORECASE),
    re.compile(
        r"\b(?:retention period|retain(?:ed|s)?(?: [^.]{0,40})? for)\s+\d+",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:hosted|hosting|data residency)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:subscription|payment provider|chargeback|credit|invoice|refund window)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bpharmacy[- ]only\b", re.IGNORECASE),
    re.compile(
        r"\bcustomer[- ]?(?:uploaded )?data\b.{0,40}\b(?:training|train)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:اتفاقية مستوى الخدمة|حذف ذاتي|تصدير ذاتي|استضافة|صيدليات فقط)"),
)

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


def _publication_has_prohibited_claims(publication: LegalPublication) -> bool:
    """Keep unverified compliance and out-of-scope commitments out of public copy."""
    document = "\n".join(
        paragraph
        for language_content in publication.content.values()
        for paragraph in language_content
    )
    if any(pattern.search(document) for pattern in _PROHIBITED_CLAIM_PATTERNS):
        return True
    return any(
        pattern.search(document)
        and not (_VERIFIED_CLAIM_EVIDENCE.get(claim, frozenset()) & publication.verified_evidence)
        for claim, pattern in _CLAIM_PATTERNS.items()
    )


def _has_verified_required_values(publication: LegalPublication, page: str) -> bool:
    """Require each operative value in both approved language variants before publication."""
    required_inputs = _REQUIRED_PUBLICATION_INPUTS.get(page, frozenset())
    if not required_inputs.issubset(publication.verified_inputs):
        return False
    for field_name in required_inputs:
        values = publication.verified_values.get(field_name, {})
        if set(values) != set(DIRECTIONS):
            return False
        for language, value in values.items():
            if not value or value not in "\n".join(publication.content[language]):
                return False
    return True


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
    if _publication_has_prohibited_claims(publication):
        return None
    if not _has_verified_required_values(publication, page):
        return None
    return content


def _published_pages(language: str) -> tuple[tuple[str, str], ...]:
    """List only destinations that render in this language, so footer links cannot be dead."""
    return tuple(
        (page, LEGAL_PAGE_TITLES[language][page])
        for page in LEGAL_PAGES
        if _published_content(language, page) is not None
    )


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
        legal_links=_published_pages(language),
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
