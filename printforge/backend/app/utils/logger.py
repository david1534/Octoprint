"""Logging utilities."""

import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler


def setup_file_logging(log_dir: str = "/home/pi/printforge/logs") -> None:
    """Set up rotating file logs in addition to stdout."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Main application log
    handler = RotatingFileHandler(
        log_path / "printforge.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logging.getLogger().addHandler(handler)

    # Serial communication log (separate file for debugging)
    serial_handler = RotatingFileHandler(
        log_path / "serial.log",
        maxBytes=2 * 1024 * 1024,  # 2MB
        backupCount=2,
    )
    serial_handler.setFormatter(
        logging.Formatter("%(asctime)s %(message)s")
    )
    serial_logger = logging.getLogger("app.serial")
    serial_logger.addHandler(serial_handler)
