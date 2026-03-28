"""Tests for Marlin serial protocol handling."""

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

    @pytest.mark.asyncio
    async def test_reset_line_number(self):
        proto = MarlinProtocol.__new__(MarlinProtocol)
        proto._line_number = 50
        proto._conn = None
        proto._last_numbered_line = ""
        proto._temp_callbacks = []
        proto._terminal_callbacks = []
        proto._position_callbacks = []
        proto.default_timeout = 10.0
        proto.long_timeout = 300.0
        proto._long_commands = {"G28", "G29", "M109", "M190", "M303"}

        # Mock the connection to simulate M110 N0 success
        from unittest.mock import AsyncMock, MagicMock

        mock_conn = MagicMock()
        mock_conn.send = AsyncMock()
        mock_conn.read_line = AsyncMock(return_value="ok")
        proto._conn = mock_conn

        await proto.reset_line_number()
        assert proto._line_number == 0
        mock_conn.send.assert_called_once_with("M110 N0")


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
