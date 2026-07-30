"""Concrete surfaces for one report bundle.

`khepri.rra.bundle` decides what a report says. The modules here decide only
how one surface presents it, and each of them satisfies `SurfaceRenderer` so
the assembler can refuse a surface that presents anything else.
"""

from __future__ import annotations
