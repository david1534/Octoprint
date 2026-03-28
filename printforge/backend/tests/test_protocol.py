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
