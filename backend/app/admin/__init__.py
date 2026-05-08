"""
Admin API — Phase 5.

Endpoints for LLM-assisted content generation and human review.
Per AGENTS.MD Section 15 & 16 (Admin API).
All LLM outputs are stored with prompt version and input hash before any review.
No question is ever surfaced to users until human_review_status = 'approved'.
"""

import uuid
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException, status, BackgroundTasks, UploadFile, File
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Annotated

from backend.app.db import get_db
from backend.app.config import get_settings, Settings
from backend.app.models.question import Question, AnswerScaleType
from backend.app.models.policy_item import PolicyItem, ReviewStatus
from backend.app.models.topic import Topic
from backend.app.models.llm_audit import LlmRun, LlmOutput
from backend.app.services.llm import get_llm_provider
from backend.app.services.llm.audit_service import AuditedLLMService
from backend.app.services.llm.question_format import check_question_format

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


class BulkApproveBody(BaseModel):
    ids: list[str] | None = None   # if None → approve ALL non-approved questions
    status_filter: str | None = None  # optionally restrict to a specific status


@admin_router.post("/review/bulk-approve")
def bulk_approve_items(
    body: BulkApproveBody, db: Session = Depends(get_db)
) -> dict:
    """
    Approve multiple questions in one call.
    If `ids` is omitted, approves ALL questions that are not yet approved
    (optionally filtered by `status_filter`, e.g. "needs_review").
    Returns the number of questions approved.
    """
    q = db.query(Question)
    if body.ids is not None:
        uuids = [uuid.UUID(i) for i in body.ids]
        q = q.filter(Question.id.in_(uuids))
    else:
        q = q.filter(Question.human_review_status != ReviewStatus.approved)
        if body.status_filter:
            q = q.filter(Question.human_review_status == body.status_filter)

    questions = q.all()
    count = 0
    for question in questions:
        question.human_review_status = ReviewStatus.approved
        count += 1
    db.commit()
    return {"approved": count, "status": "ok"}


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
    max_workers: int = 6   # parallel LLM calls; keep ≤ 10 to avoid rate limits


