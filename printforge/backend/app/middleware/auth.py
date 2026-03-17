"""API key authentication middleware.

When an API key is configured in settings, all API requests (except WebSocket
and a few public endpoints) must include the key as a Bearer token or query
parameter. If no key is set, all requests are allowed (open access).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)

# Endpoints that never require authentication
PUBLIC_PATHS = frozenset({
    "/api/system/health",
    "/docs",
    "/openapi.json",
})

# Prefixes that skip auth (static frontend, websocket handled separately)
PUBLIC_PREFIXES = (
    "/ws",
    "/_app/",
    "/favicon",
)


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return "pf_" + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    """Create a SHA-256 hash of the API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(provided: str, stored_hash: str) -> bool:
    """Constant-time comparison of provided key against stored hash."""
    provided_hash = hashlib.sha256(provided.encode()).hexdigest()
    return hmac.compare_digest(provided_hash, stored_hash)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces API key authentication when configured."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Skip auth for public paths
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # Skip auth for public prefixes (frontend static, websocket)
        for prefix in PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Skip auth for non-API paths (frontend HTML pages)
        if not path.startswith("/api/"):
            return await call_next(request)

        # Check if API key auth is enabled
        from ..storage.models import get_setting

        api_key_hash = await get_setting("api_key_hash", "")
        if not api_key_hash:
            # No key configured = open access
            return await call_next(request)

        # Extract key from Authorization header or query param
        key = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            key = auth_header[7:]
        if not key:
            key = request.query_params.get("apikey", "")

        if not key or not verify_api_key(key, api_key_hash):
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code= 401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)
