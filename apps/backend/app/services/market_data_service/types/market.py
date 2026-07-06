"""
Standard domain models for the Market Data Service.
All providers must transform their raw responses into these models.
The rest of the application never sees raw provider data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Quote:
    symbol: str
    name: str
    exchange: str
    price: float
    change: float
    change_percent: float
    open: float
    high: float
    low: float
    previous_close: float
    volume: int
    last_updated: str

    @property
    def positive(self) -> bool:
        return self.change >= 0

    def to_dict(self) -> dict:
        sign = "+" if self.positive else ""
        return {
            "symbol":          self.symbol,
            "name":            self.name,
            "exchange":        self.exchange,
            "price":           self.price,
            "price_str":       f"{self.price:,.2f}",
            "change":          self.change,
            "change_str":      f"{sign}{self.change:,.2f}",
            "change_percent":  round(self.change_percent, 2),
            "change_pct_str":  f"{sign}{self.change_percent:.2f}%",
            "open":            self.open,
            "high":            self.high,
            "low":             self.low,
            "previous_close":  self.previous_close,
            "volume":          self.volume,
            "positive":        self.positive,
            "last_updated":    self.last_updated,
        }


@dataclass
class Company:
    symbol: str
    name: str
    sector: str
    industry: str
    market_cap: float
    pe: float
    eps: float
    roe: float
    book_value: float
    dividend_yield: float
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol":         self.symbol,
            "name":           self.name,
            "sector":         self.sector,
            "industry":       self.industry,
            "market_cap":     self.market_cap,
            "pe":             self.pe,
            "eps":            self.eps,
            "roe":            self.roe,
            "book_value":     self.book_value,
            "dividend_yield": self.dividend_yield,
            "description":    self.description,
        }


@dataclass
class Candle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "open":      self.open,
            "high":      self.high,
            "low":       self.low,
            "close":     self.close,
            "volume":    self.volume,
        }


@dataclass
class IndexQuote:
    name: str
    ticker: str
    value: float
    change: float
    change_percent: float
    flag: str = ""
    chart: list[dict] = field(default_factory=list)

    @property
    def positive(self) -> bool:
        return self.change_percent >= 0

    def to_dict(self) -> dict:
        sign = "+" if self.positive else ""
        return {
            "name":        self.name,
            "ticker":      self.ticker,
            "value":       f"{self.value:,.2f}",
            "value_raw":   round(self.value, 2),
            "change":      f"{sign}{self.change:,.2f}",
            "change_str":  f"{sign}{self.change_percent:.2f}%",
            "pct":         f"{sign}{self.change_percent:.2f}%",
            "positive":    self.positive,
            "flag":        self.flag,
            "chart":       self.chart,
        }


@dataclass
class SectorPerformance:
    id: str
    name: str
    change_percent: float

    @property
    def positive(self) -> bool:
        return self.change_percent >= 0

    def to_dict(self) -> dict:
        sign = "+" if self.positive else ""
        return {
            "id":       self.id,
            "name":     self.name,
            "value":    f"{sign}{self.change_percent:.1f}%",
            "positive": self.positive,
        }


@dataclass
class MarketStatus:
    is_open: bool
    status: str           # open | pre_open | pre_market | closed | weekend
    time_ist: str
    date: str

    def to_dict(self) -> dict:
        return {
            "is_open":   self.is_open,
            "status":    self.status,
            "time_ist":  self.time_ist,
            "date":      self.date,
        }


@dataclass
class TopMover:
    symbol: str
    name: str
    price: float
    change_percent: float
    volume_cr: float
    direction: str        # up | down

    def to_dict(self) -> dict:
        sign = "+" if self.direction == "up" else ""
        return {
            "ticker":   self.symbol,
            "company":  self.name,
            "value":    f"{sign}{self.change_percent:.2f}%",
            "subtitle": f"₹{self.price:,.2f}",
            "positive": self.direction == "up",
        }