@admin_router.post("/llm/generate-questions")
def generate_questions(
    body: GenerateQuestionsBody,
    background_tasks: BackgroundTasks,
    settings=Depends(get_settings),
) -> dict:
    """
    Use LLM to generate questions for specified policy items.
    Runs as a background job (parallel workers) so the HTTP call returns immediately.
    All outputs are stored for audit and placed in needs_review status.
    Human approval required before questions become public.
    Poll /api/admin/ingest/status/{job_id} for progress.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from backend.app.db.session import SessionLocal

    job_id = str(uuid.uuid4())[:8]
    _ingestion_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "step": "generate-questions",
        "total": len(body.policy_item_ids),
        "completed": 0,
        "errors": 0,
        "generated": [],
    }

    def _process_one(pid_str: str) -> dict:
        """Worker: each call gets its own DB session."""
        db = SessionLocal()
        try:
            try:
                pid = uuid.UUID(pid_str)
            except ValueError:
                return {"policy_item_id": pid_str, "error": "invalid UUID"}

            pi = db.query(PolicyItem).filter(PolicyItem.id == pid).first()
            if not pi:
                return {"policy_item_id": pid_str, "error": "not found"}

            provider = get_llm_provider(settings)
            svc = AuditedLLMService(provider, db)
            input_data = {
                "title": pi.title,
                "description": pi.description or "",
                "directional_axis": pi.directional_axis or "",
            }

            try:
                result = svc.generate_question(input_data, entity_id=pid)
            except Exception as exc:
                return {"policy_item_id": pid_str, "error": str(exc)}

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

            # ── Format validation: block open-ended questions before DB insert ──
            question_en_text = result.get("question_en") or result.get("question", "")
            fmt = check_question_format(
                question_en=question_en_text,
                question_he=result.get("question_he", ""),
                question_ru=result.get("question_ru", ""),
            )
            if not fmt["is_valid"]:
                logger.warning(
                    "generate_questions: open-ended question rejected for policy_item %s — %s",
                    pid_str, fmt["issue"],
                )
                return {
                    "policy_item_id": pid_str,
                    "error": f"open_ended_question: {fmt['issue']}",
                    "format_check": fmt,
                }

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

            return {
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
            }
        except Exception as exc:
            return {"policy_item_id": pid_str, "error": str(exc)}
        finally:
            db.close()

    def _run():
        _ingestion_jobs[job_id]["status"] = "running"
        workers = min(max(1, body.max_workers), 10)
        try:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(_process_one, pid_str): pid_str
                    for pid_str in body.policy_item_ids
                }
                for future in as_completed(futures):
                    try:
                        result = future.result()
                    except Exception as exc:
                        result = {"policy_item_id": futures[future], "error": str(exc)}
                        _ingestion_jobs[job_id]["errors"] += 1
                    if "error" in result:
                        _ingestion_jobs[job_id]["errors"] += 1
                    _ingestion_jobs[job_id]["generated"].append(result)
                    _ingestion_jobs[job_id]["completed"] += 1
            _ingestion_jobs[job_id]["status"] = "done"
        except Exception as exc:
            _ingestion_jobs[job_id].update({"status": "error", "error": str(exc)})

    background_tasks.add_task(_run)
    return {
        "job_id": job_id,
        "status": "queued",
        "total": len(body.policy_item_ids),
        "workers": min(max(1, body.max_workers), 10),
        "message": f"Question generation started for {len(body.policy_item_ids)} policy items.",
    }


class DiscoveryQuestionsBody(BaseModel):
    limit: int = 20
    max_workers: int = 4


@admin_router.post("/llm/generate-discovery-questions")
def generate_discovery_questions(
    body: DiscoveryQuestionsBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings=Depends(get_settings),
) -> dict:
    """
    Generate niche/discovery questions for policy items where a non-mainstream
    party has a strong, evidence-backed legislative position.

    These questions feed the adaptive questionnaire's discovery phase, which
    progressively surfaces unexpected party matches (e.g. Party D with consistent
    gun-rights votes, or new Party E with a specific platform plank).

    All generated questions start as 'needs_review' and require human approval.
    Uses the 'discovery_question_from_niche' LLM prompt template.

    Returns a job_id; poll /api/admin/ingest/status/{job_id} for progress.
    """
    from backend.app.services.ingestion.question_pipeline import run_niche_discovery_pipeline

    job_id = str(uuid.uuid4())[:8]
    _ingestion_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "step": "generate-discovery-questions",
        "limit": body.limit,
        "max_workers": body.max_workers,
    }

    def _run():
        _ingestion_jobs[job_id]["status"] = "running"
        try:
            # Run in the background — creates its own DB sessions per worker
            from backend.app.db.session import SessionLocal
            bg_db = SessionLocal()
            try:
                stats = run_niche_discovery_pipeline(
                    bg_db, settings,
                    limit=body.limit,
                    max_workers=body.max_workers,
                )
                _ingestion_jobs[job_id].update({
                    "status": "done",
                    "results": stats,
                })
            finally:
                bg_db.close()
        except Exception as exc:
            _ingestion_jobs[job_id].update({"status": "error", "error": str(exc)})

    background_tasks.add_task(_run)
    return {
        "job_id": job_id,
        "status": "queued",
        "limit": body.limit,
        "message": (
            f"Discovery question generation started (limit={body.limit}). "
            "Targets niche policy items with strong outsider-party positions."
        ),
    }


# ── Question Bank generation (bulk, date-aware) ───────────────────────────────

class GenerateQuestionBankBody(BaseModel):
    max_questions: int | None = None   # defaults to settings.max_questions_to_generate
    depth_levels: int = 2              # 0=root only, 1=root+policy-items, 2=full tree
    max_workers: int = 3               # keep low to avoid 429s; semaphore further limits concurrency
    topics: list[str] | None = None   # if None, all topics
    force_regenerate: bool = False     # regenerate even if questions already exist
    root_questions_per_topic: int = 3  # how many root (depth-0) questions per topic


_question_bank_jobs: dict[str, dict] = {}


@admin_router.post("/llm/generate-question-bank")
def generate_question_bank(
    body: GenerateQuestionBankBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings=Depends(get_settings),
) -> dict:
    """
    Bulk pre-generate a large bank of diverse questions (default: 300) organised as
    a topic-tree graph:

      Depth 0 — Topic root questions (one broad values-discovery question per topic)
      Depth 1 — Policy-item questions (specific closed propositions per policy item)
      Depth 2 — Directional drill-downs (follow-ups for strong support vs oppose directions)

    All questions are date-aware (May 2026) — stale references to resolved events
    (e.g. Gaza hostage negotiations) are excluded automatically.

    The generated questions are saved to the DB in needs_review status.
    Human approval is required before questions become live in the questionnaire.

    Returns a job_id; poll GET /api/admin/llm/question-bank-status/{job_id} for progress.
    """
    from backend.app.services.ingestion.question_bank_pipeline import run_question_bank_pipeline
    from backend.app.db.session import SessionLocal

    max_q = body.max_questions or settings.max_questions_to_generate

    job_id = str(uuid.uuid4())[:8]
    _question_bank_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "max_questions": max_q,
        "depth_levels": body.depth_levels,
        "created": 0,
        "skipped": 0,
        "errors": 0,
        "stale_marked": 0,
        "message": "Queued",
    }

    def _run():
        _question_bank_jobs[job_id]["status"] = "running"
        bg_db = SessionLocal()
        try:
            def _progress(step: str, completed: int, total: int):
                _question_bank_jobs[job_id]["step"] = step
                _question_bank_jobs[job_id]["step_completed"] = completed
                _question_bank_jobs[job_id]["step_total"] = total

            stats = run_question_bank_pipeline(
                bg_db,
                settings,
                max_questions=max_q,
                depth_levels=body.depth_levels,
                max_workers=body.max_workers,
                topics_filter=body.topics or None,
                force_regenerate=body.force_regenerate,
                root_questions_per_topic=body.root_questions_per_topic,
                progress_callback=_progress,
            )
            _question_bank_jobs[job_id].update({
                "status": "done",
                **stats,
            })
        except Exception as exc:
            _question_bank_jobs[job_id].update({"status": "error", "error": str(exc)})
            logger.error("generate_question_bank job %s failed: %s", job_id, exc, exc_info=True)
        finally:
            bg_db.close()

    background_tasks.add_task(_run)
    return {
        "job_id": job_id,
        "status": "queued",
        "max_questions": max_q,
        "depth_levels": body.depth_levels,
        "message": (
            f"Question bank generation queued (max={max_q} questions, "
            f"depth={body.depth_levels}, workers={body.max_workers}). "
            "Poll /api/admin/llm/question-bank-status/{job_id} for progress."
        ),
    }


@admin_router.get("/llm/question-bank-status/{job_id}")
def get_question_bank_status(job_id: str) -> dict:
    """Poll the status of a question bank generation job."""
    job = _question_bank_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return job


@admin_router.get("/llm/question-bank-jobs")
def list_question_bank_jobs() -> list[dict]:
    """List all recent question bank generation jobs."""
    return list(_question_bank_jobs.values())


@admin_router.post("/llm/mark-stale-questions")
def mark_stale_questions_endpoint(db: Session = Depends(get_db)) -> dict:
    """
    Scan all questions for stale-event keywords (e.g. 'release the hostages')
    and mark them as is_stale=True. They will be hidden from the live questionnaire
    but kept in the DB for audit purposes.
    """
    from backend.app.services.ingestion.question_bank_pipeline import mark_stale_questions
    count = mark_stale_questions(db)
    return {"marked_stale": count, "message": f"{count} questions marked as stale."}


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


@admin_router.get("/ingest/available-data")
def get_available_knesset_data(db: Session = Depends(get_db)) -> dict:
    """
    Return a summary of which Knessets already have data in the database.
    Useful to display before launching ingestion so the admin knows what is
    already available (votes, factions/party instances, bills, persons).
    """
    from sqlalchemy import func
    from backend.app.models.vote import Vote
    from backend.app.models.bill import Bill
    from backend.app.models.party_instance import PartyInstance
    from backend.app.models.person import Person
    from backend.app.models.vote_result import VoteResult

    # Per-Knesset vote counts
    vote_rows = (
        db.query(Vote.knesset_number, func.count(Vote.id).label("cnt"))
        .filter(Vote.knesset_number.isnot(None))
        .group_by(Vote.knesset_number)
        .order_by(Vote.knesset_number)
        .all()
    )

    # Per-Knesset faction/party-instance counts
    faction_rows = (
        db.query(PartyInstance.knesset_number, func.count(PartyInstance.id).label("cnt"))
        .filter(PartyInstance.knesset_number.isnot(None))
        .group_by(PartyInstance.knesset_number)
        .order_by(PartyInstance.knesset_number)
        .all()
    )

    vote_counts: dict[str, int] = {str(r.knesset_number): r.cnt for r in vote_rows}
    faction_counts: dict[str, int] = {str(r.knesset_number): r.cnt for r in faction_rows}

    knessets_with_votes = sorted(int(k) for k in vote_counts)
    knessets_with_factions = sorted(int(k) for k in faction_counts)
    all_knessets = sorted(set(knessets_with_votes) | set(knessets_with_factions))

    # Global totals
    total_votes = db.query(func.count(Vote.id)).scalar() or 0
    total_bills = db.query(func.count(Bill.id)).scalar() or 0
    total_persons = db.query(func.count(Person.id)).scalar() or 0
    total_vote_results = db.query(func.count(VoteResult.id)).scalar() or 0

    if all_knessets:
        if len(all_knessets) == 1:
            summary = f"Кнессет {all_knessets[0]}"
        else:
            summary = f"Кнессет {min(all_knessets)}–{max(all_knessets)}"
    else:
        summary = None

    return {
        "knessets": all_knessets,
        "knessets_with_votes": knessets_with_votes,
        "knessets_with_factions": knessets_with_factions,
        "vote_counts": vote_counts,
        "faction_counts": faction_counts,
        "total_votes": total_votes,
        "total_bills": total_bills,
        "total_persons": total_persons,
        "total_vote_results": total_vote_results,
        "summary": summary,
    }


# ── Full Multi-Knesset Pipeline ───────────────────────────────────────────────

class FullPipelineBody(BaseModel):
    last_n_knessets: int = 2          # how many recent Knessets to import
    no_llm: bool = True               # default True — LLM costs money; enable explicitly
    current_knesset: int | None = None  # override settings.current_knesset


def _run_full_pipeline(job_id: str, body: FullPipelineBody, settings: Settings) -> None:
    """
    Background task: full pipeline for the last N Knessets.

    Phase 1 (per Knesset): factions → votes* → bills → persons → vote_results*
        (* skipped for Knessets > settings.last_knesset_with_votes)

    Phase 2 (once, after all Knessets): policy_items → party_positions →
        [questions if not no_llm] → lineage → volatility
    """
    from backend.app.db.session import SessionLocal
    from backend.app.services.ingestion.importers import (
        import_factions, import_votes, import_bills,
        import_persons, import_vote_results,
    )
    from backend.app.services.ingestion.policy_item_pipeline import run_policy_item_pipeline
    from backend.app.services.ingestion.party_position_pipeline import run_party_position_pipeline
    from backend.app.services.ingestion.question_pipeline import run_question_pipeline
    from backend.app.services.lineage.lineage_service import run_lineage_inference
    from backend.app.services.volatility.volatility_service import run_volatility_update

    current = body.current_knesset or settings.current_knesset
    last_votes = settings.last_knesset_with_votes
    knessets = list(range(current, current - body.last_n_knessets, -1))  # e.g. [25, 24]

    db = SessionLocal()
    _ingestion_jobs[job_id]["status"] = "running"
    _ingestion_jobs[job_id]["knessets"] = knessets
    _ingestion_jobs[job_id]["knesset_results"] = {
        str(kn): {"knesset_number": kn, "status": "pending"} for kn in knessets
    }

    def _step(kn: int | None, label: str, fn, *args, **kwargs):
        key = str(kn) if kn is not None else "analysis"
        _ingestion_jobs[job_id]["current_knesset"] = kn
        _ingestion_jobs[job_id]["current_step"] = label
        try:
            out = fn(*args, **kwargs)
            if kn is not None:
                _ingestion_jobs[job_id]["knesset_results"][key][label] = out
            else:
                _ingestion_jobs[job_id][label] = out
            logger.info("Full pipeline job %s [%s/%s]: %s", job_id, key, label, out)
            return out
        except Exception as exc:
            err = {"error": str(exc)}
            if kn is not None:
                _ingestion_jobs[job_id]["knesset_results"][key][label] = err
            else:
                _ingestion_jobs[job_id][label] = err
            logger.error("Full pipeline job %s [%s/%s] failed: %s",
                         job_id, key, label, exc, exc_info=True)
            return err

    try:
        # ── Phase 1: raw data per Knesset ────────────────────────────────────
        for kn in knessets:
            _ingestion_jobs[job_id]["knesset_results"][str(kn)]["status"] = "running"

            _step(kn, "factions", import_factions, db, kn, settings)

            if kn <= last_votes:
                _step(kn, "votes", import_votes, db, kn, settings,
                      limit=5000, enrich_with_llm=not body.no_llm)
                _step(kn, "vote_results", import_vote_results, db, kn, settings,
                      vote_limit=5000)
            else:
                _ingestion_jobs[job_id]["knesset_results"][str(kn)]["votes"] = {
                    "skipped": 1,
                    "reason": f"Knesset {kn} > {last_votes}: vote data not yet in Votes.svc",
                }
                _ingestion_jobs[job_id]["knesset_results"][str(kn)]["vote_results"] = {
                    "skipped": 1,
                }

            _step(kn, "bills", import_bills, db, kn, settings,
                  limit=5000, enrich_with_llm=not body.no_llm)
            _step(kn, "persons", import_persons, db, kn, settings, limit=2000)

            _ingestion_jobs[job_id]["knesset_results"][str(kn)]["status"] = "done"

        # ── Phase 2: analysis pipeline (runs once) ───────────────────────────
        _ingestion_jobs[job_id]["current_step"] = "analysis"

        _step(None, "policy_items", run_policy_item_pipeline, db, settings,
              knesset_number=None, limit=500, enrich_with_llm=not body.no_llm)
        _step(None, "party_positions", run_party_position_pipeline, db, settings,
              knesset_number=None, enrich_with_llm=not body.no_llm)
        if not body.no_llm:
            _step(None, "questions", run_question_pipeline, db, settings, limit=100)
        _step(None, "lineage", run_lineage_inference, db, settings,
              knesset_number=knessets[0], enrich_with_llm=not body.no_llm)
        _step(None, "volatility", run_volatility_update, db, knesset_number=knessets[0])

        _ingestion_jobs[job_id]["status"] = "done"
        _ingestion_jobs[job_id]["current_step"] = None
        logger.info("Full pipeline job %s complete. Knessets: %s", job_id, knessets)

    except Exception as exc:
        logger.error("Full pipeline job %s failed: %s", job_id, exc, exc_info=True)
        _ingestion_jobs[job_id]["status"] = "error"
        _ingestion_jobs[job_id]["error"] = str(exc)
    finally:
        db.close()


@admin_router.post("/ingest/full-pipeline")
def trigger_full_pipeline(
    body: FullPipelineBody,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    One-button wizard: import all data for the last N Knessets and run the full
    analysis pipeline (policy items, party positions, lineage, volatility).

    Designed to be run once before going live, or after each election.
    Poll /api/admin/ingest/status/{job_id} for progress.
    """
    import uuid as _uuid
    current = body.current_knesset or settings.current_knesset
    last_n = max(1, min(body.last_n_knessets, 10))
    knessets = list(range(current, current - last_n, -1))

    job_id = str(_uuid.uuid4())[:8]
    _ingestion_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "mode": "full_pipeline",
        "knessets": knessets,
        "no_llm": body.no_llm,
        "current_knesset": None,
        "current_step": None,
        "knesset_results": {},
    }
    background_tasks.add_task(_run_full_pipeline, job_id, body, settings)
    return {
        "job_id": job_id,
        "status": "queued",
        "knessets": knessets,
        "no_llm": body.no_llm,
        "message": (
            f"Full pipeline queued for Knessets {knessets}. "
            f"Poll /api/admin/ingest/status/{job_id} for progress."
        ),
    }



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


