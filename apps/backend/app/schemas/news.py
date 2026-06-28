from pydantic import BaseModel
from typing import List, Optional

class NewsArticle(BaseModel):
    id: str
    headline: str
    summary: str
    source: str
    published_at: str
    companies: List[str]
    impact_score: float
    url: Optional[str] = None
