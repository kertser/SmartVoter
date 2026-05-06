"""
FallbackLLMProvider — wraps OpenAIProvider with retry logic and falls back to
MockLLMProvider on repeated failure. (AGENTS.MD Section 4 / Phase 5)
"""
import logging
import time

from backend.app.services.llm.base import LLMProvider
from backend.app.services.llm.mock_provider import MockLLMProvider
from backend.app.services.llm.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class LLMProviderError(Exception):
    """Raised when an LLM provider call fails after all retries."""


class FallbackLLMProvider(LLMProvider):
    """
    Tries OpenAIProvider first; falls back to MockLLMProvider after max_retries.
    Each retry waits 2 ^ attempt seconds (exponential back-off, capped at 8 s).
    """

    provider = "fallback"
    model = "fallback"  # required by AuditedLLMService / LlmRun row

    def __init__(self, openai: OpenAIProvider, max_retries: int = 2):
        self.model = f"fallback({openai.model})"  # more descriptive at runtime
        self._openai = openai
        self._mock = MockLLMProvider()
        self._max_retries = max_retries

    def _call_with_fallback(self, method_name: str, input_data: dict) -> dict:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return getattr(self._openai, method_name)(input_data)
            except Exception as exc:
                last_error = exc
                wait = min(2**attempt, 8)
                logger.warning(
                    "OpenAI %s failed (attempt %d/%d): %s. Retrying in %ds.",
                    method_name,
                    attempt + 1,
                    self._max_retries + 1,
                    exc,
                    wait,
                )
                if attempt < self._max_retries:
                    time.sleep(wait)

        logger.error(
            "OpenAI %s failed after %d retries. Falling back to mock. Error: %s",
            method_name,
            self._max_retries + 1,
            last_error,
        )
        return getattr(self._mock, method_name)(input_data)

    def summarize_bill_or_vote(self, input_data: dict) -> dict:
        return self._call_with_fallback("summarize_bill_or_vote", input_data)

    def classify_policy_item(self, input_data: dict) -> dict:
        return self._call_with_fallback("classify_policy_item", input_data)

    def extract_policy_axis(self, input_data: dict) -> dict:
        return self._call_with_fallback("extract_policy_axis", input_data)

    def generate_question(self, input_data: dict) -> dict:
        return self._call_with_fallback("generate_question", input_data)

    def critique_question(self, input_data: dict) -> dict:
        return self._call_with_fallback("critique_question", input_data)

    def infer_party_position(self, input_data: dict) -> dict:
        return self._call_with_fallback("infer_party_position", input_data)

    def infer_party_lineage(self, input_data: dict) -> dict:
        return self._call_with_fallback("infer_party_lineage", input_data)

