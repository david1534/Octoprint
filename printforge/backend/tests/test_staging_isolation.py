"""Integration coverage for staging/production host isolation."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from app.api import printer as printer_api
from app.api import settings as settings_api
from app.api import system
from app.api import websocket as websocket_api
from app.middleware import auth
from app.printer.state import PrinterState, PrinterStatus

HOST_PATHS = (
    "/api/system/restart-service",
    "/api/system/restart-os",
    "/api/system/shutdown-os",
    "/api/system/promote",
)


def _system_app(environment: str, mock_serial: bool) -> FastAPI:
    app = FastAPI()
    system.register_routers(app, environment, mock_serial)
    return app


@pytest.mark.asyncio
async def test_staging_idle_cannot_reach_host_controls_while_production_prints(
    monkeypatch,
):
    """The staging process has no destructive route to authorize locally."""
    staging_state = PrinterState(status=PrinterStatus.IDLE)
    production = SimpleNamespace(
        state=PrinterState(status=PrinterStatus.PRINTING),
    )
    monkeypatch.setattr(printer_api, "_controller", production)
    popen = MagicMock()
    monkeypatch.setattr(system.subprocess, "Popen", popen)

    staging_app = _system_app("staging", mock_serial=True)
    transport = httpx.ASGITransport(app=staging_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://staging") as client:
        for path in HOST_PATHS:
            response = await client.post(path)
            assert response.status_code == 404

    assert staging_state.status is PrinterStatus.IDLE
    assert production.state.status is PrinterStatus.PRINTING
    popen.assert_not_called()


@pytest.mark.asyncio
async def test_production_owned_host_controls_check_production_controller(monkeypatch):
    production = SimpleNamespace(
        state=PrinterState(status=PrinterStatus.PRINTING),
    )
    monkeypatch.setattr(printer_api, "_controller", production)
    popen = MagicMock()
    monkeypatch.setattr(system.subprocess, "Popen", popen)

    production_app = _system_app("production", mock_serial=False)
    transport = httpx.ASGITransport(app=production_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://production") as client:
        for path in HOST_PATHS:
            response = await client.post(path)
            assert response.status_code == 409

    popen.assert_not_called()


@pytest.mark.asyncio
async def test_host_controls_fail_closed_when_controller_is_unavailable(monkeypatch):
    monkeypatch.setattr(printer_api, "_controller", None)
    popen = MagicMock()
    monkeypatch.setattr(system.subprocess, "Popen", popen)

    production_app = _system_app("production", mock_serial=False)
    transport = httpx.ASGITransport(app=production_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://production") as client:
        response = await client.post("/api/system/restart-service")

    assert response.status_code == 503
    popen.assert_not_called()


@pytest.mark.asyncio
async def test_staging_http_api_fails_closed_without_key(monkeypatch):
    from app.storage import models

    monkeypatch.setattr(auth.settings, "environment", "staging")
    monkeypatch.setattr(models, "get_setting", AsyncMock(return_value=""))
    auth.APIKeyMiddleware.invalidate_api_key_cache()

    app = FastAPI()
    app.add_middleware(auth.APIKeyMiddleware)

    @app.get("/api/printer/state")
    async def printer_state():
        return {"status": "idle"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://staging") as client:
        response = await client.get("/api/printer/state")

    assert response.status_code == 503
    assert "authentication is required" in response.json()["detail"].lower()
    auth.APIKeyMiddleware.invalidate_api_key_cache()


@pytest.mark.asyncio
async def test_staging_websocket_fails_closed_without_key(monkeypatch):
    from app.storage import models

    monkeypatch.setattr(websocket_api.settings, "environment", "staging")
    monkeypatch.setattr(models, "get_setting", AsyncMock(return_value=""))
    socket = MagicMock()
    socket.close = AsyncMock()

    await websocket_api.websocket_endpoint(socket)

    socket.close.assert_awaited_once_with(
        code=4401,
        reason="Staging authentication is required but no API key is configured",
    )


@pytest.mark.asyncio
async def test_staging_api_key_cannot_be_revoked(monkeypatch):
    monkeypatch.setattr(settings_api.app_settings, "environment", "staging")

    with pytest.raises(HTTPException) as exc_info:
        await settings_api.revoke_api_key()

    assert exc_info.value.status_code == 403
