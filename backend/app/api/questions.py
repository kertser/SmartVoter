from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import uuid
import logging

from backend.app.db import get_db
from backend.app.config import get_settings, Settings
from backend.app.models.user_session import UserSession
from backend.app.models.question import Question, AnswerScaleType
from backend.app.models.user_answer import UserAnswer
from backend.app.models.user_skipped_question import UserSkippedQuestion
from backend.app.models.policy_item import PolicyItem, ReviewStatus
from backend.app.models.topic import Topic
from backend.app.models.party_position import PartyPosition
from backend.app.schemas.question import QuestionOut
from backend.app.schemas.session import SessionCreate, SessionOut
from backend.app.services.questionnaire import (
    select_next_question,
    aggregate_salience_by_topic,
    aggregate_salience_by_policy_item,
    compute_ranking_stability,
    should_offer_results,
    force_results,
    QuestionCandidate,
    PartyPositionSlim,
    DISCOVERY_SIGNAL_THRESHOLD,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["questionnaire"])


# ── Background pre-warming helper ─────────────────────────────────────────────

def _prefetch_questions_background(settings: Settings) -> None:
    """
    Background task: generate discovery + niche questions in advance so
    the user doesn't wait for LLM calls during the depth phase.
    Runs at most once per session creation.
    Only runs when OPENAI_API_KEY is configured.
    Errors are logged but never bubble up to the user.
    """
    if not settings.openai_api_key:
        return
    try:
        from backend.app.db.session import SessionLocal
        from backend.app.services.ingestion.question_pipeline import run_niche_discovery_pipeline
        bg_db = SessionLocal()
        try:
            stats = run_niche_discovery_pipeline(bg_db, settings, limit=12, max_workers=3)
            logger.info("Session prefetch: discovery pipeline → %s", stats)
        finally:
            bg_db.close()
    except Exception as exc:
        logger.debug("Background question prefetch failed (non-critical): %s", exc)


def _ui_strings() -> dict:
    """Static UI strings for why-selected explanations (i18n-ready placeholder)."""
    return {
        "why_selected": {
            "first_question": (
                "This is the first question. It helps us understand your general priorities."
            ),
            "survey_question": (
                "This question introduces a new topic area, helping us map your overall priorities."
            ),
            "adaptive_question": (
                "This question helps distinguish between parties that are currently "
                "close in your results."
            ),
            "depth_question": (
                "You rated this topic as very important — this question explores it further."
            ),
            "discovery_question": (
                "This question explores a specific policy area where some parties have a "
                "consistent, evidence-backed legislative track record that your top results "
                "may not yet reflect. You might find an unexpected match here."
            ),
            "auto_generated": (
                "This question was automatically generated because no pre-existing "
                "question covered this policy area."
            ),
        }
    }

# ── Statuses that the questionnaire can serve ─────────────────────────────────
# approved  = human-curated seed questions (highest quality)
# llm_generated = auto-generated on-the-fly, pending post-hoc admin review
_SERVABLE_STATUSES = {ReviewStatus.approved, ReviewStatus.llm_generated}


def _get_current_top_party_ids(
    db: Session,
    answered_rows: list[UserAnswer],
    all_positions: list[PartyPosition],
    n: int = 3,
) -> list[uuid.UUID]:
    """
    Return current top-N party IDs ranked by match score given existing answers.
    Used to split positions into top-party vs outsider groups for discovery scoring.
    Returns empty list if fewer than 2 answers have been submitted.
    """
    if len(answered_rows) < 2:
        return []
    try:
        from backend.app.services.scoring.engine import (
            compute_match_score,
            AnswerData,
            PositionData,
        )
        answer_data = [
            AnswerData(
                policy_item_id=a.policy_item_id,
                answer_value=a.answer_value,
                salience=a.salience,
            )
            for a in answered_rows
            if a.policy_item_id is not None
        ]
        if not answer_data:
            return []
        party_ids = list({p.party_instance_id for p in all_positions})
        scores: dict[uuid.UUID, float] = {}
        for pid in party_ids:
            pos_data = [
                PositionData(
                    policy_item_id=p.policy_item_id,
                    position_mean=p.position_mean,
                    position_uncertainty=p.position_uncertainty,
                    evidence_strength=p.evidence_strength,
                    evidence_type=p.evidence_type or "platform",
                )
                for p in all_positions
                if p.party_instance_id == pid
            ]
            scores[pid] = compute_match_score(answer_data, pos_data)
        return sorted(party_ids, key=lambda pid: scores[pid], reverse=True)[:n]
    except Exception as exc:
        logger.debug("_get_current_top_party_ids failed: %s", exc)
        return []


