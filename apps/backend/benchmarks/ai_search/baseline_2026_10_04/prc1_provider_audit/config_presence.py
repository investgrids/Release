"""
PRC-1 configuration audit. Prints ONLY which AI providers are configured (a boolean per provider key) and the model slugs the chain would try, in chain order. Never prints a key,
a prefix of a key, a base URL with credentials, or any other secret value.

Local:       cd apps/backend && PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/prc1_provider_audit/config_presence.py
Production:  from the linked monorepo checkout, `railway run python <this file>` (the environment is injected into this local process; nothing is printed except the booleans below)
"""
import sys

sys.path.insert(0, ".")
from app.core.config import settings  # noqa: E402
from app.services import ai_service as S  # noqa: E402

chain = [
    ("groq-hq", "groq_api_key", S._GROQ_HIGH),
    ("groq-fast", "groq_api_key", S._GROQ_FAST),
    ("openrouter-hq", "openrouter_api_key", S._OR_HIGH_QUALITY),
    ("mistral", "mistral_api_key", S._MISTRAL_MODELS),
    ("gemini", "gemini_api_key", S._GEMINI_MODELS),
    ("openrouter-small", "openrouter_api_key", S._OR_SMALL),
]
print("environment label:", "production-like" if getattr(settings, "is_production", False) else "not production (is_production False)")
for tier, key_attr, models in chain:
    configured = bool(getattr(settings, key_attr, None))
    print(f"{tier:17} key configured: {str(configured):5} | tier attempted by the chain: {str(configured):5} | models: {', '.join(models)}")
print("settings fields that exist for other tiers (booleans only):",
      {n: bool(getattr(settings, n, None)) for n in ("nvidia_api_key", "deepseek_api_key", "openai_api_key") if hasattr(settings, n)})
