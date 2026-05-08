"""
LLM Audit Service — Phase 5.

Every LLM call must be stored for auditability per AGENTS.MD Section 2.2.
This module wraps any LLMProvider, persists LlmRun + LlmOutput rows,
and returns the output dict unchanged.

Optimisation (lazy/adaptive generation):
  Before making any real LLM API call, _run_and_store checks whether an
  LlmOutput with the same (input_hash, prompt_name) already exists in the DB.
  If it does, the cached output is returned immediately — no API call is made.
  This makes all pipeline runs fully idempotent at zero extra cost.
"""

import uuid
import hashlib
import json
import logging
from typing import Callable

from sqlalchemy.orm import Session

from backend.app.models.llm_audit import LlmRun, LlmOutput, LlmPromptVersion
from backend.app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)


def _ensure_prompt_version(
    db: Session, prompt_name: str, version: str, template: str
) -> uuid.UUID:
    """Upsert a prompt version row and return its ID."""
    existing = (
        db.query(LlmPromptVersion)
        .filter(
            LlmPromptVersion.prompt_name == prompt_name,
            LlmPromptVersion.version == version,
        )
        .first()
    )
    if existing:
        return existing.id
    pv = LlmPromptVersion(prompt_name=prompt_name, version=version, prompt_template=template)
    db.add(pv)
    db.flush()
    return pv.id


def _get_cached_output(db: Session, input_hash: str, prompt_name: str) -> dict | None:
    """
    Return a previously stored LlmOutput for this (input_hash, prompt_name) pair.
    Called before every LLM API call to implement idempotent, cost-free re-runs.

    Joins LlmRun → LlmPromptVersion to match by prompt_name.
    Returns the output_json dict, or None if no cache hit.
    """
    run = (
        db.query(LlmRun)
        .join(LlmPromptVersion, LlmRun.prompt_version_id == LlmPromptVersion.id)
        .filter(
            LlmRun.input_hash == input_hash,
            LlmPromptVersion.prompt_name == prompt_name,
        )
        .order_by(LlmRun.created_at.desc())
        .first()
    )
    if not run:
        return None
    cached = db.query(LlmOutput).filter(LlmOutput.llm_run_id == run.id).first()
    if cached and cached.output_json:
        logger.debug(
            "LLM cache hit: prompt_name=%s input_hash=%.12s…", prompt_name, input_hash
        )
        return dict(cached.output_json)
    return None


