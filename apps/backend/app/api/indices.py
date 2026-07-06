from fastapi import APIRouter, Query
from app.services.market_data import get_extended_indices, get_index_chart
from app.cache import get as cache_get, set as cache_set

router = APIRouter()

_INDICES_KEY = "indices:list"
_INDICES_TTL = 60        # 60-second cache — indices update every ~1 min
_CHART_TTL   = 300       # 5-minute cache for chart data


@router.get("/chart/{symbol}")
async def index_chart(symbol: str, period: str = Query("1M")):
    cache_key = f"indices:chart:{symbol}:{period}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached
    data = await get_index_chart(symbol, period)
    if data:
        await cache_set(cache_key, data, _CHART_TTL)
    return data


@router.get("/", response_model=list[dict])
async def list_indices():
    cached = await cache_get(_INDICES_KEY)
    if cached is not None:
        return cached
    data = await get_extended_indices()
    if data:
        await cache_set(_INDICES_KEY, data, _INDICES_TTL)
    return data
