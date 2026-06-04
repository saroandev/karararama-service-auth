"""
CAPTCHA verification (Cloudflare Turnstile).

Stage 1 (this file's current state): a stub that accepts any non-empty
token so the rest of the brute-force pipeline can be wired up and tested
without provisioning a Turnstile site key yet. Set
`TURNSTILE_ALWAYS_PASS=true` in local .env to keep this behaviour
explicit — the helper logs a warning every call so we notice if it leaks
into a non-dev environment.

Stage 2 (next PR): swap in the real Cloudflare siteverify call using
`TURNSTILE_SECRET_KEY` from env. The function signature stays the same.
"""
import logging
import os
from typing import Optional

import httpx


logger = logging.getLogger(__name__)


TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "")
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
# Explicit dev escape hatch — must be set locally if no real Turnstile keys.
TURNSTILE_ALWAYS_PASS = os.getenv("TURNSTILE_ALWAYS_PASS", "false").lower() == "true"


async def verify_captcha_token(
    token: Optional[str],
    *,
    client_ip: Optional[str] = None,
) -> bool:
    """
    Verify a Turnstile token against Cloudflare's siteverify.

    Returns True on success, False on missing/invalid token. Never raises;
    network errors are logged and treated as a failed verification so an
    outage in Cloudflare cannot bypass the gate.
    """
    if not token:
        return False

    if TURNSTILE_ALWAYS_PASS:
        logger.warning(
            "TURNSTILE_ALWAYS_PASS=true — accepting captcha token without "
            "remote verification. This must NEVER be set outside local dev."
        )
        return True

    if not TURNSTILE_SECRET_KEY:
        # Fail-closed: missing config in a non-dev env should NOT silently
        # allow logins. Tell the operator something is wrong.
        logger.error(
            "TURNSTILE_SECRET_KEY not configured; refusing captcha verification."
        )
        return False

    payload = {"secret": TURNSTILE_SECRET_KEY, "response": token}
    if client_ip:
        payload["remoteip"] = client_ip

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(TURNSTILE_VERIFY_URL, data=payload)
        if resp.status_code != 200:
            logger.warning(
                "Turnstile siteverify returned %s: %s",
                resp.status_code,
                resp.text[:200],
            )
            return False
        body = resp.json()
        return bool(body.get("success"))
    except Exception as e:  # noqa: BLE001
        logger.warning("Turnstile verification error: %s", e)
        return False
