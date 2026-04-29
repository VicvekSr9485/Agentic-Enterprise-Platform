"""
Bearer-token auth middleware.

If PLATFORM_API_KEY is set, every request to /orchestrator and /{agent}/a2a
endpoints must include `Authorization: Bearer <key>`. Other paths (health,
docs, agent cards) are public.

A user_id is derived from the token (sha256, truncated) so HITL approvals
and ADK sessions can be scoped per caller without leaking the raw token.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Iterable

from fastapi import Request
from fastapi.responses import JSONResponse

from shared.logging_utils import get_logger

logger = get_logger("shared.auth")

PUBLIC_PATH_PREFIXES: tuple[str, ...] = (
    "/",
    "/health",
    "/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
)

# Paths that are public exact-matches OR end with these suffixes.
PUBLIC_PATH_SUFFIXES: tuple[str, ...] = (
    "/.well-known/agent-card.json",
)


def _path_is_public(path: str) -> bool:
    if path in PUBLIC_PATH_PREFIXES:
        return True
    for suffix in PUBLIC_PATH_SUFFIXES:
        if path.endswith(suffix):
            return True
    return False


def _allowed_keys() -> list[str]:
    """Return the set of accepted bearer tokens.

    PLATFORM_API_KEY may contain a comma-separated list to allow rotation.
    """
    raw = os.getenv("PLATFORM_API_KEY", "")
    return [k.strip() for k in raw.split(",") if k.strip()]


def derive_user_id(token: str | None) -> str:
    """Stable, non-reversible identifier per token. Anonymous when token is None."""
    if not token:
        return "anonymous"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"u_{digest[:16]}"


def _matches_any(token: str, allowed: Iterable[str]) -> bool:
    for candidate in allowed:
        if hmac.compare_digest(token, candidate):
            return True
    return False


async def bearer_auth_middleware(request: Request, call_next):
    """FastAPI middleware enforcing bearer-token auth where configured."""
    allowed = _allowed_keys()
    path = request.url.path

    # Auth disabled (no PLATFORM_API_KEY) → behave like before, anonymous user_id.
    if not allowed:
        request.state.user_id = derive_user_id(None)
        return await call_next(request)

    # Public paths skip auth.
    if _path_is_public(path):
        # If a token is present, still bind user_id so logging stays consistent.
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer ") else None
        request.state.user_id = derive_user_id(token if (token and _matches_any(token, allowed)) else None)
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.info("auth_missing_bearer", path=path)
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized", "message": "Missing Authorization: Bearer <token> header"},
        )

    token = auth_header.removeprefix("Bearer ").strip()
    if not _matches_any(token, allowed):
        logger.info("auth_invalid_token", path=path)
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized", "message": "Invalid bearer token"},
        )

    request.state.user_id = derive_user_id(token)
    return await call_next(request)
