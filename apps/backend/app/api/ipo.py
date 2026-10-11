"""
IPO Hub: real issues from NSE's public lists (see app/services/ipo_feed.py for exactly what is and is not available).
There is no placeholder data in this module; if NSE has never answered, the list is empty and data_source is "unavailable".
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.ipo_feed import get_ipos

router = APIRouter()


@router.get("/")
async def list_ipos(status: str | None = None, board: str | None = None):
    data = await get_ipos()
    ipos = data["ipos"]
    if status and status.lower() in ("upcoming", "ongoing", "closed", "listed"):
        ipos = [i for i in ipos if i["status"].lower() == status.lower()]
    if board and board.lower() in ("mainboard", "sme"):
        ipos = [i for i in ipos if i["type"].lower() == board.lower()]
    return {**data, "ipos": ipos}


@router.get("/{ipo_id}")
async def get_ipo(ipo_id: str):
    ipo = next((i for i in (await get_ipos())["ipos"] if i["id"] == ipo_id.lower()), None)
    if not ipo:
        raise HTTPException(status_code=404, detail="IPO not found")
    return ipo