# ── Root question generation ──────────────────────────────────────────────────

class GenerateRootQuestionBody(BaseModel):
    topic_id: str
    force_regenerate: bool = False  # bypass LLM cache to get a fresh question


def _generate_root_question_for_topic(
    topic: Topic,
    db: Session,
    settings,
    force_regenerate: bool = False,
) -> dict:
    """
    Core logic shared by single and batch root-question generation.
    Returns the result dict. Raises on LLM error.
    """
    from backend.app.services.llm.audit_service import AuditedLLMService

    provider = get_llm_provider(settings)
    svc = AuditedLLMService(provider, db)

    input_data = {
        "topic_name_en": topic.name_en,
        "topic_name_he": topic.name_he,
        "topic_name_ru": topic.name_ru or "",
        "topic_description": (
            topic.description
            or f"Policy questions related to the topic: {topic.name_en}"
        ),
    }

    # Bust the LLM cache by adding a unique nonce when force_regenerate is requested.
    if force_regenerate:
        input_data["_cache_bust"] = str(uuid.uuid4())

    result = svc.generate_root_question(input_data, entity_id=topic.id)
    question_en = result.get("question_en") or result.get("question", "")

    if not question_en:
        raise ValueError(f"LLM returned empty question for topic {topic.slug!r}")

    # ── Format validation: root questions must also be closed propositions ──
    fmt = check_question_format(
        question_en=question_en,
        question_he=result.get("question_he", ""),
        question_ru=result.get("question_ru", ""),
    )
    if not fmt["is_valid"]:
        logger.warning(
            "_generate_root_question_for_topic: open-ended root question rejected "
            "for topic %r — %s", topic.slug, fmt["issue"],
        )
        raise ValueError(
            f"LLM generated an open-ended root question for topic {topic.slug!r}: "
            f"{fmt['issue']}"
        )

    neutrality_score = float(result.get("neutrality_score", 0.7))

    existing = db.query(Question).filter(
        Question.topic_id == topic.id,
        Question.is_root_question.is_(True),
    ).first()

    if existing:
        existing.question_text_en = question_en
        existing.question_text_he = result.get("question_he", existing.question_text_he)
        existing.question_text_ru = result.get("question_ru")
        existing.neutrality_score = neutrality_score
        existing.llm_prompt_version = result.get("_prompt_version", "v1.1-root")
        existing.human_review_status = ReviewStatus.needs_review
        db.commit()
        db.refresh(existing)
        q = existing
        action = "updated"
    else:
        q = Question(
            id=uuid.uuid4(),
            is_root_question=True,
            topic_id=topic.id,
            policy_item_id=None,
            question_text_en=question_en,
            question_text_he=result.get("question_he", ""),
            question_text_ru=result.get("question_ru"),
            answer_scale_type=AnswerScaleType.likert_5,
            neutrality_score=neutrality_score,
            llm_prompt_version=result.get("_prompt_version", "v1.1-root"),
            human_review_status=ReviewStatus.needs_review,
        )
        db.add(q)
        db.commit()
        db.refresh(q)
        action = "created"

    return {
        "action": action,
        "question_id": str(q.id),
        "topic_id": str(topic.id),
        "topic_slug": topic.slug,
        "topic_name_en": topic.name_en,
        "question_en": q.question_text_en,
        "question_he": q.question_text_he,
        "question_ru": q.question_text_ru,
        "neutrality_score": neutrality_score,
        "status": q.human_review_status.value,
        "provider": provider.provider,
    }


