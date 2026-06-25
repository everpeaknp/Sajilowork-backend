"""
Geocoding helpers for tasks.

Uses OpenStreetMap Nominatim (free, no API key required) to resolve free-form
address strings into latitude/longitude pairs.

Nominatim usage policy:
- Max 1 request per second
- Custom User-Agent identifying the application is required
- Cache results when possible

Reference: https://operations.osmfoundation.org/policies/nominatim/
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "sajilowork/1.0 (geocoding for task listings)"
REQUEST_TIMEOUT = 6  # seconds


def _round6(value: float) -> Decimal:
    """Round to 6 decimal places (matches Task.latitude/longitude DecimalField)."""
    return Decimal(f"{value:.6f}")


def geocode_location(query: str) -> Optional[Tuple[Decimal, Decimal]]:
    """
    Resolve a free-form location string to (latitude, longitude).

    Returns None if the query is empty, the request fails, or no results
    are found. Never raises — callers can safely degrade.
    """
    if not query or not query.strip():
        return None

    params = {
        "q": query.strip(),
        "format": "json",
        "limit": 1,
        "addressdetails": 0,
    }
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en"}

    try:
        response = requests.get(
            NOMINATIM_URL,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Geocoding request failed for %r: %s", query, exc)
        return None

    if not isinstance(data, list) or not data:
        logger.info("Geocoding returned no results for %r", query)
        return None

    try:
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Malformed geocoding response for %r: %s", query, exc)
        return None

    return _round6(lat), _round6(lon)


def build_query_for_task(task) -> str:
    """
    Build the most specific location query we can from a task's fields.

    Prefers full address, falls back to city + country, and appends
    'Nepal' if no country is set since this app is Nepal-focused.
    """
    parts = []
    if task.address:
        parts.append(str(task.address).strip())
    if task.city and str(task.city).strip() not in [p.lower() for p in parts] \
            and str(task.city).strip() not in parts:
        parts.append(str(task.city).strip())
    if task.state:
        parts.append(str(task.state).strip())
    if task.country:
        parts.append(str(task.country).strip())
    else:
        # Project is Nepal-focused — bias search if no country given.
        parts.append("Nepal")

    # Deduplicate while preserving order.
    seen = set()
    deduped = []
    for p in parts:
        key = p.lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(p)
    return ", ".join(deduped)
