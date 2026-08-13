"""Browser security policy for the same-origin journey."""

from __future__ import annotations

from fastapi import HTTPException, Request

MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def require_same_origin(request: Request) -> None:
    if request.method not in MUTATION_METHODS:
        return
    site = request.headers.get("sec-fetch-site")
    origin = request.headers.get("origin")
    expected = f"{request.url.scheme}://{request.url.netloc}"
    if site not in {None, "same-origin", "none"} or origin not in {None, expected}:
        raise HTTPException(status_code=403, detail="Cross-site mutation is not allowed.")


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
