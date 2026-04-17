"""Notifications REST API — test-send endpoint for the Settings page."""

from fastapi import APIRouter, HTTPException

from ..services import notifier

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.post("/test")
async def send_test_notification():
    """Send a test ntfy notification using the currently-saved settings.

    Returns 400 if notifications are disabled or no topic is configured.
    Returns 502 if ntfy accepted the request but failed delivery.
    """
    ok, message = await notifier.send_test()
    if not ok:
        # Disabled/misconfigured → 400; actual delivery failure → 502
        if message.startswith("Notifications disabled"):
            raise HTTPException(status_code=400, detail=message)
        raise HTTPException(status_code=502, detail=message)
    return {"ok": True, "message": message}
