"""
Party Position Pipeline — Phase 6 / Gap 3.

Derives PartyPosition records from real vote_results:

  vote_results (per party faction)
    → aggregate for/against/abstain counts
    → LLM infer_party_position (interprets counts against the policy axis)
    → PartyPosition (needs_review)

AGENTS.MD §8.3 weighted evidence formula is used for the formula-based path.
The LLM path adds a natural-language explanation and refines the position mean.

Usage:
    from backend.app.services.ingestion.party_position_pipeline import (
        run_party_position_pipeline
    )
    stats = run_party_position_pipeline(db, settings, knesset_number=25)
"""
import logging
import math
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.party_instance import PartyInstance
from backend.app.models.party_position import PartyPosition
from backend.app.models.policy_item import PolicyItem
from backend.app.models.vote import Vote
from backend.app.models.vote_result import VoteResult
from backend.app.services.scoring.engine import EVIDENCE_WEIGHTS
from backend.app.services.llm import get_llm_provider
from backend.app.services.llm.audit_service import AuditedLLMService

if TYPE_CHECKING:
    from backend.app.config import Settings

logger = logging.getLogger(__name__)

_PRIOR_STRENGTH = 2.0  # AGENTS.MD §8.3


def _aggregate_faction_votes(
    db: Session,
    party_instance_id: uuid.UUID,
    vote_ids: list[uuid.UUID],
) -> dict:
    """
    Summarise this party's voting record across a list of vote IDs.
    Returns counts and derived raw position signal.
    """
    if not vote_ids:
        return {"for": 0, "against": 0, "abstain": 0, "absent": 0, "total": 0, "raw_signal": 0.0}

    rows = (
        db.query(VoteResult.vote_value, func.count(VoteResult.id))
        .filter(
            VoteResult.party_instance_id_at_time == party_instance_id,
            VoteResult.vote_id.in_(vote_ids),
        )
        .group_by(VoteResult.vote_value)
        .all()
    )

    counts = {"for": 0, "against": 0, "abstain": 0, "absent": 0}
    for val, cnt in rows:
        key = val.value if hasattr(val, "value") else str(val)
        counts[key] = counts.get(key, 0) + cnt

    substantive = counts["for"] + counts["against"] + counts["abstain"]
    total = substantive + counts["absent"]

    # Raw position signal: +1 = fully for, -1 = fully against
    # Abstain treated as 0 / neutral signal, absent excluded
    if substantive > 0:
        raw_signal = (counts["for"] - counts["against"]) / substantive
    else:
        raw_signal = 0.0

    return {**counts, "total": total, "substantive": substantive, "raw_signal": raw_signal}


def _evidence_strength_from_votes(counts: dict) -> float:
    """
    AGENTS.MD §8.3: evidence_strength ∝ sum of evidence weights / (sum + prior).
    For votes, each substantive vote carries weight 1.0.
    Absent votes carry 0.2 (low signal, per AGENTS.MD §6.8).
    """
    substantive_weight = counts.get("substantive", 0) * EVIDENCE_WEIGHTS["vote"]
    absent_weight = counts.get("absent", 0) * 0.2
    total_weight = substantive_weight + absent_weight
    # Normalise 0→1 using sigmoid-like formula: w / (w + prior)
    return round(total_weight / (total_weight + _PRIOR_STRENGTH), 4) if total_weight > 0 else 0.0


def _uncertainty_from_votes(counts: dict) -> float:
    """AGENTS.MD §8.3: uncertainty = 1 / sqrt(sum_weight + prior_strength)."""
    w = counts.get("substantive", 0) * EVIDENCE_WEIGHTS["vote"]
    return round(1.0 / math.sqrt(w + _PRIOR_STRENGTH), 4)


