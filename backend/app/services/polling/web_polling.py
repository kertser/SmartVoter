"""
Web Polling Ingestion Service — Phase 14B.

Fetches current Israeli opinion polls via:
  1. OpenAI Responses API with web_search_preview (primary)
  2. Seed / hardcoded data (fallback if OpenAI is not configured)

The service stores its results in the polls / poll_party_results tables and
clears stale simulation_runs so the next GET /api/simulation/latest triggers
a fresh Monte Carlo run with the new data.

Per AGENTS.MD Section 14B.2 (polling data sources) and 14B.5 (poll aggregation).
"""

import json
import logging
import re
import string
import uuid
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── Default alias seed data ────────────────────────────────────────────────────
# This is only used to populate the party_poll_aliases table on first run.
# After that, all aliases are managed via the database and the admin API.
# Format: (alias_text, official_name, language)

DEFAULT_ALIASES: list[tuple[str, str, str]] = [
    # Likud
    ("הליכוד", "Likud", "he"), ("ליכוד", "Likud", "he"), ("likud", "Likud", "en"),
    # Yesh Atid
    ("יש עתיד", "Yesh Atid", "he"), ("yesh atid", "Yesh Atid", "translit"),
    # Mamlakhtit / National Unity
    ("מחנה ממלכתי", "Mamlakhtit", "he"), ("mamlakhtit", "Mamlakhtit", "translit"),
    ("national unity", "Mamlakhtit", "en"), ("מחנה לאומי", "Mamlakhtit", "he"),
    # Shas
    ('ש"ס', "Shas", "he"), ("שס", "Shas", "he"), ("shas", "Shas", "translit"),
    # Yahadut HaTorah
    ("יהדות התורה", "Yahadut HaTorah", "he"),
    ("yahadut hatorah", "Yahadut HaTorah", "translit"),
    ("united torah", "Yahadut HaTorah", "en"),
    # Yisrael Beiteinu
    ("ישראל ביתנו", "Yisrael Beiteinu", "he"),
    ("yisrael beiteinu", "Yisrael Beiteinu", "translit"),
    ("lieberman", "Yisrael Beiteinu", "en"),
    # HaDemokratim (Democrats / Golan)
    ("הדמוקרטים", "HaDemokratim", "he"), ("דמוקרטים", "HaDemokratim", "he"),
    ("the democrats", "HaDemokratim", "en"), ("democrats", "HaDemokratim", "en"),
    ("גולן", "HaDemokratim", "he"), ("yair golan", "HaDemokratim", "en"),
    # Otzma Yehudit
    ("עוצמה יהודית", "OtzmaYehudit", "he"),
    ("otzma yehudit", "OtzmaYehudit", "translit"),
    ("jewish power", "OtzmaYehudit", "en"),
    ("ben gvir", "OtzmaYehudit", "en"), ("בן גביר", "OtzmaYehudit", "he"),
    # Hatzionut HaDatit
    ("הציונות הדתית", "Hatzionut HaDatit 26", "he"),
    ("religious zionism", "Hatzionut HaDatit 26", "en"),
    ("smotrich", "Hatzionut HaDatit 26", "en"),
    ("סמוטריץ", "Hatzionut HaDatit 26", "he"),
    # Raam
    ('רע"מ', "Raam", "he"), ("רעם", "Raam", "he"), ("raam", "Raam", "translit"),
    ("united arab list", "Raam", "en"),
    ("mansour", "Raam", "en"), ("מנסור עבאס", "Raam", "he"),
    # Hadash-Taal
    ('חד"ש', "Hadash-Taal", "he"), ("חדש", "Hadash-Taal", "he"),
    ('תע"ל', "Hadash-Taal", "he"), ("תעל", "Hadash-Taal", "he"),
    ("hadash", "Hadash-Taal", "translit"), ("taal", "Hadash-Taal", "translit"),
    ("hadash-taal", "Hadash-Taal", "translit"), ("joint list", "Hadash-Taal", "en"),
    # Yachad 2026
    ("ביחד", "Yachad 2026", "he"), ("yachad", "Yachad 2026", "translit"),
    ("bennett", "Yachad 2026", "en"), ("בנט ולפיד", "Yachad 2026", "he"),
    ("lapid bennett", "Yachad 2026", "en"), ("bennett lapid", "Yachad 2026", "en"),
    # Yashar
    ("ישר", "Yashar", "he"), ("yashar", "Yashar", "translit"),
    ("eisenkot", "Yashar", "en"), ("איזנקוט", "Yashar", "he"),
    # Kahol Lavan
    ("כחול לבן", "Kahol Lavan", "he"), ("blue and white", "Kahol Lavan", "en"),
    ("blue & white", "Kahol Lavan", "en"), ("kahol lavan", "Kahol Lavan", "translit"),
    ("gantz", "Kahol Lavan", "en"), ("גנץ", "Kahol Lavan", "he"),
    # HaMiluimnikiim (The Reservists)
    ("המילואימניקים", "HaMiluimnikiim", "he"),
    ("מילואימניקים", "HaMiluimnikiim", "he"),
    ("reservists", "HaMiluimnikiim", "en"),
    ("the reservists", "HaMiluimnikiim", "en"),
    # Avoda
    ("העבודה", "Avoda", "he"), ("labor", "Avoda", "en"),
    ("labour", "Avoda", "en"), ("avoda", "Avoda", "translit"),
    # Meretz
    ("מרצ", "Meretz", "he"), ("meretz", "Meretz", "translit"),
    # New Hope
    ("תקווה חדשה", "New Hope", "he"), ("tikvah hadasha", "New Hope", "translit"),
    ("new hope", "New Hope", "en"), ("סער", "New Hope", "he"), ("saar", "New Hope", "translit"),
    # Balad
    ("בלד", "Balad", "he"), ("balad", "Balad", "translit"),
    ("national democratic", "Balad", "en"),
]

