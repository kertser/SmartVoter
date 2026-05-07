from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from backend.app.db import get_db
from backend.app.models.user_session import UserSession
from backend.app.models.user_answer import UserAnswer
from backend.app.models.party_instance import PartyInstance
from backend.app.models.party_position import PartyPosition
from backend.app.models.political_brand import PoliticalBrand
from backend.app.models.topic import Topic
from backend.app.models.policy_item import PolicyItem
from backend.app.models.recommendation_run import RecommendationRun
from backend.app.schemas.results import (
    ResultsOut,
    PartyResult,
    RepresentationGap,
    BestPartyByTopic,
)
from backend.app.services.scoring import (
    AnswerData,
    PositionData,
    compute_match_score,
    compute_confidence_score,
    compute_coverage_score,
    compute_answer_stability,
)
from backend.app.services.volatility import get_party_volatility

router = APIRouter(tags=["results"])

# Threshold below which we consider a party a "new" party (limited evidence)
NEW_PARTY_EVIDENCE_THRESHOLD = 0.45


@router.get("/results/{session_id}", response_model=ResultsOut)
def get_results(session_id: uuid.UUID, db: Session = Depends(get_db)) -> ResultsOut:
    """
    Compute and return full match results for a session.
    Implements AGENTS.MD Section 17 output schema.
    """
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_answers_rows = (
        db.query(UserAnswer).filter(UserAnswer.session_id == session_id).all()
    )
    if not user_answers_rows:
        raise HTTPException(
            status_code=422, detail="No answers recorded for this session"
        )

    user_answers = [
        AnswerData(
            policy_item_id=a.policy_item_id,
            answer_value=a.answer_value,
            salience=a.salience,
        )
        for a in user_answers_rows
    ]

    # Load all party instances
    party_instances = db.query(PartyInstance).all()
    if not party_instances:
        raise HTTPException(status_code=500, detail="No party data in database")

    # Build lookup caches so we don't query inside loops
    all_brands: dict = {b.id: b for b in db.query(PoliticalBrand).all()}
    all_policy_items: dict = {pi.id: pi for pi in db.query(PolicyItem).all()}
    all_topics: dict = {t.id: t for t in db.query(Topic).all()}
    answered_item_ids_global: set = {a.policy_item_id for a in user_answers_rows}

    party_results: list[PartyResult] = []

    for party in party_instances:
        # Load brand name (from bulk-fetch cache)
        brand = all_brands.get(party.political_brand_id)
        party_name = brand.canonical_name if brand else party.official_name
        names = brand.names_json or {} if brand else {}
        name_he = names.get("he") or party_name
        # For Russian, prefer "he" over the English canonical fallback
        name_ru = names.get("ru") or names.get("he") or party_name

        # Load party positions
        positions_rows = (
            db.query(PartyPosition)
            .filter(PartyPosition.party_instance_id == party.id)
            .all()
        )
        if not positions_rows:
            continue

        positions = [
            PositionData(
                policy_item_id=p.policy_item_id,
                position_mean=p.position_mean,
                position_uncertainty=p.position_uncertainty,
                evidence_strength=p.evidence_strength,
                evidence_type=p.evidence_type or "party_platform",
            )
            for p in positions_rows
        ]

        match_score = compute_match_score(user_answers, positions)
        coverage = compute_coverage_score(user_answers, positions)
        answer_stability = compute_answer_stability(user_answers, positions)
        volatility = get_party_volatility(party.id, db)
        confidence = compute_confidence_score(
            positions, user_answers, volatility, coverage, answer_stability
        )

        avg_evidence_strength = sum(p.evidence_strength for p in positions) / len(positions)
        is_new_party = avg_evidence_strength < NEW_PARTY_EVIDENCE_THRESHOLD

        # Find agreements and disagreements (top 3 topics each)
        topic_scores: dict[str, list[float]] = {}
        # Maps topic name_en → (name_he, name_ru)
        topic_names_i18n: dict[str, tuple[str | None, str | None]] = {}
        answered_item_ids = answered_item_ids_global
        for pos in positions:
            if pos.policy_item_id not in answered_item_ids:
                continue
            pi = all_policy_items.get(pos.policy_item_id)
            if not pi:
                continue
            topic = all_topics.get(pi.topic_id) if pi.topic_id else None
            if not topic:
                continue
            user_ans = next(
                (a for a in user_answers if a.policy_item_id == pos.policy_item_id), None
            )
            if not user_ans:
                continue
            distance = abs(user_ans.answer_value - pos.position_mean)
            similarity = 1.0 - distance / 2.0
            topic_scores.setdefault(topic.name_en, []).append(similarity)
            topic_names_i18n.setdefault(topic.name_en, (topic.name_he, topic.name_ru))

        topic_avg = {t: sum(v) / len(v) for t, v in topic_scores.items()}
        sorted_topics = sorted(topic_avg.items(), key=lambda x: -x[1])

        # Evidence-by-type breakdown
        evidence_counts: dict[str, float] = {}
        for p in positions_rows:
            etype = p.evidence_type or "party_platform"
            evidence_counts[etype] = evidence_counts.get(etype, 0) + p.evidence_strength
        total_evidence = sum(evidence_counts.values()) or 1.0
        evidence_by_type = {k: round(v / total_evidence, 3) for k, v in sorted(evidence_counts.items(), key=lambda x: -x[1])}

        top_agreements = [t for t, s in sorted_topics if s >= 0.65][:3]
        top_disagreements = [t for t, s in sorted_topics if s < 0.5][:3]

        # Localized agreement/disagreement lists
        top_agreements_he = [
            topic_names_i18n.get(t, (None, None))[0] or t for t in top_agreements
        ]
        top_agreements_ru = [
            topic_names_i18n.get(t, (None, None))[1] or t for t in top_agreements
        ]
        top_disagreements_he = [
            topic_names_i18n.get(t, (None, None))[0] or t for t in top_disagreements
        ]
        top_disagreements_ru = [
            topic_names_i18n.get(t, (None, None))[1] or t for t in top_disagreements
        ]
        weak_evidence = [
            all_topics[all_policy_items[p.policy_item_id].topic_id]
            for p in positions_rows
            if p.evidence_strength < 0.4
            and p.policy_item_id in all_policy_items
            and all_policy_items[p.policy_item_id].topic_id in all_topics
        ]
        weak_evidence_topic_names = list({t.name_en for t in weak_evidence})[:3]

        explanation = (
            f"Based on available evidence, your preferences align with {party_name} "
            f"on {len(top_agreements)} key topics."
        )
        explanation_he = (
            f"בהתבסס על הראיות הזמינות, העדפותיך מתאימות ל{name_he} "
            f"ב-{len(top_agreements)} נושאים מרכזיים."
        )
        explanation_ru = (
            f"На основе имеющихся данных ваши предпочтения совпадают с позицией {name_ru} "
            f"по {len(top_agreements)} ключевым темам."
        )
        if is_new_party:
            explanation += (
                " Note: this party has limited parliamentary history. "
                "Match score is based on candidate history and declared positions."
            )
            explanation_he += (
                " שים לב: למפלגה זו היסטוריה פרלמנטרית מוגבלת. "
                "ציון ההתאמה מבוסס על היסטוריית המועמדים ועמדות מוצהרות."
            )
            explanation_ru += (
                " Примечание: у этой партии ограниченная парламентская история. "
                "Оценка совпадения основана на истории кандидатов и задекларированных позициях."
            )

        party_results.append(
            PartyResult(
                party_id=party.id,
                name=party_name,
                name_he=name_he,
                name_ru=name_ru,
                match_score=round(match_score, 4),
                confidence=round(confidence, 4),
                evidence_strength=round(avg_evidence_strength, 4),
                volatility=round(volatility, 4),
                coverage=round(coverage, 4),
                answer_stability=round(answer_stability, 4),
                is_new_party=is_new_party,
                explanation=explanation,
                explanation_he=explanation_he,
                explanation_ru=explanation_ru,
                top_agreements=top_agreements,
                top_agreements_he=top_agreements_he,
                top_agreements_ru=top_agreements_ru,
                top_disagreements=top_disagreements,
                top_disagreements_he=top_disagreements_he,
                top_disagreements_ru=top_disagreements_ru,
                weak_evidence_topics=weak_evidence_topic_names,
                topic_scores={t: round(s, 3) for t, s in topic_avg.items()},
                evidence_by_type=evidence_by_type,
            )
        )

    # Sort by match_score descending
    party_results.sort(key=lambda p: -p.match_score)

    # Build a global topic name_en → (name_he, name_ru) lookup from the bulk cache
    all_topic_names_i18n: dict[str, tuple[str | None, str | None]] = {
        t.name_en: (t.name_he, t.name_ru) for t in all_topics.values()
    }

    # Representation gap
    answered_topics: dict[str, list[float]] = {}
    for a in user_answers:
        pi = all_policy_items.get(a.policy_item_id)
        if not pi:
            continue
        topic = all_topics.get(pi.topic_id) if pi.topic_id else None
        if not topic:
            continue
        answered_topics.setdefault(topic.name_en, []).append(a.salience)

    best_by_topic: list[BestPartyByTopic] = []
    for topic_name in answered_topics:
        best_party_result: PartyResult | None = None
        best_topic_score = -1.0
        for pr in party_results:
            # Use per-party topic similarity scores (more accurate than match_score)
            topic_sim = pr.topic_scores.get(topic_name, -1.0)
            if topic_sim > best_topic_score:
                best_topic_score = topic_sim
                best_party_result = pr
        if best_party_result and best_topic_score >= 0:
            topic_he, topic_ru = all_topic_names_i18n.get(topic_name, (None, None))
            best_by_topic.append(
                BestPartyByTopic(
                    topic=topic_name,
                    topic_he=topic_he,
                    topic_ru=topic_ru,
                    party=best_party_result.name,
                    party_he=best_party_result.name_he,
                )
            )

    max_match = max((p.match_score for p in party_results), default=0.0)
    has_gap = max_match < 0.65

    top_party = party_results[0] if party_results else None
    top_party_name_he = top_party.name_he or top_party.name if top_party else "N/A"
    gap_explanation = (
        "No party strongly represents all of your high-priority positions."
        if has_gap
        else f"Your closest party ({top_party.name if top_party else 'N/A'}) "
        f"aligns well with your preferences."
    )

    representation_gap = RepresentationGap(
        has_gap=has_gap,
        explanation=gap_explanation,
        best_party_by_topic=best_by_topic,
    )

    # Persist recommendation run
    run = RecommendationRun(
        session_id=session_id,
        scoring_config_json={"methodology_version": "0.1.0"},
        result_json={
            "parties": [p.model_dump(mode="json") for p in party_results],
            "representation_gap": representation_gap.model_dump(),
        },
        methodology_version="0.1.0",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return ResultsOut(
        session_id=session_id,
        run_id=run.id,
        parties=party_results,
        representation_gap=representation_gap,
    )

