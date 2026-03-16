"""Print history API endpoints."""

from fastapi import APIRouter, HTTPException, Query

from ..storage.database import get_db

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

    jobs = [
        {
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
        }
        for r in rows
    ]

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

    return {
        "total_prints": total,
        "completed": completed,
        "cancelled": row["cancelled"] or 0,
        "failed": row["failed"] or 0,
        "success_rate": round(completed / total, 2) if total > 0 else 0,
        "total_hours": round((row["total_seconds"] or 0) / 3600, 1),
        "total_filament_m": round((row["total_filament_mm"] or 0) / 1000, 1),
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
