"""Filament spool management REST API endpoints."""

from fastapi import APIRouter, Body, HTTPException

from ..storage.models import (
    create_spool,
    deduct_filament,
    delete_spool,
    get_active_spool,
    get_setting,
    get_spool,
    get_spools,
    set_active_spool,
    update_spool,
)

router = APIRouter(prefix="/api/filament", tags=["filament"])


@router.get("/")
async def list_spools():
    """List all filament spools."""
    return {"spools": await get_spools()}


@router.post("/")
async def add_spool(data: dict = Body(...)):
    """Create a new filament spool."""
    spool_id = await create_spool(
        name=data.get("name", "New Spool"),
        material=data.get("material", "PLA"),
        color=data.get("color", "#CCCCCC"),
        total_weight_g=data.get("total_weight_g", 1000),
        cost_per_kg=data.get("cost_per_kg", 18),
        notes=data.get("notes", ""),
    )
    return {"id": spool_id, "ok": True}


@router.get("/active")
async def get_active():
    """Get the currently active spool."""
    spool = await get_active_spool()
    return {"spool": spool}


@router.get("/warnings")
async def get_low_filament_warnings():
    """Get spools that are below the low-filament warning threshold."""
    threshold_g = float(await get_setting("low_filament_threshold_g", "50"))
    all_spools = await get_spools()
    warnings = []
    for spool in all_spools:
        remaining = max(0, spool["total_weight_g"] - spool["used_weight_g"])
        if remaining <= threshold_g:
            warnings.append({
                **spool,
                "remaining_g": round(remaining, 1),
            })
    return {"warnings": warnings, "threshold_g": threshold_g}


@router.post("/{spool_id}/activate")
async def activate_spool(spool_id: int):
    """Set a spool as the active spool."""
    await set_active_spool(spool_id)
    return {"ok": True}


@router.put("/{spool_id}")
async def edit_spool(spool_id: int, data: dict = Body(...)):
    """Update spool properties."""
    allowed = {"name", "material", "color", "total_weight_g", "used_weight_g", "cost_per_kg", "notes"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        raise HTTPException(400, "No valid fields to update")
    await update_spool(spool_id, **updates)
    return {"ok": True}


@router.post("/{spool_id}/deduct")
async def deduct_from_spool(spool_id: int, data: dict = Body(...)):
    """Manually deduct filament usage from a spool."""
    grams = data.get("grams", 0)
    if grams <= 0:
        raise HTTPException(400, "grams must be positive")
    await deduct_filament(spool_id, grams)
    return {"ok": True}


@router.delete("/{spool_id}")
async def remove_spool(spool_id: int):
    """Delete a filament spool."""
    await delete_spool(spool_id)
    return {"ok": True}
