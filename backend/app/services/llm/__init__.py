from backend.app.services.llm.base import LLMProvider
from backend.app.services.llm.mock_provider import MockLLMProvider
from backend.app.config import Settings


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Factory: returns the appropriate LLM provider based on APP_ENV.
    Phase 1: always returns MockLLMProvider.
    Phase 5+: wire in real providers (OpenAI, Anthropic, etc.)."""
    if settings.app_env in ("development", "test"):
        return MockLLMProvider()
    # Future: return OpenAIProvider(settings) etc.
    return MockLLMProvider()

