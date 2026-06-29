from datetime import datetime
from pydantic import BaseModel
from typing import List

class CompanyImpact(BaseModel):
    symbol: str
    name: str
    impact: str

class EventSummary(BaseModel):
    id: str
    title: str
    summary: str
    impact_score: float
    confidence: float
    sectors: List[str]
    companies: List[CompanyImpact]
    date: datetime
    category: str = "Macro"
    event_type: str = ""
    source: str = ""
