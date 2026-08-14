from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional

class CompanyImpact(BaseModel):
    symbol: str
    name: str
    impact: str

class EventSummary(BaseModel):
    id: str
    slug: str = ""
    title: str
    summary: str
    # None means "not yet scored" — must stay distinct from a real 0, which
    # would otherwise read as "confirmed zero impact" instead of "pending."
    impact_score: Optional[float] = None
    confidence: Optional[float] = None
    sectors: List[str]
    companies: List[CompanyImpact]
    date: datetime
    category: str = "Macro"
    event_type: str = ""
    source: str = ""
    # Homepage-ranking-only fields (see event_lifecycle.py) — always present
    # (computed for every event, cheap), but only surfaces that opt into
    # `sort_by=active` actually use them for ordering/filtering. impact_score
    # above is never altered by these.
    active_score: Optional[float] = None
    lifecycle: str = "Historical"
    # Phase 15 — sitemap/search eligibility (see coverage_engine.
    # compute_indexable_batch). False is the safe default absent real
    # evidence of importance, so this defaults False here too rather than
    # True — a caller that forgets to set it explicitly fails closed.
    indexable: bool = False
