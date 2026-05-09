from pydantic import BaseModel
import uuid


class PartyResult(BaseModel):
    party_id: uuid.UUID
    name: str  # canonical English name
    name_he: str | None = None
    name_ru: str | None = None
    match_score: float
    confidence: float
    evidence_strength: float
    volatility: float
    coverage: float
    answer_stability: float = 1.0
    is_new_party: bool
    explanation: str
    explanation_he: str | None = None
    explanation_ru: str | None = None
    top_agreements: list[str]
    top_agreements_he: list[str] = []
    top_agreements_ru: list[str] = []
    top_disagreements: list[str]
    top_disagreements_he: list[str] = []
    top_disagreements_ru: list[str] = []
    weak_evidence_topics: list[str]
    # Per-topic similarity breakdown (topic_name_en → 0..1 similarity)
    topic_scores: dict[str, float] = {}
    # Evidence source composition (evidence_type → proportion 0..1)
    evidence_by_type: dict[str, float] = {}
    # Sectoral / agenda breadth signals
    agenda_breadth: float = 1.0          # 0..1 fraction of all system topics covered
    is_sectoral: bool = False            # True when agenda_breadth < SECTORAL_THRESHOLD
    high_salience_coverage: float = 1.0  # fraction of user's very-important topics covered
    # Confidence score decomposition (for UI display)
    confidence_breakdown: dict[str, float] = {}


class BestPartyByTopic(BaseModel):
    topic: str           # English topic name (canonical key)
    topic_he: str | None = None
    topic_ru: str | None = None
    party: str           # English canonical party name
    party_he: str | None = None


class DiscoveryMatch(BaseModel):
    """
    A topic where an outsider party aligns significantly better with the user
    than all top-3 parties.  Shown as "unexpected match" on the results page.
    """
    topic: str                    # English topic name
    topic_he: str | None = None
    topic_ru: str | None = None
    party: str                    # English party name
    party_he: str | None = None
    party_ru: str | None = None
    party_id: uuid.UUID
    similarity: float             # 0..1 similarity for this party on this topic
    top3_best_similarity: float   # best similarity among top-3 parties on same topic


class RepresentationGap(BaseModel):
    has_gap: bool
    explanation: str
    explanation_he: str | None = None
    explanation_ru: str | None = None
    best_party_by_topic: list[BestPartyByTopic]


class ResultsOut(BaseModel):
    session_id: uuid.UUID
    run_id: uuid.UUID
    parties: list[PartyResult]
    representation_gap: RepresentationGap
    # Unexpected / niche topic matches from outside the top-3 parties
    discovery_matches: list[DiscoveryMatch] = []

