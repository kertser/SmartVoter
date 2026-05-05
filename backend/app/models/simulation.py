"""
Simulation models — Phase 14B.
Polls, simulation runs, party seat results, coalition scenarios.
Per AGENTS.MD Sections 14B.3 and 14B.13.
"""

import uuid
from datetime import datetime, timezone, date

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


# ── Pollsters ──────────────────────────────────────────────────────────────────

class Pollster(Base):
    __tablename__ = "pollsters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    country = Column(String(10), default="IL")
    historical_bias_json = Column(JSON, default=dict, nullable=False)
    historical_error_std_json = Column(JSON, default=dict, nullable=False)
    reliability_score = Column(Float, default=0.7)
    source_url = Column(Text, nullable=True)

    polls = relationship("Poll", back_populates="pollster", cascade="all, delete-orphan")


class Poll(Base):
    __tablename__ = "polls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pollster_id = Column(UUID(as_uuid=True), ForeignKey("pollsters.id"), nullable=False)
    field_start_date = Column(Date, nullable=True)
    field_end_date = Column(Date, nullable=False)
    publication_date = Column(Date, nullable=True)
    sample_size = Column(Integer, nullable=True)
    population = Column(String(200), default="Israeli eligible voters")
    method = Column(String(100), default="telephone/online")
    source_url = Column(Text, nullable=True)
    raw_json = Column(JSON, default=dict, nullable=False)
    quality_score = Column(Float, default=0.7)

    pollster = relationship("Pollster", back_populates="polls")
    party_results = relationship("PollPartyResult", back_populates="poll", cascade="all, delete-orphan")


class PollPartyResult(Base):
    __tablename__ = "poll_party_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    poll_id = Column(UUID(as_uuid=True), ForeignKey("polls.id"), nullable=False)
    party_instance_id = Column(UUID(as_uuid=True), ForeignKey("party_instances.id"), nullable=True)
    reported_name = Column(String(200), nullable=False)
    seats_mean = Column(Float, nullable=True)
    vote_share_mean = Column(Float, nullable=True)   # 0.0..1.0
    lower_bound = Column(Float, nullable=True)
    upper_bound = Column(Float, nullable=True)
    undecided_handling_notes = Column(Text, nullable=True)

    poll = relationship("Poll", back_populates="party_results")


# ── Historical elections ───────────────────────────────────────────────────────

class HistoricalElectionResult(Base):
    __tablename__ = "historical_election_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    election_cycle = Column(String(20), nullable=False)
    election_date = Column(Date, nullable=False)
    turnout = Column(Float, nullable=True)
    threshold_percent = Column(Float, default=3.25)
    total_valid_votes = Column(Integer, nullable=True)
    source_url = Column(Text, nullable=True)

    party_results = relationship("HistoricalPartyResult", back_populates="election", cascade="all, delete-orphan")


class HistoricalPartyResult(Base):
    __tablename__ = "historical_party_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    historical_election_result_id = Column(UUID(as_uuid=True), ForeignKey("historical_election_results.id"), nullable=False)
    party_instance_id = Column(UUID(as_uuid=True), ForeignKey("party_instances.id"), nullable=True)
    reported_name = Column(String(200), nullable=False)
    vote_share = Column(Float, nullable=True)
    votes = Column(Integer, nullable=True)
    seats = Column(Integer, nullable=True)
    passed_threshold = Column(Boolean, default=True)

    election = relationship("HistoricalElectionResult", back_populates="party_results")


# ── Simulation runs and results ────────────────────────────────────────────────

class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    model_version = Column(String(50), default="v1.0-mock")
    data_cutoff_date = Column(Date, nullable=True)
    n_iterations = Column(Integer, default=5000)
    assumptions_json = Column(JSON, default=dict, nullable=False)
    input_snapshot_hash = Column(String(64), nullable=True)

    party_results = relationship("SimulationPartyResult", back_populates="run", cascade="all, delete-orphan")
    coalition_scenarios = relationship("CoalitionScenario", back_populates="run", cascade="all, delete-orphan")


class SimulationPartyResult(Base):
    __tablename__ = "simulation_party_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    simulation_run_id = Column(UUID(as_uuid=True), ForeignKey("simulation_runs.id"), nullable=False)
    party_instance_id = Column(UUID(as_uuid=True), ForeignKey("party_instances.id"), nullable=True)
    party_name = Column(String(200), nullable=False)
    seats_mean = Column(Float, nullable=True)
    seats_median = Column(Float, nullable=True)
    seats_p10 = Column(Float, nullable=True)
    seats_p25 = Column(Float, nullable=True)
    seats_p75 = Column(Float, nullable=True)
    seats_p90 = Column(Float, nullable=True)
    threshold_pass_probability = Column(Float, nullable=True)
    vote_share_mean = Column(Float, nullable=True)
    volatility_score = Column(Float, default=0.0)
    is_new_party = Column(Boolean, default=False)

    run = relationship("SimulationRun", back_populates="party_results")


# ── Coalition constraints and scenarios ────────────────────────────────────────

class CoalitionConstraint(Base):
    __tablename__ = "coalition_constraints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_party_instance_id = Column(UUID(as_uuid=True), ForeignKey("party_instances.id"), nullable=False)
    target_party_instance_id = Column(UUID(as_uuid=True), ForeignKey("party_instances.id"), nullable=True)
    target_bloc = Column(String(100), nullable=True)
    # refuses | prefers | requires | impossible | uncertain
    constraint_type = Column(String(50), nullable=False)
    strength = Column(String(10), default="soft")   # hard | soft
    confidence = Column(Float, default=0.8)
    source_refs_json = Column(JSON, default=list, nullable=False)
    llm_explanation = Column(Text, nullable=True)
    human_review_status = Column(String(20), default="approved")


class CoalitionScenario(Base):
    __tablename__ = "coalition_scenarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    simulation_run_id = Column(UUID(as_uuid=True), ForeignKey("simulation_runs.id"), nullable=False)
    scenario_name = Column(String(200), nullable=False)
    probability_estimate = Column(Float, nullable=True)
    seat_mean = Column(Float, nullable=True)
    seat_p10 = Column(Float, nullable=True)
    seat_p90 = Column(Float, nullable=True)
    feasibility_score = Column(Float, nullable=True)
    stability_score = Column(Float, nullable=True)
    ideological_coherence_score = Column(Float, nullable=True)
    explanation = Column(Text, nullable=True)

    run = relationship("SimulationRun", back_populates="coalition_scenarios")
    members = relationship("CoalitionScenarioMember", back_populates="scenario", cascade="all, delete-orphan")


class CoalitionScenarioMember(Base):
    __tablename__ = "coalition_scenario_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario_id = Column(UUID(as_uuid=True), ForeignKey("coalition_scenarios.id"), nullable=False)
    party_instance_id = Column(UUID(as_uuid=True), ForeignKey("party_instances.id"), nullable=True)
    party_name = Column(String(200), nullable=False)
    expected_seats = Column(Float, nullable=True)
    # lead | member | kingmaker
    role = Column(String(50), default="member")

    scenario = relationship("CoalitionScenario", back_populates="members")

