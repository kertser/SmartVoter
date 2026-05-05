"""
Knesset OData v3 client.
Fetches votes and bills from the official Knesset data services.

IMPORTANT: As of 2024, votes were moved to a SEPARATE OData service:
  Votes service: https://knesset.gov.il/Odata/Votes.svc

  Entity: View_vote_rslts_hdr_Approved  (vote headers / plenary vote records)
    Fields: vote_id, knesset_num, sess_item_dscr (Hebrew title),
            vote_item_dscr (vote item description), vote_date, vote_type,
            is_accepted, total_for, total_against, total_abstain

  Entity: vote_rslts_kmmbr_shadow  (per-MK results)
    Fields: vote_id, kmmbr_id, kmmbr_name, vote_result (1=for, 2=against,
            3=abstain, 4=absent, 0=cancelled/void), knesset_num, faction_id, faction_name

Bills remain at the original ParliamentInfo service:
  Bills service: https://knesset.gov.il/Odata/ParliamentInfo.svc
  Entity: KNS_Bill
    Key date field: LastUpdatedDate (SubmitDate does NOT exist in the schema)
"""
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_ODATA_FMT = "$format=json"
_PAGE_SIZE = 100

# vote_result integer values from vote_rslts_kmmbr_shadow
_VOTE_RESULT_MAP = {
    0: "absent",   # void / cancelled
    1: "for",
    2: "against",
    3: "abstain",
    4: "absent",   # did not vote
}


def _odata_url(base: str, entity: str, params: str) -> str:
    return f"{base}/{entity}?{_ODATA_FMT}&{params}"


def _get_json(client: httpx.Client, url: str) -> dict[str, Any]:
    try:
        resp = client.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        logger.error("Knesset OData request failed: %s — %s", url, exc)
        raise


def probe_votes_availability(votes_base_url: str, knesset_number: int) -> bool:
    """
    Probe whether the Knesset Votes.svc endpoint has data for this Knesset number.

    Returns True if at least one vote record exists for this Knesset.
    This is useful to detect whether Knesset 25/26 data is available yet.

    NOTE: As of 2025, Knesset 25 data became partially available.
    Knesset 26 (sworn in 2025) may still be pending.
    Always check availability before running large imports on new Knessets.
    """
    try:
        url = _odata_url(
            votes_base_url,
            "View_vote_rslts_hdr_Approved",
            f"$filter=knesset_num eq {knesset_number}&$top=1",
        )
        with httpx.Client() as client:
            data = _get_json(client, url)
        rows = data.get("value", [])
        available = len(rows) > 0
        if available:
            logger.info("Knesset %d vote data IS available in Votes.svc", knesset_number)
        else:
            logger.warning(
                "Knesset %d vote data is NOT available in Votes.svc. "
                "Consider using Open Knesset (Hasadna) as an alternative: "
                "https://oknesset.org/api/v2/vote/",
                knesset_number,
            )
        return available
    except Exception as exc:
        logger.error("Failed to probe Knesset %d votes availability: %s", knesset_number, exc)
        return False