# Aggregate / meta labels returned by some polls — not real parties, skip silently.
POLL_AGGREGATE_LABELS: set[str] = {
    "האופוזיציה", "הקואליציה", "מפלגות ערביות",
    "opposition", "coalition", "arab parties", "others", "אחרים",
}


# ── DB alias helpers ───────────────────────────────────────────────────────────

def _clean_alias(s: str) -> str:
    """Lowercase and strip punctuation for consistent matching."""
    _strip = str.maketrans("", "", string.punctuation)
    return s.strip().translate(_strip).strip().lower()


def ensure_aliases_seeded(db) -> None:
    """
    Populate party_poll_aliases from DEFAULT_ALIASES if the table is empty.
    Uses INSERT ... ON CONFLICT (alias_text) DO NOTHING so it is fully
    idempotent regardless of prior transaction state.
    Never commits — caller is responsible for the transaction.
    """
    from backend.app.models.party_poll_alias import PartyPollAlias
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    rows = [
        {
            "id": uuid.uuid5(uuid.NAMESPACE_DNS, f"alias:{_clean_alias(alias_text)}"),
            "alias_text": _clean_alias(alias_text),
            "official_name": official_name,
            "language": language,
            "auto_created": False,
            "notes": None,
            "party_instance_id": None,
        }
        for alias_text, official_name, language in DEFAULT_ALIASES
        if _clean_alias(alias_text)
    ]

    if not rows:
        return

    stmt = pg_insert(PartyPollAlias).values(rows).on_conflict_do_nothing(index_elements=["alias_text"])
    result = db.execute(stmt)
    inserted = result.rowcount if result.rowcount >= 0 else "?"
    if inserted:
        logger.info("party_poll_aliases: seeded %s new aliases (on_conflict_do_nothing)", inserted)
    # Do NOT commit here — caller owns the transaction


def load_alias_map(db) -> dict[str, str]:
    """
    Load all aliases from DB into a dict: cleaned_alias_text → official_name.
    Called once per poll ingestion run.
    """
    from backend.app.models.party_poll_alias import PartyPollAlias
    ensure_aliases_seeded(db)
    return {row.alias_text: row.official_name for row in db.query(PartyPollAlias).all()}


def _normalize_party_name(
    name_he: Optional[str],
    name_en: Optional[str],
    alias_map: dict[str, str],
) -> Optional[str]:
    """Return the canonical official_name for a party, or None if unrecognised."""
    candidates = []
    if name_he:
        candidates.append(_clean_alias(name_he))
    if name_en:
        candidates.append(_clean_alias(name_en))

    for cand in candidates:
        # Exact match first
        if cand in alias_map:
            return alias_map[cand]
        # Substring match
        for alias, official in alias_map.items():
            if alias in cand or cand in alias:
                return official
    return None


