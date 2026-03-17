"""Print history API endpoints."""

from fastapi import APIRouter, HTTPException, Query

from ..printer.gcode_parser import calculate_filament_cost
from ..storage.database import get_db
from ..storage.models import get_setting

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("/")
async def list_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str = Query(None, description="Filter by status: completed, cancelled, failed"),
):
    """Return paginated print job history."""
    db = await get_db()

    where = ""
    params: list = []
    if status:
        where = "WHERE status = ?"
        params.append(status)

    # Count total
    count_row = await db.execute(
        f"SELECT COUNT(*) as cnt FROM print_jobs {where}", params
    )
    row = await count_row.fetchone()
    total = row["cnt"] if row else 0

    # Fetch page
    query = f"""
        SELECT id, filename, started_at, completed_at, status,
               duration_seconds, lines_printed, total_lines,
               filament_used_mm, hotend_target, bed_target
        FROM print_jobs
        {where}
        ORDER BY started_at DESC
        LIMIT ? OFFSET ?
    """
    cursor = await db.execute(query, [*params, limit, offset])
    rows = await cursor.fetchall()

    # Read cost settings for calculation
    cost_per_kg = float(await get_setting("filament_cost_per_kg", "18"))
    density = float(await get_setting("filament_density", "1.24"))

    jobs = []
    for r in rows:
        job = {
            "id": r["id"],
            "filename": r["filename"],
            "started_at": r["started_at"],
            "completed_at": r["completed_at"],
            "status": r["status"],
            "duration_seconds": r["duration_seconds"],
            "lines_printed": r["lines_printed"],
            "total_lines": r["total_lines"],
            "filament_used_mm": r["filament_used_mm"],
            "hotend_target": r["hotend_target"],
            "bed_target": r["bed_target"],
            "estimated_cost": None,
        }
        if r["filament_used_mm"]:
            job["estimated_cost"] = calculate_filament_cost(
                r["filament_used_mm"], cost_per_kg, density
            )
        jobs.append(job)

    return {"jobs": jobs, "total": total, "limit": limit, "offset": offset}


@router.get("/stats")
async def history_stats():
    """Return aggregate print history statistics."""
    db = await get_db()

    row = await (
        await db.execute(
            """
            SELECT
                COUNT(*) as total_prints,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'completed' THEN duration_seconds ELSE 0 END) as total_seconds,
                SUM(CASE WHEN status = 'completed' THEN filament_used_mm ELSE 0 END) as total_filament_mm
            FROM print_jobs
        """
        )
    ).fetchone()

    total = row["total_prints"] or 0
    completed = row["completed"] or 0
    total_filament_mm = row["total_filament_mm"] or 0

    # Calculate total cost
    cost_per_kg = float(await get_setting("filament_cost_per_kg", "18"))
    density = float(await get_setting("filament_density", "1.24"))
    total_cost = calculate_filament_cost(total_filament_mm, cost_per_kg, density) if total_filament_mm > 0 else 0

    # Average print time for completed prints
    avg_row = await (
        await db.execute(
            "SELECT AVG(duration_seconds) as avg_duration FROM print_jobs WHERE status = 'completed' AND duration_seconds > 0"
        )
    ).fetchone()
    avg_duration = avg_row["avg_duration"] if avg_row and avg_row["avg_duration"] else 0

    # Longest print
    longest_row = await (
        await db.execute(
            "SELECT filename, duration_seconds FROM print_jobs WHERE status = 'completed' ORDER BY duration_seconds DESC LIMIT 1"
        )
    ).fetchone()

    # Prints by month (last 12 months)
    month_cursor = await db.execute(
        """
        SELECT strftime('%Y-%m', started_at) as month,
               COUNT(*) as count,
               SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
               SUM(CASE WHEN status IN ('failed', 'cancelled') THEN 1 ELSE 0 END) as failed
        FROM print_jobs
        GROUP BY month
        ORDER BY month DESC
        LIMIT 12
        """
    )
    months = [dict(r) for r in await month_cursor.fetchall()]

    return {
        "total_prints": total,
        "completed": completed,
        "cancelled": row["cancelled"] or 0,
        "failed": row["failed"] or 0,
        "success_rate": round(completed / total, 2) if total > 0 else 0,
        "total_hours": round((row["total_seconds"] or 0) / 3600, 1),
        "total_filament_m": round(total_filament_mm / 1000, 1),
        "total_cost": total_cost,
        "avg_print_time_seconds": round(avg_duration),
        "longest_print": {
            "filename": longest_row["filename"],
            "duration_seconds": longest_row["duration_seconds"],
        } if longest_row and longest_row["duration_seconds"] else None,
        "prints_by_month": months,
    }


@router.delete("/{job_id}")
async def delete_history_entry(job_id: int):
    """Delete a single print history entry."""
    db = await get_db()
    cursor = await db.execute("DELETE FROM print_jobs WHERE id = ?", [job_id])
    await db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True}