def _auto_generate_question(
    db: Session, best_pi: PolicyItem
) -> Question | None:
    """
    Generate a question for `best_pi` on-the-fly using the LLM provider.
    Stores with status=llm_generated for post-hoc admin review.
    Returns the saved Question, or None if generation fails.
    """
    from backend.app.config import get_settings
    from backend.app.services.llm import get_llm_provider
    from backend.app.services.llm.audit_service import AuditedLLMService

    try:
        settings = get_settings()
        provider = get_llm_provider(settings)
        svc = AuditedLLMService(provider, db)

        input_data = {
            "title": best_pi.title,
            "description": best_pi.description or "",
            "directional_axis": best_pi.directional_axis or "",
        }
        result = svc.generate_question(input_data, entity_id=best_pi.id)

        q = Question(
            policy_item_id=best_pi.id,
            question_text_en=result.get("question_en") or result.get("question", ""),
            question_text_he=result.get("question_he", ""),
            question_text_ru=result.get("question_ru", ""),
            answer_scale_type=AnswerScaleType.likert_5,
            neutrality_score=0.7,
            llm_prompt_version=result.get("_prompt_version", "v1.0-auto"),
            # LLM prompt instructs "Strongly Support = positive axis pole", so polarity=1.0
            answer_polarity=1.0,
            human_review_status=ReviewStatus.llm_generated,
        )
        db.add(q)
        db.commit()
        db.refresh(q)
        logger.info("Auto-generated question %s for policy_item %s", q.id, best_pi.id)
        return q
    except Exception as exc:
        logger.warning("Auto-generation failed for policy_item %s: %s", best_pi.id, exc)
        return None


def _compute_session_state(
    db: Session,
    session_id: uuid.UUID,
    answered_rows: list[UserAnswer],
) -> dict:
    """
    Build the full state dict from existing answers:
    - answered_ids
    - answered_topic_counts
    - answered_policy_item_counts
    - user_salience_by_topic
    - salience_by_policy_item
    - all_topic_slugs
    - topics_covered
    """
    answered_ids: list[uuid.UUID] = []
    answered_topic_counts: dict[str, int] = {}
    answered_policy_item_counts: dict[uuid.UUID, int] = {}
    answer_salience_pairs: list[tuple[str, float]] = []
    answer_pi_salience_pairs: list[tuple[uuid.UUID, float]] = []

    # Collect all topic slugs from DB to determine total topic universe
    all_topics = db.query(Topic).all()
    all_topic_slugs: set[str] = {t.slug for t in all_topics}

    for answer in answered_rows:
        answered_ids.append(answer.question_id)
        topic: Topic | None = None

        if answer.policy_item_id:
            answered_policy_item_counts[answer.policy_item_id] = (
                answered_policy_item_counts.get(answer.policy_item_id, 0) + 1
            )
            answer_pi_salience_pairs.append((answer.policy_item_id, answer.salience))
            # Resolve topic via policy_item → topic
            pi = db.query(PolicyItem).filter(PolicyItem.id == answer.policy_item_id).first()
            if pi and pi.topic_id:
                topic = db.query(Topic).filter(Topic.id == pi.topic_id).first()
        else:
            # Root question: policy_item_id is NULL → resolve topic directly from
            # Question.topic_id (set on all root questions by the seeder/question bank pipeline).
            q_obj = db.query(Question).filter(Question.id == answer.question_id).first()
            if q_obj and q_obj.topic_id:
                topic = db.query(Topic).filter(Topic.id == q_obj.topic_id).first()

        if topic:
            answered_topic_counts[topic.slug] = (
                answered_topic_counts.get(topic.slug, 0) + 1
            )
            answer_salience_pairs.append((topic.slug, answer.salience))

    user_salience_by_topic = aggregate_salience_by_topic(answer_salience_pairs)
    salience_by_policy_item = aggregate_salience_by_policy_item(answer_pi_salience_pairs)
    topics_covered = sum(1 for t in all_topic_slugs if answered_topic_counts.get(t, 0) > 0)

    return {
        "answered_ids": answered_ids,
        "answered_topic_counts": answered_topic_counts,
        "answered_policy_item_counts": answered_policy_item_counts,
        "user_salience_by_topic": user_salience_by_topic,
        "salience_by_policy_item": salience_by_policy_item,
        "all_topic_slugs": all_topic_slugs,
        "topics_covered": topics_covered,
        "topics_total": len(all_topic_slugs),
    }


