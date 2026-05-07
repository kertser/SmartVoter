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


def _get_polls_meta(db: Session) -> dict:
    """Return metadata about the polls currently in the DB (source, freshness)."""
    polls = db.query(Poll).order_by(Poll.field_end_date.desc()).all()
    if not polls:
        return {"count": 0, "latest_date": None, "source": "none"}

    # Detect whether ANY poll came from web_search (method column)
    sources = {p.method for p in polls if p.method}
    is_live = "web_search" in sources
    latest = polls[0].field_end_date

    return {
        "count": len(polls),
        "latest_date": latest.isoformat() if latest else None,
        "source": "live_web_search" if is_live else "seed_estimate",
        "source_label_he": "סקרים בזמן אמת (חיפוש ווב)" if is_live else "נתוני אמדן (seed)",
        "source_label_ru": "Живые данные (веб-поиск)" if is_live else "Расчётные данные (seed)",
    }


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


def _get_party_color_map(db: Session) -> dict[str, str]:
    """Return official_name → color_hex from political_brands join."""
    rows = (
        db.query(PartyInstance.official_name, PoliticalBrand.color_hex)
        .join(PoliticalBrand, PartyInstance.political_brand_id == PoliticalBrand.id)
        .all()
    )
    return {name: (color or "#94a3b8") for name, color in rows}


def _get_party_lr_map(db: Session) -> dict[str, float | None]:
    """Return official_name → left_right_score."""
    rows = db.query(PartyInstance.official_name, PartyInstance.left_right_score).all()
    return {name: lr for name, lr in rows}


def _get_party_he_name_map(db: Session) -> dict[str, str]:
    """Return official_name → Hebrew name (from political_brands.names_json['he'])."""
    rows = (
        db.query(PartyInstance.official_name, PoliticalBrand.names_json)
        .join(PoliticalBrand, PartyInstance.political_brand_id == PoliticalBrand.id)
        .all()
    )
    result: dict[str, str] = {}
    for official_name, names_json in rows:
        if names_json and names_json.get("he"):
            result[official_name] = names_json["he"]
    return result


