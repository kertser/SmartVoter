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
import uuid
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── Party name normaliser ──────────────────────────────────────────────────────
# Maps any variant found in polls (He / En / transliteration) → official_name
# in our party_instances table.  Add new rows as parties form/merge/rebrand.

PARTY_ALIASES: list[tuple[list[str], str]] = [
    (["הליכוד", "ליכוד", "likud"],                          "Likud"),
    (["יש עתיד", "yesh atid"],                              "Yesh Atid"),
    (["מחנה ממלכתי", "mamlakhtit", "national unity",
      "מחנה לאומי"],                                         "Mamlakhtit"),
    (["ש\"ס", "שס", "shas"],                                "Shas"),
    (["יהדות התורה", "yahadut hatorah", "united torah"],    "Yahadut HaTorah"),
    (["ישראל ביתנו", "yisrael beiteinu", "lieberman"],      "Yisrael Beiteinu"),
    (["הדמוקרטים", "דמוקרטים", "the democrats", "democrats",
      "גולן", "yair golan"],                                 "HaDemokratim"),
    (["עוצמה יהודית", "otzma yehudit", "jewish power",
      "ben gvir", "בן גביר"],                               "OtzmaYehudit"),
    (["הציונות הדתית", "religious zionism", "smotrich",
      "סמוטריץ"],                                            "Hatzionut HaDatit 26"),
    (["רע\"מ", "רעם", "raam", "united arab list",
      "mansour", "מנסור עבאס"],                              "Raam"),
    (["חד\"ש", "חדש", "תע\"ל", "תעל", "hadash", "taal",
      "hadash-taal", "joint list"],                          "Hadash-Taal"),
]


def _normalize_party_name(name_he: Optional[str], name_en: Optional[str]) -> Optional[str]:
    """Return the canonical official_name for a party, or None if unrecognised."""
    candidates = []
    if name_he:
        candidates.append(name_he.strip().lower())
    if name_en:
        candidates.append(name_en.strip().lower())

    for aliases, official in PARTY_ALIASES:
        for alias in aliases:
            for cand in candidates:
                if alias in cand or cand in alias:
                    return official
    return None


# ── OpenAI web search ──────────────────────────────────────────────────────────


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


# ── DB ingestion ───────────────────────────────────────────────────────────────

def _ingest_web_polls(web_data: dict, db) -> tuple[int, int, list[str]]:
    """
    Persist web-fetched polls to the database.

    Returns (polls_stored, parties_stored, warnings).
    Any party name that could not be normalised is returned in warnings.
    """
    from backend.app.models.simulation import Poll, PollPartyResult, Pollster, SimulationRun, SimulationPartyResult, CoalitionScenario, CoalitionScenarioMember
    from backend.app.models.party_instance import PartyInstance

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

        # Get or create Pollster row
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

            # Convert to vote_share fraction
            if share_pct:
                vote_share = share_pct / 100.0
            elif seats:
                vote_share = round(seats / 120 * 0.90, 4)
            else:
                continue

            if vote_share < 0.030:   # below threshold — skip
                continue

            official_name = _normalize_party_name(name_he, name_en)
            if not official_name:
                label = name_he or name_en or "unknown"
                warnings.append(f"Unrecognised party in poll: {label!r}")
                continue

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


# ── Public entry point ─────────────────────────────────────────────────────────

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