def fetch_votes(
    votes_base_url: str,
    knesset_number: int,
    limit: int = 500,
    probe_first: bool = False,
) -> list[dict[str, Any]]:
    """
    Return up to `limit` plenary vote records for the given Knesset.
    Uses the Votes.svc service (View_vote_rslts_hdr_Approved entity).

    NOTE: As of 2024, only Knesset 1–24 had vote data in this endpoint.
    Knesset 25 data became partially available in 2025.
    Knesset 26+ data may still be pending — call probe_votes_availability()
    first if you are unsure.

    Pass probe_first=True to automatically skip fetching if no data is available
    (avoids unnecessary API calls for new Knessets).

    Each returned dict maps to the Vote model fields:
      external_id, title_he, date, knesset_number, vote_type, source_url, raw_json
    """
    if probe_first and knesset_number >= 25:
        if not probe_votes_availability(votes_base_url, knesset_number):
            logger.warning(
                "Skipping vote fetch for Knesset %d — no data found in Votes.svc. "
                "Run import_votes with a lower knesset_number or use Open Knesset.",
                knesset_number,
            )
            return []
    results: list[dict[str, Any]] = []
    skip = 0
    filter_q = f"knesset_num eq {knesset_number}"

    with httpx.Client() as client:
        while len(results) < limit:
            take = min(_PAGE_SIZE, limit - len(results))
            url = _odata_url(
                votes_base_url,
                "View_vote_rslts_hdr_Approved",
                f"$filter={filter_q}&$top={take}&$skip={skip}&$orderby=vote_date desc",
            )
            data = _get_json(client, url)
            rows = data.get("value", [])
            if not rows:
                break

            for row in rows:
                vote_id = row.get("vote_id")
                # Use vote_item_dscr if available, fall back to sess_item_dscr
                title = (
                    row.get("vote_item_dscr")
                    or row.get("sess_item_dscr")
                    or "—"
                )
                results.append({
                    "external_id": str(vote_id),
                    "title_he": title,
                    "title_en": None,
                    "date": _parse_odata_date(row.get("vote_date")),
                    "knesset_number": knesset_number,
                    "vote_type": row.get("vote_type"),
                    "is_procedural_estimate": False,
                    "importance_score": None,
                    "signal_quality_score": None,
                    "source_url": (
                        f"https://knesset.gov.il/vote/heb/Vote_Res_Map.asp?vote_id_t={vote_id}"
                        if vote_id else None
                    ),
                    "raw_json": row,
                })
            skip += len(rows)
            if len(rows) < take:
                break

    logger.info("Fetched %d votes for Knesset %d", len(results), knesset_number)
    return results


