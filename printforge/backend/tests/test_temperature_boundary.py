"""Regression tests for C3: every print path must honor heater ceilings."""

import asyncio
from io import BytesIO
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.datastructures import UploadFile

from app.printer.command_guard import (
    TemperatureLimitError,
    is_heater_shutdown_command,
    preflight_gcode_file,
    preflight_gcode_text,
    temperature_command_error,
)
from app.printer.controller import PrinterController
from app.printer.state import PrinterState, PrinterStatus
from app.serial.command_queue import CommandPriority, CommandQueue, QueuedCommand


@pytest.mark.parametrize(
    "command",
    [
        "M104 S500",
        "m104 s500",
        "  M104    S500  ",
        "M104S500",
        "M104 S 500",
        "M109 R500",
        "m109 r 500",
        "M140 S150",
        "M190 R150",
    ],
)
def test_s_r_case_and_spacing_variants_are_blocked(command):
    assert temperature_command_error(command, 290.0, 110.0) is not None


def test_inline_comment_cannot_create_false_violation():
    assert temperature_command_error("M104 S200 ; S500", 290.0, 110.0) is None


def test_file_body_preflight_reports_line_and_command(tmp_path):
    filepath = tmp_path / "unsafe.gcode"
    filepath.write_text("G28\nM104 S500 ; unsafe\nG1 X1\n", encoding="utf-8")

    violations = preflight_gcode_file(filepath, 290.0, 110.0)

    assert len(violations) == 1
    assert violations[0].line_number == 2
    assert violations[0].command == "M104 S500"


@pytest.mark.parametrize("source", ["custom start G-code", "custom end G-code"])
def test_custom_sequences_are_preflighted(source):
    violations = preflight_gcode_text(
        "G28\nM190 R150\n", 290.0, 110.0, source
    )
    assert [(v.source, v.line_number, v.command) for v in violations] == [
        (source, 2, "M190 R150")
    ]


def test_only_zero_target_heater_commands_can_be_trusted_shutdowns():
    assert is_heater_shutdown_command("M104 S0") is True
    assert is_heater_shutdown_command("m140 s 0") is True
    assert is_heater_shutdown_command("M104 S1") is False
    assert is_heater_shutdown_command("M106 S0") is False


class TestQueueWireBoundary:
    async def test_file_or_internal_overtemp_never_reaches_protocol(self):
        protocol = MagicMock()
        protocol.send_command = AsyncMock()
        queue = CommandQueue(protocol, max_hotend_temp=290, max_bed_temp=110)

        with pytest.raises(TemperatureLimitError):
            await queue.enqueue("M104 S500", CommandPriority.PRINT)

        protocol.send_command.assert_not_awaited()

    async def test_trusted_flag_rejects_non_shutdown_command(self):
        queue = CommandQueue(MagicMock())
        with pytest.raises(ValueError, match="zero-target"):
            await queue.enqueue(
                "M104 S500",
                CommandPriority.SYSTEM,
                trusted_shutdown=True,
            )

    async def test_trusted_shutdown_can_be_enqueued(self):
        queue = CommandQueue(MagicMock())
        future = await queue.enqueue(
            "M104 S0", CommandPriority.SYSTEM, trusted_shutdown=True
        )
        assert isinstance(future, asyncio.Future)

    async def test_final_wire_check_blocks_direct_internal_queue_insertion(self):
        protocol = MagicMock()
        protocol.send_command = AsyncMock()
        protocol.drain_unsolicited = AsyncMock()
        queue = CommandQueue(protocol, max_hotend_temp=290, max_bed_temp=110)
        future = asyncio.get_running_loop().create_future()
        await queue._queue.put(
            QueuedCommand(
                priority=CommandPriority.PRINT,
                timestamp=time.monotonic(),
                command="M109 R500",
                future=future,
            )
        )
        queue.start()

        result = await asyncio.wait_for(future, timeout=1)
        queue.stop()
        await queue.wait_for_stop()

        assert result.ok is False
        assert "safety limit" in result.error
        protocol.send_command.assert_not_awaited()


class TestUploadPreflight:
    async def test_upload_response_lists_blocked_file_command(
        self, tmp_path, monkeypatch
    ):
        from app.api import files as files_api

        monkeypatch.setattr(files_api, "GCODE_DIR", tmp_path)
        upload = UploadFile(
            filename="unsafe.gcode",
            file=BytesIO(b"G28\nM104 S500\n"),
        )

        response = await files_api.upload_file(upload, path="")

        assert response["ok"] is True
        assert response["file"]["safetyBlocked"] is True
        assert response["file"]["blockedCommands"] == [
            {
                "source": "unsafe.gcode",
                "lineNumber": 2,
                "command": "M104 S500",
                "message": (
                    "Hotend target 500C exceeds the safety limit of 290C"
                ),
            },
            {
                "source": "metadata",
                "lineNumber": None,
                "command": "nozzle_temp=500.0, bed_temp=None",
                "message": (
                    "Hotend target 500C exceeds the safety limit of 290C"
                ),
            },
        ]


def _controller() -> PrinterController:
    controller = PrinterController(PrinterState())
    controller.state.status = PrinterStatus.IDLE
    controller._connection = MagicMock(connected=True)
    controller._protocol = MagicMock()
    controller._queue = MagicMock()
    controller._sender = MagicMock(is_printing=False)
    controller._sender.start_print = AsyncMock()
    return controller


async def _safe_setting(key: str, default: str = "") -> str:
    return default


async def _correction_factor() -> float:
    return 1.0


class TestControllerPrintPreflight:
    async def test_metadata_temperature_is_blocked_before_substitution(
        self, tmp_path, monkeypatch
    ):
        from app.storage import models

        filepath = tmp_path / "metadata.gcode"
        filepath.write_text(
            "; nozzle_temperature = 500\nG28\nG1 X1\n", encoding="utf-8"
        )
        monkeypatch.setattr(models, "get_setting", _safe_setting)
        monkeypatch.setattr(
            models, "get_time_correction_factor", _correction_factor
        )
        controller = _controller()

        with pytest.raises(TemperatureLimitError) as exc:
            await controller.start_print(filepath)

        assert any(v.source == "metadata" for v in exc.value.violations)
        controller._protocol.reset_line_number.assert_not_called()
        controller._sender.start_print.assert_not_awaited()

    @pytest.mark.parametrize(
        ("setting_key", "unsafe_command", "expected_source"),
        [
            ("start_gcode", "m104 s 500", "custom start G-code"),
            ("end_gcode", "M190 R150", "custom end G-code"),
        ],
    )
    async def test_custom_sequence_is_blocked_before_print_side_effects(
        self,
        tmp_path,
        monkeypatch,
        setting_key,
        unsafe_command,
        expected_source,
    ):
        from app.storage import models

        filepath = tmp_path / "safe.gcode"
        filepath.write_text("G28\nG1 X1\n", encoding="utf-8")

        async def get_setting(key: str, default: str = "") -> str:
            return unsafe_command if key == setting_key else default

        monkeypatch.setattr(models, "get_setting", get_setting)
        monkeypatch.setattr(
            models, "get_time_correction_factor", _correction_factor
        )
        controller = _controller()

        with pytest.raises(TemperatureLimitError) as exc:
            await controller.start_print(filepath)

        assert any(v.source == expected_source for v in exc.value.violations)
        controller._protocol.reset_line_number.assert_not_called()
        controller._sender.start_print.assert_not_awaited()
