"""
Lineage Service — Phase 4 / Gap 5.

Proposes PartyLineageEdge records for party instances that lack lineage edges.

Algorithm:
  1. Find party instance pairs that share a similar canonical name OR
     have overlapping time periods in adjacent Knesset numbers.
  2. Call LLM.infer_party_lineage() to classify the relationship.
  3. Insert PartyLineageEdge with human_review_status = "needs_review".

All proposed edges require human review before they affect scoring.
(AGENTS.MD §6.3, §9.1, §10.2)

Usage:
    from backend.app.services.lineage.lineage_service import run_lineage_inference
    stats = run_lineage_inference(db, settings, knesset_number=25)
"""
import logging
import uuid
import difflib
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from backend.app.models.party_instance import PartyInstance
from backend.app.models.political_brand import PoliticalBrand
from backend.app.models.party_lineage_edge import (
    PartyLineageEdge, LineageRelationType, LineageReviewStatus
)
from backend.app.services.llm import get_llm_provider
from backend.app.services.llm.audit_service import AuditedLLMService

if TYPE_CHECKING:
    from backend.app.config import Settings

logger = logging.getLogger(__name__)

# Minimum name similarity ratio to consider a pair for lineage inference
_MIN_NAME_SIMILARITY = 0.55

# Continuity weights from AGENTS.MD §6.3
_CONTINUITY_WEIGHTS = {
    "rename":     0.90,
    "rebrand":    0.75,
    "successor":  0.50,
    "split":      0.35,
    "merger":     0.45,
    "alliance":   0.20,
}


def _name_similarity(a: str, b: str) -> float:
    """SequenceMatcher ratio between two party names (case-insensitive)."""
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _already_has_edge(
    db: Session, from_id: uuid.UUID, to_id: uuid.UUID
) -> bool:
    return bool(
        db.query(PartyLineageEdge)
        .filter(
            PartyLineageEdge.from_party_instance_id == from_id,
            PartyLineageEdge.to_party_instance_id == to_id,
        )
        .first()
    )


def run_lineage_inference(
    db: Session,
    settings: "Settings",
    knesset_number: int | None = None,
    enrich_with_llm: bool = True,
) -> dict[str, int]:
    """
    Propose lineage edges between party instances in adjacent Knesset numbers.

    For the target knesset_number, try to match each party instance with
    party instances in knesset_number-1 by name similarity.
    If LLM is available, call infer_party_lineage to classify the relationship.

    Returns {"candidates_evaluated": N, "edges_proposed": N, "skipped": N}.
    """
    llm_raw = get_llm_provider(settings) if enrich_with_llm else None
    llm = AuditedLLMService(llm_raw, db) if llm_raw else None

    # Load party instances for target knesset and previous knesset
    if knesset_number:
        current_parties = (
            db.query(PartyInstance)
            .filter(PartyInstance.knesset_number == knesset_number)
            .all()
        )
        prev_parties = (
            db.query(PartyInstance)
            .filter(PartyInstance.knesset_number == knesset_number - 1)
            .all()
        )
    else:
        # Process all parties without edges
        all_parties = db.query(PartyInstance).order_by(PartyInstance.knesset_number).all()
        # Group by knesset
        knesset_map: dict[int, list[PartyInstance]] = {}
        for p in all_parties:
            k = p.knesset_number or 0
            knesset_map.setdefault(k, []).append(p)
        knessets = sorted(knesset_map.keys())
        if len(knessets) < 2:
            return {"candidates_evaluated": 0, "edges_proposed": 0, "skipped": 0}
        # Process the two most recent knessets
        current_parties = knesset_map[knessets[-1]]
        prev_parties = knesset_map[knessets[-2]]

    candidates_evaluated = edges_proposed = skipped = 0

    for current in current_parties:
        best_match: PartyInstance | None = None
        best_score = 0.0

        for prev in prev_parties:
            if _already_has_edge(db, prev.id, current.id):
                continue
            score = _name_similarity(current.official_name, prev.official_name)
            if score > best_score and score >= _MIN_NAME_SIMILARITY:
                best_score = score
                best_match = prev

        if not best_match:
            # Also check by political brand continuity
            brand_match = _find_brand_match(db, current, prev_parties)
            if brand_match and not _already_has_edge(db, brand_match.id, current.id):
                best_match = brand_match
                best_score = 0.80  # brand continuity implies high similarity

        if not best_match:
            skipped += 1
            continue

        candidates_evaluated += 1

        # Determine relation type and continuity weight
        relation_type = LineageRelationType.successor
        continuity_weight = _CONTINUITY_WEIGHTS["successor"]
        explanation = f"Auto-proposed: name similarity {best_score:.0%} between Knesset {best_match.knesset_number} and {current.knesset_number}."

        if llm:
            try:
                from_brand = db.query(PoliticalBrand).filter(
                    PoliticalBrand.id == best_match.political_brand_id
                ).first()
                to_brand = db.query(PoliticalBrand).filter(
                    PoliticalBrand.id == current.political_brand_id
                ).first()

                llm_result = llm.infer_party_lineage(
                    {
                        "from_party": f"{best_match.official_name} (Knesset {best_match.knesset_number})",
                        "to_party": f"{current.official_name} (Knesset {current.knesset_number})",
                        "context": (
                            f"From brand: {from_brand.description if from_brand else 'unknown'}. "
                            f"To brand: {to_brand.description if to_brand else 'unknown'}. "
                            f"Name similarity: {best_score:.0%}."
                        ),
                    }
                )
                rel_str = llm_result.get("relation_type", "successor")
                try:
                    relation_type = LineageRelationType(rel_str)
                except ValueError:
                    relation_type = LineageRelationType.successor

                continuity_weight = float(
                    llm_result.get("continuity_weight", _CONTINUITY_WEIGHTS.get(rel_str, 0.5))
                )
                explanation = llm_result.get("explanation", explanation)
            except Exception as exc:
                logger.warning(
                    "infer_party_lineage failed %s→%s: %s",
                    best_match.official_name, current.official_name, exc,
                )

        edge = PartyLineageEdge(
            id=uuid.uuid4(),
            from_party_instance_id=best_match.id,
            to_party_instance_id=current.id,
            relation_type=relation_type,
            continuity_weight=max(0.0, min(1.0, continuity_weight)),
            llm_explanation=explanation,
            human_review_status=LineageReviewStatus.needs_review,
        )
        db.add(edge)
        edges_proposed += 1

    db.commit()
    stats = {
        "candidates_evaluated": candidates_evaluated,
        "edges_proposed": edges_proposed,
        "skipped": skipped,
    }
    logger.info("lineage_inference → %s", stats)
    return stats


def _find_brand_match(
    db: Session,
    current: PartyInstance,
    prev_parties: list[PartyInstance],
) -> PartyInstance | None:
    """
    Find a previous-knesset party that shares the same political brand.
    """
    for prev in prev_parties:
        if prev.political_brand_id == current.political_brand_id:
            return prev
    return None

