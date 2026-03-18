"""Tests for application configuration."""

import pytest

from app.config import Settings


class TestSettingsDefaults:
    """Verify all settings have sensible defaults for Pi deployment."""

    def test_serial_defaults(self):
        s = Settings()
        assert s.serial_port == "/dev/ttyUSB0"
        assert s.serial_baudrate == 115200

    def test_server_defaults(self):
        s = Settings()
        assert s.host == "0.0.0.0"
        assert s.port == 8000

    def test_safety_limits(self):
        s = Settings()
        assert s.max_hotend_temp == 260.0
        assert s.max_bed_temp == 110.0

    def test_camera_default(self):
        s = Settings()
        assert s.camera_url == "http://localhost:1984"

    def test_log_level_default(self):
        s = Settings()
        assert s.log_level == "INFO"

    def test_storage_paths_expanduser(self):
        # Create a fresh Settings without env overrides to test defaults
        import os

        saved_gcode = os.environ.pop("PRINTFORGE_GCODE_DIR", None)
        saved_data = os.environ.pop("PRINTFORGE_DATA_DIR", None)
        try:
            s = Settings()
            # Should be expanded, not contain ~
            assert "~" not in s.gcode_dir
            assert "~" not in s.data_dir
            assert "printforge" in s.gcode_dir
            assert "printforge" in s.data_dir
        finally:
            if saved_gcode is not None:
                os.environ["PRINTFORGE_GCODE_DIR"] = saved_gcode
            if saved_data is not None:
                os.environ["PRINTFORGE_DATA_DIR"] = saved_data

    def test_env_prefix(self):
        """Settings should use PRINTFORGE_ env prefix."""
        assert Settings.model_config.get("env_prefix") == "PRINTFORGE_"


class TestSettingsOverride:
    """Test that settings can be overridden."""

    def test_override_serial_port(self):
        s = Settings(serial_port="/dev/ttyACM0")
        assert s.serial_port == "/dev/ttyACM0"

    def test_override_baudrate(self):
        s = Settings(serial_baudrate=250000)
        assert s.serial_baudrate == 250000

    def test_override_safety_limits(self):
        s = Settings(max_hotend_temp=300.0, max_bed_temp=120.0)
        assert s.max_hotend_temp == 300.0
        assert s.max_bed_temp == 120.0

    def test_override_port(self):
        s = Settings(port=3000)
        assert s.port == 3000
