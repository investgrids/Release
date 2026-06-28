from typing import Any, Dict
from app.services.ai_provider import AIProvider

class DeepSeekProvider(AIProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def classify_event(self, text: str) -> Dict[str, Any]:
        return {"category": "macro", "confidence": 0.87}

    async def summarize_news(self, text: str) -> str:
        return "A precise AI summary for the provided news text."

    async def generate_story(self, context: Dict[str, Any]) -> str:
        return "Generated market story based on event context."

    async def generate_radar(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {"theme": "Market Shifts", "score": 82}
