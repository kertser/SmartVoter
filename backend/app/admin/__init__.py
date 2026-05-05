"""
Admin API — Phase 5.

Endpoints for LLM-assisted content generation and human review.
Per AGENTS.MD Section 15 & 16 (Admin API).
All LLM outputs are stored with prompt version and input hash before any review.
No question is ever surfaced to users until human_review_status = 'approved'.
"""

import uuid
import logging
from fastapi import APIRouter, Depends, Header, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Annotated

from backend.app.db import get_db
from backend.app.config import get_settings, Settings
from backend.app.models.question import Question, AnswerScaleType
from backend.app.models.policy_item import PolicyItem, ReviewStatus
from backend.app.models.llm_audit import LlmRun, LlmOutput
from backend.app.services.llm import get_llm_provider
from backend.app.services.llm.audit_service import AuditedLLMService

logger = logging.getLogger(__name__)


def verify_admin(
    x_admin_password: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    """Dependency: reject requests missing or with wrong admin password."""
    if not x_admin_password or x_admin_password != settings.admin_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin password (X-Admin-Password header).",
        )


admin_router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(verify_admin)],
)


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


# ── Real Knesset data ingestion endpoint ──────────────────────────────────────

class IngestKnessetBody(BaseModel):
    knesset_number: int = 25
    limit: int = 200
    votes_only: bool = False
    bills_only: bool = False
    no_llm: bool = False
    # Phase 6 pipeline flags
    run_factions: bool = False
    run_persons: bool = False
    run_vote_results: bool = False
    run_policy_items: bool = False
    run_party_positions: bool = False
    run_questions: bool = False
    run_lineage: bool = False
    run_volatility: bool = False
    full: bool = False   # run all steps in sequence


# Track running ingestion jobs in memory (MVP: single-process)
_ingestion_jobs: dict[str, dict] = {}


def _run_ingestion(job_id: str, body: IngestKnessetBody, settings: Settings) -> None:
    """
    Background task: fetch → upsert → LLM enrich.
    Phase 6 expanded: also imports factions, persons, vote_results,
    and optionally runs the full pipeline.
    """
    from backend.app.db.session import SessionLocal
    from backend.app.services.ingestion.importers import (
        import_votes, import_bills, import_factions, import_persons, import_vote_results,
    )
    from backend.app.services.ingestion.policy_item_pipeline import run_policy_item_pipeline
    from backend.app.services.ingestion.party_position_pipeline import run_party_position_pipeline
    from backend.app.services.ingestion.question_pipeline import run_question_pipeline
    from backend.app.services.lineage.lineage_service import run_lineage_inference
    from backend.app.services.volatility.volatility_service import run_volatility_update

    db = SessionLocal()
    _ingestion_jobs[job_id]["status"] = "running"
    results: dict[str, object] = {}

    def _step(label: str, fn, *args, **kwargs):
        try:
            out = fn(*args, **kwargs)
            results[label] = out
            _ingestion_jobs[job_id][label] = out
            logger.info("Job %s [%s]: %s", job_id, label, out)
        except Exception as exc:
            results[label] = {"error": str(exc)}
            _ingestion_jobs[job_id][label] = {"error": str(exc)}
            logger.error("Job %s [%s] failed: %s", job_id, label, exc, exc_info=True)

    try:
        # Step 1: factions (party instances)
        if body.run_factions or body.full:
            _step("factions", import_factions, db, body.knesset_number, settings)

        # Step 2: votes
        if (not body.bills_only) or body.full:
            _step("votes", import_votes, db, body.knesset_number, settings,
                  limit=body.limit, enrich_with_llm=not body.no_llm)

        # Step 3: bills
        if (not body.votes_only) or body.full:
            _step("bills", import_bills, db, body.knesset_number, settings,
                  limit=body.limit, enrich_with_llm=not body.no_llm)

        # Step 4: persons / MK memberships
        if body.run_persons or body.full:
            _step("persons", import_persons, db, body.knesset_number, settings, limit=body.limit)

        # Step 5: per-MK vote results
        if body.run_vote_results or body.full:
            _step("vote_results", import_vote_results, db, body.knesset_number, settings,
                  vote_limit=body.limit)

        # Pipeline steps (only if requested or full)
        if body.run_policy_items or body.full:
            _step("policy_items", run_policy_item_pipeline, db, settings,
                  knesset_number=body.knesset_number,
                  limit=body.limit, enrich_with_llm=not body.no_llm)

        if body.run_party_positions or body.full:
            _step("party_positions", run_party_position_pipeline, db, settings,
                  knesset_number=body.knesset_number,
                  enrich_with_llm=not body.no_llm)

        if body.run_questions or body.full:
            _step("questions", run_question_pipeline, db, settings, limit=body.limit)

        if body.run_lineage or body.full:
            _step("lineage", run_lineage_inference, db, settings,
                  knesset_number=body.knesset_number,
                  enrich_with_llm=not body.no_llm)

        if body.run_volatility or body.full:
            _step("volatility", run_volatility_update, db,
                  knesset_number=body.knesset_number)

        _ingestion_jobs[job_id]["status"] = "done"
        _ingestion_jobs[job_id]["results"] = results
        logger.info("Ingestion job %s complete", job_id)
    except Exception as exc:
        logger.error("Ingestion job %s failed: %s", job_id, exc, exc_info=True)
        _ingestion_jobs[job_id]["status"] = "error"
        _ingestion_jobs[job_id]["error"] = str(exc)
    finally:
        db.close()


