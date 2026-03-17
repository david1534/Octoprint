"""Settings REST API endpoints."""

from fastapi import APIRouter, Body

from ..middleware.auth import generate_api_key, hash_api_key
from ..storage.models import get_all_settings, get_setting, get_time_correction_factor, set_setting

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/")
async def list_settings():
    """Get all settings as a key-value dict."""
    return await get_all_settings()


@router.put("/")
async def update_settings(settings: dict = Body(...)):
    """Update multiple settings at once."""
    for key, value in settings.items():
        await set_setting(str(key), str(value))
    return await get_all_settings()


@router.post("/api-key/generate")
async def generate_new_api_key():
    """Generate a new API key. Returns the raw key once — store it safely.

    The key is stored as a hash; the raw value cannot be retrieved later.
    """
    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    await set_setting("api_key_hash", key_hash)
    return {"api_key": raw_key, "message": "Save this key — it cannot be shown again."}


@router.delete("/api-key")
async def revoke_api_key():
    """Remove the API key (disables auth, returns to open access)."""
    await set_setting("api_key_hash", "")
    return {"ok": True, "message": "API key revoked. All requests are now allowed."}


@router.get("/api-key/status")
async def api_key_status():
    """Check if an API key is currently configured."""
    key_hash = await get_setting("api_key_hash", "")
    return {"enabled": bool(key_hash)}


@router.get("/time-correction")
async def time_correction():
    """Get the computed print time correction factor."""
    factor = await get_time_correction_factor()
    return {"factor": round(factor, 3), "description": f"Prints take ~{factor:.1%} of slicer estimate"}


@router.get("/{key}")
async def get_single_setting(key: str, default: str = ""):
    """Get a single setting value."""
    value = await get_setting(key, default)
    return {"key": key, "value": value}
