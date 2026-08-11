"""Hash-derived random streams: structural randomness that never depends on
call order (per-receiver bias, fading fields, per-tag phase, batch stagger).
Same (seed, *parts) -> same stream, always."""

from __future__ import annotations

import hashlib
import random


def make_stream(seed: int, *parts) -> random.Random:
    h = hashlib.sha256(
        ("%d|" % seed + "|".join(str(p) for p in parts)).encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))
