"""WebSocket endpoint for real-time printer state and terminal.

Performance improvements over the original:
- Parallel broadcast to all clients via asyncio.gather (slow client
  doesn't block others)
- Batched terminal lines flushed every 100ms instead of creating a
  new asyncio.Task per line (saves hundreds of task creations/sec
  during active prints)
- Dirty-flag state broadcasting: only serializes and sends state
  when it has actually changed
"""

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
        self._last_state_json: str = ""

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket client connected (%d total)", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(
            "WebSocket client disconnected (%d remaining)",
            len(self.active_connections),
        )

    async def broadcast(self, message: dict) -> None:
        """Send a message to all connected clients (parallel)."""
        if not self.active_connections:
            return
        data = json.dumps(message)
        self._broadcast_raw(data)

    def _broadcast_raw(self, data: str) -> None:
        """Fire-and-forget parallel send to all clients."""
        if not self.active_connections:
            return

        async def _send_all():
            results = await asyncio.gather(
                *[ws.send_text(data) for ws in self.active_connections],
                return_exceptions=True,
            )
            disconnected = [
                ws
                for ws, result in zip(self.active_connections, results)
                if isinstance(result, Exception)
            ]
            for ws in disconnected:
                self.disconnect(ws)

        asyncio.create_task(_send_all())

    def start_broadcasting(self) -> None:
        if self._broadcast_task is None or self._broadcast_task.done():
            self._broadcast_task = asyncio.create_task(self._broadcast_loop())

    async def _broadcast_loop(self) -> None:
        """Periodically broadcast printer state to all clients.

        Only serializes and sends when state has actually changed (dirty flag).
        """
        while True:
            try:
                await asyncio.sleep(1.0)
                if _controller and self.active_connections:
                    state_dict = _controller.state.to_dict()
                    state_json = json.dumps({"type": "state", "data": state_dict})
                    # Skip broadcast if state hasn't changed
                    if state_json != self._last_state_json:
                        self._last_state_json = state_json
                        self._broadcast_raw(state_json)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in broadcast loop")
                await asyncio.sleep(1.0)


manager = ConnectionManager()


# ── Batched terminal relay ────────────────────────────────────────
# Instead of creating an asyncio.Task for every terminal line (hundreds
# per second during a print), we buffer lines and flush every 100ms.

_terminal_buffer: list[dict] = []
_terminal_flush_task: Optional[asyncio.Task] = None
_terminal_clients: list[WebSocket] = []


def _buffer_terminal_line(line: str, direction: str) -> None:
    """Sync callback from the printer controller — just appends to the buffer."""
    _terminal_buffer.append({"line": line, "direction": direction})


async def _terminal_flush_loop() -> None:
    """Flush buffered terminal lines to all subscribed clients every 100ms."""
    global _terminal_buffer
    while True:
        try:
            await asyncio.sleep(0.1)
            if not _terminal_buffer or not _terminal_clients:
                continue
            # Atomic swap: grab current buffer and replace with empty list.
            # This prevents the race where _buffer_terminal_line appends
            # between .copy() and .clear(), which would lose the line.
            lines, _terminal_buffer = _terminal_buffer, []
            # Send as a batch message
            data = json.dumps({"type": "terminal_batch", "data": lines})
            results = await asyncio.gather(
                *[ws.send_text(data) for ws in _terminal_clients],
                return_exceptions=True,
            )
            disconnected = [
                ws
                for ws, result in zip(_terminal_clients, results)
                if isinstance(result, Exception)
            ]
            for ws in disconnected:
                if ws in _terminal_clients:
                    _terminal_clients.remove(ws)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Error in terminal flush loop")


def _ensure_terminal_flush_task() -> None:
    """Start the terminal flush background task if not already running."""
    global _terminal_flush_task
    if _terminal_flush_task is None or _terminal_flush_task.done():
        _terminal_flush_task = asyncio.create_task(_terminal_flush_loop())


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

    # Register this client for terminal batches
    _terminal_clients.append(websocket)
    _ensure_terminal_flush_task()

    # Register the shared terminal buffer callback (idempotent — controller
    # deduplicates, but we guard anyway)
    if _controller and _buffer_terminal_line not in _controller._terminal_callbacks:
        _controller.add_terminal_callback(_buffer_terminal_line)

    try:
        # Send initial state
        if _controller:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "state",
                        "data": _controller.state.to_dict(),
                    }
                )
            )

        # Listen for client messages
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                await _handle_client_message(msg, websocket)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "data": {"message": "Invalid JSON"},
                        }
                    )
                )
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error")
    finally:
        if websocket in _terminal_clients:
            _terminal_clients.remove(websocket)
        # Only remove the shared callback when no clients remain
        if not _terminal_clients and _controller:
            _controller.remove_terminal_callback(_buffer_terminal_line)
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
                await ws.send_text(
                    json.dumps(
                        {
                            "type": "command_result",
                            "data": {
                                "command": result.command,
                                "response": result.response_lines,
                                "ok": result.ok,
                                "error": result.error,
                            },
                        }
                    )
                )
            except Exception as e:
                await ws.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "data": {"message": str(e)},
                        }
                    )
                )

    elif msg_type == "ping":
        await ws.send_text(json.dumps({"type": "pong"}))
