"""
USD → TRY exchange rate provider.

Strategy:
  1. Try TCMB (Türkiye Cumhuriyet Merkez Bankası) — the authoritative source
     used by banks. Returns the daily fixing rate; not updated on weekends/
     holidays but stays valid until the next business day.
  2. Fallback to open.er-api.com if TCMB is unreachable or its response is
     malformed (e.g. holiday with no <Currency Kod="USD"> entry).
  3. Last-resort fallback to settings.USD_TRY_RATE so the system never
     refuses to quote.

A small in-process cache (15 minutes) avoids hammering TCMB on every
/billing/plans page load.
"""
from __future__ import annotations

import logging
import time
from typing import Optional
from xml.etree import ElementTree as ET

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TCMB_URL = "https://www.tcmb.gov.tr/kurlar/today.xml"
FALLBACK_URL = "https://open.er-api.com/v6/latest/USD"
CACHE_TTL_SECONDS = 15 * 60  # 15 minutes — kur sıklığı + TCMB rate-limit dostu
REQUEST_TIMEOUT_SECONDS = 4.0

# Module-level cache: (rate, fetched_at_unix, source)
_cache: dict[str, tuple[float, float, str]] = {}


def _fetch_tcmb() -> Optional[float]:
    """Returns the TCMB forex selling rate for USD, or None on failure."""
    try:
        resp = httpx.get(TCMB_URL, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        for currency in root.findall("Currency"):
            if currency.get("Kod") == "USD":
                # ForexSelling = döviz satış; en yaygın kullanılan referans.
                node = currency.find("ForexSelling")
                if node is not None and node.text:
                    value = float(node.text.replace(",", "."))
                    if value > 0:
                        return value
        logger.warning("TCMB response did not contain a USD entry")
    except Exception as exc:  # network, XML, parse — hepsi fallback'e düşmeli
        logger.warning("TCMB fetch failed: %s", exc)
    return None


def _fetch_fallback() -> Optional[float]:
    """open.er-api.com returns rates with USD as base; we want TRY rate."""
    try:
        resp = httpx.get(FALLBACK_URL, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
        rates = data.get("rates") or {}
        try_rate = rates.get("TRY")
        if isinstance(try_rate, (int, float)) and try_rate > 0:
            return float(try_rate)
        logger.warning("Fallback response had no TRY rate")
    except Exception as exc:
        logger.warning("Fallback rate fetch failed: %s", exc)
    return None


def get_usd_try_rate(force_refresh: bool = False) -> tuple[float, str]:
    """Returns (rate, source) — source is "tcmb"|"fallback"|"settings"|"cache".

    Caller doesn't have to await; the call is synchronous so it can be invoked
    from both async endpoints (FastAPI runs it in a threadpool when needed)
    and from billing_service.create_order without coroutine overhead.
    """
    now = time.time()
    if not force_refresh:
        cached = _cache.get("usd_try")
        if cached and (now - cached[1]) < CACHE_TTL_SECONDS:
            return cached[0], "cache"

    # Try TCMB first
    rate = _fetch_tcmb()
    if rate is not None:
        _cache["usd_try"] = (rate, now, "tcmb")
        return rate, "tcmb"

    # Fallback API
    rate = _fetch_fallback()
    if rate is not None:
        _cache["usd_try"] = (rate, now, "fallback")
        return rate, "fallback"

    # Last resort: configured static default
    static = float(settings.USD_TRY_RATE)
    logger.warning("Returning static USD_TRY_RATE=%s — live sources unavailable", static)
    # Don't cache the static value; we want the next call to retry the network.
    return static, "settings"
