"""Settings REST API endpoints."""

from fastapi import APIRouter, Body, HTTPException

from ..middleware.auth import generate_api_key, hash_api_key
from ..storage.models import get_all_settings, get_setting, get_time_correction_factor, set_setting

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Settings that gate authentication or other security-sensitive state. These
# must not be writable or readable through the generic settings endpoints:
# api_key_hash has dedicated generate/revoke endpoints, and exposing it here
# would let any caller lock the owner out (or plant a known hash), and would
# leak the stored hash to any authed client.
PROTECTED_SETTINGS = frozenset({"api_key_hash"})


def _public_settings(all_settings: dict) -> dict:
    """Strip protected keys from a settings dict before returning it."""
    return {k: v for k, v in all_settings.items() if k not in PROTECTED_SETTINGS}


@router.get("/")
async def list_settings():
    """Get all settings as a key-value dict (protected keys redacted)."""
    return _public_settings(await get_all_settings())


@router.put("/")
async def update_settings(settings: dict = Body(...)):
    """Update multiple settings at once (protected keys are rejected)."""
    blocked = sorted(k for k in settings if k in PROTECTED_SETTINGS)
    if blocked:
        raise HTTPException(
            400,
            f"These settings cannot be changed here: {', '.join(blocked)}. "
            "Use the dedicated API-key endpoints instead.",
        )
    for key, value in settings.items():
        await set_setting(str(key), str(value))
    return _public_settings(await get_all_settings())


@router.post("/api-key/generate")
async def generate_new_api_key():
    """Generate a new API key. Returns the raw key once — store it safely.

    The key is stored as a hash; the raw value cannot be retrieved later.
    """
    from ..middleware.auth import APIKeyMiddleware

    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    await set_setting("api_key_hash", key_hash)
    APIKeyMiddleware.invalidate_api_key_cache()
    return {"api_key": raw_key, "message": "Save this key — it cannot be shown again."}


@router.delete("/api-key")
async def revoke_api_key():
    """Remove the API key (disables auth, returns to open access)."""
    from ..middleware.auth import APIKeyMiddleware

    await set_setting("api_key_hash", "")
    APIKeyMiddleware.invalidate_api_key_cache()
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
    """Get a single setting value (protected keys are not readable)."""
    if key in PROTECTED_SETTINGS:
        raise HTTPException(403, "This setting is not readable")
    value = await get_setting(key, default)
    return {"key": key, "value": value}
