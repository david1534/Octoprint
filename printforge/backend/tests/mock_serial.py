"""Backwards-compat shim — canonical location is app.serial.mock."""

from app.serial.mock import MockMarlinPrinter  # noqa: F401

__all__ = ["MockMarlinPrinter"]
