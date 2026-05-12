"""
Party Deduplication Service
===========================

Automatically detects and merges duplicate PartyInstance rows that represent
the same real-world party imported under different names (e.g. Hebrew names
from Knesset OData vs English names from seed data).

Called automatically after every faction import and on startup.
Can also be triggered manually via the admin API.

Detection strategy (in priority order):
  1. LLM-based  — if OpenAI key is configured (most accurate)
  2. Rule-based  — token-overlap heuristic (always available as fallback)

Merge strategy:
  - All FK references are re-pointed to the canonical (kept) party.
  - Orphaned PoliticalBrand rows are deleted.
  - A dedup log entry is created so changes are auditable.

Per AGENTS.MD: party identity is modelled via political_brands + party_instances.
A canonical entry is preferred over raw imports when both exist.
"""

import json
import logging
import re
import unicodedata
import uuid
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ── Canonicalisation preference ───────────────────────────────────────────────
# Seed/English entries are generally preferred as canonical because they have
# richer metadata (colors, positions, questions, etc.).
# Heuristic: prefer entries whose official_name is all-ASCII (English) over
# entries whose official_name contains Hebrew/Arabic script.

def _is_latin(s: str) -> bool:
    return all(ord(c) < 0x0590 for c in s if c.strip())


def _canonical_preference(a: dict, b: dict) -> dict:
    """Return whichever of a/b is the better canonical (more data, Latin preferred)."""
    score_a = (
        int(_is_latin(a["name"])) * 10
        + a.get("positions", 0)
        + a.get("vote_results", 0) * 2
        + a.get("poll_results", 0)
    )
    score_b = (
        int(_is_latin(b["name"])) * 10
        + b.get("positions", 0)
        + b.get("vote_results", 0) * 2
        + b.get("poll_results", 0)
    )
    return a if score_a >= score_b else b


# ── Rule-based detection ──────────────────────────────────────────────────────

def _normalise(s: str) -> str:
    s = unicodedata.normalize("NFC", s.lower().strip())
    for ch in "-–—()[]״'\"/,.״":
        s = s.replace(ch, " ")
    # Strip common prefixes: ה, ו, מ, ל, כ, ב in Hebrew
    tokens = []
    for tok in s.split():
        if len(tok) > 2 and tok[0] in "הומלכב":
            tokens.append(tok[1:])
        tokens.append(tok)
    return " ".join(dict.fromkeys(tokens))  # dedupe while preserving order


_KNOWN_EQUIVALENTS: list[tuple[str, str]] = [
    # (substring_a, substring_b) — if both appear in a pair's names → likely same party
    ("מחנה ממלכתי", "mamlakhtit"),
    ("מחנה ממלכתי", "national unity"),
    ("כחול לבן", "kahol lavan"),
    ("כחול לבן", "blue and white"),
    ("יש עתיד", "yesh atid"),
    ("הליכוד", "likud"),
    ("ש\"ס", "shas"),
    ("יהדות התורה", "yahadut hatorah"),
    ("יהדות התורה", "united torah"),
    ("ישראל ביתנו", "yisrael beiteinu"),
    ("עוצמה יהודית", "otzma yehudit"),
    ("ציונות הדתית", "hatzionut hadatit"),
    ("ציונות הדתית", "religious zionism"),
    ("הדמוקרטים", "hademokratim"),
    ("הדמוקרטים", "the democrats"),
    ('רע"מ', "raam"),
    ('חד"ש', "hadash"),
    ("מרצ", "meretz"),
    ("העבודה", "haavoda"),
    ("העבודה", "labor"),
    ("תקווה חדשה", "new hope"),
    ("תקווה חדשה", "tikva hadasha"),
    ("ביחד", "yachad"),
    ("מחנה", "mamlakhtit"),
]


def _known_equivalent(a: str, b: str) -> bool:
    an, bn = a.lower(), b.lower()
    for x, y in _KNOWN_EQUIVALENTS:
        if (x in an and y in bn) or (y in an and x in bn):
            return True
    return False