def _build_convergence_meta(
    db: Session,
    session_id: uuid.UUID,
    answered_ids: list[uuid.UUID],
    answered_topic_counts: dict[str, int],
    all_topic_slugs: set[str],
    topics_covered: int,
    topics_total: int,
) -> dict:
    """
    Compute ranking stability and whether results can be shown.
    Uses the scoring engine to rank parties with/without the last answer.
    Returns: {can_show_results, ranking_stability, phase}
    """
    from backend.app.services.questionnaire.selector import _determine_phase

    answered_count = len(answered_ids)
    phase = _determine_phase(answered_count, answered_topic_counts, all_topic_slugs)

    # Lightweight ranking stability: compare rankings with all answers vs. without last
    ranking_stability = 1.0
    if answered_count >= 2:
        try:
            from backend.app.services.scoring.engine import (
                compute_match_score,
                AnswerData,
                PositionData,
            )
            answered_rows_all = (
                db.query(UserAnswer)
                .filter(UserAnswer.session_id == session_id)
                .all()
            )
            # Build answer data
            answer_data_full = [
                AnswerData(
                    policy_item_id=a.policy_item_id,
                    answer_value=a.answer_value,
                    salience=a.salience,
                )
                for a in answered_rows_all
                if a.policy_item_id is not None
            ]
            answer_data_prev = answer_data_full[:-1]

            all_positions = db.query(PartyPosition).all()
            party_ids = list({p.party_instance_id for p in all_positions})

            def _rank(answer_data):
                scores = {}
                for pid in party_ids:
                    pos_data = [
                        PositionData(
                            policy_item_id=p.policy_item_id,
                            position_mean=p.position_mean,
                            position_uncertainty=p.position_uncertainty,
                            evidence_strength=p.evidence_strength,
                            evidence_type=p.evidence_type or "platform",
                        )
                        for p in all_positions
                        if p.party_instance_id == pid
                    ]
                    scores[pid] = compute_match_score(answer_data, pos_data)
                return sorted(party_ids, key=lambda pid: scores[pid], reverse=True)

            curr_ranking = _rank(answer_data_full)
            prev_ranking = _rank(answer_data_prev)
            ranking_stability = compute_ranking_stability(prev_ranking, curr_ranking)
        except Exception as exc:
            logger.debug("Ranking stability computation failed: %s", exc)
            ranking_stability = 0.5  # assume partially stable on error

    all_topics_covered = topics_covered >= topics_total
    can_show = should_offer_results(answered_count, ranking_stability, all_topics_covered)

    return {
        "can_show_results": can_show,
        "ranking_stability": round(ranking_stability, 3),
        "phase": phase,
    }


