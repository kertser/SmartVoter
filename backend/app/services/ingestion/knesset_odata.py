"""
Knesset OData v3 client.
Fetches votes and bills from the official Knesset data service.
API base: https://knesset.gov.il/Odata/ParliamentInfo.svc

OData endpoints used:
  KNS_Vote           — plenary votes
  KNS_Bill           — proposed bills
  KNS_VoteMK         — per-MK vote results

Note: The Knesset OData service is slow and may rate-limit bulk requests.
Paginate with $top=100 and $skip=N. Store raw_json immediately.
"""
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# OData query parameters
_ODATA_FMT = "$format=json"
_PAGE_SIZE = 100


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


def fetch_votes(
    base_url: str,
    knesset_number: int,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """
    Return up to `limit` plenary vote records for the given Knesset.

    Each returned dict maps to the Vote model fields:
      external_id, title_he, date, knesset_number, vote_type, source_url, raw_json
    """
    results: list[dict[str, Any]] = []
    skip = 0
    filter_q = f"KnessetNum eq {knesset_number}"

    with httpx.Client() as client:
        while len(results) < limit:
            take = min(_PAGE_SIZE, limit - len(results))
            url = _odata_url(
                base_url,
                "KNS_Vote",
                f"$filter={filter_q}&$top={take}&$skip={skip}&$orderby=VoteDate desc",
            )
            data = _get_json(client, url)
            rows = data.get("value", [])
            if not rows:
                break

            for row in rows:
                results.append({
                    "external_id": str(row.get("VoteID")),
                    "title_he": row.get("ItemTitle") or row.get("Title") or "—",
                    "title_en": None,  # OData does not provide EN titles
                    "date": _parse_odata_date(row.get("VoteDate")),
                    "knesset_number": knesset_number,
                    "vote_type": row.get("VoteType"),
                    "is_procedural_estimate": False,
                    "importance_score": None,
                    "signal_quality_score": None,
                    "source_url": f"https://knesset.gov.il/vote/heb/Vote_Res_Map.asp?vote_id_t={row.get('VoteID')}",
                    "raw_json": row,
                })
            skip += len(rows)
            if len(rows) < take:
                break

    logger.info("Fetched %d votes for Knesset %d", len(results), knesset_number)
    return results


def fetch_bills(
    base_url: str,
    knesset_number: int,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """
    Return up to `limit` bill records for the given Knesset.

    Each returned dict maps to the Bill model fields:
      external_id, title_he, date_submitted, status, source_url, raw_json
    """
    results: list[dict[str, Any]] = []
    skip = 0
    filter_q = f"KnessetNum eq {knesset_number}"

    with httpx.Client() as client:
        while len(results) < limit:
            take = min(_PAGE_SIZE, limit - len(results))
            url = _odata_url(
                base_url,
                "KNS_Bill",
                f"$filter={filter_q}&$top={take}&$skip={skip}&$orderby=SubmitDate desc",
            )
            data = _get_json(client, url)
            rows = data.get("value", [])
            if not rows:
                break

            for row in rows:
                results.append({
                    "external_id": str(row.get("BillID")),
                    "title_he": row.get("Name") or "—",
                    "title_en": None,
                    "summary_he": None,
                    "summary_en": None,
                    "full_text_url": None,
                    "date_submitted": _parse_odata_date(row.get("SubmitDate")),
                    "status": row.get("StatusDesc"),
                    "source_url": f"https://main.knesset.gov.il/Activity/Legislation/Laws/Pages/LawBill.aspx?t=lawbill&lawbillid={row.get('BillID')}",
                    "raw_json": row,
                })
            skip += len(rows)
            if len(rows) < take:
                break

    logger.info("Fetched %d bills for Knesset %d", len(results), knesset_number)
    return results


def fetch_vote_results(
    base_url: str,
    vote_external_id: str,
) -> list[dict[str, Any]]:
    """
    Return per-MK vote results for a specific vote.
    Used to populate vote_results table.
    """
    filter_q = f"VoteID eq {vote_external_id}"
    url = _odata_url(base_url, "KNS_VoteMK", f"$filter={filter_q}&$top=200")

    with httpx.Client() as client:
        data = _get_json(client, url)

    results = []
    for row in data.get("value", []):
        vote_val_raw = row.get("VoteValue", "").lower()
        if vote_val_raw in ("for", "כן"):
            vote_value = "for"
        elif vote_val_raw in ("against", "נגד"):
            vote_value = "against"
        elif vote_val_raw in ("abstain", "נמנע"):
            vote_value = "abstain"
        else:
            vote_value = "absent"

        results.append({
            "person_external_id": str(row.get("MkID")),
            "vote_value": vote_value,
            "raw": row,
        })
    return results


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_odata_date(value: str | None) -> str | None:
    """
    OData dates come as '/Date(1234567890000)/' — convert to ISO date string.
    Returns None if value is missing or unparseable.
    """
    if not value:
        return None
    import re
    from datetime import datetime, timezone

    m = re.search(r"/Date\((\d+)", value)
    if m:
        ts_ms = int(m.group(1))
        return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date().isoformat()
    # May already be ISO: 2023-01-15T00:00:00
    if "T" in value:
        return value.split("T")[0]
    return value