def _token_overlap(a: str, b: str) -> float:
    na, nb = _normalise(a), _normalise(b)
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def rule_based_groups(parties: list[dict]) -> list[dict]:
    """Return duplicate groups detected by rule-based heuristics."""
    groups: list[dict] = []
    used: set[str] = set()

    for i, a in enumerate(parties):
        if a["id"] in used:
            continue
        dupes = []
        for j, b in enumerate(parties):
            if i == j or b["id"] in used:
                continue
            if _known_equivalent(a["name"], b["name"]):
                dupes.append(b)
            elif _token_overlap(a["name"], b["name"]) >= 0.55:
                dupes.append(b)

        if dupes:
            all_entries = [a] + dupes
            used.update(p["id"] for p in all_entries)
            canonical = _canonical_preference(
                all_entries[0],
                all_entries[1] if len(all_entries) > 1 else all_entries[0],
            )
            for other in all_entries[2:]:
                canonical = _canonical_preference(canonical, other)
            rest = [p for p in all_entries if p["id"] != canonical["id"]]
            groups.append({
                "canonical_id": canonical["id"],
                "canonical_name": canonical["name"],
                "duplicate_ids": [p["id"] for p in rest],
                "duplicate_names": [p["name"] for p in rest],
                "reason": "Rule-based: name equivalence / token overlap",
                "source": "rule_based",
            })

    return groups


# ── LLM-based detection ───────────────────────────────────────────────────────

