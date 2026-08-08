"""Tests for the command priority queue."""

import asyncio
import time

import pytest

from app.serial.command_queue import CommandPriority, CommandQueue, QueuedCommand


class TestCommandPriority:
    """Test that priority ordering works correctly."""

    def test_emergency_is_highest_priority(self):
        assert CommandPriority.EMERGENCY < CommandPriority.SAFETY
        assert CommandPriority.EMERGENCY < CommandPriority.USER

    def test_priority_order(self):
        assert (
            CommandPriority.EMERGENCY
            < CommandPriority.SAFETY
            < CommandPriority.SYSTEM
            < CommandPriority.PRINT
            < CommandPriority.USER
        )


class TestQueuedCommand:
    """Test QueuedCommand ordering."""

    def test_higher_priority_sorts_first(self):
        now = time.monotonic()
        emergency = QueuedCommand(
            priority=CommandPriority.EMERGENCY,
            timestamp=now + 1,  # Later timestamp
            command="M112",
        )
        user = QueuedCommand(
            priority=CommandPriority.USER,
            timestamp=now,  # Earlier timestamp
            command="G28",
        )
        # Emergency should sort before user even with later timestamp
        assert emergency < user

    def test_same_priority_fifo(self):
        t1 = time.monotonic()
        t2 = t1 + 0.001
        cmd1 = QueuedCommand(
            priority=CommandPriority.USER, timestamp=t1, command="G28"
        )
        cmd2 = QueuedCommand(
            priority=CommandPriority.USER, timestamp=t2, command="G1 X10"
        )
        # Earlier timestamp should sort first when priority is equal
        assert cmd1 < cmd2


class _BlockingProtocol:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def send_command(self, command, with_checksum=False):
        self.started.set()
        await self.release.wait()

    async def drain_unsolicited(self):
        return None


class TestCommandQueueShutdown:
    async def test_stop_resolves_in_flight_and_queued_futures(self):
        protocol = _BlockingProtocol()
        queue = CommandQueue(protocol)
        queue.start()
        in_flight = await queue.enqueue("G28")
        queued = await queue.enqueue("M105")

        await protocol.started.wait()
        queue.stop()

        first, second = await asyncio.wait_for(
            asyncio.gather(in_flight, queued), timeout=1.0
        )
        await queue.wait_for_stop(timeout=1.0)

        assert first.ok is False
        assert second.ok is False
        assert "stopped" in first.error.lower()
        assert "stopped" in second.error.lower()

    async def test_enqueue_after_stop_fails_fast(self):
        queue = CommandQueue(_BlockingProtocol())
        queue.start()
        queue.stop()

        with pytest.raises(ConnectionError, match="stopped"):
            await queue.enqueue("M105")
        await queue.wait_for_stop(timeout=1.0)
