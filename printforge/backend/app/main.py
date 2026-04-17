from __future__ import annotations
"""PrintForge - 3D Printer Control System

Main FastAPI application entry point.
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from .api import (
    errors as errors_api,
    filament,
    files,
    history,
    notifications,
    octoprint_compat,
    printer,
    settings as settings_api,
    system,
    timelapse,
    websocket,
)
from .config import settings
from .middleware.auth import APIKeyMiddleware
from .printer.controller import PrinterController
from .printer.state import PrinterState
from .storage.database import close_db, init_db

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Shared state
state = PrinterState()
controller = PrinterController(state)

# Persistent HTTP client for camera proxying (reused across requests)
_camera_client: httpx.AsyncClient | None = None

# Frame cache: avoid re-fetching from ustreamer for rapid snapshot polling
_frame_cache: bytes | None = None
_frame_cache_time: float = 0
_frame_cache_lock: asyncio.Lock | None = None
_FRAME_CACHE_TTL = 0.03  # 30ms — limits ustreamer hits to ~33fps max


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    global _camera_client, _frame_cache_lock
    logger.info("PrintForge starting up...")
    _frame_cache_lock = asyncio.Lock()

    # Init database
    await init_db()

    # Ensure G-code directory exists
    Path(settings.gcode_dir).mkdir(parents=True, exist_ok=True)

    # Inject controller into API modules
    printer.set_controller(controller)
    websocket.set_controller(controller)
    errors_api.set_controller(controller)

    # Initialize camera service + timelapse recorder
    timelapse_dir = Path(settings.data_dir).parent / "timelapse"
    timelapse_dir.mkdir(parents=True, exist_ok=True)
    await controller.init_camera_and_timelapse(settings.camera_url, timelapse_dir)
    if controller.timelapse:
        await controller.timelapse.load_settings()
        timelapse.set_recorder(controller.timelapse)

    # Create persistent camera HTTP client (used by MJPEG proxy + snapshot)
    _camera_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=3.0, read=None, write=5.0, pool=5.0)
    )

    # Auto-connect to printer if enabled
    await controller.auto_connect()

    logger.info("PrintForge ready at http://%s:%d", settings.host, settings.port)
    yield

    # Shutdown
    logger.info("PrintForge shutting down...")
    if _camera_client:
        await _camera_client.aclose()
    if controller.camera:
        await controller.camera.close()
    await controller.disconnect()
    await close_db()


app = FastAPI(
    title="PrintForge",
    description="3D Printer Control System",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — restrict origins in production to prevent cross-site printer control.
# Set PRINTFORGE_CORS_ORIGINS env var to a comma-separated list of allowed
# origins (e.g. "http://100.108.194.105:8000,http://printforge.local:8000").
# Defaults to "*" for development convenience.
_cors_origins_raw = os.environ.get("PRINTFORGE_CORS_ORIGINS", "*")
_cors_origins = (
    ["*"] if _cors_origins_raw.strip() == "*"
    else [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip compression for JSON API responses (reduces bandwidth on Pi WiFi).
# Skips camera paths to avoid compressing JPEG/MJPEG binary data which
# wastes CPU (significant on Pi) for negligible size reduction.


class SelectiveGZipMiddleware:
    """GZip middleware that skips binary camera endpoints."""

    def __init__(self, app: ASGIApp, minimum_size: int = 500):
        self._gzip = GZipMiddleware(app, minimum_size=minimum_size)
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            # Skip GZip for camera endpoints (binary JPEG/MJPEG)
            if path.startswith("/api/camera/"):
                await self._app(scope, receive, send)
                return
        await self._gzip(scope, receive, send)


app.add_middleware(SelectiveGZipMiddleware, minimum_size=500)

# API key auth middleware (enforces auth when a key is configured)
app.add_middleware(APIKeyMiddleware)

# Register API routers
app.include_router(printer.router)
app.include_router(files.router)
app.include_router(octoprint_compat.router)
app.include_router(system.router)
app.include_router(websocket.router)
app.include_router(history.router)
app.include_router(timelapse.router)
app.include_router(settings_api.router)
app.include_router(filament.router)
app.include_router(errors_api.router)
app.include_router(notifications.router)


# ── Camera endpoints ─────────────────────────────────────────────


@app.get("/api/camera/stream")
async def camera_stream_url(request: Request):
    """Return camera stream URLs for the frontend.

    Returns a direct ustreamer URL for MJPEG streaming (the browser
    connects directly via Tailscale — no proxy needed, no auth issues)
    plus the proxied snapshot URL as a fallback.
    """
    host = request.headers.get("host", "localhost").split(":")[0]
    return {
        "mjpeg": f"http://{host}:8080/stream",
        "snapshot": "/api/camera/snapshot",
    }


@app.get("/api/camera/mjpeg")
async def camera_mjpeg_proxy():
    """Proxy ustreamer's MJPEG stream (fallback if direct access fails)."""
    stream_url = f"{settings.camera_url}/stream"

    # Use a dedicated client per MJPEG stream (the stream is long-lived
    # and must be closed independently of other requests)
    client = httpx.AsyncClient(timeout=httpx.Timeout(connect=3.0, read=None, write=5.0, pool=5.0))

    try:
        resp = await client.send(
            client.build_request("GET", stream_url),
            stream=True,
        )
    except Exception:
        await client.aclose()
        return JSONResponse(content={"error": "Camera unavailable"}, status_code=503)

    if resp.status_code != 200:
        await resp.aclose()
        await client.aclose()
        return JSONResponse(content={"error": "Camera unavailable"}, status_code=503)

    content_type = resp.headers.get("content-type", "multipart/x-mixed-replace; boundary=--frame")

    async def stream():
        try:
            async for chunk in resp.aiter_bytes(chunk_size=32768):
                yield chunk
        except (httpx.ReadError, httpx.TimeoutException, asyncio.CancelledError):
            pass
        finally:
            await resp.aclose()
            await client.aclose()

    return StreamingResponse(
        stream(),
        media_type=content_type,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/camera/snapshot")
async def camera_snapshot():
    """Return a single JPEG snapshot from ustreamer.

    Uses a frame cache to avoid hammering ustreamer on rapid polling.
    Multiple frontend requests within the TTL window get the same frame.
    """
    global _frame_cache, _frame_cache_time

    now = time.monotonic()

    # Serve cached frame if fresh enough
    if _frame_cache and (now - _frame_cache_time) < _FRAME_CACHE_TTL:
        return Response(
            content=_frame_cache,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-cache, no-store"},
        )

    # Fetch a new frame (serialized to avoid thundering herd)
    jpg: bytes | None = None
    if _frame_cache_lock:
        async with _frame_cache_lock:
            # Double-check: another coroutine may have refreshed while we waited
            if _frame_cache and (time.monotonic() - _frame_cache_time) < _FRAME_CACHE_TTL:
                jpg = _frame_cache
            else:
                jpg = await _fetch_snapshot()
                if jpg:
                    _frame_cache = jpg
                    _frame_cache_time = time.monotonic()
    else:
        jpg = await _fetch_snapshot()

    if jpg:
        return Response(
            content=jpg,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-cache, no-store"},
        )
    return JSONResponse({"error": "Camera unavailable"}, status_code=503)


async def _fetch_snapshot() -> bytes | None:
    """Fetch a JPEG frame from ustreamer's snapshot endpoint."""
    try:
        if _camera_client:
            resp = await _camera_client.get(f"{settings.camera_url}/snapshot")
            if resp.status_code == 200 and len(resp.content) > 100:
                return resp.content
    except Exception:
        pass
    # Fallback: use camera service's full chain (ffmpeg direct, fswebcam)
    if controller.camera:
        return await controller.camera.snapshot()
    return None


# Serve built frontend — MUST be last, catches all routes.
# Uses a custom SPAStaticFiles class that returns index.html for unknown
# paths instead of 404, enabling SvelteKit client-side routing to work
# when the user refreshes on /control, /files, etc.
frontend_dir = Path(__file__).parent.parent / "frontend" / "build"
if frontend_dir.exists():

    class SPAStaticFiles(StaticFiles):
        """StaticFiles with SPA fallback — serves index.html for unknown paths."""

        async def get_response(self, path: str, scope) -> Response:
            try:
                return await super().get_response(path, scope)
            except Exception:
                # Path not found as a static file — serve SPA entry point
                return await super().get_response("index.html", scope)

    app.mount("/", SPAStaticFiles(directory=str(frontend_dir), html=True), name="frontend")
else:
    logger.warning(
        "Frontend build not found at %s. Run 'npm run build' in frontend/",
        frontend_dir,
    )
