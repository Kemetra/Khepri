"""Browser security policy for the same-origin journey."""

from __future__ import annotations

from fastapi import HTTPException, Request

MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_CROSS_SITE = "Cross-site mutation is not allowed."


def require_same_origin(request: Request) -> None:
    """Refuse a mutation a browser would mark cross-site, or one riding a cookie unmarked.

    The approved journey design (`2026-08-13-client-journey-ui-design.md` §Browser security)
    requires mutating browser requests to carry an allowed `Origin` and same-origin Fetch Metadata.
    One same-origin signal is enough, because a browser without Fetch Metadata still sends `Origin`
    on a mutation. **Neither signal is refused only when a cookie is present** (`#434` §2). The
    cookie is the one ambient credential a forged request can ride on. An old client, a WebView, or
    a replayed cookie sends it unmarked, so that request must fail closed. A cookieless caller,
    such as a bearer or non-browser client, carries nothing to forge and is admitted. No CSRF
    token is added. `shell_pins.py` records that stance.
    """
    if request.method not in MUTATION_METHODS:
        return
    if _marked_cross_site(request) or _unmarked_with_cookie(request):
        raise HTTPException(status_code=403, detail=_CROSS_SITE)


def _marked_cross_site(request: Request) -> bool:
    """Whether either browser signal present names another site."""
    site = request.headers.get("sec-fetch-site")
    origin = request.headers.get("origin")
    expected = f"{request.url.scheme}://{request.url.netloc}"
    return site not in {None, "same-origin", "none"} or origin not in {None, expected}


def _unmarked_with_cookie(request: Request) -> bool:
    """Whether a cookie rides a request that carries neither browser signal."""
    headers = request.headers
    unmarked = "sec-fetch-site" not in headers and "origin" not in headers
    return unmarked and "cookie" in headers


SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
        "font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; "
        "frame-ancestors 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cache-Control": "private, no-store",
}

__all__ = ["SECURITY_HEADERS", "require_same_origin"]
