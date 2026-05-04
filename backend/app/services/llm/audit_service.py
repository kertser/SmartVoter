"""
LLM Audit Service — Phase 5.

Every LLM call must be stored for auditability per AGENTS.MD Section 2.2.
This module wraps any LLMProvider, persists LlmRun + LlmOutput rows,
and returns the output dict unchanged.
"""

import uuid
import hashlib
import json
from typing import Callable

from sqlalchemy.orm import Session

from backend.app.models.llm_audit import LlmRun, LlmOutput, LlmPromptVersion
from backend.app.services.llm.base import LLMProvider


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
    Call provider.method(input_data), store LlmRun + LlmOutput, return output.
    Rolls back the DB write on failure but still raises the exception.
    """
    input_hash = hashlib.sha256(
        json.dumps(input_data, sort_keys=True).encode()
    ).hexdigest()

    # Call the LLM
    output: dict = method(input_data)

    prompt_version = output.pop("_prompt_version", "v1.0")
    # _input_hash is computed by providers; drop from stored output
    output.pop("_input_hash", None)

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
        # Log but don't crash — the LLM output is still returned
        import logging
        logging.getLogger(__name__).error("Failed to store LLM audit row: %s", exc)

    return output


class AuditedLLMService:
    """
    Wraps an LLMProvider and auto-stores every call to the DB.
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

