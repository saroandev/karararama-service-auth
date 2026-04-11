"""
Disposable email domain validation.

Loads a blocklist of disposable email domains from disposable_email_blocklist.conf
and provides a function to check if an email address uses a disposable domain.
"""
from pathlib import Path

_BLOCKLIST_PATH = Path(__file__).resolve().parent.parent.parent / "disposable_email_blocklist.conf"


def _load_blocklist() -> frozenset[str]:
    try:
        with open(_BLOCKLIST_PATH, "r") as f:
            return frozenset(
                line.strip().lower() for line in f if line.strip()
            )
    except FileNotFoundError:
        return frozenset()


_DISPOSABLE_DOMAINS: frozenset[str] = _load_blocklist()


def is_disposable_email(email: str) -> bool:
    """Check if the given email address uses a disposable/temporary domain."""
    domain = email.rsplit("@", 1)[-1].lower()
    return domain in _DISPOSABLE_DOMAINS
