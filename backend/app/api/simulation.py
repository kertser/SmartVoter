"""
Simulation API — Phase 14B.
Per AGENTS.MD Sections 14B.13 and 14B.14.

All outputs are probabilistic scenarios. Never present as predictions.
Outputs are visually and semantically separated from personal matching results.
"""

import uuid
import hashlib
import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from backend.app.db import get_db
from backend.app.models.simulation import (
    Pollster, Poll, PollPartyResult,
    HistoricalElectionResult, HistoricalPartyResult,
    SimulationRun, SimulationPartyResult,
    CoalitionConstraint, CoalitionScenario, CoalitionScenarioMember,
)
from backend.app.models.party_instance import PartyInstance
from backend.app.models.political_brand import PoliticalBrand
from backend.app.services.simulation import (
    PollAggregator, KnessetSimulator, CoalitionSimulator,
)

router = APIRouter(prefix="/simulation", tags=["simulation"])

VOLATILITY_MAP: dict[str, float] = {}  # populated from DB by party_name


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_polls(db: Session) -> list[dict]:
    polls = db.query(Poll).options(joinedload(Poll.party_results)).all()
    result = []
    for poll in polls:
        result.append({
            "field_end_date": poll.field_end_date,
            "sample_size": poll.sample_size or 500,
            "quality_score": poll.quality_score or 0.7,
            "party_results": [
                {"reported_name": pr.reported_name, "vote_share_mean": pr.vote_share_mean or 0.0}
                for pr in poll.party_results
            ],
        })
    return result


def _load_constraints(db: Session) -> list[dict]:
    rows = db.query(CoalitionConstraint).all()
    # Map party_instance_id → official_name
    party_map: dict[str, str] = {
        str(p.id): p.official_name
        for p in db.query(PartyInstance).all()
    }
    constraints = []
    for row in rows:
        src = party_map.get(str(row.source_party_instance_id), "unknown")
        tgt = party_map.get(str(row.target_party_instance_id), "") if row.target_party_instance_id else ""
        constraints.append({
            "source": src,
            "target": tgt,
            "type": row.constraint_type,
            "strength": row.strength,
        })
    return constraints


