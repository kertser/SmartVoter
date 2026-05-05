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


class BestPartyByTopic(BaseModel):
    topic: str
    party: str


class RepresentationGap(BaseModel):
    has_gap: bool
    explanation: str
    best_party_by_topic: list[BestPartyByTopic]


class ResultsOut(BaseModel):
    session_id: uuid.UUID
    run_id: uuid.UUID
    parties: list[PartyResult]
    representation_gap: RepresentationGap

