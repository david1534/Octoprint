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

from ..printer.command_guard import (
    TemperatureLimitError,
    is_heater_shutdown_command,
    temperature_command_error,
)
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
    trusted_shutdown: bool = field(compare=False, default=False)
    timeout: Optional[float] = field(compare=False, default=None)
    future: asyncio.Future = field(compare=False, default=None)


class CommandQueue:
    """Thread-safe priority queue for printer commands."""

    def __init__(
        self,
        protocol: MarlinProtocol,
        max_hotend_temp: float = 290.0,
        max_bed_temp: float = 110.0,
    ):
        self._protocol = protocol
        self._max_hotend_temp = max_hotend_temp
        self._max_bed_temp = max_bed_temp
        self._queue: asyncio.PriorityQueue[QueuedCommand] = asyncio.PriorityQueue()
        self._paused = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Start unpaused
        self._processing = False
        self._stopped = False
        self._task: Optional[asyncio.Task] = None
        self._in_flight: Optional[QueuedCommand] = None

    @property
    def is_paused(self) -> bool:
        return self._paused

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopped = False
            self._processing = True
            self._task = asyncio.create_task(self._process_loop())
            logger.info("Command queue started")

    def stop(self) -> None:
        """Stop accepting commands and resolve every outstanding future.

        Resolving the futures synchronously is important: the serial connection
        may be torn down immediately after this method returns.  A caller that
        was awaiting either the command currently on the wire or one still in
        the priority queue must be woken instead of being left behind on a queue
        that no longer has a consumer.
        """
        self._processing = False
        self._stopped = True
        if self._in_flight:
            self._resolve_stopped(self._in_flight)
        drained = self._drain_stopped()
        if self._task:
            self._task.cancel()
        logger.info("Command queue stopped (%d queued commands drained)", drained)

    @staticmethod
    def _resolve_stopped(queued: QueuedCommand) -> None:
        if queued.future and not queued.future.done():
            queued.future.set_result(
                CommandResult(
                    command=queued.command,
                    ok=False,
                    error="Command queue stopped before completion",
                )
            )

    def _drain_stopped(self) -> int:
        drained = 0
        while True:
            try:
                queued = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                return drained
            self._resolve_stopped(queued)
            drained += 1

    async def wait_for_stop(self, timeout: float = 5.0) -> None:
        """Wait for the processing task to fully exit after stop().

        Use this instead of accessing _task directly from external code.
        """
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

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
        trusted_shutdown: bool = False,
        timeout: Optional[float] = None,
    ) -> asyncio.Future:
        if self._stopped:
            raise ConnectionError("Command queue is stopped")
        self._validate_temperature_command(command, trusted_shutdown)

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        queued = QueuedCommand(
            priority=priority,
            timestamp=time.monotonic(),
            command=command,
            with_checksum=with_checksum,
            trusted_shutdown=trusted_shutdown,
            timeout=timeout,
            future=future,
        )
        await self._queue.put(queued)
        return future

    def _validate_temperature_command(
        self, command: str, trusted_shutdown: bool
    ) -> None:
        """Enforce heater ceilings before enqueue and immediately before send."""
        if trusted_shutdown:
            if not is_heater_shutdown_command(command):
                raise ValueError(
                    "trusted_shutdown is restricted to zero-target heater commands"
                )
        else:
            error = temperature_command_error(
                command, self._max_hotend_temp, self._max_bed_temp
            )
            if error:
                logger.error("Blocked unsafe heater command at queue boundary: %s", command)
                raise TemperatureLimitError(error)

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
            self._in_flight = queued
            if self._paused and queued.priority == CommandPriority.PRINT:
                # Put the print command back and wait for resume instead
                # of busy-looping (saves CPU during long pauses)
                self._in_flight = None
                await self._queue.put(queued)
                await self._pause_event.wait()
                continue
            try:
                # Re-check at the final wire boundary. This also protects
                # against commands inserted directly into the internal queue.
                self._validate_temperature_command(
                    queued.command, queued.trusted_shutdown
                )
                result = await self._protocol.send_command(
                    queued.command,
                    with_checksum=queued.with_checksum,
                    timeout=queued.timeout,
                )
                if queued.future and not queued.future.done():
                    queued.future.set_result(result)
            except asyncio.CancelledError:
                self._resolve_stopped(queued)
                break
            except Exception as e:
                logger.exception("Error processing command: %s", queued.command)
                if queued.future and not queued.future.done():
                    queued.future.set_result(
                        CommandResult(command=queued.command, ok=False, error=str(e))
                    )
            finally:
                self._in_flight = None
        # Also cover an unexpected consumer exit.  Once there is no processing
        # task, no future may remain pending in this queue.
        self._processing = False
        self._stopped = True
        self._drain_stopped()
        logger.info("Command processing loop stopped")
