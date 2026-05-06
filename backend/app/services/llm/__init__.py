from backend.app.services.llm.base import LLMProvider
from backend.app.services.llm.openai_provider import OpenAIProvider
from backend.app.services.llm.fallback_provider import FallbackLLMProvider
from backend.app.config import Settings


class LLMNotConfiguredError(RuntimeError):
    """Raised when no real LLM provider is configured."""


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Factory: returns a real LLM provider (OpenAI with retry logic).

    Raises LLMNotConfiguredError if OPENAI_API_KEY is not set.
    There is no mock fallback — every LLM call must go to a real provider.

    To add another provider (Anthropic, Gemini, etc.), add a branch here
    without changing any callers.
    """
    if settings.has_openai:
        openai = OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model)
        return FallbackLLMProvider(openai=openai, max_retries=settings.llm_max_retries)

    raise LLMNotConfiguredError(
        "No LLM provider is configured. "
        "Set OPENAI_API_KEY (starting with 'sk-') in your .env file. "
        "Seed data (questions, topics, policy items) is loaded from "
        "backend/app/seed/data/*.json and does not require an LLM key."
    )

