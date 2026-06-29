from pydantic import BaseModel
from typing import List, Optional


class StockEvent(BaseModel):
    title: str
    date: str


class StockNews(BaseModel):
    headline: str
    published_at: str


class StockDetail(BaseModel):
    symbol: str
    name: str = ""
    price: str
    prev_close: str = ""
    open: str = ""
    day_high: str = ""
    day_low: str = ""
    change: str
    change_abs: str = ""
    pct_change: float = 0.0
    week52_high: str = ""
    week52_low: str = ""
    volume: str = ""
    avg_volume: str = ""
    market_cap: str
    industry: str
    sector: str = ""
    description: str = ""
    pe: str
    forward_pe: str = ""
    pb: str
    eps: str = ""
    roe: str
    roa: str = ""
    beta: str = ""
    dividend_yield: str = ""
    dividend_rate: str = ""
    gross_margins: str = ""
    operating_margins: str = ""
    net_margins: str = ""
    debt_to_equity: str = ""
    current_ratio: str = ""
    free_cashflow: str = ""
    recommendation: str = "hold"
    target_mean: str = ""
    target_high: str = ""
    target_low: str = ""
    analyst_count: int = 0
    buy_count: int = 0
    hold_count: int = 0
    sell_count: int = 0
    held_institutions: str = ""
    held_insiders: str = ""
    quarterly_revenue: List[dict] = []
    quarterly_net_income: List[dict] = []
    enterprise_value: str = ""
    roce: str = ""
    annual_financials: List[dict] = []
    dna_scores: dict = {}
    gov_score: int = 0
    gov_level: str = ""
    gov_breakdown: List[dict] = []
    gov_support_areas: List[str] = []
    events: List[StockEvent] = []
    news: List[StockNews] = []
    peers: List[str] = []
    chart_data: List[dict] = []
