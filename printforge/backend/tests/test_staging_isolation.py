"""Integration coverage for staging/production host isolation."""

import asyncio
import os
import shutil
import subprocess
from pathlib import Path
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
    "/api/system/promote/rollback",
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
        for path in HOST_PATHS[:3]:
            response = await client.post(path)
            assert response.status_code == 409
        monkeypatch.setattr(system.settings, "promotion_token", "promotion-secret")
        for path in HOST_PATHS[3:]:
            response = await client.post(
                path,
                headers={"X-PrintForge-Promotion-Token": "promotion-secret"},
            )
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

    @app.get("/api/system/health")
    async def health():
        return {"status": "ok"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://staging") as client:
        response = await client.get("/api/printer/state")
        health_response = await client.get("/api/system/health")

    assert response.status_code == 503
    assert health_response.status_code == 503
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


@pytest.mark.parametrize(
    "status",
    [
        PrinterStatus.PRINTING,
        PrinterStatus.PAUSED,
        PrinterStatus.FINISHING,
        PrinterStatus.ERROR,
        PrinterStatus.CONNECTING,
        "unknown",
        None,
        {},
    ],
)
def test_host_operations_reject_every_non_safe_or_malformed_state(monkeypatch, status):
    monkeypatch.setattr(
        printer_api,
        "_controller",
        SimpleNamespace(state=SimpleNamespace(status=status)),
    )

    with pytest.raises(HTTPException) as exc_info:
        system._require_safe_production_state()

    assert exc_info.value.status_code == 409


@pytest.mark.parametrize("status", [PrinterStatus.IDLE, PrinterStatus.DISCONNECTED])
def test_host_operations_accept_only_exact_safe_states(monkeypatch, status):
    monkeypatch.setattr(
        printer_api,
        "_controller",
        SimpleNamespace(state=SimpleNamespace(status=status)),
    )

    assert system._require_safe_production_state() == status.value


def test_host_operations_reject_missing_status_as_unverifiable(monkeypatch):
    monkeypatch.setattr(
        printer_api,
        "_controller",
        SimpleNamespace(state=SimpleNamespace()),
    )

    with pytest.raises(HTTPException) as exc_info:
        system._require_safe_production_state()

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_promote_requires_separate_token_and_force_cannot_bypass(monkeypatch):
    monkeypatch.setattr(system.settings, "promotion_token", "promotion-secret")
    monkeypatch.setattr(
        printer_api,
        "_controller",
        SimpleNamespace(state=PrinterState(status=PrinterStatus.PRINTING)),
    )
    stage_release = AsyncMock()
    monkeypatch.setattr(system, "_stage_release", stage_release)

    app = _system_app("production", mock_serial=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://production") as client:
        missing = await client.post("/api/system/promote")
        wrong = await client.post(
            "/api/system/promote",
            headers={"X-PrintForge-Promotion-Token": "wrong"},
        )
        forced = await client.post(
            "/api/system/promote?force=true",
            headers={"X-PrintForge-Promotion-Token": "promotion-secret"},
        )

    assert missing.status_code == 403
    assert wrong.status_code == 403
    assert forced.status_code == 409
    stage_release.assert_not_awaited()


@pytest.mark.asyncio
async def test_promotion_is_disabled_when_privileged_token_is_unconfigured(monkeypatch):
    monkeypatch.setattr(system.settings, "promotion_token", "")
    monkeypatch.setattr(
        printer_api,
        "_controller",
        SimpleNamespace(state=PrinterState(status=PrinterStatus.IDLE)),
    )

    app = _system_app("production", mock_serial=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://production") as client:
        response = await client.post("/api/system/promote")

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_subprocess_timeout_terminates_command(monkeypatch):
    class HangingProcess:
        returncode = None

        def __init__(self):
            self.terminate = MagicMock()
            self.kill = MagicMock()
            self.wait = AsyncMock(return_value=0)

        async def communicate(self):
            await asyncio.sleep(60)

    process = HangingProcess()
    monkeypatch.setattr(
        system.asyncio,
        "create_subprocess_exec",
        AsyncMock(return_value=process),
    )

    rc, output = await system._run(["rsync"], timeout=0.001)

    assert rc == 124
    assert "timed out" in output.lower()
    process.terminate.assert_called_once()
    process.kill.assert_not_called()


def test_release_pointer_switch_is_atomic_and_retains_previous(monkeypatch, tmp_path):
    if os.name == "nt":
        pytest.skip("Windows test users cannot create symlinks without elevation")

    releases = tmp_path / "releases"
    releases.mkdir()
    old_release = releases / "old"
    new_release = releases / "new"
    old_release.mkdir()
    new_release.mkdir()
    current = tmp_path / "current"
    previous = tmp_path / "previous"
    monkeypatch.setattr(system, "RELEASES_ROOT", releases)

    system._atomic_release_link(old_release, current)
    system._atomic_release_link(old_release, previous)
    system._atomic_release_link(new_release, current)

    assert system._release_target(current) == new_release.resolve()
    assert system._release_target(previous) == old_release.resolve()


def test_promotion_refuses_legacy_service_working_directory(monkeypatch, tmp_path):
    current = (tmp_path / "releases" / "current-release").resolve()
    legacy = (tmp_path / "legacy" / "app" / "api" / "system.py").resolve()
    monkeypatch.setattr(system, "_release_target", lambda _link: current)
    monkeypatch.setattr(system, "__file__", str(legacy))

    with pytest.raises(HTTPException) as exc_info:
        system._require_active_release_layout()

    assert exc_info.value.status_code == 503


def test_promotion_accepts_process_running_from_current_release(monkeypatch, tmp_path):
    current = (tmp_path / "releases" / "current-release").resolve()
    module_path = current / "app" / "api" / "system.py"
    monkeypatch.setattr(system, "_release_target", lambda _link: current)
    monkeypatch.setattr(system, "__file__", str(module_path))

    assert system._require_active_release_layout() == current


@pytest.mark.parametrize(
    ("body", "status_code", "should_succeed"),
    [
        ('{"status":"promoted"}', "200", True),
        ("not-json", "200", False),
        ("{}", "200", False),
        ('{"status":"promoted"}', "500", False),
        ('{"detail":"Invalid or missing API key"}', "401", False),
    ],
)
def test_promotion_shell_rejects_malformed_and_non_200_responses(
    tmp_path, body, status_code, should_succeed
):
    bash = shutil.which("bash")
    if bash is None or os.name == "nt":
        pytest.skip("Behavioral shell test requires bash on a POSIX host")

    fake_curl = tmp_path / "curl"
    fake_curl.write_text(
        '#!/bin/sh\nprintf \'%s\\n%s\\n\' "$FAKE_BODY" "$FAKE_STATUS"\n',
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)
    script = Path(__file__).resolve().parents[2] / "scripts" / "promote-staging.sh"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{tmp_path}{os.pathsep}{env['PATH']}",
            "PRINTFORGE_PROMOTION_TOKEN": "test-token",
            "FAKE_BODY": body,
            "FAKE_STATUS": status_code,
        }
    )

    result = subprocess.run(
        [bash, str(script)],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert (result.returncode == 0) is should_succeed
