"""
GoatRaw — Export API Route
GET /export/{task_id}/csv     — download task result as CSV
GET /export/{task_id}/json    — download full result JSON
POST /export/leads/csv        — convert lead list to CSV directly
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, JSONResponse
from datetime import datetime

from app.api.deps import get_current_user
from app.core.redis_client import get_task_result
from app.utils.export import task_result_to_csv, leads_to_csv, format_for_google_sheets

router = APIRouter()


@router.get("/{task_id}/csv")
async def export_csv(task_id: str, user=Depends(get_current_user)):
    """Download a completed task's data output as CSV."""
    result = await get_task_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task result not found or expired (results cached for 1 hour).")

    csv_content = task_result_to_csv(result)
    filename    = f"goatraw_{task_id[:8]}_{datetime.utcnow().strftime('%Y%m%d')}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{task_id}/json")
async def export_json(task_id: str, user=Depends(get_current_user)):
    """Download full task result as JSON."""
    result = await get_task_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task result not found or expired.")

    filename = f"goatraw_{task_id[:8]}_{datetime.utcnow().strftime('%Y%m%d')}.json"
    import json
    return Response(
        content=json.dumps(result, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/leads/csv")
async def leads_to_csv_direct(body: dict, user=Depends(get_current_user)):
    """Convert a lead list directly to CSV (no task needed)."""
    leads = body.get("leads", [])
    if not leads:
        raise HTTPException(status_code=400, detail="No leads provided.")

    csv_content = leads_to_csv(leads)
    filename    = f"leads_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{task_id}/sheets-format")
async def export_sheets_format(task_id: str, user=Depends(get_current_user)):
    """Get task data formatted for Google Sheets API append."""
    result = await get_task_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task result not found.")

    output = result.get("output", {})
    data   = output.get("data", [])

    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="Task data is not a list.")

    sheets_data = format_for_google_sheets(data)
    return {"task_id": task_id, "row_count": len(sheets_data["values"]) - 1, "data": sheets_data}