@router.post("/sessions", response_model=SessionOut)
def create_or_get_session(
    body: SessionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SessionOut:
    """Upsert an anonymous session. Client provides UUID or gets a new one.
    Also fires a background task to pre-warm discovery questions.
    """
    session_id = body.session_id or uuid.uuid4()
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        session = UserSession(id=session_id)
        db.add(session)
        db.commit()
        db.refresh(session)
        # Pre-warm niche/discovery questions in background (non-blocking)
        background_tasks.add_task(_prefetch_questions_background, settings)
    return SessionOut(session_id=session.id, created_at=session.created_at)


@router.get("/questions/next", response_model=QuestionOut | None)
def get_next_question(
    session_id: uuid.UUID, db: Session = Depends(get_db)
) -> QuestionOut | None:
    """
    Returns the next adaptive question for a session.

    Phase 1 (survey): one question per topic → breadth coverage.
    Phase 2 (depth):  salience-driven follow-up, avoids repeating same policy item
                      unless the user rated it Very Important.
    Returns null when HARD_MAX questions have been answered or no candidates remain.
    Never exposes party scores. (AGENTS.MD Section 13)
    """
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    answered_rows = (
        db.query(UserAnswer).filter(UserAnswer.session_id == session_id).all()
    )

    state = _compute_session_state(db, session_id, answered_rows)
    answered_ids = state["answered_ids"]
    answered_topic_counts = state["answered_topic_counts"]
    answered_policy_item_counts = state["answered_policy_item_counts"]
    user_salience_by_topic = state["user_salience_by_topic"]
    salience_by_policy_item = state["salience_by_policy_item"]
    all_topic_slugs = state["all_topic_slugs"]
    topics_covered = state["topics_covered"]
    topics_total = state["topics_total"]

    # Load any questions the user has explicitly skipped (excluded from all future selection)
    skipped_rows = (
        db.query(UserSkippedQuestion)
        .filter(UserSkippedQuestion.session_id == session_id)
        .all()
    )
    skipped_question_ids: set[uuid.UUID] = {s.question_id for s in skipped_rows}
    # Merge skipped IDs into answered_ids so the rest of the selection logic ignores them
    answered_ids_set = set(answered_ids) | skipped_question_ids

    if force_results(len(answered_ids)):
        return None

    # Compute convergence metadata (used for UI hints even though we don't stop here)
    conv = _build_convergence_meta(
        db, session_id, answered_ids, answered_topic_counts,
        all_topic_slugs, topics_covered, topics_total,
    )

    # Build candidates from servable questions (approved + llm_generated, not stale) not yet answered
    servable_questions = (
        db.query(Question)
        .filter(
            Question.human_review_status.in_(list(_SERVABLE_STATUSES)),
            Question.is_stale == False,  # noqa: E712
        )
        .all()
    )

    # ── Phase 1: Root questions (topic survey) ────────────────────────────────
    # Root questions are always served before entering adaptive selection.
    # But: respect topic coverage — only serve root questions for topics not yet
    # covered (unless all root questions are done).
    #
    # Adjacent-topic coverage: if a topic has no root question in the servable
    # pool, the best non-root question for that topic is used as a survey entry
    # so that ALL topics get at least one question during Phase 1.
    from backend.app.services.questionnaire.selector import _determine_phase
    phase = _determine_phase(len(answered_ids), answered_topic_counts, all_topic_slugs)

    unanswered_root_qs = [
        q for q in servable_questions
        if q.id not in answered_ids_set and q.is_root_question
    ]

    if phase == "survey":
        # Determine which topic_slugs already have an available (unanswered) root question
        slugs_with_avail_root: set[str] = set()
        for q in unanswered_root_qs:
            if q.topic_id:
                t = db.query(Topic).filter(Topic.id == q.topic_id).first()
                if t:
                    slugs_with_avail_root.add(t.slug)

        # Uncovered root questions → sort uncovered topics first
        def _root_priority(q: Question) -> int:
            topic = db.query(Topic).filter(Topic.id == q.topic_id).first() if q.topic_id else None
            slug = topic.slug if topic else ""
            return 0 if answered_topic_counts.get(slug, 0) == 0 else 1

        unanswered_root_qs.sort(key=_root_priority)

        # Best non-root question for topics that have NO root question at all
        # (adjacent-topic coverage — ensures survey spans all topics)
        non_root_survey_qs: list[Question] = []
        for q in servable_questions:
            if q.id in answered_ids_set or q.is_root_question:
                continue
            if not q.policy_item_id:
                continue
            pi = db.query(PolicyItem).filter(PolicyItem.id == q.policy_item_id).first()
            if not pi or not pi.topic_id:
                continue
            topic = db.query(Topic).filter(Topic.id == pi.topic_id).first()
            if not topic:
                continue
            slug = topic.slug
            # Only if uncovered AND the topic has no unanswered root question
            if answered_topic_counts.get(slug, 0) == 0 and slug not in slugs_with_avail_root:
                non_root_survey_qs.append(q)

        # Choose the best survey question: root first, non-root fallback second
        survey_q: Question | None = unanswered_root_qs[0] if unanswered_root_qs else None
        if not survey_q and non_root_survey_qs:
            # Score non-root fallbacks by evidence quality, prefer highest
            def _non_root_score(q: Question) -> float:
                pos = db.query(PartyPosition).filter(PartyPosition.policy_item_id == q.policy_item_id).all()
                return sum(p.evidence_strength for p in pos) / len(pos) if pos else 0.0
            non_root_survey_qs.sort(key=_non_root_score, reverse=True)
            survey_q = non_root_survey_qs[0]

        if survey_q:
            if survey_q.is_root_question:
                topic = db.query(Topic).filter(Topic.id == survey_q.topic_id).first() if survey_q.topic_id else None
            else:
                pi_lookup = db.query(PolicyItem).filter(PolicyItem.id == survey_q.policy_item_id).first() if survey_q.policy_item_id else None
                topic = db.query(Topic).filter(Topic.id == pi_lookup.topic_id).first() if pi_lookup and pi_lookup.topic_id else None

            t_slug = topic.slug if topic else "unknown"
            conv_meta = _build_convergence_meta(
                db, session_id, answered_ids, answered_topic_counts,
                all_topic_slugs, topics_covered, topics_total,
            )
            return QuestionOut(
                id=survey_q.id,
                question_text_en=survey_q.question_text_en,
                question_text_he=survey_q.question_text_he,
                question_text_ru=survey_q.question_text_ru,
                answer_scale_type=survey_q.answer_scale_type.value,
                policy_item_id=survey_q.policy_item_id,
                topic_slug=t_slug,
                topic_name_he=topic.name_he if topic else None,
                topic_name_ru=topic.name_ru if topic else None,
                context_note=None,
                why_selected=_ui_strings()["why_selected"]["survey_question"],
                is_root_question=survey_q.is_root_question,
                answer_polarity=survey_q.answer_polarity if hasattr(survey_q, "answer_polarity") else 1.0,
                can_show_results=conv_meta["can_show_results"],
                phase=conv_meta["phase"],
                topics_covered=topics_covered,
                topics_total=topics_total,
                answered_count=len(answered_ids),
                ranking_stability=conv_meta["ranking_stability"],
            )

    # ── Adaptive candidate scoring ────────────────────────────────────────────
    candidates: list[QuestionCandidate] = []
    topic_lookup: dict[uuid.UUID, Topic] = {}  # question_id → Topic

    # Fetch ALL positions once; split into top-party vs outsider groups
    all_positions = db.query(PartyPosition).all()
    top_party_ids = _get_current_top_party_ids(db, answered_rows, all_positions, n=3)
    top_party_ids_set = set(top_party_ids)

    for q in servable_questions:
        if q.id in answered_ids_set:  # includes both answered and skipped
            continue
        pi = db.query(PolicyItem).filter(PolicyItem.id == q.policy_item_id).first()
        if not pi:
            continue
        topic = db.query(Topic).filter(Topic.id == pi.topic_id).first()
        topic_slug = topic.slug if topic else "unknown"
        topic_lookup[q.id] = topic

        positions = [p for p in all_positions if p.policy_item_id == q.policy_item_id]
        avg_evidence = (
            sum(p.evidence_strength for p in positions) / len(positions)
            if positions else 0.0
        )

        # Compute outsider discovery signal: how much a non-top party diverges
        # from the top-parties' consensus on this item, weighted by evidence strength
        top_pos_values = [
            p.position_mean for p in positions
            if p.party_instance_id in top_party_ids_set
        ]
        top_mean = sum(top_pos_values) / len(top_pos_values) if top_pos_values else 0.0

        outsider_signal = 0.0
        for p in positions:
            if p.party_instance_id in top_party_ids_set:
                continue
            signal = abs(p.position_mean - top_mean) * p.evidence_strength
            if signal > outsider_signal:
                outsider_signal = signal

        candidates.append(
            QuestionCandidate(
                question_id=q.id,
                policy_item_id=q.policy_item_id,
                topic_slug=topic_slug,
                evidence_quality=avg_evidence,
                outsider_party_signal=outsider_signal,
            )
        )

    # Top-party positions (capped at 5 for performance, sufficient for separation score)
    party_ids = list({p.party_instance_id for p in all_positions})
    top_party_positions: list[list[PartyPositionSlim]] = []
    for pid in party_ids[:5]:
        party_pos = [
            PartyPositionSlim(
                policy_item_id=p.policy_item_id,
                position_mean=p.position_mean,
                evidence_strength=p.evidence_strength,
            )
            for p in all_positions
            if p.party_instance_id == pid
        ]
        top_party_positions.append(party_pos)

    best = select_next_question(
        answered_ids=answered_ids,
        candidates=candidates,
        top_party_positions=top_party_positions,
        answered_topic_counts=answered_topic_counts,
        user_salience_by_topic=user_salience_by_topic,
        answered_policy_item_counts=answered_policy_item_counts,
        salience_by_policy_item=salience_by_policy_item,
        all_topic_slugs=all_topic_slugs,
    )
    if not best:
        answered_policy_ids = {a.policy_item_id for a in answered_rows}
        servable_pi_ids = {q.policy_item_id for q in servable_questions}

        candidate_pis = (
            db.query(PolicyItem)
            .filter(PolicyItem.id.notin_(answered_policy_ids | servable_pi_ids))
            .all()
        )

    # ── Auto-generate on-the-fly when no pre-existing question is available ──
    if not best:
        answered_policy_ids = {a.policy_item_id for a in answered_rows}
        servable_pi_ids = {q.policy_item_id for q in servable_questions}

        candidate_pis = (
            db.query(PolicyItem)
            .filter(PolicyItem.id.notin_(answered_policy_ids | servable_pi_ids))
            .all()
        )

        best_pi: PolicyItem | None = None
        best_score = -1.0
        for pi in candidate_pis:
            positions = (
                db.query(PartyPosition).filter(PartyPosition.policy_item_id == pi.id).all()
            )
            if not positions:
                continue
            score = sum(p.evidence_strength for p in positions) / len(positions)
            if score > best_score:
                best_score = score
                best_pi = pi

        if best_pi:
            new_q = _auto_generate_question(db, best_pi)
            if new_q:
                topic = (
                    db.query(Topic)
                    .join(PolicyItem, PolicyItem.topic_id == Topic.id)
                    .filter(PolicyItem.id == best_pi.id)
                    .first()
                )
                return QuestionOut(
                    id=new_q.id,
                    question_text_en=new_q.question_text_en,
                    question_text_he=new_q.question_text_he,
                    question_text_ru=new_q.question_text_ru,
                    answer_scale_type=new_q.answer_scale_type.value,
                    policy_item_id=new_q.policy_item_id,
                    topic_slug=topic.slug if topic else "unknown",
                    topic_name_he=topic.name_he if topic else None,
                    topic_name_ru=topic.name_ru if topic else None,
                    context_note=None,
                    why_selected=_ui_strings()["why_selected"]["auto_generated"],
                    answer_polarity=new_q.answer_polarity if hasattr(new_q, "answer_polarity") else 1.0,
                    can_show_results=conv["can_show_results"],
                    phase=conv["phase"],
                    topics_covered=topics_covered,
                    topics_total=topics_total,
                    answered_count=len(answered_ids),
                    ranking_stability=conv["ranking_stability"],
                )
        return None

    q = db.query(Question).filter(Question.id == best.question_id).first()
    if not q:
        return None

    topic = topic_lookup.get(best.question_id)
    if not topic:
        topic = db.query(Topic).join(PolicyItem, PolicyItem.topic_id == Topic.id).filter(
            PolicyItem.id == q.policy_item_id
        ).first()

    # Determine why-selected message based on phase, salience, and discovery signal
    answered_count = len(answered_ids)
    is_discovery = (
        conv["phase"] == "depth"
        and best.outsider_party_signal >= DISCOVERY_SIGNAL_THRESHOLD
    )

    if answered_count == 0:
        why = _ui_strings()["why_selected"]["first_question"]
    elif conv["phase"] == "survey":
        why = _ui_strings()["why_selected"]["survey_question"]
    elif is_discovery:
        why = _ui_strings()["why_selected"]["discovery_question"]
    elif topic and user_salience_by_topic.get(topic.slug if topic else "", 1.0) >= 1.8:
        why = _ui_strings()["why_selected"]["depth_question"]
    else:
        why = _ui_strings()["why_selected"]["adaptive_question"]

    # Populate context_note from policy item description (no migration needed)
    context_note: str | None = None
    if q.policy_item_id:
        pi_for_note = db.query(PolicyItem).filter(PolicyItem.id == q.policy_item_id).first()
        if pi_for_note and pi_for_note.description:
            context_note = pi_for_note.description
    if not context_note and topic and topic.description:
        context_note = topic.description

    return QuestionOut(
        id=q.id,
        question_text_en=q.question_text_en,
        question_text_he=q.question_text_he,
        question_text_ru=q.question_text_ru,
        answer_scale_type=q.answer_scale_type.value,
        policy_item_id=q.policy_item_id,
        topic_slug=topic.slug if topic else "unknown",
        topic_name_he=topic.name_he if topic else None,
        topic_name_ru=topic.name_ru if topic else None,
        context_note=context_note,
        why_selected=why,
        is_root_question=q.is_root_question,
        answer_polarity=q.answer_polarity if hasattr(q, "answer_polarity") else 1.0,
        can_show_results=conv["can_show_results"],
        phase=conv["phase"],
        topics_covered=topics_covered,
        topics_total=topics_total,
        answered_count=answered_count,
        ranking_stability=conv["ranking_stability"],
        is_discovery_question=is_discovery,
        outsider_signal_strength=round(best.outsider_party_signal, 3),
    )


@router.get("/questions/{question_id}/context")
def get_question_context(
    question_id: uuid.UUID,
    lang: str = "en",
    db: Session = Depends(get_db),
) -> dict:
    """
    Return a plain-language explanation of what this question is about.
    Uses the policy item description and topic description as context.
    No LLM call — returns stored data only (fast, no latency).
    """
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    context_note: str | None = None
    topic_name: str | None = None

    if q.policy_item_id:
        pi = db.query(PolicyItem).filter(PolicyItem.id == q.policy_item_id).first()
        if pi and pi.description:
            context_note = pi.description
        if pi and pi.topic_id:
            topic = db.query(Topic).filter(Topic.id == pi.topic_id).first()
            if topic:
                if lang == "he" and topic.name_he:
                    topic_name = topic.name_he
                elif lang == "ru" and topic.name_ru:
                    topic_name = topic.name_ru
                else:
                    topic_name = topic.name_en

    if not context_note and q.topic_id:
        topic = db.query(Topic).filter(Topic.id == q.topic_id).first()
        if topic:
            context_note = topic.description
            if lang == "he" and topic.name_he:
                topic_name = topic.name_he
            elif lang == "ru" and topic.name_ru:
                topic_name = topic.name_ru
            else:
                topic_name = topic.name_en

    return {
        "question_id": str(question_id),
        "context_note": context_note,
        "topic_name": topic_name,
        "lang": lang,
    }


@router.get("/questions/{question_id}/explain")
def explain_question(
    question_id: uuid.UUID,
    lang: str = "en",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """
    Return a detailed, language-specific background explanation of the political
    issue behind this question — who, why, and how it became contested in Israel.

    Cache strategy:
      1. Check `question_explanations` table by (question_id, lang).
         If present → return immediately (zero LLM cost).
      2. On cache miss → call LLM (also logged via audit system).
      3. Store result in `question_explanations` for all future requests.

    Falls back to stored policy-item description if LLM is unavailable.

    lang: "en" | "he" | "ru"
    """
    from backend.app.models.question_explanation import QuestionExplanation

    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    # ── Step 1: dedicated explanation cache ──────────────────────────────────
    cached = (
        db.query(QuestionExplanation)
        .filter(
            QuestionExplanation.question_id == question_id,
            QuestionExplanation.lang == lang,
        )
        .first()
    )
    if cached:
        logger.debug(
            "explanation cache hit: question_id=%s lang=%s", question_id, lang
        )
        topic_name_str = ""
        if q.topic_id:
            topic = db.query(Topic).filter(Topic.id == q.topic_id).first()
            if topic:
                if lang == "he" and topic.name_he:
                    topic_name_str = topic.name_he
                elif lang == "ru" and topic.name_ru:
                    topic_name_str = topic.name_ru
                else:
                    topic_name_str = topic.name_en
        elif q.policy_item_id:
            pi = db.query(PolicyItem).filter(PolicyItem.id == q.policy_item_id).first()
            if pi and pi.topic_id:
                topic = db.query(Topic).filter(Topic.id == pi.topic_id).first()
                if topic:
                    if lang == "he" and topic.name_he:
                        topic_name_str = topic.name_he
                    elif lang == "ru" and topic.name_ru:
                        topic_name_str = topic.name_ru
                    else:
                        topic_name_str = topic.name_en
        return {
            "question_id": str(question_id),
            "lang": lang,
            "topic_name": topic_name_str,
            "background": cached.background or "",
            "why_relevant": cached.why_relevant or "",
            "support_side": cached.support_side or "",
            "oppose_side": cached.oppose_side or "",
            "everyday_example": cached.everyday_example or "",
            "source": "cached",
        }

    # ── Step 2: build context for LLM ────────────────────────────────────────
    _LANG_NAMES = {
        "he": "Hebrew (עברית)",
        "ru": "Russian (русский)",
        "en": "English",
    }
    language_name = _LANG_NAMES.get(lang, "English")

    if lang == "he":
        question_text = q.question_text_he or q.question_text_en
    elif lang == "ru":
        question_text = q.question_text_ru or q.question_text_en
    else:
        question_text = q.question_text_en

    policy_description = ""
    directional_axis = ""
    topic_name_str = ""

    pi = None
    topic = None

    if q.policy_item_id:
        pi = db.query(PolicyItem).filter(PolicyItem.id == q.policy_item_id).first()
        if pi:
            policy_description = pi.description or pi.title
            directional_axis = pi.directional_axis or ""
            if pi.topic_id:
                topic = db.query(Topic).filter(Topic.id == pi.topic_id).first()

    if not topic and q.topic_id:
        topic = db.query(Topic).filter(Topic.id == q.topic_id).first()

    if topic:
        if lang == "he" and topic.name_he:
            topic_name_str = topic.name_he
        elif lang == "ru" and topic.name_ru:
            topic_name_str = topic.name_ru
        else:
            topic_name_str = topic.name_en
        if not policy_description and topic.description:
            policy_description = topic.description

    # ── Step 3: LLM call (with audit-level caching as secondary) ─────────────
    if settings.openai_api_key:
        try:
            from backend.app.services.llm import get_llm_provider
            from backend.app.services.llm.audit_service import AuditedLLMService

            provider = get_llm_provider(settings)
            svc = AuditedLLMService(provider, db)

            input_data = {
                "question_text": question_text,
                "topic_name": topic_name_str,
                "policy_description": policy_description,
                "directional_axis": directional_axis,
                "language_name": language_name,
                "lang": lang,
            }
            result = svc.explain_question_context(input_data, entity_id=question_id)

            # ── Step 4: store in dedicated cache ─────────────────────────────
            try:
                expl = QuestionExplanation(
                    question_id=question_id,
                    lang=lang,
                    background=result.get("background", ""),
                    why_relevant=result.get("why_relevant", ""),
                    support_side=result.get("support_side", ""),
                    oppose_side=result.get("oppose_side", ""),
                    everyday_example=result.get("everyday_example", ""),
                    source="llm",
                )
                db.add(expl)
                db.commit()
                logger.info(
                    "explanation cached: question_id=%s lang=%s", question_id, lang
                )
            except Exception as cache_exc:
                db.rollback()
                logger.warning(
                    "Failed to cache explanation for %s lang=%s: %s",
                    question_id, lang, cache_exc,
                )

            return {
                "question_id": str(question_id),
                "lang": lang,
                "topic_name": topic_name_str,
                "background": result.get("background", ""),
                "why_relevant": result.get("why_relevant", ""),
                "support_side": result.get("support_side", ""),
                "oppose_side": result.get("oppose_side", ""),
                "everyday_example": result.get("everyday_example", ""),
                "source": "llm",
            }
        except Exception as exc:
            logger.warning("LLM explain_question_context failed for %s: %s", question_id, exc)

    # ── Graceful fallback — LLM not available ────────────────────────────────
    return {
        "question_id": str(question_id),
        "lang": lang,
        "topic_name": topic_name_str,
        "background": "",
        "why_relevant": "",
        "support_side": "",
        "oppose_side": "",
        "everyday_example": "",
        "source": "stored",
    }


@router.post("/questions/{question_id}/skip")
def skip_question(
    question_id: uuid.UUID,
    session_id: uuid.UUID,
    reason: str = "outdated",
    db: Session = Depends(get_db),
) -> dict:
    """
    Mark a question as skipped by the user for this session.
    The question will not be shown again to this session.
    reason: "outdated" | "not_relevant" | "other"
    """
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    # Idempotent — don't insert duplicate skip records
    existing = (
        db.query(UserSkippedQuestion)
        .filter(
            UserSkippedQuestion.session_id == session_id,
            UserSkippedQuestion.question_id == question_id,
        )
        .first()
    )
    if not existing:
        skip = UserSkippedQuestion(
            session_id=session_id,
            question_id=question_id,
            reason=reason,
        )
        db.add(skip)
        db.commit()

    return {"skipped": True, "question_id": str(question_id), "reason": reason}


@router.delete("/questions/{question_id}/explain/cache")
def clear_explanation_cache(
    question_id: uuid.UUID,
    lang: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """
    Clear the cached explanation for a question (admin / dev use).
    If lang is omitted, clears all languages.
    The next call to /explain will re-generate via LLM.
    """
    from backend.app.models.question_explanation import QuestionExplanation

    q_filter = db.query(QuestionExplanation).filter(
        QuestionExplanation.question_id == question_id
    )
    if lang:
        q_filter = q_filter.filter(QuestionExplanation.lang == lang)

    deleted = q_filter.delete()
    db.commit()
    return {"deleted": deleted, "question_id": str(question_id), "lang": lang}
