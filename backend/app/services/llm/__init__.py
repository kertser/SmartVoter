from backend.app.services.llm.base import LLMProvider
from backend.app.services.llm.mock_provider import MockLLMProvider
from backend.app.services.llm.openai_provider import OpenAIProvider
from backend.app.services.llm.fallback_provider import FallbackLLMProvider
from backend.app.config import Settings


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Factory: returns the appropriate LLM provider.
    Uses OpenAI (with mock fallback) when OPENAI_API_KEY is set, pure mock otherwise.
    Phase 5+: wire in Anthropic/Gemini here without changing callers."""
    if settings.has_openai:
        openai = OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model)
        return FallbackLLMProvider(openai=openai, max_retries=settings.llm_max_retries)
    return MockLLMProvider()

