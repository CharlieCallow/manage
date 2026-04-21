"""Serve chart PNGs produced by app/tools/charts.py.

The research graph writes charts under data/charts/{job_id}/{name}.png; this
route streams them back to the renderer. The router validates that the
requested path stays inside the charts root — no "../" escapes.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.tools.charts import chart_dir_for

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/charts/{job_id}/{name}")
async def serve_chart(job_id: str, name: str) -> FileResponse:
    if any(ch in name for ch in ("/", "\\", "..")) or not name.endswith(".png"):
        raise HTTPException(status_code=400, detail="invalid chart name")
    if any(ch in job_id for ch in ("/", "\\", "..")):
        raise HTTPException(status_code=400, detail="invalid job id")

    base = chart_dir_for(job_id)
    target = (base / name).resolve()
    # Defense in depth: resolved path must live inside the job directory.
    try:
        target.relative_to(base.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="path escapes root") from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail="chart not found")
    return FileResponse(target, media_type="image/png")
