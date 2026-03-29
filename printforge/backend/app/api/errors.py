"""API endpoints for error log management."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

from ..printer.controller import PrinterController

router = APIRouter(prefix="/api/errors", tags=["errors"])

_controller: Optional[PrinterController] = None


def set_controller(controller: PrinterController) -> None:
    global _controller
    _controller = controller


@router.get("/")
async def get_errors(active_only: bool = False):
    """Get all error log entries."""
    if not _controller:
        return {"errors": [], "active_count": 0}

    entries = (
        _controller.error_log.active_entries
        if active_only
        else _controller.error_log.entries
    )
    active = len(_controller.error_log.active_entries)
    return {
        "errors": [e.to_dict() for e in entries],
        "active_count": active,
    }


@router.post("/{error_id}/dismiss")
async def dismiss_error(error_id: int):
    """Dismiss a single error by ID."""
    if not _controller:
        return {"ok": False}
    ok = _controller.error_log.dismiss(error_id)
    return {"ok": ok}


@router.post("/dismiss-all")
async def dismiss_all_errors():
    """Dismiss all active errors."""
    if not _controller:
        return {"dismissed": 0}
    count = _controller.error_log.dismiss_all()
    return {"dismissed": count}


@router.post("/clear")
async def clear_errors():
    """Clear all error history."""
    if not _controller:
        return {"ok": False}
    _controller.error_log.clear()
    return {"ok": True}
