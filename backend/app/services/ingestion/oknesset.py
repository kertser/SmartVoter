"""
Open Knesset (Hasadna) API client.
Base: https://oknesset.org/api/v2/

Endpoints used:
  /vote/      — vote list (richer English metadata)
  /bill/      — bill list
  /member/    — MK list (for persons table)

Open Knesset data may lag behind the latest Knesset session.
Use as secondary enrichment source, not primary.
"""
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _get_json(client: httpx.Client, url: str) -> dict[str, Any]:
    try:
        resp = client.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        logger.error("Open Knesset request failed: %s — %s", url, exc)
        raise


def fetch_members(base_url: str, limit: int = 200) -> list[dict[str, Any]]:
    """
    Return MK records. Maps to Person model fields:
      name_he, name_en, external_ids_json, public_profile_url
    """
    results: list[dict[str, Any]] = []
    url = f"{base_url}/member/?format=json&limit={limit}"

    with httpx.Client() as client:
        while url and len(results) < limit:
            data = _get_json(client, url)
            objects = data.get("objects", [])
            for obj in objects:
                results.append({
                    "name_he": obj.get("name", ""),
                    "name_en": obj.get("name", ""),
                    "external_ids_json": {"oknesset_id": obj.get("id")},
                    "birth_year": obj.get("year_of_birth"),
                    "public_profile_url": obj.get("img_url"),
                })
            meta = data.get("meta", {})
            next_url = meta.get("next")
            url = f"{base_url.rstrip('/')}{next_url}" if next_url else None

    logger.info("Fetched %d members from Open Knesset", len(results))
    return results


def fetch_votes_enriched(base_url: str, limit: int = 200) -> list[dict[str, Any]]:
    """
    Return vote summaries with English titles (where available).
    Use to enrich votes already ingested from the official OData source.
    Returns list of {external_id, title_en} for upsert.
    """
    results: list[dict[str, Any]] = []
    url = f"{base_url}/vote/?format=json&limit=100"

    with httpx.Client() as client:
        while url and len(results) < limit:
            data = _get_json(client, url)
            objects = data.get("objects", [])
            for obj in objects:
                results.append({
                    "external_id": str(obj.get("src_id", obj.get("id", ""))),
                    "title_en": obj.get("title", None),
                })
            meta = data.get("meta", {})
            next_url = meta.get("next")
            url = f"{base_url.rstrip('/')}{next_url}" if next_url else None

    logger.info("Fetched %d enriched votes from Open Knesset", len(results))
    return results

