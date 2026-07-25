"""Serves generated media (hero images, etc.) from the persistent /data
volume — see app/services/media/storage.py for where these are written."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from app.services.media.storage import read_image

router = APIRouter()


@router.get("/{filename}")
async def get_media(filename: str):
    content = read_image(filename)
    if content is None:
        raise HTTPException(status_code=404, detail="Not found")
    ext = filename.rsplit(".", 1)[-1].lower()
    media_type = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
    return Response(content=content, media_type=media_type, headers={"Cache-Control": "public, max-age=31536000, immutable"})
