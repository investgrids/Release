from typing import Any, Dict
from app.services.ai_provider import AIProvider

class GeminiProvider(AIProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def classify_event(self, text: str) -> Dict[str, Any]:
        return {"category": "policy", "confidence": 0.75}

    async def summarize_news(self, text: str) -> str:
        return "Gemini-style concise summary with event-aware framing."

    async def generate_story(self, context: Dict[str, Any]) -> str:
        return "Gemini-driven narrative for market themes."

    async def generate_radar(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return {"theme": "Policy Pulse", "score": 80}
