"""
Admin API — Phase 5.

Endpoints for LLM-assisted content generation and human review.
Per AGENTS.MD Section 15 & 16 (Admin API).
All LLM outputs are stored with prompt version and input hash before any review.
No question is ever surfaced to users until human_review_status = 'approved'.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.db import get_db
from backend.app.config import get_settings
from backend.app.models.question import Question, AnswerScaleType
from backend.app.models.policy_item import PolicyItem, ReviewStatus
from backend.app.models.llm_audit import LlmRun, LlmOutput
from backend.app.services.llm import get_llm_provider
from backend.app.services.llm.audit_service import AuditedLLMService

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Review endpoints ──────────────────────────────────────────────────────────

@admin_router.get("/review/items")
def get_review_items(
    status: str | None = None, db: Session = Depends(get_db)
) -> list[dict]:
    """Return questions for admin review, optionally filtered by status."""
    q = db.query(Question)
    if status:
        q = q.filter(Question.human_review_status == status)
    else:
        q = q.filter(Question.human_review_status != ReviewStatus.approved)
    questions = q.order_by(Question.human_review_status).all()
    return [
        {
            "id": str(q.id),
            "policy_item_id": str(q.policy_item_id),
            "question_text_en": q.question_text_en,
            "question_text_he": q.question_text_he,
            "question_text_ru": q.question_text_ru,
            "status": q.human_review_status.value,
            "answer_scale_type": q.answer_scale_type.value,
            "neutrality_score": q.neutrality_score,
            "complexity_score": q.complexity_score,
            "llm_prompt_version": q.llm_prompt_version,
        }
        for q in questions
    ]


@admin_router.post("/review/{item_id}/approve")
def approve_item(item_id: str, db: Session = Depends(get_db)) -> dict:
    """Approve a question for public use."""
    q = db.query(Question).filter(Question.id == uuid.UUID(item_id)).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    q.human_review_status = ReviewStatus.approved
    db.commit()
    return {"status": "approved", "id": item_id}


@admin_router.post("/review/{item_id}/reject")
def reject_item(item_id: str, db: Session = Depends(get_db)) -> dict:
    """Reject a question."""
    q = db.query(Question).filter(Question.id == uuid.UUID(item_id)).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    q.human_review_status = ReviewStatus.rejected
    db.commit()
    return {"status": "rejected", "id": item_id}


class EditQuestionBody(BaseModel):
    question_text_en: str | None = None
    question_text_he: str | None = None
    question_text_ru: str | None = None
    neutrality_score: float | None = None


@admin_router.patch("/review/{item_id}/edit")
def edit_question(item_id: str, body: EditQuestionBody, db: Session = Depends(get_db)) -> dict:
    """Edit question text before approving."""
    q = db.query(Question).filter(Question.id == uuid.UUID(item_id)).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    if body.question_text_en is not None:
        q.question_text_en = body.question_text_en
    if body.question_text_he is not None:
        q.question_text_he = body.question_text_he
    if body.question_text_ru is not None:
        q.question_text_ru = body.question_text_ru
    if body.neutrality_score is not None:
        q.neutrality_score = body.neutrality_score
    q.human_review_status = ReviewStatus.needs_review
    db.commit()
    return {"status": "edited", "id": item_id}


# ── LLM generation endpoints ──────────────────────────────────────────────────

class GenerateQuestionsBody(BaseModel):
    policy_item_ids: list[str]


@admin_router.post("/llm/generate-questions")
def generate_questions(
    body: GenerateQuestionsBody,
    db: Session = Depends(get_db),
    settings=Depends(get_settings),
) -> dict:
    """
    Use LLM to generate questions for specified policy items.
    All outputs are stored for audit and placed in needs_review status.
    Human approval required before questions become public.
    """
    provider = get_llm_provider(settings)
    svc = AuditedLLMService(provider, db)
    generated = []

    for pid_str in body.policy_item_ids:
        try:
            pid = uuid.UUID(pid_str)
        except ValueError:
            generated.append({"policy_item_id": pid_str, "error": "invalid UUID"})
            continue

        pi = db.query(PolicyItem).filter(PolicyItem.id == pid).first()
        if not pi:
            generated.append({"policy_item_id": pid_str, "error": "not found"})
            continue

        input_data = {
            "title": pi.title,
            "description": pi.description or "",
            "directional_axis": pi.directional_axis or "",
        }

        try:
            result = svc.generate_question(input_data, entity_id=pid)
        except Exception as exc:
            generated.append({"policy_item_id": pid_str, "error": str(exc)})
            continue

        # Critique pass to compute neutrality score
        critique_input = {"question": result.get("question_en", result.get("question", ""))}
        try:
            critique = svc.critique_question(critique_input)
        except Exception:
            critique = {"neutrality_risk": "unknown", "is_loaded": False}

        neutrality_score = (
            0.4 if critique.get("is_loaded") else
            0.9 if result.get("neutrality_risk") == "low" else
            0.7 if result.get("neutrality_risk") == "medium" else 0.5
        )

        q = Question(
            policy_item_id=pid,
            question_text_en=result.get("question_en") or result.get("question", ""),
            question_text_he=result.get("question_he", ""),
            question_text_ru=result.get("question_ru", ""),
            answer_scale_type=AnswerScaleType.likert_5,
            neutrality_score=neutrality_score,
            llm_prompt_version=result.get("_prompt_version", "v1.0"),
            human_review_status=ReviewStatus.needs_review,
        )
        db.add(q)
        db.commit()
        db.refresh(q)

        generated.append({
            "policy_item_id": pid_str,
            "question_id": str(q.id),
            "question_en": q.question_text_en,
            "question_he": q.question_text_he,
            "question_ru": q.question_text_ru,
            "neutrality_score": neutrality_score,
            "is_loaded": critique.get("is_loaded", False),
            "suggested_revision": critique.get("suggested_revision"),
            "status": "needs_review",
            "provider": provider.provider,
        })

    return {"generated": generated, "count": len(generated)}


class ClassifyPolicyBody(BaseModel):
    policy_item_id: str


@admin_router.post("/llm/classify")
def classify_policy(
    body: ClassifyPolicyBody,
    db: Session = Depends(get_db),
    settings=Depends(get_settings),
) -> dict:
    """Run LLM topic classification for a policy item. Stores output for audit."""
    try:
        pid = uuid.UUID(body.policy_item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    pi = db.query(PolicyItem).filter(PolicyItem.id == pid).first()
    if not pi:
        raise HTTPException(status_code=404, detail="Policy item not found")

    provider = get_llm_provider(settings)
    svc = AuditedLLMService(provider, db)
    result = svc.classify_policy_item(
        {"title": pi.title, "description": pi.description or ""},
        entity_id=pid,
    )
    pi.llm_confidence = result.get("classification_confidence")
    db.commit()

    return {
        "policy_item_id": str(pid),
        "title": pi.title,
        "classification": result,
        "provider": provider.provider,
    }


# ── LLM audit viewer ──────────────────────────────────────────────────────────

@admin_router.get("/llm/outputs")
def get_llm_outputs(
    limit: int = 50, offset: int = 0, db: Session = Depends(get_db)
) -> list[dict]:
    """Return recent LLM outputs for admin audit."""
    rows = (
        db.query(LlmOutput)
        .join(LlmRun, LlmRun.id == LlmOutput.llm_run_id)
        .order_by(LlmOutput.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    result = []
    for row in rows:
        run = db.query(LlmRun).filter(LlmRun.id == row.llm_run_id).first()
        result.append({
            "id": str(row.id),
            "run_id": str(row.llm_run_id),
            "provider": run.provider if run else "unknown",
            "model": run.model if run else "unknown",
            "entity_type": row.entity_type,
            "entity_id": str(row.entity_id) if row.entity_id else None,
            "confidence": row.confidence,
            "output_summary": _summarize_output(row.output_json),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })
    return result


@admin_router.get("/policy-items")
def list_policy_items(db: Session = Depends(get_db)) -> list[dict]:
    """List all policy items for LLM generation target selection."""
    items = db.query(PolicyItem).all()
    return [
        {
            "id": str(pi.id),
            "title": pi.title,
            "description": pi.description,
            "directional_axis": pi.directional_axis,
            "source_type": pi.source_type.value,
            "llm_confidence": pi.llm_confidence,
            "human_review_status": pi.human_review_status.value,
        }
        for pi in items
    ]


def _summarize_output(output: dict) -> str:
    if "question_en" in output or "question" in output:
        return f"Q: {(output.get('question_en') or output.get('question', ''))[:120]}"
    if "primary_topic" in output:
        return f"Topic: {output['primary_topic']} conf={output.get('classification_confidence', '?')}"
    if "party_position_mean" in output:
        return f"Position: {output['party_position_mean']:.2f} ± {output.get('uncertainty', '?')}"
    if "plain_summary" in output:
        return output["plain_summary"][:120]
    return str(output)[:120]

