from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from collections import defaultdict
import uuid

from backend.app.db import get_db
from backend.app.models.user_session import UserSession
from backend.app.models.user_answer import UserAnswer
from backend.app.models.party_instance import PartyInstance, PartyStatus
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
    DiscoveryMatch,
)
from backend.app.services.scoring import (
    AnswerData,
    PositionData,
    compute_match_score,
    compute_confidence_score,
    compute_coverage_score,
    compute_answer_stability,
    compute_agenda_breadth,
    compute_high_salience_topic_coverage,
    effective_evidence_strength,
    normalise_evidence_type,
    SECTORAL_THRESHOLD,
)
from backend.app.services.volatility import get_party_volatility

router = APIRouter(tags=["results"])

# Threshold below which we consider a party a "new" party (limited evidence).
# Aligned with the AGENTS.MD §8.2 "party_platform" prior (0.35) — any party
# whose average effective evidence strength is below this is essentially
# resting on declared positions / statements rather than observed behaviour.
NEW_PARTY_EVIDENCE_THRESHOLD = 0.35

# Minimum match score to include a party in results
# Parties with 0 policy-item overlap (different data sources) are filtered out
MIN_MATCH_THRESHOLD = 0.03

# Hebrew leadership-suffix patterns stripped when deduplicating party names
_HE_STRIP_PATTERNS = [" בהנהגת ", " בראשות ", " – ", " - "]


def _canonicalize_he_name(name_he: str | None) -> str:
    """
    Strip Hebrew election-period leadership suffixes so that
    'הליכוד בהנהגת בנימין נתניהו...' and 'הליכוד' resolve to the same key.
    Used for cross-brand deduplication in results.
    """
    if not name_he:
        return ""
    result = name_he.strip()
    for pat in _HE_STRIP_PATTERNS:
        idx = result.find(pat)
        if idx > 0:
            result = result[:idx].strip()
    return result


