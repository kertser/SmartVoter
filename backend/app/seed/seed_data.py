"""
Seed data loader — reads all mock data from backend/app/seed/data/*.json
so that text content (topics, parties, questions, etc.) can be edited
without touching Python code.

The exported names (TOPICS, POLITICAL_BRANDS, PARTY_POSITIONS_RAW, …)
are identical to what run_seed.py imports, so no other file needs to change.
"""
import json
import uuid
import datetime
import re
from pathlib import Path

# ─── helpers ────────────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).parent / "data"


def _load(filename: str):
    with open(_DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def _uuid(s: str | None) -> uuid.UUID | None:
    return uuid.UUID(s) if s else None


def _date(s: str | None) -> datetime.date | None:
    """Parse ISO date string or 'today±N' relative offset."""
    if s is None:
        return None
    m = re.fullmatch(r"today([+-]\d+)", s)
    if m:
        return datetime.date.today() + datetime.timedelta(days=int(m.group(1)))
    if s == "today":
        return datetime.date.today()
    return datetime.date.fromisoformat(s)


# ─── load and transform each file ────────────────────────────────────────────

# --- Topics ------------------------------------------------------------------
TOPICS: list[dict] = [
    {
        "id": _uuid(t["id"]),
        "slug": t["slug"],
        "name_en": t["name_en"],
        "name_he": t["name_he"],
        "name_ru": t["name_ru"],
        "description": t["description"],
    }
    for t in _load("topics.json")
]

# Build slug → UUID lookup (used by policy items)
_topic_slug_to_id: dict[str, uuid.UUID] = {t["slug"]: t["id"] for t in TOPICS}  # type: ignore[index]

# --- Political Brands --------------------------------------------------------
POLITICAL_BRANDS: list[dict] = [
    {
        "id": _uuid(b["id"]),
        "canonical_name": b["canonical_name"],
        "names_json": b["names_json"],
        "description": b["description"],
        "color_hex": b.get("color_hex"),
    }
    for b in _load("political_brands.json")
]

# canonical_name → UUID lookup (used by party instances)
_brand_name_to_id: dict[str, uuid.UUID] = {
    b["canonical_name"]: _uuid(b["id"])  # type: ignore[arg-type]
    for b in _load("political_brands.json")
}

# --- Party Instances ---------------------------------------------------------
PARTY_INSTANCES: list[dict] = [
    {
        "id": _uuid(p["id"]),
        "political_brand_id": _brand_name_to_id[p["brand_canonical_name"]],
        "official_name": p["official_name"],
        "election_cycle": p.get("election_cycle"),
        "knesset_number": p.get("knesset_number"),
        "start_date": _date(p.get("start_date")),
        "end_date": _date(p.get("end_date")),
        "status": p["status"],
        "left_right_score": p.get("left_right_score"),
    }
    for p in _load("party_instances.json")
    if not p.get("_comment", "").startswith("Dissolved predecessor for lineage")
    or True  # include all, lineage demo included
]

# official_name → UUID lookup (used by many other entities)
_party_name_to_id: dict[str, uuid.UUID] = {
    p["official_name"]: _uuid(p["id"])  # type: ignore[arg-type]
    for p in _load("party_instances.json")
}

# Stable UUID constants (imported by run_seed.py)
PARTY_LIKUD = _party_name_to_id["Likud"]
PARTY_LABOR = _party_name_to_id["HaAvoda"]
PARTY_UTJ = _party_name_to_id["Yahadut HaTorah"]
PARTY_YESH_ATID = _party_name_to_id["Yesh Atid"]
PARTY_NEW_HOPE = _party_name_to_id["Tikva Hadasha"]
PARTY_MAMLAKHTIT = _party_name_to_id.get("Mamlakhtit")
PARTY_SHAS = _party_name_to_id.get("Shas")
PARTY_HATZIONUT = _party_name_to_id.get("Hatzionut HaDatit")
PARTY_BEITEINU = _party_name_to_id.get("Yisrael Beiteinu")
PARTY_RAAM = _party_name_to_id.get("Raam")
PARTY_HADASH = _party_name_to_id.get("Hadash-Taal")
PARTY_MERETZ = _party_name_to_id.get("Meretz")

# --- Lineage Edges -----------------------------------------------------------
LINEAGE_EDGES: list[dict] = [
    {
        "from_party_instance_id": _party_name_to_id[e["from_party_official_name"]],
        "to_party_instance_id": _party_name_to_id[e["to_party_official_name"]],
        "relation_type": e["relation_type"],
        "continuity_weight": e["continuity_weight"],
        "llm_explanation": e.get("llm_explanation"),
        "human_review_status": e.get("human_review_status", "draft"),
    }
    for e in _load("lineage_edges.json")
]

# --- Persons -----------------------------------------------------------------
PERSONS: list[dict] = [
    {
        "id": _uuid(p["id"]),
        "name_en": p["name_en"],
        "name_he": p["name_he"],
        "birth_year": p.get("birth_year"),
    }
    for p in _load("persons.json")
]

# name_en → UUID lookup (used by memberships)
_person_name_to_id: dict[str, uuid.UUID] = {
    p["name_en"]: _uuid(p["id"])  # type: ignore[arg-type]
    for p in _load("persons.json")
}

# --- Memberships -------------------------------------------------------------
MEMBERSHIPS: list[dict] = [
    {
        "person_id": _person_name_to_id[m["person_name_en"]],
        "party_instance_id": _party_name_to_id[m["party_official_name"]],
        "role": m["role"],
        "start_date": _date(m.get("start_date")),
        "end_date": _date(m.get("end_date")),
    }
    for m in _load("memberships.json")
]

# --- Policy Items ------------------------------------------------------------
POLICY_ITEMS: list[dict] = [
    {
        "slug": item["slug"],
        "topic_id": _topic_slug_to_id[item["topic_slug"]],
        "title": item["title"],
        "description": item.get("description"),
        "directional_axis": item.get("directional_axis"),
        "source_type": item["source_type"],
    }
    for item in _load("policy_items.json")
]

# --- Party Positions ---------------------------------------------------------
# Output: {(party_uuid, policy_slug): (mean, uncertainty, strength, ev_type)}
PARTY_POSITIONS_RAW: dict[tuple[uuid.UUID, str], tuple[float, float, float, str]] = {}
for _block in _load("party_positions.json"):
    _party_id = _party_name_to_id[_block["party_official_name"]]
    for _slug, _vals in _block["positions"].items():
        PARTY_POSITIONS_RAW[(_party_id, _slug)] = (
            _vals[0],
            _vals[1],
            _vals[2],
            _vals[3],
        )

# --- Party Volatility --------------------------------------------------------
# Output: {party_uuid: float}
PARTY_VOLATILITY: dict[uuid.UUID, float] = {
    _party_name_to_id[name]: score
    for name, score in _load("party_volatility.json").items()
    if not name.startswith("_")
}

# --- Questions ---------------------------------------------------------------
# Output: list of (policy_slug, text_en, text_he, text_ru)
QUESTIONS_DATA: list[tuple[str, str, str, str]] = [
    (
        q["policy_slug"],
        q["question_text_en"],
        q["question_text_he"],
        q.get("question_text_ru", ""),
    )
    for q in _load("questions.json")
]

# ─── Phase 14B: Simulation data ──────────────────────────────────────────────

# --- Pollsters ---------------------------------------------------------------
POLLSTERS: list[dict] = [
    {
        "id": _uuid(p["id"]),
        "name": p["name"],
        "country": p["country"],
        "reliability_score": p["reliability_score"],
        "historical_bias_json": p["historical_bias_json"],
        "historical_error_std_json": p["historical_error_std_json"],
    }
    for p in _load("pollsters.json")
]

# pollster name → UUID lookup (used by polls)
_pollster_name_to_id: dict[str, uuid.UUID] = {
    p["name"]: _uuid(p["id"])  # type: ignore[arg-type]
    for p in _load("pollsters.json")
}

# --- Polls -------------------------------------------------------------------
POLLS: list[dict] = [
    {
        "id": _uuid(p["id"]),
        "pollster_id": _pollster_name_to_id[p["pollster_name"]],
        "field_end_date": _date(p["field_end_date"]),
        "sample_size": p["sample_size"],
        "quality_score": p["quality_score"],
        "results": [
            (r["party_official_name"], r["vote_share"])
            for r in p["results"]
        ],
    }
    for p in _load("polls.json")
]

# --- Historical Election -----------------------------------------------------
_he_raw = _load("historical_election.json")
HISTORICAL_ELECTION: dict = {
    "id": _uuid(_he_raw["id"]),
    "election_cycle": _he_raw["election_cycle"],
    "election_date": _date(_he_raw["election_date"]),
    "turnout": _he_raw["turnout"],
    "threshold_percent": _he_raw["threshold_percent"],
    "total_valid_votes": _he_raw["total_valid_votes"],
    "results": [
        (r["party_official_name"], r["vote_share"], r["seats"], r["passed_threshold"])
        for r in _he_raw["results"]
    ],
}

# --- Coalition Constraints ---------------------------------------------------
# Output: list of (src_name, tgt_name, type, strength, explanation) tuples
COALITION_CONSTRAINTS_RAW: list[tuple[str, str, str, str, str]] = [
    (
        c["source_party_official_name"],
        c["target_party_official_name"],
        c["constraint_type"],
        c["strength"],
        c["explanation"],
    )
    for c in _load("coalition_constraints.json")
]
