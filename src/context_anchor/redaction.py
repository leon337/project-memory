"""Central, fail-closed redaction for persisted and operator-visible data.

The runtime still keeps the original values in memory while it executes and
verifies a goal.  This module is for trust-boundary crossings only: result
payloads, logs and the small cross-task context store.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit


_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_SECRET_ASSIGNMENT = re.compile(
    r"(?ix)"
    r"\b("
    r"api[_-]?key|access[_-]?token|auth(?:orization)?|bearer[_-]?token|"
    r"client[_-]?secret|password|passwd|private[_-]?key|secret|token|"
    r"aws[_-]?access[_-]?key[_-]?id|aws[_-]?secret[_-]?access[_-]?key|"
    r"cloudflare[_-]?api[_-]?token|gemini[_-]?api[_-]?key|zai[_-]?api[_-]?key"
    r")"
    r"(\s*(?::|=)\s*)"
    r"(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_AUTHORIZATION_SCHEME = re.compile(
    r"(?i)\bAuthorization\s*[:=]\s*(?:Bearer|Basic)\s+[^\s,;]+"
)
_OPENAI_STYLE_KEY = re.compile(r"(?i)\bsk-[a-z0-9_-]{6,}\b")
_GITHUB_TOKEN = re.compile(
    r"(?i)\b(?:gh[pousr]_[a-z0-9]{10,}|github_pat_[a-z0-9_]{10,})\b"
)
_JWT = re.compile(
    r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\b"
)
_BARE_TOKEN = re.compile(r"(?i)\b(token\s+)([a-z0-9._~+/-]{8,})\b")
_GOOGLE_API_KEY = re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")
_AWS_ACCESS_KEY = re.compile(
    r"\b(?:AKIA|ASIA|AIDA|AROA|AIPA|ANPA|ANVA|ASCA)[A-Z0-9]{16}\b"
)
_PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?"
    r"-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
_TRAILING_URL_PUNCTUATION = ".,;:!?)]}"


def redact_url(value: str) -> str:
    """Expose only a URL's origin and whether a path/query was present.

    Userinfo, path segments, query names and values, and fragments can all
    carry credentials or user text.  None of them cross a persistence/logging
    boundary.
    """

    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        if parsed.scheme.casefold() not in {"http", "https"} or not hostname:
            return "[redacted-url]"
        port = parsed.port
    except ValueError:
        return "[redacted-url]"

    display_host = f"[{hostname}]" if ":" in hostname else hostname
    authority = f"{display_host}:{port}" if port is not None else display_host
    redacted = f"{parsed.scheme.casefold()}://{authority}"
    if parsed.path == "/":
        redacted += "/"
    elif parsed.path:
        redacted += "/[redacted-path]"
    if parsed.query:
        redacted += "?[redacted]"
    return redacted


def _redact_url_match(match: re.Match[str]) -> str:
    candidate = match.group(0)
    url = candidate.rstrip(_TRAILING_URL_PUNCTUATION)
    suffix = candidate[len(url) :]
    return f"{redact_url(url)}{suffix}"


def redact_text(value: str, *, max_chars: int | None = None) -> str:
    """Redact recognized credentials and sensitive URL components."""

    if not isinstance(value, str):
        raise TypeError("value must be a string")
    redacted = _URL.sub(_redact_url_match, value)
    redacted = _PRIVATE_KEY.sub("[redacted-private-key]", redacted)
    redacted = _AUTHORIZATION_SCHEME.sub("Authorization: [redacted]", redacted)
    # Redact the complete bearer credential before the generic assignment
    # matcher can consume only the word "Bearer" after ``Authorization:``.
    redacted = _BEARER.sub("Bearer [redacted]", redacted)
    redacted = _SECRET_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[redacted]",
        redacted,
    )
    redacted = _OPENAI_STYLE_KEY.sub("[redacted-api-key]", redacted)
    redacted = _GITHUB_TOKEN.sub("[redacted-github-token]", redacted)
    redacted = _JWT.sub("[redacted-jwt]", redacted)
    redacted = _BARE_TOKEN.sub(r"\1[redacted]", redacted)
    redacted = _GOOGLE_API_KEY.sub("[redacted-api-key]", redacted)
    redacted = _AWS_ACCESS_KEY.sub("[redacted-aws-access-key]", redacted)
    return redacted if max_chars is None else redacted[:max_chars]


def redact_value(value: Any, *, depth: int = 0) -> Any:
    """Recursively redact a small JSON-compatible public value."""

    if depth >= 3:
        return redact_text(str(value), max_chars=240)
    if isinstance(value, str):
        return redact_text(value, max_chars=800)
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    if isinstance(value, dict):
        return {
            redact_text(str(key), max_chars=80): redact_value(item, depth=depth + 1)
            for key, item in list(value.items())[:20]
        }
    if isinstance(value, (list, tuple)):
        return [redact_value(item, depth=depth + 1) for item in value[:12]]
    return redact_text(str(value), max_chars=400)


def redact_payload(value: Any) -> Any:
    """Redact a persisted JSON payload without dropping valid fields/items."""

    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    if isinstance(value, dict):
        return {
            redact_text(str(key)): redact_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_payload(item) for item in value]
    return redact_text(str(value))


def contains_sensitive_data(value: str) -> bool:
    """Return whether storing ``value`` would preserve sensitive material."""

    if not isinstance(value, str):
        return False
    return redact_text(value) != value


def redact_exception(exc: BaseException) -> str:
    """Return an exception diagnostic safe for payloads and logs."""

    return f"{type(exc).__name__}: {redact_text(str(exc), max_chars=600)}"


__all__ = [
    "contains_sensitive_data",
    "redact_exception",
    "redact_payload",
    "redact_text",
    "redact_url",
    "redact_value",
]