@admin_router.post("/ingest/knesset")
def trigger_knesset_ingestion(
    body: IngestKnessetBody,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Trigger real Knesset data ingestion.
    Fetches votes and/or bills from the official Knesset OData API,
    upserts into the database, and optionally enriches with LLM summaries.
    Runs as a background task. Poll /api/admin/ingest/status/{job_id} for progress.
    Per AGENTS.MD Section 16.
    """
    import uuid as _uuid
    job_id = str(_uuid.uuid4())[:8]
    _ingestion_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "knesset_number": body.knesset_number,
        "limit": body.limit,
        "no_llm": body.no_llm,
    }
    background_tasks.add_task(_run_ingestion, job_id, body, settings)
    return {"job_id": job_id, "status": "queued", "message": f"Ingestion started for Knesset {body.knesset_number}."}


@admin_router.get("/ingest/status/{job_id}")
def get_ingestion_status(job_id: str) -> dict:
    """Poll the status of a background ingestion job."""
    job = _ingestion_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@admin_router.get("/ingest/probe-votes/{knesset_number}")
def probe_knesset_votes(
    knesset_number: int,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Probe whether the Knesset Votes.svc OData endpoint has data for the given
    Knesset number.  Useful for checking Knesset 25/26 availability before
    triggering a full import. (Gap 8 — AGENTS.MD)
    """
    from backend.app.services.ingestion.knesset_odata import probe_votes_availability
    available = probe_votes_availability(settings.knesset_votes_api_base_url, knesset_number)
    return {
        "knesset_number": knesset_number,
        "votes_available": available,
        "message": (
            f"Knesset {knesset_number} vote data is {'available' if available else 'NOT available'} "
            f"in the official OData API (Votes.svc)."
        ),
        "alternative": (
            None if available
            else "Consider Open Knesset (https://oknesset.org/api/v2/vote/) "
                 "as a supplemental source for newer Knessets."
        ),
    }


@admin_router.get("/ingest/jobs")
def list_ingestion_jobs() -> list[dict]:
    """List all ingestion jobs (current process only, not persisted)."""
    return list(_ingestion_jobs.values())



# ── Dedicated pipeline endpoints ──────────────────────────────────────────────

class PipelineBody(BaseModel):
    knesset_number: int | None = None
    limit: int = 100
    no_llm: bool = False
    overwrite: bool = False


@admin_router.post("/pipeline/policy-items")
def trigger_policy_item_pipeline(
    body: PipelineBody,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Convert imported votes/bills into PolicyItem records via LLM classification.
    All created items start with human_review_status = needs_review.
    """
    job_id = str(__import__("uuid").uuid4())[:8]
    _ingestion_jobs[job_id] = {"job_id": job_id, "status": "queued", "step": "policy_items"}

    def _run():
        from backend.app.db.session import SessionLocal
        from backend.app.services.ingestion.policy_item_pipeline import run_policy_item_pipeline
        db = SessionLocal()
        _ingestion_jobs[job_id]["status"] = "running"
        try:
            stats = run_policy_item_pipeline(
                db, settings,
                knesset_number=body.knesset_number,
                limit=body.limit,
                enrich_with_llm=not body.no_llm,
            )
            _ingestion_jobs[job_id].update({"status": "done", **stats})
        except Exception as exc:
            _ingestion_jobs[job_id].update({"status": "error", "error": str(exc)})
        finally:
            db.close()

    background_tasks.add_task(_run)
    return {"job_id": job_id, "status": "queued"}


@admin_router.post("/pipeline/party-positions")
def trigger_party_position_pipeline(
    body: PipelineBody,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Derive PartyPosition records from vote_results for each
    (party_instance × policy_item) pair. Uses LLM to infer positions.
    """
    job_id = str(__import__("uuid").uuid4())[:8]
    _ingestion_jobs[job_id] = {"job_id": job_id, "status": "queued", "step": "party_positions"}

    def _run():
        from backend.app.db.session import SessionLocal
        from backend.app.services.ingestion.party_position_pipeline import run_party_position_pipeline
        db = SessionLocal()
        _ingestion_jobs[job_id]["status"] = "running"
        try:
            stats = run_party_position_pipeline(
                db, settings,
                knesset_number=body.knesset_number,
                enrich_with_llm=not body.no_llm,
                overwrite_existing=body.overwrite,
            )
            _ingestion_jobs[job_id].update({"status": "done", **stats})
        except Exception as exc:
            _ingestion_jobs[job_id].update({"status": "error", "error": str(exc)})
        finally:
            db.close()

    background_tasks.add_task(_run)
    return {"job_id": job_id, "status": "queued"}


@admin_router.post("/pipeline/questions")
def trigger_question_pipeline(
    body: PipelineBody,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Batch-generate questions for approved/needs_review policy items.
    All questions start as needs_review — human approval required.
    """
    job_id = str(__import__("uuid").uuid4())[:8]
    _ingestion_jobs[job_id] = {"job_id": job_id, "status": "queued", "step": "questions"}

    def _run():
        from backend.app.db.session import SessionLocal
        from backend.app.services.ingestion.question_pipeline import run_question_pipeline
        db = SessionLocal()
        _ingestion_jobs[job_id]["status"] = "running"
        try:
            stats = run_question_pipeline(db, settings, limit=body.limit)
            _ingestion_jobs[job_id].update({"status": "done", **stats})
        except Exception as exc:
            _ingestion_jobs[job_id].update({"status": "error", "error": str(exc)})
        finally:
            db.close()

    background_tasks.add_task(_run)
    return {"job_id": job_id, "status": "queued"}


@admin_router.post("/pipeline/lineage")
def trigger_lineage_pipeline(
    body: PipelineBody,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Propose lineage edges between party instances via LLM name/context analysis.
    All edges start as needs_review.
    """
    job_id = str(__import__("uuid").uuid4())[:8]
    _ingestion_jobs[job_id] = {"job_id": job_id, "status": "queued", "step": "lineage"}

    def _run():
        from backend.app.db.session import SessionLocal
        from backend.app.services.lineage.lineage_service import run_lineage_inference
        db = SessionLocal()
        _ingestion_jobs[job_id]["status"] = "running"
        try:
            stats = run_lineage_inference(
                db, settings,
                knesset_number=body.knesset_number,
                enrich_with_llm=not body.no_llm,
            )
            _ingestion_jobs[job_id].update({"status": "done", **stats})
        except Exception as exc:
            _ingestion_jobs[job_id].update({"status": "error", "error": str(exc)})
        finally:
            db.close()

    background_tasks.add_task(_run)
    return {"job_id": job_id, "status": "queued"}


@admin_router.post("/pipeline/volatility")
def trigger_volatility_pipeline(
    body: PipelineBody,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Compute and cache candidate and party volatility scores.
    """
    job_id = str(__import__("uuid").uuid4())[:8]
    _ingestion_jobs[job_id] = {"job_id": job_id, "status": "queued", "step": "volatility"}

    def _run():
        from backend.app.db.session import SessionLocal
        from backend.app.services.volatility.volatility_service import run_volatility_update
        db = SessionLocal()
        _ingestion_jobs[job_id]["status"] = "running"
        try:
            result = run_volatility_update(db, knesset_number=body.knesset_number)
            summary = result.get("summary", {})
            _ingestion_jobs[job_id].update({"status": "done", **summary})
        except Exception as exc:
            _ingestion_jobs[job_id].update({"status": "error", "error": str(exc)})
        finally:
            db.close()

    background_tasks.add_task(_run)
    return {"job_id": job_id, "status": "queued"}