def _auto_create_alias(name_he: Optional[str], name_en: Optional[str], db) -> str:
    """
    Insert an unrecognised party as a new alias row (auto_created=True)
    so an admin can later link it to a party instance.
    Returns the official_name used (raw name).
    """
    from backend.app.models.party_poll_alias import PartyPollAlias
    raw_name = name_he or name_en or "unknown"
    cleaned = _clean_alias(raw_name)
    language = "he" if name_he else "en"
    existing = db.query(PartyPollAlias).filter(PartyPollAlias.alias_text == cleaned).first()
    if not existing:
        db.add(PartyPollAlias(
            alias_text=cleaned,
            official_name=raw_name,
            language=language,
            auto_created=True,
            notes="Auto-created from unrecognised poll entry. Link to a party instance via admin.",
        ))
        db.flush()
        logger.info("party_poll_aliases: auto-created alias %r → %r", cleaned, raw_name)
    return raw_name


def _is_aggregate_label(name_he: Optional[str], name_en: Optional[str]) -> bool:
    """Return True if the name is a known aggregate/meta label, not a real party."""
    for name in (name_he, name_en):
        if name and name.strip() in POLL_AGGREGATE_LABELS:
            return True
    return False


# ── OpenAI web search ─────────────────────────────────────────────────────────


def _extract_first_json_object(text: str) -> Optional[dict]:
    """
    Find and parse the first complete, balanced JSON object in `text`.
    Handles nested braces correctly unlike a simple regex.
    """
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                fragment = text[start : i + 1]
                try:
                    return json.loads(fragment)
                except json.JSONDecodeError:
                    # Keep searching for next object
                    start = -1
    return None


