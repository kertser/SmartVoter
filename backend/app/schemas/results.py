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
    is_new_party: bool
    explanation: str
    top_agreements: list[str]
    top_disagreements: list[str]
    weak_evidence_topics: list[str]


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