def _run_and_persist(db: Session, n_iterations: int = 5000) -> SimulationRun:
    polls = _load_polls(db)
    if not polls:
        raise HTTPException(status_code=422, detail="No poll data available. Run --simulation-reset seed script first.")

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
        model_version="v1.2-bader-ofer",
        data_cutoff_date=date.today(),
        n_iterations=n_iterations,
        assumptions_json={
            "method": "Bader-Ofer (d'Hondt) — official Israeli seat allocation law (Elections Law §69a)",
            "threshold": "3.25%",
            "total_seats": 120,
            "surplus_agreements": "not modelled in MVP",
            "poll_weighting": "recency+sample+quality",
            "half_life_days": 14,
            "note": "נתוני סקרים הם אמדנים ידניים בהשראת מגמות 2025-2026 — לא נמשכו ממחברות סקרים ממשיות. לא תוצאות בחירות רשמיות.",
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


def _serialize_run(run: SimulationRun, color_map: dict[str, str] | None = None, lr_map: dict[str, float | None] | None = None, he_name_map: dict[str, str] | None = None) -> dict:
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
                "name_he": (he_name_map or {}).get(r.party_name),
                "party_instance_id": str(r.party_instance_id) if r.party_instance_id else None,
                "seats_mean": r.seats_mean,
                "seats_median": r.seats_median,
                "seats_p10": r.seats_p10,
                "seats_p25": r.seats_p25,
                "seats_p75": r.seats_p75,
                "seats_p90": r.seats_p90,
                "threshold_pass_probability": r.threshold_pass_probability,
                "vote_share_mean": r.vote_share_mean,
                "color_hex": (color_map or {}).get(r.party_name, "#94a3b8"),
                "left_right_score": (lr_map or {}).get(r.party_name),
            }
            for r in sorted(run.party_results, key=lambda x: -(x.seats_mean or 0))
        ],
        "coalitions": [
            {
                "scenario_id": str(sc.id),
                "scenario_name": " + ".join(
                    (he_name_map or {}).get(m.party_name, m.party_name)
                    for m in sc.members
                ),
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
                        "name_he": (he_name_map or {}).get(m.party_name),
                        "expected_seats": m.expected_seats,
                        "role": m.role,
                        "color_hex": (color_map or {}).get(m.party_name, "#94a3b8"),
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
    color_map = _get_party_color_map(db)
    lr_map = _get_party_lr_map(db)
    he_name_map = _get_party_he_name_map(db)
    polls_meta = _get_polls_meta(db)
    result = _serialize_run(run, color_map, lr_map, he_name_map)
    result["polls_meta"] = polls_meta
    return result


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
    color_map = _get_party_color_map(db)
    lr_map = _get_party_lr_map(db)
    he_name_map = _get_party_he_name_map(db)
    polls_meta = _get_polls_meta(db)
    result = _serialize_run(run, color_map, lr_map, he_name_map)
    result["polls_meta"] = polls_meta
    return result


@router.get("/knesset/current")
def get_current_knesset(db: Session = Depends(get_db)) -> dict:
    """
    Return the real 25th Knesset composition from historical election results,
    with parties sorted left-to-right by their political position score.
    """
    hist = (
        db.query(HistoricalElectionResult)
        .options(joinedload(HistoricalElectionResult.party_results))
        .filter(HistoricalElectionResult.election_cycle == "2022")
        .order_by(HistoricalElectionResult.election_date.desc())
        .first()
    )
    if not hist:
        raise HTTPException(status_code=404, detail="No 25th Knesset data found. Run seed script.")

    # Build enrichment maps
    party_map: dict[str, PartyInstance] = {
        p.official_name: p for p in db.query(PartyInstance).all()
    }
    brand_map: dict[uuid.UUID, PoliticalBrand] = {
        b.id: b for b in db.query(PoliticalBrand).all()
    }

    parties = []
    for pr in hist.party_results:
        if not pr.passed_threshold:
            continue
        pi = party_map.get(pr.reported_name)
        brand = brand_map.get(pi.political_brand_id) if pi else None
        lr = (pi.left_right_score if pi else None) or 0.0

        # Determine political bloc from LR score
        if lr >= 0.70:
            bloc = "far-right"
        elif lr >= 0.35:
            bloc = "right"
        elif lr >= 0.0:
            bloc = "center-right"
        elif lr >= -0.30:
            bloc = "center-left"
        elif lr >= -0.50:
            bloc = "left"
        else:
            bloc = "arab-left"

        parties.append({
            "official_name": pr.reported_name,
            "name_en": (brand.names_json or {}).get("en", pr.reported_name) if brand else pr.reported_name,
            "name_he": (brand.names_json or {}).get("he") if brand else None,
            "name_ru": (brand.names_json or {}).get("ru") if brand else None,
            "seats": pr.seats or 0,
            "vote_share": pr.vote_share,
            "left_right_score": lr,
            "political_bloc": bloc,
            "color_hex": brand.color_hex if brand else "#94a3b8",
            "party_instance_id": str(pi.id) if pi else None,
        })

    # Sort left (-1) to right (+1)
    parties.sort(key=lambda p: p["left_right_score"])

    total_seats = sum(p["seats"] for p in parties)
    return {
        "knesset_number": 25,
        "election_date": hist.election_date.isoformat(),
        "election_cycle": hist.election_cycle,
        "total_seats": total_seats,
        "threshold_percent": hist.threshold_percent,
        "parties": parties,
    }


@router.post("/coalition/evaluate")
def evaluate_coalition(
    party_names: list[str],
    use_forecast_seats: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    """
    Evaluate a user-assembled coalition.
    Returns seat count, majority status, score decomposition, and constraint violations.
    """
    # Get seat counts
    if use_forecast_seats:
        latest_run = (
            db.query(SimulationRun)
            .options(joinedload(SimulationRun.party_results))
            .order_by(SimulationRun.created_at.desc())
            .first()
        )
        seat_map: dict[str, float] = {}
        if latest_run:
            for pr in latest_run.party_results:
                seat_map[pr.party_name] = pr.seats_median or 0
    else:
        # Use actual 25th Knesset seats
        hist = (
            db.query(HistoricalElectionResult)
            .options(joinedload(HistoricalElectionResult.party_results))
            .filter(HistoricalElectionResult.election_cycle == "2022")
            .first()
        )
        seat_map = {}
        if hist:
            for pr in hist.party_results:
                seat_map[pr.reported_name] = pr.seats or 0

    # Get constraints
    constraints = _load_constraints(db)
    # Build constraint lookup: (source, target) → strength
    constraint_set: dict[tuple[str, str], str] = {
        (c["source"], c["target"]): c["strength"]
        for c in constraints
        if c["type"] == "refuses"
    }

    coalition_seats = sum(seat_map.get(p, 0) for p in party_names)
    has_majority = coalition_seats >= 61

    # Check constraint violations
    violations = []
    for i, a in enumerate(party_names):
        for b in party_names[i + 1:]:
            for s, t in [(a, b), (b, a)]:
                strength = constraint_set.get((s, t))
                if strength:
                    violations.append({
                        "source": s,
                        "target": t,
                        "strength": strength,
                        "description": f"{s} has declared {strength} refusal to sit with {t}",
                    })

    hard_violations = sum(1 for v in violations if v["strength"] == "hard")
    soft_violations = sum(1 for v in violations if v["strength"] == "soft")

    # Scores
    feasibility = max(0.0, 1.0 - hard_violations * 0.4 - soft_violations * 0.1)
    stability = min(1.0, max(0.0, (coalition_seats - 61) / 20.0)) if has_majority else 0.0

    # Ideological coherence: based on variance of LR scores
    lr_map = _get_party_lr_map(db)
    lr_scores = [lr_map.get(p) for p in party_names if lr_map.get(p) is not None]
    if lr_scores:
        mean_lr = sum(lr_scores) / len(lr_scores)
        variance = sum((x - mean_lr) ** 2 for x in lr_scores) / len(lr_scores)
        ideological_coherence = max(0.0, 1.0 - variance * 2)
    else:
        ideological_coherence = 0.5

    return {
        "party_names": party_names,
        "seats": coalition_seats,
        "has_majority": has_majority,
        "seat_breakdown": {p: seat_map.get(p, 0) for p in party_names},
        "feasibility_score": round(feasibility, 3),
        "stability_score": round(stability, 3),
        "ideological_coherence_score": round(ideological_coherence, 3),
        "constraint_violations": violations,
        "hard_violations": hard_violations,
        "soft_violations": soft_violations,
    }


@router.get("/polls/list")
def list_polls(db: Session = Depends(get_db)) -> list[dict]:
    """List all polls used for aggregation. Must be defined BEFORE /{run_id} to avoid route shadowing."""
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
    color_map = _get_party_color_map(db)
    lr_map = _get_party_lr_map(db)
    he_name_map = _get_party_he_name_map(db)
    return _serialize_run(run, color_map, lr_map, he_name_map)


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





