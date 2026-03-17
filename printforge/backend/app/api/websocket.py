"""WebSocket endpoint for real-time printer state and terminal."""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..printer.controller import PrinterController

logger = logging.getLogger(__name__)
router = APIRouter()

_controller: Optional[PrinterController] = None


def set_controller(controller: PrinterController) -> None:
    global _controller
    _controller = controller


class ConnectionManager:
    """Manages WebSocket connections and broadcasts state updates."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._broadcast_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            "WebSocket client connected (%d total)", len(self.active_connections)
        )

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(
            "WebSocket client disconnected (%d remaining)",
            len(self.active_connections),
        )

    async def broadcast(self, message: dict) -> None:
        """Send a message to all connected clients."""
        if not self.active_connections:
            return
        data = json.dumps(message)
        disconnected = []
        for ws in self.active_connections:
            try:
                await ws.send_text(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)

    def start_broadcasting(self) -> None:
        if self._broadcast_task is None or self._broadcast_task.done():
            self._broadcast_task = asyncio.create_task(self._broadcast_loop())

    async def _broadcast_loop(self) -> None:
        """Periodically broadcast printer state to all clients."""
        while True:
            try:
                await asyncio.sleep(1.0)
                if _controller and self.active_connections:
                    await self.broadcast({
                        "type": "state",
                        "data": _controller.state.to_dict(),
                    })
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in broadcast loop")
                await asyncio.sleep(1.0)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Validate API key if authentication is enabled
    from ..middleware.auth import verify_api_key
    from ..storage.models import get_setting

    api_key_hash = await get_setting("api_key_hash", "")
    if api_key_hash:
        key = websocket.query_params.get("apikey", "")
        if not key or not verify_api_key(key, api_key_hash):
            await websocket.close(code=4401, reason="Invalid or missing API key")
            return

    await manager.connect(websocket)
    manager.start_broadcasting()

    # Register terminal callback for this client
    async def send_terminal(line: str, direction: str) -> None:
        try:
            await websocket.send_text(json.dumps({
                "type": "terminal",
                "data": {"line": line, "direction": direction},
            }))
        except Exception:
            pass

    # We need a sync wrapper since the protocol callback is sync
    def terminal_callback(line: str, direction: str) -> None:
        try:
            asyncio.get_event_loop().create_task(
                send_terminal(line, direction)
            )
        except RuntimeError:
            pass

    if _controller:
        _controller.add_terminal_callback(terminal_callback)

    try:
        # Send initial state
        if _controller:
            await websocket.send_text(json.dumps({
                "type": "state",
                "data": _controller.state.to_dict(),
            }))

        # Listen for client messages
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                await _handle_client_message(msg, websocket)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "data": {"message": "Invalid JSON"},
                }))
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error")
    finally:
        if _controller:
            _controller.remove_terminal_callback(terminal_callback)
        manager.disconnect(websocket)


async def _handle_client_message(msg: dict, ws: WebSocket) -> None:
    """Handle messages from WebSocket clients."""
    if not _controller:
        return

    msg_type = msg.get("type")

    if msg_type == "command":
        # Send a G-code command from the terminal
        command = msg.get("data", {}).get("gcode", "").strip()
        if command:
            try:
                result = await _controller.send_command(command)
                await ws.send_text(json.dumps({
                    "type": "command_result",
                    "data": {
                        "command": result.command,
                        "response": result.response_lines,
                        "ok": result.ok,
                        "error": result.error,
                    },
                }))
            except Exception as e:
                await ws.send_text(json.dumps({
                    "type": "error",
                    "data": {"message": str(e)},
                }))

    elif msg_type == "ping":
        await ws.send_text(json.dumps({"type": "pong"}))
