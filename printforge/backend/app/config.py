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

    # Deployment environment name. "production" on the main Pi service,
    # "staging" on the test instance (:8001). Surfaced to the frontend so
    # the UI can show a banner when you're not on production.
    environment: str = "production"

    # Separate privileged credential for release promotion/rollback. This is
    # intentionally not the normal API key: a leaked UI credential must not
    # grant permission to replace production code. An empty value disables
    # promotion and rollback (fail closed).
    promotion_token: str = ""

    model_config = {"env_prefix": "PRINTFORGE_"}


settings = Settings()
