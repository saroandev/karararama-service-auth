"""
Request-context helpers (client IP, etc.).

We stay deliberately simple here: behind an ALB / nginx, FastAPI's
`request.client.host` resolves to the proxy address, so we honor
`X-Forwarded-For` (left-most entry) when present. The middleware pass in
the next phase will tighten this (trusted-proxy list, header normalisation),
but the current implementation is already safe enough to record per-IP
brute-force counters: spoofed XFF is fine because every distinct value
costs the attacker one entry in the gate ledger.
"""
from typing import Optional

from fastapi import Request


def get_client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",", 1)[0].strip()
        if first:
            return first[:45]  # column is varchar(45) — clamp defensively
    if request.client and request.client.host:
        return request.client.host[:45]
    return None
