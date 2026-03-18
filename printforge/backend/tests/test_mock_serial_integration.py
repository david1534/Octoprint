"""Integration tests using MockMarlinPrinter to validate protocol interactions."""

import asyncio
import pytest

from tests.mock_serial import MockMarlinPrinter


class TestMockMarlinStartup:
    """Verify mock printer sends correct startup sequence."""

    @pytest.mark.asyncio
    async def test_startup_messages(self):
        printer = MockMarlinPrinter()
        await printer.start()
        lines = []
        while not printer._response_queue.empty():
            lines.append(await printer.read_response())
        assert lines[0] == "start"
        assert "Marlin" in lines[1]
        assert lines[-1] == "ok"

    @pytest.mark.asyncio
    async def test_initial_state(self):
        printer = MockMarlinPrinter()
        assert printer.hotend_actual == pytest.approx(22.0)
        assert printer.hotend_target == 0.0
        assert printer.bed_actual == pytest.approx(21.0)
        assert printer.bed_target == 0.0
        assert printer.homed is False
        assert printer.relative_mode is False


class TestMockMarlinCommands:
    """Test command processing on the mock printer."""

    @pytest.mark.asyncio
    async def test_g28_homes(self):
        printer = MockMarlinPrinter()
        printer.x = 100.0
        printer.y = 50.0
        printer.z = 10.0
        await printer.process_command("G28")
        assert printer.x == 0.0
        assert printer.y == 0.0
        assert printer.z == 0.0
        assert printer.homed is True

    @pytest.mark.asyncio
    async def test_g1_absolute_move(self):
        printer = MockMarlinPrinter()
        await printer.process_command("G1 X50 Y30 Z10 E5")
        assert printer.x == pytest.approx(50.0)
        assert printer.y == pytest.approx(30.0)
        assert printer.z == pytest.approx(10.0)
        assert printer.e == pytest.approx(5.0)

    @pytest.mark.asyncio
    async def test_g91_relative_mode(self):
        printer = MockMarlinPrinter()
        await printer.process_command("G1 X10")
        assert printer.x == pytest.approx(10.0)

        await printer.process_command("G91")
        assert printer.relative_mode is True

        await printer.process_command("G1 X5")
        assert printer.x == pytest.approx(15.0)

    @pytest.mark.asyncio
    async def test_g90_absolute_mode(self):
        printer = MockMarlinPrinter()
        await printer.process_command("G91")
        await printer.process_command("G90")
        assert printer.relative_mode is False

    @pytest.mark.asyncio
    async def test_m104_set_hotend_no_wait(self):
        printer = MockMarlinPrinter()
        await printer.process_command("M104 S210")
        assert printer.hotend_target == pytest.approx(210.0)
        # Actual should not change immediately (non-blocking)
        resp = await printer.read_response()
        assert resp == "ok"

    @pytest.mark.asyncio
    async def test_m140_set_bed_no_wait(self):
        printer = MockMarlinPrinter()
        await printer.process_command("M140 S60")
        assert printer.bed_target == pytest.approx(60.0)

    @pytest.mark.asyncio
    async def test_m105_temp_report(self):
        printer = MockMarlinPrinter()
        printer.hotend_actual = 200.0
        printer.hotend_target = 210.0
        printer.bed_actual = 55.0
        printer.bed_target = 60.0

        await printer.process_command("M105")
        temp_line = await printer.read_response()
        assert "T:200.0" in temp_line
        assert "/210.0" in temp_line
        assert "B:55.0" in temp_line
        assert "/60.0" in temp_line

    @pytest.mark.asyncio
    async def test_m114_position_report(self):
        printer = MockMarlinPrinter()
        printer.x = 10.5
        printer.y = 20.3
        printer.z = 0.2
        printer.e = 1.5

        await printer.process_command("M114")
        pos_line = await printer.read_response()
        assert "X:10.50" in pos_line
        assert "Y:20.30" in pos_line
        assert "Z:0.20" in pos_line
        assert "E:1.50" in pos_line

    @pytest.mark.asyncio
    async def test_m115_firmware_info(self):
        printer = MockMarlinPrinter()
        await printer.process_command("M115")
        firmware_line = await printer.read_response()
        assert "FIRMWARE_NAME:Marlin" in firmware_line

    @pytest.mark.asyncio
    async def test_m106_fan_speed(self):
        printer = MockMarlinPrinter()
        await printer.process_command("M106 S255")
        assert printer.fan_speed == 255

    @pytest.mark.asyncio
    async def test_m112_emergency_stop(self):
        printer = MockMarlinPrinter()
        printer.hotend_target = 210.0
        printer.bed_target = 60.0
        printer.fan_speed = 255

        await printer.process_command("M112")
        assert printer.hotend_target == 0
        assert printer.bed_target == 0
        assert printer.fan_speed == 0

    @pytest.mark.asyncio
    async def test_line_number_stripping(self):
        """Commands with line numbers and checksums should be parsed."""
        printer = MockMarlinPrinter()
        await printer.process_command("N1 G28*45")
        assert printer.homed is True

    @pytest.mark.asyncio
    async def test_unknown_command_ack(self):
        printer = MockMarlinPrinter()
        await printer.process_command("M999")
        resp = await printer.read_response()
        assert resp == "ok"

    @pytest.mark.asyncio
    async def test_stop(self):
        printer = MockMarlinPrinter()
        await printer.stop()
        assert printer._running is False