def _call_openai_web_search(api_key: str, model: str) -> Optional[dict]:
    """
    Call the OpenAI Responses API with web_search_preview and return parsed JSON.

    Two-step approach:
      1. Web-search call → get prose text with real poll data and citations.
      2. Extraction call → convert prose to structured JSON (no web search needed).

    Returns None on any error.
    """
    try:
        from openai import OpenAI  # local import
        client = OpenAI(api_key=api_key)
        today = date.today().isoformat()

        # ── Step 1: Web search for current Israeli polls ───────────────────────
        search_prompt = (
            f"Today is {today}. Search the web for the most recent Israeli opinion polls "
            "about the next Knesset (26th Knesset) election published in 2025–2026.\n\n"
            "Look for polls from: Midgam (מידגם), Direct Polls (סקרי ישיר), "
            "Panels Politics (פאנלס פוליטיקס), Dahaf (דהף), Smith Research, Lazar, "
            "or other reputable Israeli pollsters.\n\n"
            "Check Israeli news sites: Walla, Maariv, Ynet, Haaretz, N12, Channel 13.\n\n"
            "Summarise the 2–4 most recent polls you find, including:\n"
            "- pollster name\n"
            "- publication date\n"
            "- source URL\n"
            "- sample size if available\n"
            "- seat counts or vote-share percentages for each party\n\n"
            "Include ALL parties mentioned (even small ones near the threshold).\n"
            "הדמוקרטים (Democrats/Golan) is one party — do NOT split into Labor/Meretz.\n"
            "עוצמה יהודית (Ben Gvir) and הציונות הדתית (Smotrich) are SEPARATE parties.\n"
            "ביחד (Bennett+Lapid) and ישר (Eisenkot) are SEPARATE new parties for 2026.\n"
            "Do NOT include aggregate labels like 'האופוזיציה', 'הקואליציה', 'מפלגות ערביות' — list individual parties only.\n"
        )

        logger.info("web_search step 1: fetching poll data via web search")
        r1 = client.responses.create(
            model=model,
            tools=[{"type": "web_search_preview"}],
            input=search_prompt,
        )
        prose_text = getattr(r1, "output_text", None)
        if not prose_text:
            # Fallback: iterate output items
            parts = []
            for item in r1.output:
                if hasattr(item, "content"):
                    for block in item.content:
                        t = getattr(block, "text", None)
                        if t:
                            parts.append(t)
            prose_text = "\n".join(parts)

        if not prose_text or len(prose_text) < 50:
            logger.warning("web_search step 1: empty or too-short response")
            return None

        logger.info("web_search step 1: got %d chars of poll prose", len(prose_text))

        # ── Step 2: Extract structured JSON from the prose ─────────────────────
        json_schema = (
            "{\n"
            "  \"polls\": [\n"
            "    {\n"
            "      \"pollster\": \"string\",\n"
            "      \"publication_date\": \"YYYY-MM-DD\",\n"
            "      \"source_url\": \"https://...\",\n"
            "      \"sample_size\": 500,\n"
            "      \"parties\": [\n"
            "        {\n"
            "          \"name_he\": \"שם המפלגה\",\n"
            "          \"name_en\": \"Party name\",\n"
            "          \"seats\": 14,\n"
            "          \"vote_share_percent\": 11.5\n"
            "        }\n"
            "      ]\n"
            "    }\n"
            "  ],\n"
            "  \"data_as_of\": \"YYYY-MM-DD\",\n"
            "  \"notes\": \"any caveats\"\n"
            "}"
        )
        extraction_prompt = (
            "Extract structured data from the following Israeli poll summary text.\n\n"
            f"TODAY: {today}\n\n"
            "TEXT:\n"
            f"{prose_text}\n\n"
            "Return ONLY a JSON object — no markdown, no explanation — "
            "matching this schema exactly:\n"
            f"{json_schema}\n\n"
            "Rules:\n"
            "- If only seats given: vote_share_percent = seats / 120 * 100.\n"
            "- If only vote_share given: seats = round(vote_share / 100 * 120 * 0.9).\n"
            "- Include parties mentioned even without exact data (estimate from context).\n"
            "- Use Hebrew party names for name_he.\n"
            "- Use null for unknown numeric values.\n"
            "- Do NOT include aggregate entries like האופוזיציה, הקואליציה, מפלגות ערביות.\n"
            "- If you cannot find any polls, return {\"polls\": [], \"data_as_of\": null, "
            "\"notes\": \"No polls found\"}.\n"
        )

        logger.info("web_search step 2: extracting JSON from prose")
        r2 = client.responses.create(
            model=model,
            input=extraction_prompt,
        )
        raw = getattr(r2, "output_text", None) or ""
        for item in r2.output:
            if hasattr(item, "content"):
                for block in item.content:
                    t = getattr(block, "text", None)
                    if t:
                        raw += t

        raw = raw.strip()

        # Strip markdown fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
        raw = raw.strip()

        # Find the first balanced JSON object (handles nested braces correctly)
        data = _extract_first_json_object(raw)
        if data is None:
            logger.warning("web_search step 2: no valid JSON found:\n%s", raw[:400])
            return None

        logger.info(
            "web_search: fetched %d polls (as of %s)",
            len(data.get("polls", [])),
            data.get("data_as_of", "unknown"),
        )
        return data

    except Exception as exc:
        logger.error("web_search: OpenAI Responses API failed: %s", exc)
        return None


# ── DB ingestion ──────────────────────────────────────────────────────────────

