"""Regression tests for the 2026-07 code-review fixes.

Covers: path containment (M5), disconnect ref-nulling (M2), the controller
start-print guard (M3), the temperature ceiling on structured sets (H1),
protected settings (M6), and G90/G91 tracking across pause/resume (L3).
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.printer.controller import (
    PrinterController,
    TemperatureLimitError,
)
from app.printer.state import PrinterState, PrinterStatus
from app.utils.paths import is_within


class TestIsWithin:
    def test_root_itself(self, tmp_path):
        assert is_within(tmp_path, tmp_path) is True

    def test_direct_child(self, tmp_path):
        assert is_within(tmp_path, tmp_path / "a.gcode") is True

    def test_nested_child(self, tmp_path):
        assert is_within(tmp_path, tmp_path / "sub" / "deep" / "a.gcode") is True

    def test_parent_rejected(self, tmp_path):
        assert is_within(tmp_path, tmp_path.parent) is False

    def test_sibling_prefix_rejected(self, tmp_path):
        # THE M5 case: /base/gcodes_backup shares a string prefix with
        # /base/gcodes — startswith() allowed it, containment must not.
        root = tmp_path / "gcodes"
        evil = tmp_path / "gcodes_backup" / "x.gcode"
        assert is_within(root, evil) is False

    def test_dotdot_traversal_rejected(self, tmp_path):
        root = tmp_path / "gcodes"
        assert is_within(root, root / ".." / "gcodes_backup" / "x") is False

    def test_dotdot_back_inside_allowed(self, tmp_path):
        root = tmp_path / "gcodes"
        assert is_within(root, root / "sub" / ".." / "a.gcode") is True


def _connected_controller() -> PrinterController:
    """Controller with fake connection/queue/sender wired in, status IDLE."""
    ctrl = PrinterController(PrinterState())
    ctrl.state.status = PrinterStatus.IDLE
    ctrl._connection = MagicMock()
    ctrl._connection.disconnect = AsyncMock()
    ctrl._connection.connected = True
    ctrl._protocol = MagicMock()
    ctrl._queue = MagicMock()
    ctrl._queue.stop = MagicMock()
    ctrl._sender = MagicMock()
    ctrl._sender.is_printing = False
    return ctrl


class TestDisconnectNullsRefs:
    """M2: after disconnect(), commands must fail fast, not hang forever."""

    async def test_refs_nulled(self):
        ctrl = _connected_controller()
        await ctrl.disconnect()
        assert ctrl._queue is None
        assert ctrl._sender is None
        assert ctrl._protocol is None
        assert ctrl._connection is None
        assert ctrl._safety_task is None
        assert ctrl.state.status == PrinterStatus.DISCONNECTED

    async def test_send_command_fails_fast_after_disconnect(self):
        ctrl = _connected_controller()
        await ctrl.disconnect()
        with pytest.raises(ConnectionError):
            await ctrl.send_command("M105")

    async def test_start_print_fails_fast_after_disconnect(self, tmp_path):
        ctrl = _connected_controller()
        await ctrl.disconnect()
        with pytest.raises(ConnectionError):
            await ctrl.start_print(tmp_path / "x.gcode")


class TestStartPrintGuard:
    """M3: a second start must be rejected before any side effects."""

    async def test_rejected_while_printing(self, tmp_path):
        ctrl = _connected_controller()
        ctrl.state.status = PrinterStatus.PRINTING
        with pytest.raises(RuntimeError, match="already in progress"):
            await ctrl.start_print(tmp_path / "x.gcode")
        # No side effects fired: line numbers untouched, no M110 enqueued
        ctrl._protocol.reset_line_number.assert_not_called()
        ctrl._queue.enqueue.assert_not_called()

    async def test_rejected_while_sender_task_alive(self, tmp_path):
        # Covers the race where status hasn't flipped yet but the sender
        # already has a live print task.
        ctrl = _connected_controller()
        ctrl._sender.is_printing = True
        with pytest.raises(RuntimeError, match="already in progress"):
            await ctrl.start_print(tmp_path / "x.gcode")

    @pytest.mark.parametrize("status", [PrinterStatus.PAUSED, PrinterStatus.FINISHING])
    async def test_rejected_in_other_active_states(self, status, tmp_path):
        ctrl = _connected_controller()
        ctrl.state.status = status
        with pytest.raises(RuntimeError, match="already in progress"):
            await ctrl.start_print(tmp_path / "x.gcode")


class TestSetTemperatureCeiling:
    """H1: structured temperature sets honor the configured limits."""

    async def test_hotend_over_limit_rejected(self):
        ctrl = _connected_controller()
        with pytest.raises(TemperatureLimitError):
            await ctrl.set_temperature(hotend=500)

    async def test_bed_over_limit_rejected(self):
        ctrl = _connected_controller()
        with pytest.raises(TemperatureLimitError):
            await ctrl.set_temperature(bed=150)

    async def test_no_command_sent_when_rejected(self):
        ctrl = _connected_controller()
        with pytest.raises(TemperatureLimitError):
            await ctrl.set_temperature(hotend=500, bed=60)
        ctrl._queue.enqueue.assert_not_called()

    async def test_limits_come_from_config(self):
        # L2 regression: the monitor must be built from config, not hard-coded.
        from app.config import settings as app_settings

        ctrl = PrinterController(PrinterState())
        assert ctrl.safety_monitor.max_hotend_temp == app_settings.max_hotend_temp
        assert ctrl.safety_monitor.max_bed_temp == app_settings.max_bed_temp


class TestProtectedSettings:
    """M6: api_key_hash is not writable or readable via generic endpoints."""

    async def test_update_rejects_api_key_hash(self):
        from app.api.settings import update_settings

        with pytest.raises(HTTPException) as exc:
            await update_settings({"api_key_hash": "0" * 64})
        assert exc.value.status_code == 400

    async def test_get_single_refuses_api_key_hash(self):
        from app.api.settings import get_single_setting

        with pytest.raises(HTTPException) as exc:
            await get_single_setting("api_key_hash")
        assert exc.value.status_code == 403


class TestPositioningModeTracking:
    """L3: resume restores the file's G90/G91 mode instead of forcing G90."""

    def _sender(self):
        from app.serial.gcode_sender import GcodeSender

        queue = MagicMock()
        queue.enqueue = AsyncMock()
        queue.pause = MagicMock()
        queue.resume = MagicMock()
        return GcodeSender(queue), queue

    def test_tracker_follows_mode(self):
        sender, _ = self._sender()
        assert sender._absolute_positioning is True
        sender._track_positioning_mode("G91")
        assert sender._absolute_positioning is False
        sender._track_positioning_mode("G90")
        assert sender._absolute_positioning is True

    def test_tracker_ignores_lookalikes(self):
        sender, _ = self._sender()
        sender._track_positioning_mode("G911")  # not a mode switch
        assert sender._absolute_positioning is True
        sender._track_positioning_mode("G91")
        sender._track_positioning_mode("G901")  # not a mode switch
        assert sender._absolute_positioning is False

    async def test_resume_restores_relative_mode(self):
        sender, queue = self._sender()
        # Simulate a live, paused print streaming in relative mode
        sender._task = MagicMock()
        sender._task.done.return_value = False
        sender._paused = True
        sender._pause_time = None
        sender._absolute_positioning = False

        await sender.resume()

        enqueued = [c.args[0] for c in queue.enqueue.await_args_list]
        # The restore command (after the G91/prime pair) must be G91, not G90
        assert enqueued[-2] == "G91", f"expected relative-mode restore, got {enqueued}"

    async def test_resume_restores_absolute_mode(self):
        sender, queue = self._sender()
        sender._task = MagicMock()
        sender._task.done.return_value = False
        sender._paused = True
        sender._pause_time = None
        sender._absolute_positioning = True

        await sender.resume()

        enqueued = [c.args[0] for c in queue.enqueue.await_args_list]
        assert enqueued[-2] == "G90"


class TestMotionLockSerialization:
    """M7: concurrent jog/extrude sequences can't interleave G90/G91."""

    async def test_sequences_are_atomic(self):
        ctrl = _connected_controller()
        order: list[str] = []

        async def fake_send(cmd: str):
            order.append(cmd)
            await asyncio.sleep(0)  # yield so tasks would interleave if unlocked
            result = MagicMock()
            result.ok = True
            return result

        ctrl.send_command = fake_send  # type: ignore[assignment]

        await asyncio.gather(ctrl.jog(x=10), ctrl.extrude(length=5))

        # Each G91 must be followed by its own move then G90 before the next
        # sequence starts — i.e. commands come in contiguous triples.
        assert len(order) == 6
        for i in (0, 3):
            assert order[i] == "G91"
            assert order[i + 1].startswith("G1 ")
            assert order[i + 2] == "G90"
