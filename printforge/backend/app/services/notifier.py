"""Push-notification service (ntfy.sh).

Fires notifications for milestone events — layer completion, print done,
print cancelled/failed — to a user-configured ntfy topic. Delivery is
best-effort: any failure (network error, bad topic, ntfy outage) is
logged and swallowed so it can never disrupt the print path.

All config is read from the settings table on each call so the user can
change topic/milestones without restarting the service.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from ..storage.models import get_setting

logger = logging.getLogger(__name__)

_DEFAULT_SERVER = "https://ntfy.sh"
_DEFAULT_MILESTONES = "1,3"
# ntfy enforces 32KB per message; realistic messages are <1KB. Keep the
# client timeout short so a slow ntfy server can't stall the caller.
_HTTP_TIMEOUT = 5.0


async def _is_enabled() -> tuple[bool, str, str]:
    """Return (enabled, server, topic). Enabled iff toggle is on AND topic is set."""
    enabled = (await get_setting("ntfy_enabled", "false")) == "true"
    topic = (await get_setting("ntfy_topic", "")).strip()
    server = (await get_setting("ntfy_server", _DEFAULT_SERVER)).strip() or _DEFAULT_SERVER
    return (enabled and bool(topic), server, topic)


async def _send(
    title: str,
    body: str,
    priority: str = "default",
    tags: Optional[str] = None,
) -> bool:
    """POST a notification to ntfy. Returns True on success, False otherwise.

    All exceptions are caught — this function never raises, so callers can
    fire-and-forget without a try/except.
    """
    enabled, server, topic = await _is_enabled()
    if not enabled:
        return False

    # ntfy URL is server/topic; body is the message; headers carry metadata.
    url = f"{server.rstrip('/')}/{topic}"
    headers = {
        "Title": title,
        "Priority": priority,
    }
    if tags:
        headers["Tags"] = tags

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.post(url, content=body.encode("utf-8"), headers=headers)
            if resp.status_code >= 400:
                logger.warning(
                    "ntfy returned HTTP %d for topic=%s: %s",
                    resp.status_code, topic, resp.text[:200],
                )
                return False
        logger.info("ntfy sent: %s", title)
        return True
    except Exception as e:
        logger.warning("ntfy send failed: %s", e)
        return False


async def send_test() -> tuple[bool, str]:
    """Send a test notification. Returns (success, message) for the API."""
    enabled, _, topic = await _is_enabled()
    if not enabled:
        return (False, "Notifications disabled or topic not set")
    ok = await _send(
        title="PrintForge test",
        body="If you see this, ntfy is wired up correctly.",
        priority="default",
        tags="test_tube",
    )
    if ok:
        return (True, f"Test notification sent to topic '{topic}'")
    return (False, "Send failed — check backend logs")


def _ordinal(n: int) -> str:
    """1 -> '1st', 2 -> '2nd', 3 -> '3rd', 11 -> '11th', etc."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


async def notify_layer_completed(
    completed_layer: int,
    filename: str,
    total_layers: int,
) -> None:
    """Fire a milestone notification if `completed_layer` is in the user's list."""
    if completed_layer < 1:
        return
    raw = await get_setting("ntfy_layer_milestones", _DEFAULT_MILESTONES)
    try:
        milestones = {int(s.strip()) for s in raw.split(",") if s.strip()}
    except ValueError:
        logger.warning("Invalid ntfy_layer_milestones setting: %r", raw)
        return
    if completed_layer not in milestones:
        return

    ordinal = _ordinal(completed_layer)
    total_str = str(total_layers) if total_layers > 0 else "?"
    await _send(
        title=f"{ordinal} layer complete",
        body=f"{filename}\nLayer {completed_layer}/{total_str} done",
        priority="default",
        tags="package",
    )


async def notify_print_complete(filename: str, elapsed_seconds: float) -> None:
    """Fire a notification when a print completes normally."""
    await _send(
        title="Print complete",
        body=f"{filename}\nFinished in {_format_duration(elapsed_seconds)}",
        priority="high",
        tags="white_check_mark,printer",
    )


async def notify_print_cancelled(filename: str) -> None:
    """Fire a notification when a print is cancelled by the user."""
    await _send(
        title="Print cancelled",
        body=filename,
        priority="default",
        tags="no_entry_sign",
    )


async def notify_print_failed(filename: str, reason: str = "") -> None:
    """Fire a notification when a print aborts due to an error."""
    body = filename
    if reason:
        body = f"{filename}\n{reason}"
    await _send(
        title="Print failed",
        body=body,
        priority="urgent",
        tags="warning",
    )


def _format_duration(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"
