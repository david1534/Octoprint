"""Regression tests for sender/controller print outcome handling."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.printer.controller import PrinterController
from app.printer.state import PrinterState, PrinterStatus
from app.serial.gcode_sender import PrintResult


class TestControllerPrintOutcome:
    async def test_failed_sender_task_never_runs_success_cleanup(self):
        state = PrinterState(
            status=PrinterStatus.PRINTING,
            current_file="broken.gcode",
        )
        controller = PrinterController(state)

        sender = MagicMock()
        sender.is_printing = False
        sender._task.done.return_value = True
        sender.result = PrintResult.FAILED
        sender.failure = OSError("SD card read failed")
        sender.in_start_gcode = False
        sender._filament_used_mm = 12.5
        sender.elapsed_seconds = 42.0
        sender.current_line = 17
        controller._sender = sender

        controller._stop_timelapse = AsyncMock()
        controller._deduct_filament = AsyncMock()
        controller._on_print_complete = AsyncMock()

        # Let the safety loop process exactly one tick, then stop it.
        sleep = AsyncMock(side_effect=[None, asyncio.CancelledError()])
        failed_notification = AsyncMock()
        completed_notification = AsyncMock()
        with (
            patch("app.printer.controller.asyncio.sleep", sleep),
            patch(
                "app.printer.controller.notifier.notify_print_failed",
                failed_notification,
            ),
            patch(
                "app.printer.controller.notifier.notify_print_complete",
                completed_notification,
            ),
        ):
            await controller._safety_loop()

        controller._on_print_complete.assert_not_awaited()
        completed_notification.assert_not_awaited()
        controller._stop_timelapse.assert_awaited_once_with(success=False)
        controller._deduct_filament.assert_awaited_once_with(12.5)
        failed_notification.assert_awaited_once()
        sender.reset.assert_called_once()
        assert state.status == PrinterStatus.ERROR
        assert state.error_message == "Print failed: OSError: SD card read failed"