def _snapshot_hash(polls: list[dict]) -> str:
    raw = json.dumps(
        [{"name": pr["reported_name"], "share": pr["vote_share_mean"]}
         for poll in polls for pr in poll["party_results"]],
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _run_and_persist(db: Session, n_iterations: int = 5000) -> SimulationRun:
    polls = _load_polls(db)
    if not polls:
        raise HTTPException(status_code=422, detail="No poll data available. Seed mock data first.")

    aggregator = PollAggregator()
    aggregate = aggregator.aggregate(polls)

    simulator = KnessetSimulator(n_iterations=n_iterations)
    party_results = simulator.run(aggregate)

    constraints = _load_constraints(db)
    coalition_sim = CoalitionSimulator(constraints)
    seat_means = {p: r["seats_mean"] for p, r in party_results.items()}
    scenarios = coalition_sim.generate_viable_coalitions(seat_means)

    # Map party names to party_instance_ids
    party_instance_map: dict[str, str] = {
        p.official_name: str(p.id)
        for p in db.query(PartyInstance).all()
    }

    run = SimulationRun(
        model_version="v1.1-bader-ofer",
        data_cutoff_date=date.today(),
        n_iterations=n_iterations,
        assumptions_json={
            "method": "Bader-Ofer (d'Hondt) — official Israeli seat allocation law (Elections Law §69a)",
            "threshold": "3.25%",
            "total_seats": 120,
            "surplus_agreements": "not modelled in MVP",
            "poll_weighting": "recency+sample+quality",
            "half_life_days": 14,
            "note": "Mock polling data — not real Knesset polling.",
        },
        input_snapshot_hash=_snapshot_hash(polls),
    )
    db.add(run)
    db.flush()

    # Persist party results
    for name, r in party_results.items():
        pid = party_instance_map.get(name)
        spr = SimulationPartyResult(
            simulation_run_id=run.id,
            party_instance_id=uuid.UUID(pid) if pid else None,
            party_name=name,
            seats_mean=r["seats_mean"],
            seats_median=r["seats_median"],
            seats_p10=r["seats_p10"],
            seats_p25=r["seats_p25"],
            seats_p75=r["seats_p75"],
            seats_p90=r["seats_p90"],
            threshold_pass_probability=r["threshold_pass_probability"],
            vote_share_mean=r["vote_share_mean"],
        )
        db.add(spr)

    # Persist coalition scenarios
    for sc in scenarios:
        scenario = CoalitionScenario(
            simulation_run_id=run.id,
            scenario_name=" + ".join(sc["members"]),
            probability_estimate=sc["probability_estimate"],
            seat_mean=sc["seat_mean"],
            seat_p10=sc["seat_p10"],
            seat_p90=sc["seat_p90"],
            feasibility_score=sc["feasibility_score"],
            stability_score=sc["stability_score"],
            ideological_coherence_score=sc["ideological_coherence_score"],
            explanation=sc["explanation"],
        )
        db.add(scenario)
        db.flush()

        for party_name in sc["members"]:
            member_seats = seat_means.get(party_name, 0)
            pid = party_instance_map.get(party_name)
            db.add(CoalitionScenarioMember(
                scenario_id=scenario.id,
                party_instance_id=uuid.UUID(pid) if pid else None,
                party_name=party_name,
                expected_seats=member_seats,
            ))

    db.commit()
    db.refresh(run)
    return run


def _serialize_run(run: SimulationRun) -> dict:
    return {
        "run_id": str(run.id),
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "model_version": run.model_version,
        "data_cutoff_date": run.data_cutoff_date.isoformat() if run.data_cutoff_date else None,
        "n_iterations": run.n_iterations,
        "assumptions": run.assumptions_json,
        "parties": [
            {
                "party_name": r.party_name,
                "party_instance_id": str(r.party_instance_id) if r.party_instance_id else None,
                "seats_mean": r.seats_mean,
                "seats_median": r.seats_median,
                "seats_p10": r.seats_p10,
                "seats_p25": r.seats_p25,
                "seats_p75": r.seats_p75,
                "seats_p90": r.seats_p90,
                "threshold_pass_probability": r.threshold_pass_probability,
                "vote_share_mean": r.vote_share_mean,
            }
            for r in sorted(run.party_results, key=lambda x: -(x.seats_mean or 0))
        ],
        "coalitions": [
            {
                "scenario_id": str(sc.id),
                "scenario_name": sc.scenario_name,
                "probability_estimate": sc.probability_estimate,
                "seat_mean": sc.seat_mean,
                "seat_p10": sc.seat_p10,
                "seat_p90": sc.seat_p90,
                "feasibility_score": sc.feasibility_score,
                "stability_score": sc.stability_score,
                "ideological_coherence_score": sc.ideological_coherence_score,
                "explanation": sc.explanation,
                "members": [
                    {
                        "party_name": m.party_name,
                        "expected_seats": m.expected_seats,
                        "role": m.role,
                    }
                    for m in sc.members
                ],
            }
            for sc in sorted(run.coalition_scenarios, key=lambda x: -(x.probability_estimate or 0))
        ],
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/latest")
def get_latest_simulation(db: Session = Depends(get_db)) -> dict:
    """
    Return the most recent simulation run, or trigger a new one if none exists.
    Per AGENTS.MD Section 14B.13.
    """
    run = (
        db.query(SimulationRun)
        .options(
            joinedload(SimulationRun.party_results),
            joinedload(SimulationRun.coalition_scenarios).joinedload(CoalitionScenario.members),
        )
        .order_by(SimulationRun.created_at.desc())
        .first()
    )
    if run is None:
        run = _run_and_persist(db)
        run = (
            db.query(SimulationRun)
            .options(
                joinedload(SimulationRun.party_results),
                joinedload(SimulationRun.coalition_scenarios).joinedload(CoalitionScenario.members),
            )
            .filter(SimulationRun.id == run.id)
            .first()
        )
    return _serialize_run(run)


@router.post("/run")
def trigger_simulation(
    n_iterations: int = 5000, db: Session = Depends(get_db)
) -> dict:
    """Trigger a fresh simulation run."""
    run = _run_and_persist(db, n_iterations=min(n_iterations, 20000))
    run = (
        db.query(SimulationRun)
        .options(
            joinedload(SimulationRun.party_results),
            joinedload(SimulationRun.coalition_scenarios).joinedload(CoalitionScenario.members),
        )
        .filter(SimulationRun.id == run.id)
        .first()
    )
    return _serialize_run(run)


@router.get("/{run_id}")
def get_simulation_run(run_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        rid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id")
    run = (
        db.query(SimulationRun)
        .options(
            joinedload(SimulationRun.party_results),
            joinedload(SimulationRun.coalition_scenarios).joinedload(CoalitionScenario.members),
        )
        .filter(SimulationRun.id == rid)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    return _serialize_run(run)


@router.get("/{run_id}/coalitions")
def get_coalition_scenarios(run_id: str, db: Session = Depends(get_db)) -> list[dict]:
    try:
        rid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id")
    scenarios = (
        db.query(CoalitionScenario)
        .options(joinedload(CoalitionScenario.members))
        .filter(CoalitionScenario.simulation_run_id == rid)
        .order_by(CoalitionScenario.probability_estimate.desc())
        .all()
    )
    return [
        {
            "scenario_name": sc.scenario_name,
            "probability_estimate": sc.probability_estimate,
            "seat_mean": sc.seat_mean,
            "feasibility_score": sc.feasibility_score,
            "stability_score": sc.stability_score,
            "explanation": sc.explanation,
            "members": [{"party_name": m.party_name, "expected_seats": m.expected_seats} for m in sc.members],
        }
        for sc in scenarios
    ]


@router.get("/polls/list")
def list_polls(db: Session = Depends(get_db)) -> list[dict]:
    """List all polls used for aggregation."""
    polls = db.query(Poll).options(joinedload(Poll.pollster), joinedload(Poll.party_results)).all()
    return [
        {
            "pollster": p.pollster.name if p.pollster else "unknown",
            "field_end_date": p.field_end_date.isoformat(),
            "sample_size": p.sample_size,
            "quality_score": p.quality_score,
            "parties": [
                {"name": pr.reported_name, "vote_share": pr.vote_share_mean}
                for pr in p.party_results
            ],
        }
        for p in polls
    ]

