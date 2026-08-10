from __future__ import annotations

import re


_EXACT_WRITE_MODIFIER_RE = re.compile(r"^exatamente\s*[:,-]?\s*", re.IGNORECASE)


def strip_exact_write_modifier(value: str) -> str:
    """Remove the instruction modifier `exatamente` from a write payload.

    The modifier describes how the downstream text must be preserved; it is not
    itself part of the requested payload.
    """

    return _EXACT_WRITE_MODIFIER_RE.sub("", value.strip(), count=1)


__all__ = ["strip_exact_write_modifier"]
