"""Hand-written collaborators the benchmark tests share.

Kept in one module so the faithful renderer is written once: two copies of it
would drift, and a benchmark measured against a renderer that quietly stopped
reconciling would report completions nobody rendered.
"""

from __future__ import annotations

from khepri.rra.bundle import (
    LANGUAGE_DIRECTION,
    REQUIRED_SURFACES,
    ReportBundle,
    StatedFigure,
    SurfaceContent,
    SurfaceLanguage,
    SurfaceUnavailable,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH


class Renderer:
    """A faithful renderer, remembering the bundle it was asked to present."""

    def __init__(self, surface: str) -> None:
        self._surface = surface
        self.seen: list[ReportBundle] = []

    @property
    def surface(self) -> str:
        return self._surface

    def render(self, bundle: ReportBundle) -> SurfaceContent:
        self.seen.append(bundle)
        return SurfaceContent(
            surface=self._surface,
            bundle_id=bundle.bundle_id,
            languages=tuple(
                _language(bundle, language) for language in (LANGUAGE_ARABIC, LANGUAGE_ENGLISH)
            ),
        )


class BrokenRenderer(Renderer):
    """A renderer that could not produce its surface."""

    def render(self, bundle: ReportBundle) -> SurfaceContent:
        self.seen.append(bundle)
        raise SurfaceUnavailable("the Cairo workbook could not be written")


def faithful_renderers() -> tuple[Renderer, ...]:
    return tuple(Renderer(name) for name in REQUIRED_SURFACES)


def renderers_but(failing: Renderer) -> tuple[Renderer, ...]:
    return tuple(
        failing if name == failing.surface else Renderer(name) for name in REQUIRED_SURFACES
    )


def _language(bundle: ReportBundle, language: str) -> SurfaceLanguage:
    return SurfaceLanguage(
        language=language,
        direction=LANGUAGE_DIRECTION[language],
        stated=tuple(
            StatedFigure(figure_id=figure.figure_id, text=figure.renderings[language])
            for figure in bundle.figures
        ),
        caveats=bundle.caveats,
        disclosure=bundle.disclosure(language),
    )
