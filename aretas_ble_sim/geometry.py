"""2D segment geometry for the virtual-building RF model.

Pure stdlib — the whole simulator deliberately avoids numpy so it can run
anywhere the API wrapper runs.
"""

from __future__ import annotations

import math

Point = tuple[float, float]


def _orient(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    """Signed area orientation of C relative to segment A->B."""
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _on_segment(a: Point, b: Point, c: Point) -> bool:
    """True when collinear point c lies within the bounding box of a-b."""
    return (min(a[0], b[0]) - 1e-9 <= c[0] <= max(a[0], b[0]) + 1e-9
            and min(a[1], b[1]) - 1e-9 <= c[1] <= max(a[1], b[1]) + 1e-9)


def segments_intersect(p1: Point, p2: Point, q1: Point, q2: Point) -> bool:
    """Segment p1-p2 crosses segment q1-q2 (touching an endpoint counts —
    a ray grazing a wall end is still 'through the wall' for RF purposes)."""
    d1 = _orient(*q1, *q2, *p1)
    d2 = _orient(*q1, *q2, *p2)
    d3 = _orient(*p1, *p2, *q1)
    d4 = _orient(*p1, *p2, *q2)

    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return True

    if abs(d1) < 1e-12 and _on_segment(q1, q2, p1):
        return True
    if abs(d2) < 1e-12 and _on_segment(q1, q2, p2):
        return True
    if abs(d3) < 1e-12 and _on_segment(p1, p2, q1):
        return True
    if abs(d4) < 1e-12 and _on_segment(p1, p2, q2):
        return True
    return False


def distance3(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def point_in_rect(x: float, y: float, x0: float, y0: float, x1: float, y1: float) -> bool:
    return x0 - 1e-9 <= x <= x1 + 1e-9 and y0 - 1e-9 <= y <= y1 + 1e-9
