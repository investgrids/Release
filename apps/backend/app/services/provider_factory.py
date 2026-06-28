from app.core.config import settings
from app.services.deepseek_provider import DeepSeekProvider
from app.services.openai_provider import OpenAIProvider
from app.services.gemini_provider import GeminiProvider
from app.services.ai_provider import AIProvider

def get_ai_provider() -> AIProvider:
    provider = settings.ai_provider.lower()
    api_key = settings.deepseek_api_key

    if provider == "openai":
        return OpenAIProvider(api_key=api_key)
    if provider == "gemini":
        return GeminiProvider(api_key=api_key)
    return DeepSeekProvider(api_key=api_key)