def _ingest_web_polls(web_data: dict, db) -> tuple[int, int, list[str]]:
    """
    Persist web-fetched polls to the database.

    Returns (polls_stored, parties_stored, warnings).
    Unrecognised party names are auto-inserted into party_poll_aliases
    (auto_created=True) and stored in poll_party_results without a party link.
    """
    from backend.app.models.simulation import Poll, PollPartyResult, Pollster, SimulationRun, SimulationPartyResult, CoalitionScenario, CoalitionScenarioMember
    from backend.app.models.party_instance import PartyInstance

    # Load alias map from DB (seeds defaults if table is empty)
    alias_map = load_alias_map(db)

    # Build official_name → party_instance_id map
    party_id_map: dict[str, uuid.UUID] = {
        pi.official_name: pi.id
        for pi in db.query(PartyInstance).all()
    }

    # Clear all existing polls and simulation runs (fresh start with live data)
    db.query(CoalitionScenarioMember).delete()
    db.query(CoalitionScenario).delete()
    db.query(SimulationPartyResult).delete()
    db.query(SimulationRun).delete()
    db.query(PollPartyResult).delete()
    db.query(Poll).delete()
    db.flush()

    polls_stored = 0
    parties_stored = 0
    warnings: list[str] = []

    for poll_raw in web_data.get("polls", []):
        pollster_name = poll_raw.get("pollster", "Unknown")

        pollster = db.query(Pollster).filter(Pollster.name == pollster_name).first()
        if not pollster:
            pollster = Pollster(name=pollster_name, country="IL", reliability_score=0.70)
            db.add(pollster)
            db.flush()

        pub_date_str = poll_raw.get("publication_date", date.today().isoformat())
        try:
            pub_date = date.fromisoformat(pub_date_str)
        except ValueError:
            pub_date = date.today()

        poll = Poll(
            pollster_id=pollster.id,
            field_end_date=pub_date,
            publication_date=pub_date,
            sample_size=poll_raw.get("sample_size") or 500,
            quality_score=poll_raw.get("quality_score", 0.75),
            source_url=poll_raw.get("source_url", ""),
            method="web_search",
        )
        db.add(poll)
        db.flush()

        for p in poll_raw.get("parties", []):
            name_he = p.get("name_he")
            name_en = p.get("name_en")
            share_pct = p.get("vote_share_percent", 0.0)
            seats = p.get("seats", 0)

            if share_pct:
                vote_share = share_pct / 100.0
            elif seats:
                vote_share = round(seats / 120 * 0.90, 4)
            else:
                continue

            if vote_share < 0.030:   # below threshold — skip
                continue

            if _is_aggregate_label(name_he, name_en):
                continue

            official_name = _normalize_party_name(name_he, name_en, alias_map)
            if not official_name:
                # Auto-create alias in DB for admin review, store poll result without party link
                official_name = _auto_create_alias(name_he, name_en, db)
                # Reload alias map so subsequent polls in this batch can find it
                alias_map[_clean_alias(official_name)] = official_name
                warnings.append(
                    f"Auto-created alias for unrecognised party {official_name!r} "
                    f"(needs admin review at /admin → Poll Aliases)"
                )

            pi_id = party_id_map.get(official_name)
            db.add(PollPartyResult(
                poll_id=poll.id,
                party_instance_id=pi_id,
                reported_name=official_name,
                vote_share_mean=round(vote_share, 4),
                seats_mean=round(vote_share * 120 * 0.9, 1),
            ))
            parties_stored += 1

        polls_stored += 1

    db.flush()
    return polls_stored, parties_stored, warnings


# ── Public entry point ────────────────────────────────────────────────────────

def fetch_and_store_live_polls(
    db,
    api_key: Optional[str] = None,
    model: str = "gpt-4o",
) -> dict:
    """
    Main entry point called by the admin endpoint.

    1. If api_key is provided — try OpenAI web search, parse, store.
    2. Regardless of result — return a status dict with source, polls_count,
       parties_count, warnings, and timestamp.

    On success the old simulation_runs are cleared so the next request
    triggers a fresh Monte Carlo run.
    """
    source = "none"
    polls_stored = 0
    parties_stored = 0
    warnings: list[str] = []
    notes = ""

    web_data = None
    if api_key and api_key.startswith("sk-"):
        logger.info("polling: attempting OpenAI web search with model=%s", model)
        web_data = _call_openai_web_search(api_key, model)
        if web_data:
            source = "openai_web_search"
            notes = web_data.get("notes", "")
            data_as_of = web_data.get("data_as_of", date.today().isoformat())
    else:
        logger.info("polling: no OpenAI key configured — skipping web search")

    if web_data and web_data.get("polls"):
        try:
            polls_stored, parties_stored, w = _ingest_web_polls(web_data, db)
            warnings.extend(w)
            db.commit()
            logger.info(
                "polling: stored %d polls, %d party results from %s",
                polls_stored, parties_stored, source,
            )
        except Exception as exc:
            db.rollback()
            logger.error("polling: DB ingestion failed: %s", exc)
            warnings.append(f"DB error: {exc}")
            source = "error"
    else:
        source = "no_data" if api_key else "no_api_key"
        warnings.append(
            "OpenAI web search returned no data. "
            "Existing seed polls remain. "
            "Configure OPENAI_API_KEY and ensure the key has Responses API access."
        )

    return {
        "source": source,
        "polls_stored": polls_stored,
        "parties_stored": parties_stored,
        "warnings": warnings,
        "notes": notes,
        "refreshed_at": datetime.utcnow().isoformat() + "Z",
        "model_used": model if (web_data and api_key) else None,
    }