def llm_based_groups(parties: list[dict], api_key: str, model: str) -> list[dict]:
    """Use LLM to detect duplicate party instances. Returns groups."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        prompt = (
            "You are a political data analyst specialising in Israeli politics.\n"
            "Below is a list of party instances. Some are the SAME party imported "
            "under different names (Hebrew vs English, with/without knesset suffix, "
            "old branding vs new, etc.).\n\n"
            "Party list:\n"
            f"{json.dumps(parties, ensure_ascii=False, indent=2)}\n\n"
            "Find groups of entries that represent the SAME party. "
            "For each group pick the best canonical entry "
            "(prefer English names with more data: positions > 0).\n\n"
            "Return ONLY valid JSON — no markdown:\n"
            "{\n"
            '  "duplicate_groups": [\n'
            "    {\n"
            '      "canonical_id": "<id>",\n'
            '      "canonical_name": "<name>",\n'
            '      "duplicate_ids": ["<id>", ...],\n'
            '      "duplicate_names": ["<name>", ...],\n'
            '      "reason": "<short explanation>"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Only include groups you are CONFIDENT about. "
            'If none found return {"duplicate_groups": []}.'
        )

        resp = client.responses.create(model=model, input=prompt)
        raw = (getattr(resp, "output_text", "") or "").strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE).strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return []
        data = json.loads(match.group())
        groups = data.get("duplicate_groups", [])
        for g in groups:
            g["source"] = "llm"
        logger.info("party_dedup: LLM found %d duplicate groups", len(groups))
        return groups
    except Exception as exc:
        logger.warning("party_dedup: LLM detection failed (%s), falling back to rule-based", exc)
        return []


# ── Merge execution ───────────────────────────────────────────────────────────

def execute_merge(canonical_id: str, duplicate_ids: list[str], db: Session) -> dict:
    """
    Re-point all FK references from duplicate party instances to canonical,
    delete duplicates, clean up orphaned brands.
    Returns a summary dict.
    """
    from backend.app.models.party_instance import PartyInstance
    from backend.app.models.political_brand import PoliticalBrand
    from backend.app.models.party_position import PartyPosition
    from backend.app.models.vote_result import VoteResult
    from backend.app.models.person_party_membership import PersonPartyMembership
    from backend.app.models.party_lineage_edge import PartyLineageEdge
    from backend.app.models.simulation import PollPartyResult, SimulationPartyResult, CoalitionConstraint, CoalitionScenarioMember
    from backend.app.models.party_poll_alias import PartyPollAlias
    from sqlalchemy import func as sqlfunc

    # Validate UUIDs before doing anything — LLM may return truncated/invalid IDs
    try:
        canonical_uuid = uuid.UUID(str(canonical_id).strip())
    except (ValueError, AttributeError):
        return {"ok": False, "error": f"Invalid canonical UUID: {canonical_id!r}"}

    valid_dup_uuids: list[uuid.UUID] = []
    for d in duplicate_ids:
        try:
            valid_dup_uuids.append(uuid.UUID(str(d).strip()))
        except (ValueError, AttributeError):
            logger.warning("execute_merge: skipping invalid duplicate UUID %r", d)

    if not valid_dup_uuids:
        return {"ok": False, "error": "No valid duplicate UUIDs to merge"}

    canonical = db.query(PartyInstance).filter(PartyInstance.id == canonical_uuid).first()
    if not canonical:
        return {"ok": False, "error": f"Canonical {canonical_id} not found"}

    # ── Safety check: ensure the canonical is truly the better entry ──────────
    # If any "duplicate" has more attached data (positions, lineage, memberships)
    # than the supposed canonical, swap them so the richer entry is always kept.
    def _data_score(pi_id: uuid.UUID) -> int:
        positions = db.query(sqlfunc.count(PartyPosition.id)).filter(
            PartyPosition.party_instance_id == pi_id).scalar() or 0
        lineage = db.query(sqlfunc.count(PartyLineageEdge.id)).filter(
            (PartyLineageEdge.from_party_instance_id == pi_id) |
            (PartyLineageEdge.to_party_instance_id == pi_id)).scalar() or 0
        memberships = db.query(sqlfunc.count(PersonPartyMembership.id)).filter(
            PersonPartyMembership.party_instance_id == pi_id).scalar() or 0
        latin_bonus = 10 if _is_latin(
            (db.query(PartyInstance).filter(PartyInstance.id == pi_id).first() or canonical).official_name
        ) else 0
        return positions * 3 + lineage * 2 + memberships + latin_bonus

    canonical_score = _data_score(canonical_uuid)
    for dup_uuid in valid_dup_uuids:
        dup_score = _data_score(dup_uuid)
        if dup_score > canonical_score:
            # Swap: the "duplicate" is actually richer — it becomes the canonical
            logger.info(
                "execute_merge: swapping canonical %s (score=%d) ↔ duplicate %s (score=%d)",
                canonical_uuid, canonical_score, dup_uuid, dup_score,
            )
            valid_dup_uuids = [canonical_uuid] + [u for u in valid_dup_uuids if u != dup_uuid]
            canonical_uuid = dup_uuid
            canonical = db.query(PartyInstance).filter(PartyInstance.id == canonical_uuid).first()
            canonical_score = dup_score
            break

    # ── Re-point all FK references, flushing after each duplicate ────────────
    merged_names: list[str] = []
    brands_to_check: list[uuid.UUID] = []

    for dup_uuid in valid_dup_uuids:
        dup = db.query(PartyInstance).filter(PartyInstance.id == dup_uuid).first()
        if not dup:
            logger.warning("execute_merge: duplicate %s not found (already merged?), skipping", dup_uuid)
            continue
        merged_names.append(dup.official_name)
        brands_to_check.append(dup.political_brand_id)

        # Re-point all FKs
        for model_cls, col in [
            (PartyPosition, "party_instance_id"),
            (PersonPartyMembership, "party_instance_id"),
            (PollPartyResult, "party_instance_id"),
            (SimulationPartyResult, "party_instance_id"),
            (PartyPollAlias, "party_instance_id"),
            (CoalitionConstraint, "source_party_instance_id"),
            (CoalitionConstraint, "target_party_instance_id"),
        ]:
            db.query(model_cls).filter(
                getattr(model_cls, col) == dup_uuid
            ).update({col: canonical_uuid}, synchronize_session=False)

        db.query(VoteResult).filter(
            VoteResult.party_instance_id_at_time == dup_uuid
        ).update({"party_instance_id_at_time": canonical_uuid}, synchronize_session=False)

        db.query(PartyLineageEdge).filter(
            PartyLineageEdge.from_party_instance_id == dup_uuid
        ).update({"from_party_instance_id": canonical_uuid}, synchronize_session=False)

        db.query(PartyLineageEdge).filter(
            PartyLineageEdge.to_party_instance_id == dup_uuid
        ).update({"to_party_instance_id": canonical_uuid}, synchronize_session=False)

        # Flush UPDATEs before DELETE — required to avoid FK violation
        db.flush()
        db.delete(dup)
        db.flush()

    # Remove orphaned political brands
    for brand_id in set(brands_to_check):
        if brand_id == canonical.political_brand_id:
            continue
        remaining = db.query(PartyInstance).filter(
            PartyInstance.political_brand_id == brand_id
        ).count()
        if remaining == 0:
            brand = db.query(PoliticalBrand).filter(PoliticalBrand.id == brand_id).first()
            if brand:
                db.delete(brand)
    db.flush()

    return {
        "ok": True,
        "canonical_id": str(canonical_uuid),
        "canonical_name": canonical.official_name,
        "merged": merged_names,
    }


# ── Main entry point ──────────────────────────────────────────────────────────

def auto_deduplicate_parties(
    db: Session,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
) -> dict:
    """
    Detect and merge duplicate party instances automatically.

    Called after every faction import and on startup.
    Uses LLM if api_key is provided, otherwise rule-based heuristics.

    Returns a summary: {merged_count, groups, skipped, source}.
    """
    from backend.app.models.party_instance import PartyInstance
    from backend.app.models.party_position import PartyPosition
    from backend.app.models.vote_result import VoteResult
    from backend.app.models.simulation import PollPartyResult
    from sqlalchemy import func as sqlfunc

    # Build party list with data counts (used for canonical selection)
    rows = db.query(PartyInstance).all()
    parties = []
    for pi in rows:
        positions = db.query(sqlfunc.count(PartyPosition.id)).filter(
            PartyPosition.party_instance_id == pi.id).scalar() or 0
        vote_results = db.query(sqlfunc.count(VoteResult.id)).filter(
            VoteResult.party_instance_id_at_time == pi.id).scalar() or 0
        poll_results = db.query(sqlfunc.count(PollPartyResult.id)).filter(
            PollPartyResult.party_instance_id == pi.id).scalar() or 0
        parties.append({
            "id": str(pi.id),
            "name": pi.official_name,
            "knesset": pi.knesset_number,
            "positions": positions,
            "vote_results": vote_results,
            "poll_results": poll_results,
        })

    if not parties:
        return {"merged_count": 0, "groups": [], "source": "none"}

    # Detect duplicates
    use_llm = bool(api_key and api_key.startswith("sk-"))
    if use_llm:
        groups = llm_based_groups(parties, api_key, model)
        source = "llm"
        if not groups:
            # LLM failed or found nothing — fall back to rule-based
            groups = rule_based_groups(parties)
            source = "rule_based_fallback"
    else:
        groups = rule_based_groups(parties)
        source = "rule_based"

    if not groups:
        logger.info("party_dedup: no duplicates found (%s)", source)
        return {"merged_count": 0, "groups": [], "source": source}

    # Execute merges — use a savepoint per group so one bad group doesn't
    # roll back the successful ones.
    merged_count = 0
    results = []
    for g in groups:
        try:
            with db.begin_nested():  # savepoint
                result = execute_merge(g["canonical_id"], g["duplicate_ids"], db)
            if result["ok"]:
                merged_count += len(g["duplicate_ids"])
                logger.info(
                    "party_dedup: merged %s → %s",
                    g["duplicate_names"], g["canonical_name"],
                )
            else:
                logger.warning("party_dedup: skipped group %r — %s", g["canonical_name"], result.get("error"))
        except Exception as exc:
            logger.warning("party_dedup: group %r failed (%s), continuing", g.get("canonical_name"), exc)
            result = {"ok": False, "error": str(exc)}
        results.append({**g, "merge_result": result})

    db.commit()
    logger.info(
        "party_dedup: done — %d duplicates removed across %d groups (source=%s)",
        merged_count, len(groups), source,
    )
    return {
        "merged_count": merged_count,
        "groups": results,
        "source": source,
    }

