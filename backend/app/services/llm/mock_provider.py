"""
MockLLMProvider — DISABLED.

This provider existed during early development to allow the app to run
without a real LLM API key. It is no longer used in any production or
development path.

To generate questions or classifications, configure a real LLM provider:
  OPENAI_API_KEY=sk-...   (required)
  OPENAI_MODEL=gpt-4o-mini (optional, default)

All seed data (questions, topics, policy items) is loaded from
  backend/app/seed/data/*.json
and seeded into the database via run_seed.py — no LLM is needed for that step.

If you need a mock for automated tests, implement your own LLMProvider
subclass with fixed responses without importing this file.
"""


class MockLLMProvider:
    """Stub — raises RuntimeError on any method call.

    The mock LLM provider has been removed from the production path.
    Configure OPENAI_API_KEY to enable real LLM generation.
    """

    provider = "mock"
    model = "mock-disabled"

    def _not_available(self, *_args, **_kwargs):
        raise RuntimeError(
            "MockLLMProvider is disabled. "
            "Set OPENAI_API_KEY in your .env file to enable real LLM generation. "
            "Seed questions are loaded from backend/app/seed/data/questions.json "
            "and do not require an LLM."
        )

    summarize_bill_or_vote = _not_available
    classify_policy_item = _not_available
    extract_policy_axis = _not_available
    classify_and_extract = _not_available
    generate_question = _not_available
    critique_question = _not_available
    generate_question_with_critique = _not_available
    generate_root_question = _not_available
    generate_follow_up_from_salience = _not_available
    generate_discovery_question = _not_available
    infer_party_position = _not_available
    infer_party_lineage = _not_available