def run_party_position_pipeline(
    db: Session,
    settings: "Settings",
    knesset_number: int | None = None,
    limit_policy_items: int = 100,
    enrich_with_llm: bool = True,
    overwrite_existing: bool = False,
) -> dict[str, int]:
    """
    For each (PartyInstance × PolicyItem) pair that has vote evidence,
    compute and store a PartyPosition.

    Steps:
    1. Load policy items that have source_refs of type "vote".
    2. For each party instance in the target knesset, aggregate vote_results.
    3. Call LLM to infer position mean + explanation (or use formula only).
    4. Upsert PartyPosition with human_review_status = "needs_review".

    Returns {"pairs_evaluated": N, "positions_created": N, "positions_updated": N,
             "skipped_no_evidence": N}.
    """
    llm_raw = get_llm_provider(settings) if enrich_with_llm else None
    llm = AuditedLLMService(llm_raw, db) if llm_raw else None

    # Load party instances
    pi_query = db.query(PartyInstance)
    if knesset_number:
        pi_query = pi_query.filter(PartyInstance.knesset_number == knesset_number)
    party_instances = pi_query.all()

    # Load policy items with vote sources
    policy_items = (
        db.query(PolicyItem)
        .filter(PolicyItem.source_refs_json.isnot(None))
        .limit(limit_policy_items)
        .all()
    )

    pairs_evaluated = positions_created = positions_updated = skipped_no_evidence = 0

    for policy_item in policy_items:
        # Extract vote UUIDs referenced by this policy item
        vote_ids = _extract_vote_ids(db, policy_item)
        if not vote_ids:
            continue

        for party in party_instances:
            pairs_evaluated += 1

            # Skip if already exists (unless overwrite requested)
            existing = (
                db.query(PartyPosition)
                .filter(
                    PartyPosition.party_instance_id == party.id,
                    PartyPosition.policy_item_id == policy_item.id,
                )
                .first()
            )
            if existing and not overwrite_existing:
                continue

            counts = _aggregate_faction_votes(db, party.id, vote_ids)

            if counts.get("substantive", 0) == 0:
                skipped_no_evidence += 1
                continue

            evidence_strength = _evidence_strength_from_votes(counts)
            uncertainty = _uncertainty_from_votes(counts)

            # Start with formula-based position mean (AGENTS.MD §8.3)
            position_mean = round(counts["raw_signal"] * 0.8, 4)  # dampened (LLM will refine)
            explanation = None

            if llm:
                try:
                    vote_titles = _fetch_vote_titles(db, vote_ids[:10])  # sample for context
                    llm_result = llm.infer_party_position(
                        {
                            "party_name": party.official_name,
                            "policy_title": policy_item.title,
                            "directional_axis": policy_item.directional_axis or "",
                            "negative_pole": _parse_axis_pole(policy_item.directional_axis, "neg"),
                            "positive_pole": _parse_axis_pole(policy_item.directional_axis, "pos"),
                            "evidence": [
                                {
                                    "type": "vote_aggregate",
                                    "for": counts["for"],
                                    "against": counts["against"],
                                    "abstain": counts["abstain"],
                                    "absent": counts["absent"],
                                    "sample_titles": vote_titles,
                                }
                            ],
                        },
                        entity_id=policy_item.id,
                    )
                    position_mean = float(llm_result.get("party_position_mean", position_mean))
                    uncertainty = float(llm_result.get("uncertainty", uncertainty))
                    evidence_strength = float(llm_result.get("evidence_strength", evidence_strength))
                    explanation = llm_result.get("explanation")
                except Exception as exc:
                    logger.warning(
                        "infer_party_position failed party=%s policy=%s: %s",
                        party.official_name, policy_item.title[:60], exc,
                    )

            if existing:
                existing.position_mean = position_mean
                existing.position_uncertainty = uncertainty
                existing.evidence_strength = evidence_strength
                existing.evidence_type = "vote"
                existing.llm_explanation = explanation
                existing.source_refs_json = [{"type": "vote", "ids": [str(v) for v in vote_ids]}]
                positions_updated += 1
            else:
                db.add(PartyPosition(
                    id=uuid.uuid4(),
                    party_instance_id=party.id,
                    policy_item_id=policy_item.id,
                    position_mean=position_mean,
                    position_uncertainty=uncertainty,
                    evidence_strength=evidence_strength,
                    evidence_type="vote",
                    source_refs_json=[{"type": "vote", "ids": [str(v) for v in vote_ids]}],
                    llm_explanation=explanation,
                ))
                positions_created += 1

        db.commit()

    stats = {
        "pairs_evaluated": pairs_evaluated,
        "positions_created": positions_created,
        "positions_updated": positions_updated,
        "skipped_no_evidence": skipped_no_evidence,
    }
    logger.info("party_position_pipeline → %s", stats)
    return stats


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _extract_vote_ids(db: Session, policy_item: PolicyItem) -> list[uuid.UUID]:
    """
    Parse policy_item.source_refs_json to extract Vote UUIDs.
    Formats supported:
      [{"type": "vote", "id": "<uuid>"}]
      [{"type": "vote", "ids": ["<uuid>", ...]}]
    """
    ids: list[uuid.UUID] = []
    for ref in (policy_item.source_refs_json or []):
        if not isinstance(ref, dict):
            continue
        if ref.get("type") != "vote":
            continue
        if "id" in ref:
            try:
                ids.append(uuid.UUID(str(ref["id"])))
            except ValueError:
                pass
        for vid in ref.get("ids", []):
            try:
                ids.append(uuid.UUID(str(vid)))
            except ValueError:
                pass
    return ids


def _fetch_vote_titles(db: Session, vote_ids: list[uuid.UUID]) -> list[str]:
    """Return Hebrew/English titles for a list of vote IDs (for LLM context)."""
    votes = db.query(Vote).filter(Vote.id.in_(vote_ids)).all()
    return [v.title_en or v.title_he for v in votes]


def _parse_axis_pole(directional_axis: str | None, pole: str) -> str:
    """
    Extract the negative or positive pole description from a directional_axis string.
    Format: "axis_name: -1=description, +1=description"
    """
    if not directional_axis:
        return ""
    try:
        if pole == "neg" and "-1=" in directional_axis:
            part = directional_axis.split("-1=")[1]
            return part.split(",")[0].strip()
        if pole == "pos" and "+1=" in directional_axis:
            part = directional_axis.split("+1=")[1]
            return part.strip()
    except (IndexError, AttributeError):
        pass
    return ""


