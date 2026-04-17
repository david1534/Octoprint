"""Application configuration.

Settings are loaded from environment variables with sensible defaults
for Raspberry Pi deployment.
"""

import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Serial connection
    serial_port: str = "/dev/ttyUSB0"
    serial_baudrate: int = 115200
    # When true, the serial layer uses an in-process Marlin simulator instead
    # of opening a real port. For local dev and CI without a printer attached.
    mock_serial: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Storage paths
    gcode_dir: str = os.path.expanduser("~/printforge/gcodes")
    data_dir: str = os.path.expanduser("~/printforge/data")

    # Camera (ustreamer)
    camera_url: str = "http://localhost:8080"

    # Safety limits
    max_hotend_temp: float = 290.0
    max_bed_temp: float = 110.0

    # Logging
    log_level: str = "INFO"

    model_config = {"env_prefix": "PRINTFORGE_"}


settings = Settings()
