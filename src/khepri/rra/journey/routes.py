"""Journey JSON and page route registration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from importlib.resources import files

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from khepri.rra.journey.copy import JOURNEY_COPY
from khepri.rra.journey.security import SECURITY_HEADERS, require_same_origin
from khepri.rra.journey.state import JourneyReader
from khepri.rra.session_cookie import SESSION_UNAVAILABLE, BetaSessionCookie


@dataclass(frozen=True, slots=True)
class JourneyServices:
    reader: JourneyReader


_ASSETS = {
    "journey.css": "text/css; charset=utf-8",
    "common.js": "text/javascript; charset=utf-8",
    "upload.js": "text/javascript; charset=utf-8",
    "review.js": "text/javascript; charset=utf-8",
    "processing.js": "text/javascript; charset=utf-8",
    "report.js": "text/javascript; charset=utf-8",
}
_TEMPLATES = {
    "upload": "upload.html.j2",
    "review": "review.html.j2",
    "processing": "processing.html.j2",
    "report": "report.html.j2",
}


def journey_environment() -> Environment:
    return Environment(
        loader=PackageLoader("khepri.rra.journey", "templates"),
        autoescape=select_autoescape(default=True, default_for_string=True),
        undefined=StrictUndefined,
    )


def add_journey_routes(
    app: FastAPI,
    *,
    services: JourneyServices | None,
    clock: Callable[[], datetime],
) -> None:
    if services is None:
        return
    environment = journey_environment()

    @app.middleware("http")
    async def journey_security(request: Request, call_next):
        try:
            require_same_origin(request)
        except HTTPException as error:
            return JSONResponse(status_code=error.status_code, content={"detail": error.detail})
        return await call_next(request)

    @app.get("/api/v1/beta/journey")
    def read_journey(
        response: Response,
        session_id: BetaSessionCookie = None,
    ) -> dict[str, object]:
        if session_id is None:
            raise HTTPException(status_code=401, detail=SESSION_UNAVAILABLE)
        found = services.reader.read(session_id, clock())
        if found is None:
            raise HTTPException(status_code=401, detail=SESSION_UNAVAILABLE)
        response.headers["Cache-Control"] = "private, no-store"
        return asdict(found)

    def page_response(request: Request, language: str, step: str) -> HTMLResponse:
        if language not in JOURNEY_COPY or step not in _TEMPLATES:
            raise HTTPException(status_code=404)
        html = environment.get_template(_TEMPLATES[step]).render(
            request=request,
            language=language,
            direction="rtl" if language == "ar" else "ltr",
            alternate="en" if language == "ar" else "ar",
            copy=JOURNEY_COPY[language],
            step=step,
        )
        return HTMLResponse(html, headers=SECURITY_HEADERS)

    @app.get("/beta/assets/{name}", name="journey_asset")
    def journey_asset(name: str) -> Response:
        media_type = _ASSETS.get(name)
        if media_type is None:
            raise HTTPException(status_code=404)
        content = files("khepri.rra.journey").joinpath("assets", name).read_bytes()
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get("/beta/{language}", response_class=HTMLResponse, name="journey_entry")
    def journey_entry(request: Request, language: str) -> HTMLResponse:
        return page_response(request, language, "upload")

    @app.get(
        "/beta/{language}/{step}", response_class=HTMLResponse, name="journey_page"
    )
    def journey_page(request: Request, language: str, step: str) -> HTMLResponse:
        return page_response(request, language, step)


__all__ = ["JourneyServices", "add_journey_routes", "journey_environment"]