def fetch_bills(
    bills_base_url: str,
    knesset_number: int,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """
    Return up to `limit` bill records for the given Knesset.
    Uses the ParliamentInfo.svc service (KNS_Bill entity).

    NOTE: The KNS_Bill entity does NOT have a 'SubmitDate' field.
    Use LastUpdatedDate for ordering. The publication date is in 'PublicationDate'.

    Each returned dict maps to the Bill model fields.
    """
    results: list[dict[str, Any]] = []
    skip = 0
    filter_q = f"KnessetNum eq {knesset_number}"

    with httpx.Client() as client:
        while len(results) < limit:
            take = min(_PAGE_SIZE, limit - len(results))
            url = _odata_url(
                bills_base_url,
                "KNS_Bill",
                f"$filter={filter_q}&$top={take}&$skip={skip}&$orderby=LastUpdatedDate desc",
            )
            data = _get_json(client, url)
            rows = data.get("value", [])
            if not rows:
                break

            for row in rows:
                bill_id = row.get("BillID")
                results.append({
                    "external_id": str(bill_id),
                    "title_he": row.get("Name") or "—",
                    "title_en": None,
                    "summary_he": row.get("SummaryLaw"),
                    "summary_en": None,
                    "full_text_url": None,
                    "date_submitted": _parse_odata_date(
                        row.get("PublicationDate") or row.get("LastUpdatedDate")
                    ),
                    "status": row.get("SubTypeDesc"),
                    "source_url": (
                        f"https://main.knesset.gov.il/Activity/Legislation/Laws/Pages/LawBill.aspx"
                        f"?t=lawbill&lawbillid={bill_id}"
                        if bill_id else None
                    ),
                    "raw_json": row,
                })
            skip += len(rows)
            if len(rows) < take:
                break

    logger.info("Fetched %d bills for Knesset %d", len(results), knesset_number)
    return results


def fetch_factions(
    base_url: str,
    knesset_number: int,
) -> list[dict[str, Any]]:
    """
    Return all factions (party groups) for the given Knesset.
    Uses KNS_Faction entity in ParliamentInfo.svc.

    Each returned dict maps to PoliticalBrand + PartyInstance:
      faction_id, name_he, knesset_number, start_date, end_date, is_current, source_url
    """
    url = _odata_url(
        base_url,
        "KNS_Faction",
        f"$filter=KnessetNum eq {knesset_number}&$orderby=Name",
    )
    with httpx.Client() as client:
        data = _get_json(client, url)

    results = []
    for row in data.get("value", []):
        faction_id = row.get("FactionID")
        results.append({
            "faction_id": faction_id,
            "name_he": row.get("Name") or "—",
            "knesset_number": knesset_number,
            "start_date": _parse_odata_date(row.get("StartDate")),
            "end_date": _parse_odata_date(row.get("FinishDate")),
            "is_current": bool(row.get("IsCurrent")),
            "source_url": f"https://knesset.gov.il/faction/heb/FactionPage.aspx?FactionID={faction_id}",
            "raw_json": row,
        })
    logger.info("Fetched %d factions for Knesset %d", len(results), knesset_number)
    return results


def fetch_persons(
    base_url: str,
    knesset_number: int,
    limit: int = 300,
) -> list[dict[str, Any]]:
    """
    Return all persons (MKs and leaders) for the given Knesset via KNS_PersonToPosition.
    Includes faction membership.

    MK PositionIDs: 43 (male), 61 (female), 48 (faction chair).
    Returns list of dicts with person + membership info.
    """
    # Positions that indicate Knesset membership
    mk_positions = "43,61,48,54"
    results: list[dict[str, Any]] = []
    skip = 0
    seen_persons: set[int] = set()

    with httpx.Client() as client:
        while len(results) < limit:
            take = min(_PAGE_SIZE, limit - len(results))
            url = _odata_url(
                base_url,
                "KNS_PersonToPosition",
                (
                    f"$filter=KnessetNum eq {knesset_number} "
                    f"and PositionID in ({mk_positions})"
                    f"&$expand=KNS_Person"
                    f"&$top={take}&$skip={skip}"
                    f"&$orderby=PersonID"
                ),
            )
            data = _get_json(client, url)
            rows = data.get("value", [])
            if not rows:
                break

            for row in rows:
                person_id = row.get("PersonID")
                person_obj = row.get("KNS_Person") or {}
                first = person_obj.get("FirstName") or ""
                last = person_obj.get("LastName") or ""
                name_he = f"{first} {last}".strip() or f"Person {person_id}"

                results.append({
                    "person_id": person_id,
                    "name_he": name_he,
                    "name_en": name_he,  # no English name in API
                    "knesset_number": knesset_number,
                    "faction_id": row.get("FactionID"),
                    "faction_name": row.get("FactionName"),
                    "position_id": row.get("PositionID"),
                    "start_date": _parse_odata_date(row.get("StartDate")),
                    "end_date": _parse_odata_date(row.get("FinishDate")),
                    "is_current": bool(row.get("IsCurrent")),
                    "public_profile_url": (
                        f"https://main.knesset.gov.il/mk/heb/MKDetails.aspx?MKID={person_id}"
                    ),
                    "raw_json": row,
                })
                seen_persons.add(person_id)

            skip += len(rows)
            if len(rows) < take:
                break

    logger.info(
        "Fetched %d person-position records for Knesset %d (%d unique persons)",
        len(results), knesset_number, len(seen_persons),
    )
    return results


def fetch_vote_results(
    votes_base_url: str,
    vote_external_id: str,
) -> list[dict[str, Any]]:
    """
    Return per-MK vote results for a specific vote.
    Uses vote_rslts_kmmbr_shadow entity in the Votes.svc service.
    """
    filter_q = f"vote_id eq {vote_external_id}"
    url = _odata_url(votes_base_url, "vote_rslts_kmmbr_shadow", f"$filter={filter_q}&$top=200")

    with httpx.Client() as client:
        data = _get_json(client, url)

    results = []
    for row in data.get("value", []):
        vote_result_raw = row.get("vote_result")
        vote_value = _VOTE_RESULT_MAP.get(vote_result_raw, "absent")

        results.append({
            "person_external_id": str(row.get("kmmbr_id", "")).strip(),
            "vote_value": vote_value,
            "faction_name": row.get("faction_name"),
            "raw": row,
        })
    return results


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_odata_date(value: str | None) -> str | None:
    """
    Handles multiple Knesset OData date formats:
    - '/Date(1234567890000)/'  (legacy OData v2 format)
    - '2023-01-15T00:00:00'   (ISO datetime, newer service)
    - '2023-01-15'            (plain ISO date)
    Returns ISO date string (YYYY-MM-DD) or None.
    """
    if not value:
        return None
    import re
    from datetime import datetime, timezone

    m = re.search(r"/Date\((\d+)", value)
    if m:
        ts_ms = int(m.group(1))
        return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date().isoformat()
    if "T" in value:
        return value.split("T")[0]
    return value

