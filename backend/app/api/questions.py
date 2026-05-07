from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid
import logging

from backend.app.db import get_db
from backend.app.models.user_session import UserSession
from backend.app.models.question import Question, AnswerScaleType
from backend.app.models.user_answer import UserAnswer
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
    HARD_MAX,
    MIN_QUESTIONS,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["questionnaire"])


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
        if answer.policy_item_id:
            answered_policy_item_counts[answer.policy_item_id] = (
                answered_policy_item_counts.get(answer.policy_item_id, 0) + 1
            )
            answer_pi_salience_pairs.append((answer.policy_item_id, answer.salience))

        pi = db.query(PolicyItem).filter(PolicyItem.id == answer.policy_item_id).first()
        if pi:
            topic = db.query(Topic).filter(Topic.id == pi.topic_id).first()
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
    body: SessionCreate, db: Session = Depends(get_db)
) -> SessionOut:
    """Upsert an anonymous session. Client provides UUID or gets a new one."""
    session_id = body.session_id or uuid.uuid4()
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        session = UserSession(id=session_id)
        db.add(session)
        db.commit()
        db.refresh(session)
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

    if force_results(len(answered_ids)):
        return None

    # Compute convergence metadata (used for UI hints even though we don't stop here)
    conv = _build_convergence_meta(
        db, session_id, answered_ids, answered_topic_counts,
        all_topic_slugs, topics_covered, topics_total,
    )

    # Build candidates from servable questions (approved + llm_generated) not yet answered
    servable_questions = (
        db.query(Question)
        .filter(Question.human_review_status.in_(list(_SERVABLE_STATUSES)))
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

    answered_ids_set = set(answered_ids)

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

    for q in servable_questions:
        if q.id in set(answered_ids):
            continue
        pi = db.query(PolicyItem).filter(PolicyItem.id == q.policy_item_id).first()
        if not pi:
            continue
        topic = db.query(Topic).filter(Topic.id == pi.topic_id).first()
        topic_slug = topic.slug if topic else "unknown"
        topic_lookup[q.id] = topic

        positions = (
            db.query(PartyPosition)
            .filter(PartyPosition.policy_item_id == q.policy_item_id)
            .all()
        )
        avg_evidence = (
            sum(p.evidence_strength for p in positions) / len(positions)
            if positions
            else 0.0
        )

        candidates.append(
            QuestionCandidate(
                question_id=q.id,
                policy_item_id=q.policy_item_id,
                topic_slug=topic_slug,
                evidence_quality=avg_evidence,
            )
        )

    # Top-party positions (use all parties, capped at 5 for performance)
    all_positions = db.query(PartyPosition).all()
    party_ids = list({p.party_instance_id for p in all_positions})
    top_party_positions: list[list[PartyPositionSlim]] = []
    for pid in party_ids[:5]:
        party_pos = [
            PartyPositionSlim(
                policy_item_id=p.policy_item_id, position_mean=p.position_mean
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

    # Determine why-selected message based on phase and salience
    answered_count = len(answered_ids)
    if answered_count == 0:
        why = _ui_strings()["why_selected"]["first_question"]
    elif conv["phase"] == "survey":
        why = _ui_strings()["why_selected"]["survey_question"]
    elif topic and user_salience_by_topic.get(topic.slug if topic else "", 1.0) >= 1.8:
        why = _ui_strings()["why_selected"]["depth_question"]
    else:
        why = _ui_strings()["why_selected"]["adaptive_question"]

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
        context_note=None,
        why_selected=why,
        is_root_question=q.is_root_question,
        can_show_results=conv["can_show_results"],
        phase=conv["phase"],
        topics_covered=topics_covered,
        topics_total=topics_total,
        answered_count=answered_count,
        ranking_stability=conv["ranking_stability"],
    )
