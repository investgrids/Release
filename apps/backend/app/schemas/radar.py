from pydantic import BaseModel
from typing import List

class RadarOpportunity(BaseModel):
    id: str
    theme: str
    score: int
    reason: str
    confidence: float
    beneficiaries: List[str]
