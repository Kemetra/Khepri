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
from khepri.rra.rendering.fonts import load_report_fonts
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
_TYPEFACE_ASSETS = {face.file_name: face.payload for face in load_report_fonts()}
_TEMPLATES = {
    "upload": "upload.html.j2",
    "review": "review.html.j2",
    "processing": "processing.html.j2",
    "report": "report.html.j2",
    "expired": "expired.html.j2",
}


def journey_environment() -> Environment:
    return Environment(
        loader=PackageLoader("khepri.rra.journey", "templates"),
        autoescape=select_autoescape(default=True, default_for_string=True),
        undefined=StrictUndefined,
    )


@dataclass(frozen=True, slots=True)
class JourneyEndpoints:
    services: JourneyServices
    clock: Callable[[], datetime]
    environment: Environment

    async def security(self, request: Request, call_next):
        try:
            require_same_origin(request)
        except HTTPException as error:
            return JSONResponse(
                status_code=error.status_code,
                content={"detail": error.detail},
            )
        return await call_next(request)

    def read(
        self,
        response: Response,
        session_id: BetaSessionCookie = None,
    ) -> dict[str, object]:
        if session_id is None:
            raise HTTPException(status_code=401, detail=SESSION_UNAVAILABLE)
        found = self.services.reader.read(session_id, self.clock())
        if found is None:
            raise HTTPException(status_code=401, detail=SESSION_UNAVAILABLE)
        response.headers["Cache-Control"] = "private, no-store"
        return asdict(found)

    def asset(self, name: str) -> Response:
        media_type, content = _asset(name)
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Cache-Control": "public, max-age=0, must-revalidate",
                "X-Content-Type-Options": "nosniff",
            },
        )

    def entry(self, request: Request, language: str) -> HTMLResponse:
        return self._page_response(request, language, "upload")

    def page(self, request: Request, language: str, step: str) -> HTMLResponse:
        return self._page_response(request, language, step)

    def _page_response(
        self,
        request: Request,
        language: str,
        step: str,
    ) -> HTMLResponse:
        if language not in JOURNEY_COPY or step not in _TEMPLATES:
            raise HTTPException(status_code=404)
        html = self.environment.get_template(_TEMPLATES[step]).render(
            request=request,
            language=language,
            direction="rtl" if language == "ar" else "ltr",
            alternate="en" if language == "ar" else "ar",
            copy=JOURNEY_COPY[language],
            step=step,
        )
        return HTMLResponse(html, headers=SECURITY_HEADERS)


def add_journey_routes(
    app: FastAPI,
    *,
    services: JourneyServices | None,
    clock: Callable[[], datetime],
) -> None:
    if services is None:
        return
    endpoints = JourneyEndpoints(services, clock, journey_environment())
    app.middleware("http")(endpoints.security)
    app.add_api_route("/api/v1/beta/journey", endpoints.read, methods=["GET"])
    app.add_api_route(
        "/beta/assets/{name}",
        endpoints.asset,
        methods=["GET"],
        name="journey_asset",
    )
    app.add_api_route(
        "/beta/{language}",
        endpoints.entry,
        methods=["GET"],
        response_class=HTMLResponse,
        name="journey_entry",
    )
    app.add_api_route(
        "/beta/{language}/{step}",
        endpoints.page,
        methods=["GET"],
        response_class=HTMLResponse,
        name="journey_page",
    )


def _asset(name: str) -> tuple[str, bytes]:
    media_type = _ASSETS.get(name)
    if media_type is not None:
        content = files("khepri.rra.journey").joinpath("assets", name).read_bytes()
        return media_type, content
    if name in _TYPEFACE_ASSETS:
        return "font/woff2", _TYPEFACE_ASSETS[name]
    raise HTTPException(status_code=404)


__all__ = [
    "JourneyEndpoints",
    "JourneyServices",
    "add_journey_routes",
    "journey_environment",
]
