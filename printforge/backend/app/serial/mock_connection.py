"""In-process mock of SerialConnection for development and CI.

Enabled by setting PRINTFORGE_MOCK_SERIAL=1. Lets the full backend
(controller, protocol, queue, API, WebSocket) run end-to-end against
MockMarlinPrinter without a physical printer attached.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .mock import MockMarlinPrinter

logger = logging.getLogger(__name__)


class MockSerialConnection:
    """Drop-in replacement for SerialConnection backed by MockMarlinPrinter."""

    def __init__(self, port: str = "mock", baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self._printer: Optional[MockMarlinPrinter] = None
        self._connected = False
        self._lock = asyncio.Lock()
        self._pending: set[asyncio.Task] = set()

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> bool:
        async with self._lock:
            if self._connected:
                return True
            logger.info("Mock serial: simulating connect to %s @ %d", self.port, self.baudrate)
            self._printer = MockMarlinPrinter()
            await self._printer.start()
            self._connected = True
            return True

    async def disconnect(self) -> None:
        async with self._lock:
            if self._printer:
                await self._printer.stop()
            for task in list(self._pending):
                task.cancel()
            self._pending.clear()
            self._printer = None
            self._connected = False
            logger.info("Mock serial: disconnected")

    async def send(self, command: str) -> None:
        if not self._connected or not self._printer:
            raise ConnectionError("Not connected to printer (mock)")
        # Run process_command as a background task — M109/M190 await internally
        # while heating, which would otherwise block the sender.
        task = asyncio.create_task(self._printer.process_command(command))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)
        logger.debug("TX (mock): %s", command.strip())

    async def read_line(self, timeout: float = 10.0) -> str:
        if not self._connected or not self._printer:
            raise ConnectionError("Not connected to printer (mock)")
        try:
            line = await asyncio.wait_for(self._printer.read_response(), timeout=timeout)
        except asyncio.TimeoutError:
            raise
        if line:
            logger.debug("RX (mock): %s", line)
        return line

    @staticmethod
    def list_ports() -> list[str]:
        return ["mock"]
