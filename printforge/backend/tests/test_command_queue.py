"""Tests for the command priority queue."""

import time
import pytest

from app.serial.command_queue import CommandPriority, QueuedCommand


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
