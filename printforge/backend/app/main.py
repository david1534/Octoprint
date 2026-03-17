"""PrintForge - 3D Printer Control System

Main FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .api import filament, files, history, printer, settings as settings_api, system, timelapse, websocket
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("PrintForge starting up...")

    # Init database
    await init_db()

    # Ensure G-code directory exists
    Path(settings.gcode_dir).mkdir(parents=True, exist_ok=True)

    # Inject controller into API modules
    printer.set_controller(controller)
    websocket.set_controller(controller)

    # Auto-connect to printer if enabled
    await controller.auto_connect()

    logger.info("PrintForge ready at http://%s:%d", settings.host, settings.port)
    yield

    # Shutdown
    logger.info("PrintForge shutting down...")
    await controller.disconnect()
    await close_db()


app = FastAPI(
    title="PrintForge",
    description="3D Printer Control System",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for development (SvelteKit dev server on different port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key auth middleware (enforces auth when a key is configured)
app.add_middleware(APIKeyMiddleware)

# Register API routers
app.include_router(printer.router)
app.include_router(files.router)
app.include_router(system.router)
app.include_router(websocket.router)
app.include_router(history.router)
app.include_router(timelapse.router)
app.include_router(settings_api.router)
app.include_router(filament.router)


@app.get("/api/camera/stream")
async def camera_stream_url(request: Request):
    """Return camera stream URLs for the frontend.

    Provides a direct go2rtc URL (lowest latency) and a proxy fallback.
    The direct URL lets the browser connect straight to go2rtc on port 1984,
    bypassing the Python proxy for near-real-time MJPEG.
    """
    # Extract the hostname/IP the browser used to reach us
    host = request.headers.get("host", "localhost").split(":")[0]
    return {
        "mjpeg": f"http://{host}:1984/api/stream.mjpeg?src=printer_cam",
        "proxy": "/api/camera/mjpeg",
    }


@app.get("/api/camera/mjpeg")
async def camera_mjpeg_proxy():
    """Proxy the MJPEG stream from go2rtc so the browser can access it."""
    upstream = f"{settings.camera_url}/api/stream.mjpeg?src=printer_cam"

    async def stream():
        timeout = httpx.Timeout(connect=10.0, read=None, write=None, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream("GET", upstream) as resp:
                    async for chunk in resp.aiter_bytes(65536):
                        yield chunk
            except (httpx.ReadError, httpx.RemoteProtocolError, httpx.StreamClosed):
                # Stream ended or was interrupted — let client reconnect
                return
            except Exception:
                return

    return StreamingResponse(
        stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Serve built frontend (static files) — MUST be last, catches all routes
frontend_dir = Path(__file__).parent.parent / "frontend" / "build"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
else:
    logger.warning(
        "Frontend build not found at %s. Run 'npm run build' in frontend/",
        frontend_dir,
    )
