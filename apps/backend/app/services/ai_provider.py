from abc import ABC, abstractmethod
from typing import Any, Dict

class AIProvider(ABC):
    @abstractmethod
    async def classify_event(self, text: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def summarize_news(self, text: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def generate_story(self, context: Dict[str, Any]) -> str:
        raise NotImplementedError

    @abstractmethod
    async def generate_radar(self, context: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError
