"""Regression tests for WebSocket command acknowledgements."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.api import websocket


async def test_command_result_does_not_repeat_terminal_response(monkeypatch):
    result = SimpleNamespace(
        command="M105",
        response_lines=["ok T:200.0 /200.0 B:60.0 /60.0"],
        ok=True,
        error=None,
    )
    controller = SimpleNamespace(send_command=AsyncMock(return_value=result))
    client = SimpleNamespace(send_text=AsyncMock())
    monkeypatch.setattr(websocket, "_controller", controller)

    await websocket._handle_client_message(
        {"type": "command", "data": {"gcode": "M105"}},
        client,
    )

    payload = json.loads(client.send_text.await_args.args[0])
    assert payload == {
        "type": "command_result",
        "data": {"command": "M105", "ok": True, "error": None},
    }