def _pick_canonical_instances(
    party_instances: list[PartyInstance],
    pos_counts: dict[uuid.UUID, int],
) -> list[PartyInstance]:
    """
    For each political_brand_id, return exactly ONE PartyInstance as the
    canonical representative.

    Selection priority (descending):
        1. Most positions (highest data richness)
        2. Active status
        3. Highest Knesset number
    """
    by_brand: dict[uuid.UUID, list[PartyInstance]] = defaultdict(list)
    for inst in party_instances:
        by_brand[inst.political_brand_id].append(inst)

    best: list[PartyInstance] = []
    for insts in by_brand.values():
        winner = max(
            insts,
            key=lambda i: (
                pos_counts.get(i.id, 0),
                1 if i.status == PartyStatus.active else 0,
                i.knesset_number or 0,
            ),
        )
        best.append(winner)
    return best


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

    # Load all party instances — pre-compute position counts for canonical selection
    all_party_instances_raw = db.query(PartyInstance).all()
    if not all_party_instances_raw:
        raise HTTPException(status_code=500, detail="No party data in database")

    # Pre-compute position counts per instance for canonical selection
    _pos_counts: dict[uuid.UUID, int] = defaultdict(int)
    for _p in db.query(PartyPosition.party_instance_id).all():
        _pos_counts[_p.party_instance_id] += 1

    # Deduplicate: one representative instance per political_brand_id
    party_instances = _pick_canonical_instances(all_party_instances_raw, _pos_counts)

    # Build lookup caches so we don't query inside loops
    all_brands: dict = {b.id: b for b in db.query(PoliticalBrand).all()}
    all_policy_items: dict = {pi.id: pi for pi in db.query(PolicyItem).all()}
    all_topics: dict = {t.id: t for t in db.query(Topic).all()}
    answered_item_ids_global: set = {a.policy_item_id for a in user_answers_rows}

    # Build a mapping policy_item_id → topic_slug for high-salience coverage check
    answered_item_to_topic: dict[uuid.UUID, str] = {}
    for a in user_answers_rows:
        pi = all_policy_items.get(a.policy_item_id)
        if pi and pi.topic_id:
            topic = all_topics.get(pi.topic_id)
            if topic:
                answered_item_to_topic[a.policy_item_id] = topic.slug

    total_topics_count = len(all_topics)

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

        # Skip parties with no overlap (different data sources / zero match)
        if match_score < MIN_MATCH_THRESHOLD:
            continue

        coverage = compute_coverage_score(user_answers, positions)
        answer_stability = compute_answer_stability(user_answers, positions)
        volatility = get_party_volatility(party.id, db)

        # Agenda-breadth: distinct topics this party has positions on
        party_topics_set: set[str] = set()
        for p in positions_rows:
            pi_obj = all_policy_items.get(p.policy_item_id)
            if pi_obj and pi_obj.topic_id:
                t_obj = all_topics.get(pi_obj.topic_id)
                if t_obj:
                    party_topics_set.add(t_obj.slug)
        agenda_breadth = compute_agenda_breadth(positions, len(party_topics_set), total_topics_count)
        is_sectoral = agenda_breadth < SECTORAL_THRESHOLD

        # High-salience topic coverage: fraction of user's very-important topics covered
        high_salience_coverage = compute_high_salience_topic_coverage(
            user_answers, answered_item_to_topic, party_topics_set
        )

        confidence = compute_confidence_score(
            positions, user_answers, volatility, coverage, answer_stability,
            high_salience_topic_coverage=high_salience_coverage,
        )

        avg_evidence_strength = (
            sum(effective_evidence_strength(p) for p in positions) / len(positions)
        )
        # §9.1 — a party is treated as "new" when its effective evidence is
        # below the §8.2 platform prior (0.35). This catches platform/statement
        # only parties as well as parties with very thin substantive votes.
        is_new_party = avg_evidence_strength < NEW_PARTY_EVIDENCE_THRESHOLD

        # Confidence breakdown for UI display
        confidence_breakdown = {
            "evidence_quality": round(avg_evidence_strength, 3),
            "coverage": round(coverage, 3),
            "answer_stability": round(answer_stability, 3),
            "volatility_penalty": round(volatility, 3),
            "high_salience_coverage": round(high_salience_coverage, 3),
        }

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

        # Evidence-by-type breakdown (uses canonical AGENTS.MD §8.2 keys).
        # Each row contributes its EFFECTIVE strength (i.e. capped by §8.2
        # prior) so the bar reflects what actually drove the score.
        evidence_counts: dict[str, float] = {}
        for p in positions_rows:
            etype = normalise_evidence_type(p.evidence_type)
            cap = {
                "vote": 1.0, "sponsored_bill": 0.8, "committee_behavior": 0.7,
                "candidate_past_vote": 0.55, "party_lineage": 0.5,
                "coalition_agreement": 0.45, "party_platform": 0.35,
                "public_statement": 0.25, "media_interview": 0.2,
                "new_party_synth": 0.55,
            }.get(etype, 0.35)
            effective = min(p.evidence_strength or 0.0, cap)
            evidence_counts[etype] = evidence_counts.get(etype, 0) + effective
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

        if is_sectoral:
            explanation += (
                " Note: this is a sector-focused party. Its high match score reflects "
                "agreement on its narrow agenda; it may not represent your views on many other topics."
            )
            explanation_he += (
                " שים לב: זוהי מפלגה סקטוריאלית. ציון ההתאמה הגבוה משקף הסכמה על אג'נדה מצומצמת "
                "בלבד; ייתכן שהיא אינה מייצגת את עמדותיך בנושאים אחרים רבים."
            )
            explanation_ru += (
                " Примечание: это партия с узкой повесткой. Высокий балл совпадения отражает "
                "согласие по её ограниченной программе; она может не представлять ваши взгляды "
                "по многим другим темам."
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
                agenda_breadth=round(agenda_breadth, 4),
                is_sectoral=is_sectoral,
                high_salience_coverage=round(high_salience_coverage, 4),
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
                confidence_breakdown=confidence_breakdown,
            )
        )

    # Sort by match_score descending
    party_results.sort(key=lambda p: -p.match_score)

    # ── Cross-brand deduplication by canonical Hebrew name ────────────────────
    # Strip election-period leadership suffixes ('בהנהגת', 'בראשות') so that
    # e.g. 'הליכוד בהנהגת בנימין נתניהו...' and 'הליכוד' resolve to the same key.
    # When two results share the same canonical key, keep the one with higher
    # evidence_strength (more data-rich), which produces better match scoring.
    seen_he_keys: dict[str, int] = {}   # canonical_key → index in deduped list
    deduped_results: list[PartyResult] = []
    for pr in party_results:
        he_key = _canonicalize_he_name(pr.name_he)
        if not he_key:
            deduped_results.append(pr)
            continue
        if he_key in seen_he_keys:
            existing_idx = seen_he_keys[he_key]
            existing = deduped_results[existing_idx]
            # Replace with higher-evidence result (better data source)
            if pr.evidence_strength > existing.evidence_strength:
                deduped_results[existing_idx] = pr
        else:
            seen_he_keys[he_key] = len(deduped_results)
            deduped_results.append(pr)

    # Re-sort after cross-brand dedup (order may have shifted)
    deduped_results.sort(key=lambda p: -p.match_score)
    party_results = deduped_results

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

    # ── Discovery / unexpected matches ────────────────────────────────────────
    # Find topics where a NON-top-3 party aligns significantly better with the
    # user than any of the top-3 parties.  Threshold: outsider_sim > top3_best + 0.15
    # and outsider_sim >= 0.70 (must be an actually good match, not just "least bad").
    DISCOVERY_ADVANTAGE = 0.15
    DISCOVERY_MIN_SIM = 0.68

    top_3_ids = {pr.party_id for pr in party_results[:3]}
    discovery_matches: list[DiscoveryMatch] = []

    for topic_name in answered_topics:
        top3_best = max(
            (pr.topic_scores.get(topic_name, 0.0) for pr in party_results if pr.party_id in top_3_ids),
            default=0.0,
        )
        for pr in party_results:
            if pr.party_id in top_3_ids:
                continue
            outsider_sim = pr.topic_scores.get(topic_name, 0.0)
            if outsider_sim >= DISCOVERY_MIN_SIM and outsider_sim > top3_best + DISCOVERY_ADVANTAGE:
                topic_he, topic_ru = all_topic_names_i18n.get(topic_name, (None, None))
                discovery_matches.append(
                    DiscoveryMatch(
                        topic=topic_name,
                        topic_he=topic_he,
                        topic_ru=topic_ru,
                        party=pr.name,
                        party_he=pr.name_he,
                        party_ru=pr.name_ru,
                        party_id=pr.party_id,
                        similarity=round(outsider_sim, 3),
                        top3_best_similarity=round(top3_best, 3),
                    )
                )

    # Sort by advantage (how much better than top-3)
    discovery_matches.sort(key=lambda m: -(m.similarity - m.top3_best_similarity))
    # Cap at 6 most significant discoveries
    discovery_matches = discovery_matches[:6]

    # Persist recommendation run
    run = RecommendationRun(
        session_id=session_id,
        scoring_config_json={"methodology_version": "0.1.0"},
        result_json={
            "parties": [p.model_dump(mode="json") for p in party_results],
            "representation_gap": representation_gap.model_dump(),
            "discovery_matches": [d.model_dump(mode="json") for d in discovery_matches],
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
        discovery_matches=discovery_matches,
    )