@admin_router.post("/llm/generate-root-question")
def generate_root_question(
    body: GenerateRootQuestionBody,
    db: Session = Depends(get_db),
    settings=Depends(get_settings),
) -> dict:
    """
    Generate a broad, topic-level root question for the question tree.
    Root questions are the entry point of the questionnaire (is_root_question=True).
    They cover a whole topic, not a specific bill or vote.
    Human approval still required before going public.
    Uses the dedicated root_question prompt from prompts.json.
    """
    try:
        tid = uuid.UUID(body.topic_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid topic UUID")

    topic = db.query(Topic).filter(Topic.id == tid).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    try:
        return _generate_root_question_for_topic(
            topic, db, settings, force_regenerate=body.force_regenerate
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Batch root question generation ───────────────────────────────────────────

# In-memory job store for batch root-question generation
_root_gen_jobs: dict[str, dict] = {}


class GenerateAllRootQuestionsBody(BaseModel):
    force_regenerate: bool = False  # regenerate even if a root question already exists
    skip_existing: bool = True      # skip topics that already have an approved root question
    max_workers: int = 8            # parallel LLM calls; capped at 15


@admin_router.post("/llm/generate-all-root-questions")
def generate_all_root_questions(
    body: GenerateAllRootQuestionsBody,
    background_tasks: BackgroundTasks,
    settings=Depends(get_settings),
) -> dict:
    """
    Generate root questions for ALL topics in a single background job.
    Returns a job_id to poll /llm/generate-all-root-questions/status/{job_id}.
    """
    job_id = str(uuid.uuid4())[:8]
    _root_gen_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "total": 0,
        "completed": 0,
        "errors": 0,
        "results": [],
        "current_topic": None,
    }

    def _run():
        from backend.app.db.session import SessionLocal
        from concurrent.futures import ThreadPoolExecutor, as_completed

        _root_gen_jobs[job_id]["status"] = "running"

        # Load topic metadata in a short-lived session, then close it.
        # Each worker thread will open its own session — SQLAlchemy sessions
        # are NOT thread-safe and must not be shared across threads.
        db_main = SessionLocal()
        try:
            topics_raw = db_main.query(Topic).order_by(Topic.slug).all()
            topic_list = [
                {
                    "id": t.id,
                    "slug": t.slug,
                    "name_en": t.name_en,
                    "name_he": t.name_he,
                    "name_ru": t.name_ru,
                    "description": t.description,
                }
                for t in topics_raw
            ]
        finally:
            db_main.close()

        _root_gen_jobs[job_id]["total"] = len(topic_list)

        def process_one(td: dict) -> dict:
            """Called in a worker thread — gets its own DB session."""
            db = SessionLocal()
            try:
                topic = db.query(Topic).filter(Topic.id == td["id"]).first()
                if not topic:
                    return {"action": "error", "topic_slug": td["slug"],
                            "topic_name_en": td["name_en"], "error": "Topic not found"}

                # Optionally skip topics that already have an approved root question
                if body.skip_existing and not body.force_regenerate:
                    existing = db.query(Question).filter(
                        Question.topic_id == topic.id,
                        Question.is_root_question.is_(True),
                        Question.human_review_status == ReviewStatus.approved,
                    ).first()
                    if existing:
                        return {"action": "skipped_approved", "topic_slug": topic.slug,
                                "topic_name_en": topic.name_en}

                return _generate_root_question_for_topic(
                    topic, db, settings, force_regenerate=body.force_regenerate
                )
            except Exception as exc:
                logger.warning(
                    "Root question generation failed for topic %s: %s", td["slug"], exc
                )
                return {"action": "error", "topic_slug": td["slug"],
                        "topic_name_en": td["name_en"], "error": str(exc)}
            finally:
                db.close()

        # Run up to MAX_WORKERS topics concurrently.
        # Limit keeps OpenAI rate limits comfortable while still cutting wall-clock
        # time from ~5 min sequential → ~30–60 sec parallel for 15 topics.
        MAX_WORKERS = min(max(1, body.max_workers), 15)
        try:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(process_one, td): td for td in topic_list}
                for future in as_completed(futures):
                    try:
                        result = future.result()
                    except Exception as exc:
                        td = futures[future]
                        result = {"action": "error", "topic_slug": td["slug"],
                                  "topic_name_en": td["name_en"], "error": str(exc)}
                        _root_gen_jobs[job_id]["errors"] += 1

                    if result.get("action") == "error":
                        _root_gen_jobs[job_id]["errors"] += 1

                    _root_gen_jobs[job_id]["results"].append(result)
                    _root_gen_jobs[job_id]["completed"] += 1
                    _root_gen_jobs[job_id]["current_topic"] = result.get("topic_name_en")

            _root_gen_jobs[job_id].update({"status": "done", "current_topic": None})
        except Exception as exc:
            _root_gen_jobs[job_id].update({"status": "error", "error": str(exc), "current_topic": None})

    background_tasks.add_task(_run)
    return {"job_id": job_id, "status": "queued"}


