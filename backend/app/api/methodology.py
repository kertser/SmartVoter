from fastapi import APIRouter

router = APIRouter(tags=["methodology"])

METHODOLOGY = {
    "version": "0.1.0",
    "description": (
        "SmartVoter compares user policy preferences with Israeli political parties "
        "based on observable parliamentary behavior and declared positions."
    ),
    "scoring": {
        "match_score": {
            "formula": "sum(similarity * salience * evidence_strength) / sum(salience * evidence_strength)",
            "similarity": "1 - abs(user_position - party_position) / 2",
            "range": "0.0 to 1.0 (displayed as percentage)",
        },
        "confidence_score": {
            "formula": "avg_evidence_strength * coverage * (1 - volatility) * answer_stability",
            "range": "0.0 to 1.0",
        },
    },
    "evidence_priority": [
        {"type": "vote", "weight": 1.00, "description": "Actual parliamentary votes"},
        {"type": "sponsored_bill", "weight": 0.80, "description": "Sponsored or supported bills"},
        {"type": "committee_behavior", "weight": 0.70, "description": "Committee behavior"},
        {"type": "candidate_past_vote", "weight": 0.55, "description": "Historical votes of current candidates"},
        {"type": "party_lineage", "weight": 0.50, "description": "Predecessor party behavior"},
        {"type": "coalition_agreement", "weight": 0.45, "description": "Coalition agreements"},
        {"type": "party_platform", "weight": 0.35, "description": "Official party platform"},
        {"type": "public_statement", "weight": 0.25, "description": "Public statements"},
        {"type": "media_interview", "weight": 0.20, "description": "Media interviews"},
    ],
    "new_party_handling": {
        "description": "New parties with no voting history are scored using candidate history, lineage, and declared positions.",
        "evidence_threshold": 0.45,
        "warning": (
            "This party has limited parliamentary history. "
            "Its score is based mostly on candidate history, lineage, and declared positions. "
            "Treat the match score as less reliable."
        ),
    },
    "limitations": [
        "This tool does not tell you whom to vote for.",
        "Confidence is lower for new parties without parliamentary voting records.",
        "Party positions may change over time.",
        "Absence from votes is treated as low-information, not opposition.",
        "Phase 1 uses mock data; real Knesset data ingestion is planned for Phase 6.",
    ],
}


@router.get("/methodology")
def get_methodology() -> dict:
    """Returns full methodology explanation."""
    return METHODOLOGY

