"""Regression tests for safety-first print cancellation."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.printer.controller import PrinterController
from app.printer.state import PrinterState, PrinterStatus
from app.services import notifier
from app.services.timelapse import TimelapseRecorder
from app.storage import models as storage_models


class _FakeSender:
    def __init__(self):
        self._filament_used_mm = 125.0
        self.elapsed_seconds = 42.0
        self.current_line = 17
        self.cancel_requested = False
        self.cancelled = False
        self.reset_called = False

    def request_cancel(self):
        self.cancel_requested = True

    async def cancel(self):
        assert self.cancel_requested
        self.cancelled = True

    def reset(self):
        self.reset_called = True

    def remove_layer_callback(self, callback):
        pass


class _StalledTimelapse:
    def __init__(self):
        self.is_recording = True
        self.started = asyncio.Event()

    async def stop_recording(self, success=True):
        self.is_recording = False
        self.started.set()
        await asyncio.Event().wait()


async def _cancel_background_tasks(controller: PrinterController) -> None:
    tasks = list(controller._background_tasks)
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


class TestControllerCancelPostprocessing:
    async def test_stalled_timelapse_does_not_block_cancel(self, monkeypatch):
        state = PrinterState(
            status=PrinterStatus.PAUSED, current_file="paused-print.gcode"
        )
        controller = PrinterController(state)
        sender = _FakeSender()
        timelapse = _StalledTimelapse()
        controller._sender = sender
        controller._timelapse = timelapse
        monkeypatch.setattr(notifier, "notify_print_cancelled", AsyncMock())

        await asyncio.wait_for(controller.cancel_print(), timeout=0.2)

        assert sender.cancel_requested is True
        assert sender.cancelled is True
        assert sender.reset_called is True
        assert state.status == PrinterStatus.IDLE
        assert state.current_file is None
        await asyncio.wait_for(timelapse.started.wait(), timeout=0.2)

        await _cancel_background_tasks(controller)

    async def test_database_and_side_effect_failures_do_not_change_cancel_result(
        self, monkeypatch
    ):
        state = PrinterState(
            status=PrinterStatus.PRINTING, current_file="failure-test.gcode"
        )
        controller = PrinterController(state)
        controller._sender = _FakeSender()
        controller._current_job_id = 99
        controller._current_spool_id = 7

        history_write = AsyncMock(side_effect=OSError("database unavailable"))
        filament_write = AsyncMock(side_effect=OSError("spool database unavailable"))
        notification = AsyncMock(side_effect=OSError("notification unavailable"))
        monkeypatch.setattr(storage_models, "complete_print_job", history_write)
        monkeypatch.setattr(controller, "_deduct_filament", filament_write)
        monkeypatch.setattr(notifier, "notify_print_cancelled", notification)

        await asyncio.wait_for(controller.cancel_print(), timeout=0.2)
        tasks = list(controller._background_tasks)
        await asyncio.gather(*tasks)

        assert state.status == PrinterStatus.IDLE
        assert controller._current_job_id is None
        assert controller._current_spool_id is None
        history_write.assert_awaited_once()
        filament_write.assert_awaited_once_with(125.0, 7)
        notification.assert_awaited_once_with("failure-test.gcode")


class _StalledProcess:
    def __init__(self):
        self.returncode = None
        self.started = asyncio.Event()
        self.killed = False
        self.reaped = False

    async def communicate(self):
        self.started.set()
        await asyncio.Event().wait()

    def kill(self):
        self.killed = True

    async def wait(self):
        self.reaped = True
        self.returncode = -9
        return self.returncode


class TestTimelapseProcessCleanup:
    async def test_cancelled_stalled_ffmpeg_is_killed_and_reaped(
        self, monkeypatch, tmp_path
    ):
        process = _StalledProcess()

        async def create_process(*args, **kwargs):
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
        recorder = TimelapseRecorder(object(), tmp_path)
        recorder._frames_dir = tmp_path
        recorder._print_filename = "stalled.gcode"
        recorder._frame_count = 10
        recorder._render_fps = 30

        assembly = asyncio.create_task(recorder._assemble_video(success=False))
        await process.started.wait()
        assembly.cancel()

        with pytest.raises(asyncio.CancelledError):
            await assembly
        assert process.killed is True
        assert process.reaped is True
