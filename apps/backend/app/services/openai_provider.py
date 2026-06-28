from typing import Any, Dict
from app.services.ai_provider import AIProvider

class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def classify_event(self, text: str) -> Dict[str, Any]:
        return {"category": "earnings", "confidence": 0.82}

    async def summarize_news(self, text: str) -> str:
        return "AI summary generated with OpenAI abstraction."

    async def generate_story(self, context: Dict[str, Any]) -> str:
        return "OpenAI-powered story narrative."

    async def generate_radar(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {"theme": "Earnings Momentum", "score": 78}
