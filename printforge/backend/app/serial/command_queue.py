"""Priority command queue for serializing printer access.

Multiple sources generate commands simultaneously (UI jog, print job,
temperature polling, emergency stop). This queue ensures:
1. Only one command is sent at a time
2. Emergency commands always go first
3. Print commands can be paused/resumed
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from .protocol import CommandResult, MarlinProtocol

logger = logging.getLogger(__name__)


class CommandPriority(IntEnum):
    EMERGENCY = 0
    SAFETY = 1
    SYSTEM = 2
    PRINT = 3
    USER = 4


@dataclass(order=True)
class QueuedCommand:
    priority: CommandPriority
    timestamp: float = field(compare=True)
    command: str = field(compare=False)
    with_checksum: bool = field(compare=False, default=False)
    future: asyncio.Future = field(compare=False, default=None)


class CommandQueue:
    """Thread-safe priority queue for printer commands."""

    def __init__(self, protocol: MarlinProtocol):
        self._protocol = protocol
        self._queue: asyncio.PriorityQueue[QueuedCommand] = asyncio.PriorityQueue()
        self._paused = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Start unpaused
        self._processing = False
        self._task: Optional[asyncio.Task] = None

    @property
    def is_paused(self) -> bool:
        return self._paused

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._processing = True
            self._task = asyncio.create_task(self._process_loop())
            logger.info("Command queue started")

    def stop(self) -> None:
        self._processing = False
        if self._task:
            self._task.cancel()

    def pause(self) -> None:
        self._paused = True
        self._pause_event.clear()
        logger.info("Command queue paused")

    def resume(self) -> None:
        self._paused = False
        self._pause_event.set()
        logger.info("Command queue resumed")

    async def clear(self) -> None:
        cleared = 0
        while not self._queue.empty():
            try:
                cmd = self._queue.get_nowait()
                if cmd.future and not cmd.future.done():
                    cmd.future.cancel()
                cleared += 1
            except asyncio.QueueEmpty:
                break
        logger.info("Cleared %d commands from queue", cleared)

    async def enqueue(
        self,
        command: str,
        priority: CommandPriority = CommandPriority.USER,
        with_checksum: bool = False,
    ) -> asyncio.Future:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        queued = QueuedCommand(
            priority=priority,
            timestamp=time.monotonic(),
            command=command,
            with_checksum=with_checksum,
            future=future,
        )
        await self._queue.put(queued)
        return future

    async def _process_loop(self) -> None:
        logger.info("Command processing loop started")
        while self._processing:
            try:
                queued = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # Drain unsolicited serial data (M155 auto-reports, etc.)
                # so temperature readings stay fresh between commands.
                try:
                    await self._protocol.drain_unsolicited()
                except Exception:
                    pass
                continue
            except asyncio.CancelledError:
                break
            if self._paused and queued.priority == CommandPriority.PRINT:
                # Put the print command back and wait for resume instead
                # of busy-looping (saves CPU during long pauses)
                await self._queue.put(queued)
                await self._pause_event.wait()
                continue
            try:
                result = await self._protocol.send_command(
                    queued.command, with_checksum=queued.with_checksum
                )
                if queued.future and not queued.future.done():
                    queued.future.set_result(result)
            except asyncio.CancelledError:
                if queued.future and not queued.future.done():
                    queued.future.cancel()
                break
            except Exception as e:
                logger.exception("Error processing command: %s", queued.command)
                if queued.future and not queued.future.done():
                    queued.future.set_result(
                        CommandResult(command=queued.command, ok=False, error=str(e))
                    )
        logger.info("Command processing loop stopped")
