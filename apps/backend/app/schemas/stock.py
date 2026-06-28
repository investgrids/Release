from pydantic import BaseModel
from typing import List

class StockEvent(BaseModel):
    title: str
    date: str

class StockNews(BaseModel):
    headline: str
    published_at: str

class StockDetail(BaseModel):
    symbol: str
    price: str
    change: str
    industry: str
    market_cap: str
    pe: str
    pb: str
    roe: str
    events: List[StockEvent]
    news: List[StockNews]
    peers: List[str]
    chart_data: List[dict]