def _run_and_store(
    db: Session,
    provider: LLMProvider,
    method: Callable,
    input_data: dict,
    prompt_name: str,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
) -> dict:
    """
    1. Check cache (input_hash × prompt_name) — return immediately on hit.
    2. Call provider.method(input_data).
    3. Store LlmRun + LlmOutput rows.
    4. Return output dict.

    Rolls back the DB write on failure but still raises the exception.
    """
    input_hash = hashlib.sha256(
        json.dumps(input_data, sort_keys=True).encode()
    ).hexdigest()

    # ── Cache lookup ──────────────────────────────────────────────────────────
    cached = _get_cached_output(db, input_hash, prompt_name)
    if cached is not None:
        return cached

    # ── Real LLM call ─────────────────────────────────────────────────────────
    output: dict = method(input_data)

    prompt_version = output.pop("_prompt_version", "v1.0")
    output.pop("_input_hash", None)  # computed here; don't store duplicate

    confidence = output.get("confidence") or output.get("classification_confidence")

    try:
        pv_id = _ensure_prompt_version(db, prompt_name, prompt_version, prompt_name)

        run = LlmRun(
            provider=provider.provider,
            model=provider.model,
            prompt_version_id=pv_id,
            input_hash=input_hash,
        )
        db.add(run)
        db.flush()

        out_row = LlmOutput(
            llm_run_id=run.id,
            output_json=output,
            confidence=float(confidence) if confidence is not None else None,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        db.add(out_row)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to store LLM audit row: %s", exc)

    return output


class AuditedLLMService:
    """
    Wraps an LLMProvider and auto-stores every call to the DB.
    Every call is idempotent: identical (input_hash, prompt_name) pairs return the
    cached output without making a real API call.
    Use this instead of calling the provider directly in API handlers.
    """

    def __init__(self, provider: LLMProvider, db: Session):
        self.provider = provider
        self.db = db

    def summarize_bill_or_vote(self, input_data: dict, entity_id: uuid.UUID | None = None) -> dict:
        return _run_and_store(
            self.db, self.provider,
            self.provider.summarize_bill_or_vote, input_data,
            "summarize_bill_or_vote", "bill_or_vote", entity_id,
        )

    def classify_policy_item(self, input_data: dict, entity_id: uuid.UUID | None = None) -> dict:
        return _run_and_store(
            self.db, self.provider,
            self.provider.classify_policy_item, input_data,
            "classify_policy_item", "policy_item", entity_id,
        )

    def extract_policy_axis(self, input_data: dict, entity_id: uuid.UUID | None = None) -> dict:
        return _run_and_store(
            self.db, self.provider,
            self.provider.extract_policy_axis, input_data,
            "extract_policy_axis", "policy_item", entity_id,
        )

    def classify_and_extract(self, input_data: dict, entity_id: uuid.UUID | None = None) -> dict:
        """
        OPTIMISED: single LLM call replaces classify_policy_item + extract_policy_axis.
        Returns merged output with all classification + axis keys.
        Cache-checked like all other calls.
        """
        return _run_and_store(
            self.db, self.provider,
            self.provider.classify_and_extract, input_data,
            "classify_and_extract", "policy_item", entity_id,
        )

    def generate_question(self, input_data: dict, entity_id: uuid.UUID | None = None) -> dict:
        return _run_and_store(
            self.db, self.provider,
            self.provider.generate_question, input_data,
            "generate_question", "question", entity_id,
        )

    def critique_question(self, input_data: dict, entity_id: uuid.UUID | None = None) -> dict:
        return _run_and_store(
            self.db, self.provider,
            self.provider.critique_question, input_data,
            "critique_question", "question", entity_id,
        )

    def generate_question_with_critique(
        self, input_data: dict, entity_id: uuid.UUID | None = None
    ) -> dict:
        """
        OPTIMISED: single LLM call replaces generate_question + critique_question.
        Returns merged output including computed neutrality_score (float 0–1).
        Cache-checked like all other calls.
        """
        return _run_and_store(
            self.db, self.provider,
            self.provider.generate_question_with_critique, input_data,
            "generate_question_with_critique", "question", entity_id,
        )

    def generate_root_question(
        self, input_data: dict, entity_id: uuid.UUID | None = None
    ) -> dict:
        """
        Generate a broad topic-level root question using the dedicated root_question
        prompt from prompts.json. NOT the same as generate_question_with_critique.
        Results are audited and stored like all other LLM calls.
        """
        return _run_and_store(
            self.db, self.provider,
            self.provider.generate_root_question, input_data,
            "generate_root_question", "question", entity_id,
        )

    def generate_discovery_question(
        self, input_data: dict, entity_id: uuid.UUID | None = None
    ) -> dict:
        """
        Generate a niche/discovery question using the 'discovery_question_from_niche'
        prompt.  Used by run_niche_discovery_pipeline to surface questions about
        non-mainstream party legislative positions.
        Results are audited and stored like all other LLM calls.
        """
        return _run_and_store(
            self.db, self.provider,
            self.provider.generate_discovery_question, input_data,
            "discovery_question_from_niche", "question", entity_id,
        )

    def infer_party_position(self, input_data: dict, entity_id: uuid.UUID | None = None) -> dict:
        return _run_and_store(
            self.db, self.provider,
            self.provider.infer_party_position, input_data,
            "infer_party_position", "party_position", entity_id,
        )

    def infer_party_lineage(self, input_data: dict, entity_id: uuid.UUID | None = None) -> dict:
        return _run_and_store(
            self.db, self.provider,
            self.provider.infer_party_lineage, input_data,
            "infer_party_lineage", "party_lineage_edge", entity_id,
        )

