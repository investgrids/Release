from fastapi import APIRouter
from app.services.market_data import get_extended_indices

router = APIRouter()


@router.get("/", response_model=list[dict])
async def list_indices():
    return await get_extended_indices()
