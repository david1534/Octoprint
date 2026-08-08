"""Tests for Marlin serial protocol handling."""

from unittest.mock import MagicMock

import pytest

from app.serial.protocol import MarlinProtocol


class TestChecksum:
    """Test line number and checksum generation."""

    def test_compute_checksum(self):
        proto = MarlinProtocol.__new__(MarlinProtocol)
        # Known checksum: XOR of all chars
        line = "N1 G28"
        expected = 0
        for ch in line:
            expected ^= ord(ch)
        assert proto._compute_checksum(line) == (expected & 0xFF)

    def test_add_line_number(self):
        proto = MarlinProtocol.__new__(MarlinProtocol)
        proto._line_number = 0

        result = proto._add_line_number("G28")
        assert result.startswith("N1 G28*")
        # Verify checksum is valid
        line_part, checksum_str = result.split("*")
        expected = 0
        for ch in line_part:
            expected ^= ord(ch)
        assert int(checksum_str) == (expected & 0xFF)

    def test_line_number_increments(self):
        proto = MarlinProtocol.__new__(MarlinProtocol)
        proto._line_number = 0

        result1 = proto._add_line_number("G28")
        assert result1.startswith("N1 ")

        result2 = proto._add_line_number("G1 X10")
        assert result2.startswith("N2 ")

    def test_reset_line_number(self):
        proto = MarlinProtocol.__new__(MarlinProtocol)
        proto._line_number = 50
        proto.reset_line_number()
        assert proto._line_number == 0


class TestTimeoutSelection:
    """Test that commands get appropriate timeouts."""

    def test_default_timeout(self):
        proto = MarlinProtocol.__new__(MarlinProtocol)
        proto.default_timeout = 10.0
        proto.long_timeout = 300.0
        proto._long_commands = {"G28", "M109", "M190", "G29"}

        assert proto._get_timeout("G1 X10") == 10.0
        assert proto._get_timeout("M104 S200") == 10.0

    def test_long_timeout(self):
        proto = MarlinProtocol.__new__(MarlinProtocol)
        proto.default_timeout = 10.0
        proto.long_timeout = 300.0
        proto._long_commands = {"G28", "M109", "M190", "G29"}

        assert proto._get_timeout("G28") == 300.0
        assert proto._get_timeout("M109 S200") == 300.0
        assert proto._get_timeout("M190 S60") == 300.0


class _ScriptedConnection:
    """Minimal serial connection that returns scripted lines/exceptions."""

    def __init__(self, responses):
        self.responses = iter(responses)
        self.sent = []

    async def send(self, command):
        self.sent.append(command)

    async def read_line(self, timeout=10.0):
        response = next(self.responses)
        if isinstance(response, BaseException):
            raise response
        return response


class TestUserInputWait:
    """LCD-controlled pauses must not make the host abandon the print stream."""

    def _protocol(self, responses):
        proto = MarlinProtocol(_ScriptedConnection(responses))
        proto.default_timeout = 0.001
        proto._terminal_callbacks = [MagicMock()]
        return proto

    def test_recognizes_lcd_wait_commands(self):
        assert MarlinProtocol._is_user_wait_command("M600")
        assert MarlinProtocol._is_user_wait_command("m0 Change filament")
        assert MarlinProtocol._is_user_wait_command("M1")
        assert not MarlinProtocol._is_user_wait_command("G1 X10")

    @pytest.mark.parametrize(
        "line",
        [
            "echo:busy: paused for user",
            "busy: paused for input",
            "//action:out_of_filament",
            "//action:filament_runout",
            "//action:filament_change",
            "//action:prompt_begin Filament Runout",
        ],
    )
    def test_recognizes_firmware_wait_signals(self, line):
        assert MarlinProtocol._is_user_wait_signal(line)

    async def test_m600_survives_silence_until_final_ok(self):
        proto = self._protocol(
            [
                TimeoutError(),
                "echo:busy: paused for user",
                TimeoutError(),
                "busy: processing",
                TimeoutError(),
                "ok",
            ]
        )

        result = await proto.send_command("M600")

        assert result.ok is True
        assert proto._conn.sent == ["M600"]

    async def test_firmware_runout_holds_current_print_command_until_ok(self):
        proto = self._protocol(
            [
                "//action:filament_runout",
                TimeoutError(),
                "echo:busy: paused for user",
                "busy: processing",
                TimeoutError(),
                "ok",
            ]
        )

        result = await proto.send_command("G1 X120 Y80 E42")

        assert result.ok is True
        assert proto._conn.sent == ["G1 X120 Y80 E42"]

    async def test_normal_command_still_times_out(self):
        proto = self._protocol([TimeoutError()])

        result = await proto.send_command("G1 X10")

        assert result.ok is False
        assert "Timeout" in result.error