@admin_router.get("/llm/generate-all-root-questions/status/{job_id}")
def get_generate_all_root_questions_status(job_id: str) -> dict:
    """Poll the status of a batch root-question generation job."""
    job = _root_gen_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ── Manual question creation ──────────────────────────────────────────────────

class ManualQuestionBody(BaseModel):
    topic_id: str
    is_root_question: bool = False
    policy_item_id: str | None = None
    question_text_en: str
    question_text_he: str = ""
    question_text_ru: str = ""
    answer_scale_type: str = "likert_5"
    context_note_en: str = ""


@admin_router.post("/questions/manual")
def create_manual_question(
    body: ManualQuestionBody,
    db: Session = Depends(get_db),
) -> dict:
    """
    Create a question manually (written by an admin, not by the LLM).
    Immediately saved as human_review_status=approved since it was human-authored.
    """
    try:
        tid = uuid.UUID(body.topic_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid topic UUID")

    topic = db.query(Topic).filter(Topic.id == tid).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    if not body.question_text_en.strip():
        raise HTTPException(status_code=400, detail="English question text is required")

    # Validate scale type
    try:
        scale = AnswerScaleType(body.answer_scale_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid answer_scale_type: {body.answer_scale_type}")

    # Resolve optional policy_item_id
    pi_id: uuid.UUID | None = None
    if body.policy_item_id:
        try:
            pi_id = uuid.UUID(body.policy_item_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid policy_item_id")
        pi = db.query(PolicyItem).filter(PolicyItem.id == pi_id).first()
        if not pi:
            raise HTTPException(status_code=404, detail="PolicyItem not found")

    # For root questions: replace existing root question for this topic if present
    if body.is_root_question:
        existing = db.query(Question).filter(
            Question.topic_id == tid,
            Question.is_root_question.is_(True),
        ).first()
        if existing:
            existing.question_text_en = body.question_text_en.strip()
            existing.question_text_he = body.question_text_he.strip() or existing.question_text_he
            existing.question_text_ru = body.question_text_ru.strip() or existing.question_text_ru
            existing.answer_scale_type = scale
            existing.human_review_status = ReviewStatus.approved
            existing.llm_prompt_version = "manual"
            db.commit()
            db.refresh(existing)
            return {
                "action": "updated",
                "question_id": str(existing.id),
                "topic_id": str(tid),
                "topic_name_en": topic.name_en,
                "question_text_en": existing.question_text_en,
            }

    q = Question(
        id=uuid.uuid4(),
        topic_id=tid,
        policy_item_id=pi_id,
        is_root_question=body.is_root_question,
        question_text_en=body.question_text_en.strip(),
        question_text_he=body.question_text_he.strip(),
        question_text_ru=body.question_text_ru.strip(),
        answer_scale_type=scale,
        neutrality_score=1.0,        # human-authored: assume neutral
        llm_prompt_version="manual",
        human_review_status=ReviewStatus.approved,
    )
    db.add(q)
    db.commit()
    db.refresh(q)

    return {
        "action": "created",
        "question_id": str(q.id),
        "topic_id": str(tid),
        "topic_name_en": topic.name_en,
        "question_text_en": q.question_text_en,
    }


@admin_router.get("/topics/with-root-questions")
def list_topics_with_root_questions(db: Session = Depends(get_db)) -> list[dict]:
    """
    List all topics with their root questions (if they exist).
    Used by the Generate tab to show the question tree overview.
    """
    topics = db.query(Topic).order_by(Topic.slug).all()
    result = []
    for topic in topics:
        root_q = db.query(Question).filter(
            Question.topic_id == topic.id,
            Question.is_root_question.is_(True),
        ).first()

        policy_item_count = db.query(PolicyItem).filter(
            PolicyItem.topic_id == topic.id
        ).count()

        followup_count = db.query(Question).filter(
            Question.topic_id.is_(None),
        ).join(PolicyItem, Question.policy_item_id == PolicyItem.id).filter(
            PolicyItem.topic_id == topic.id,
        ).count()

        result.append({
            "topic_id": str(topic.id),
            "slug": topic.slug,
            "name_en": topic.name_en,
            "name_he": topic.name_he,
            "name_ru": topic.name_ru,
            "description": topic.description,
            "policy_item_count": policy_item_count,
            "followup_question_count": followup_count,
            "root_question": {
                "id": str(root_q.id),
                "question_text_en": root_q.question_text_en,
                "question_text_he": root_q.question_text_he,
                "question_text_ru": root_q.question_text_ru,
                "status": root_q.human_review_status.value,
                "neutrality_score": root_q.neutrality_score,
            } if root_q else None,
        })
    return result


# ── Database backup and restore ───────────────────────────────────────────────

@admin_router.get("/db/backup")
def backup_database(db: Session = Depends(get_db)) -> Response:
    """
    Export the entire database as a JSON snapshot.
    Returns a downloadable JSON file that can be used to restore the database
    on a fresh deployment (avoids losing data when redeploying).

    The backup includes all tables in insertion order.
    Sensitive data (admin passwords) is NOT included.
    """
    from backend.app.models.political_brand import PoliticalBrand
    from backend.app.models.party_instance import PartyInstance
    from backend.app.models.party_lineage_edge import PartyLineageEdge
    from backend.app.models.party_position import PartyPosition
    from backend.app.models.person import Person
    from backend.app.models.person_party_membership import PersonPartyMembership
    from backend.app.models.bill import Bill
    from backend.app.models.vote import Vote
    from backend.app.models.vote_result import VoteResult
    from backend.app.models.policy_item import PolicyItem
    from backend.app.models.question import Question
    from backend.app.models.user_session import UserSession
    from backend.app.models.user_answer import UserAnswer
    from backend.app.models.recommendation_run import RecommendationRun

    def _serialize_row(row) -> dict:
        """Convert a SQLAlchemy model instance to a JSON-safe dict."""
        from datetime import date as date_type
        result = {}
        for col in row.__table__.columns:
            val = getattr(row, col.name)
            if val is None:
                result[col.name] = None
            elif isinstance(val, uuid.UUID):
                result[col.name] = str(val)
            elif isinstance(val, datetime):
                # datetime is a subclass of date — check it first
                result[col.name] = val.isoformat()
            elif isinstance(val, date_type):
                result[col.name] = val.isoformat()
            elif hasattr(val, "value"):  # Enum
                result[col.name] = val.value
            else:
                result[col.name] = val
        return result

    def _dump_table(model) -> list[dict]:
        try:
            return [_serialize_row(row) for row in db.query(model).all()]
        except Exception as exc:
            logger.warning("Backup: failed to dump %s: %s", model.__tablename__, exc)
            return []

    snapshot = {
        "version": "1.0",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "tables": {
            "topics":                  _dump_table(Topic),
            "political_brands":        _dump_table(PoliticalBrand),
            "party_instances":         _dump_table(PartyInstance),
            "party_lineage_edges":     _dump_table(PartyLineageEdge),
            "persons":                 _dump_table(Person),
            "person_party_memberships": _dump_table(PersonPartyMembership),
            "bills":                   _dump_table(Bill),
            "votes":                   _dump_table(Vote),
            "vote_results":            _dump_table(VoteResult),
            "policy_items":            _dump_table(PolicyItem),
            "party_positions":         _dump_table(PartyPosition),
            "questions":               _dump_table(Question),
        },
        "stats": {},
    }
    # Add row counts
    for table_name, rows in snapshot["tables"].items():
        snapshot["stats"][table_name] = len(rows)

    json_bytes = json.dumps(snapshot, ensure_ascii=False, indent=2).encode("utf-8")
    filename = f"smartvoter_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class RestoreOptions(BaseModel):
    skip_existing: bool = True   # if True, only insert rows that don't exist yet
    tables: list[str] | None = None  # if None, restore all tables


@admin_router.post("/db/restore")
async def restore_database(
    file: UploadFile = File(...),
    skip_existing: bool = True,
    db: Session = Depends(get_db),
) -> dict:
    """
    Restore the database from a JSON backup file.

    By default (skip_existing=True), only inserts rows that don't exist yet
    (safe merge — does NOT delete existing data). This is the recommended mode
    for recovering after a redeploy.

    To do a full replacement, set skip_existing=False — all existing rows in
    the included tables will be deleted first, then the backup is restored.

    WARNING: skip_existing=False is destructive. Back up current data first.
    """
    from backend.app.models.political_brand import PoliticalBrand
    from backend.app.models.party_instance import PartyInstance
    from backend.app.models.party_lineage_edge import PartyLineageEdge
    from backend.app.models.party_position import PartyPosition
    from backend.app.models.person import Person
    from backend.app.models.person_party_membership import PersonPartyMembership
    from backend.app.models.bill import Bill
    from backend.app.models.vote import Vote
    from backend.app.models.vote_result import VoteResult
    from backend.app.models.policy_item import PolicyItem
    from backend.app.models.question import Question

    raw = await file.read()
    try:
        snapshot = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")

    if snapshot.get("version") != "1.0":
        raise HTTPException(status_code=400, detail="Unsupported backup version")

    # Table restore order matters for FK constraints
    TABLE_MODELS = [
        ("topics",                   Topic),
        ("political_brands",         PoliticalBrand),
        ("party_instances",          PartyInstance),
        ("party_lineage_edges",      PartyLineageEdge),
        ("persons",                  Person),
        ("person_party_memberships", PersonPartyMembership),
        ("bills",                    Bill),
        ("votes",                    Vote),
        ("vote_results",             VoteResult),
        ("policy_items",             PolicyItem),
        ("party_positions",          PartyPosition),
        ("questions",                Question),
    ]

    tables_data = snapshot.get("tables", {})
    stats: dict[str, dict] = {}

    for table_name, Model in TABLE_MODELS:
        rows = tables_data.get(table_name, [])
        if not rows:
            stats[table_name] = {"inserted": 0, "skipped": 0}
            continue

        inserted = skipped = 0

        if not skip_existing:
            # Full replace: delete all existing rows first
            try:
                db.query(Model).delete()
                db.flush()
            except Exception as exc:
                logger.warning("Restore: failed to clear %s: %s", table_name, exc)

        for row_data in rows:
            try:
                pk = row_data.get("id")
                if pk and skip_existing:
                    existing = db.query(Model).filter(Model.id == pk).first()
                    if existing:
                        skipped += 1
                        continue

                # Parse UUID fields back
                parsed = {}
                for col in Model.__table__.columns:
                    if col.name not in row_data:
                        continue
                    val = row_data[col.name]
                    if val is None:
                        parsed[col.name] = None
                    elif str(col.type) in ("UUID", "VARCHAR(36)") and val:
                        try:
                            parsed[col.name] = uuid.UUID(str(val))
                        except (ValueError, AttributeError):
                            parsed[col.name] = val
                    else:
                        parsed[col.name] = val

                db.add(Model(**parsed))
                inserted += 1
            except Exception as exc:
                logger.warning("Restore: failed to insert row in %s: %s", table_name, exc)
                db.rollback()
                skipped += 1

        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("Restore: commit failed for %s: %s", table_name, exc)

        stats[table_name] = {"inserted": inserted, "skipped": skipped}

    total_inserted = sum(v["inserted"] for v in stats.values())
    total_skipped = sum(v["skipped"] for v in stats.values())
    return {
        "status": "ok",
        "skip_existing": skip_existing,
        "total_inserted": total_inserted,
        "total_skipped": total_skipped,
        "backup_created_at": snapshot.get("created_at"),
        "tables": stats,
    }


# ── Live Polling Refresh ───────────────────────────────────────────────────────

@admin_router.post("/polling/refresh")
def refresh_polling_data(
    model: str = "gpt-4o",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Fetch current Israeli opinion polls via OpenAI web search and store in DB.
    Clears stale simulation_runs so the next GET /api/simulation/latest
    triggers a fresh Monte Carlo run based on the new data.

    Requires OPENAI_API_KEY to be configured.  If not set, returns an error
    with instructions and leaves existing seed polls untouched.
    """
    from backend.app.services.polling.web_polling import fetch_and_store_live_polls

    if not settings.has_openai:
        return {
            "source": "no_api_key",
            "polls_stored": 0,
            "parties_stored": 0,
            "warnings": [
                "OPENAI_API_KEY is not configured. "
                "Add it to your .env file and restart the server."
            ],
            "notes": "Seed poll data was NOT changed.",
            "refreshed_at": None,
            "model_used": None,
        }

    result = fetch_and_store_live_polls(
        db=db,
        api_key=settings.openai_api_key,
        model=model,
    )
    return result
