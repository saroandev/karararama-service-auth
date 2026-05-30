"""
Organization subdomain (slug) helpers.

A slug is the DNS label used in the whitelabel URL (e.g. "ozayhukuk" →
ozayhukuk.onedocs.ai). It must be a valid DNS label, unique across
organizations, and must not collide with reserved app/service subdomains.

Single source of truth for:
  - normalization (slugify a free-text org name into a slug)
  - validation (length, charset, reserved-word collision)
  - the RESERVED_SLUGS set itself
"""
import re
import unicodedata
from typing import Optional


# Hard-blocked subdomains. Two categories:
#   1) Operational/infra labels that already point at first-party services or
#      are commonly assumed (api, www, admin, mail, ...).
#   2) Service-specific labels in the OneDocs ALB ingress today
#      (auth-preprod, frontend-preprod, mcp, karararama, los, ...).
#
# Keep this list intentionally generous — taking a slug back later is harder
# than rejecting it now.
RESERVED_SLUGS = frozenset({
    # Generic / infra
    "www", "api", "app", "apps", "admin", "root", "auth", "login", "logout",
    "static", "assets", "cdn", "mail", "email", "smtp", "imap", "ftp",
    "docs", "doc", "help", "support", "status", "blog", "dashboard",
    "ws", "wss", "webhook", "webhooks", "callback", "oauth", "sso",
    # OneDocs services (preprod + prod variants — guard both)
    "onedocs", "mcp", "los", "frontend", "knowledgebase", "analyzer",
    "toolkit", "onetracker", "uyap", "karararama", "karar-arama",
    "extension-registry", "billing", "payments", "paytr",
    "auth-preprod", "frontend-preprod", "knowledgebase-preprod",
    "analyzer-preprod", "toolkit-preprod", "onetracker-preprod",
    "uyap-preprod", "karararama-preprod", "karar-arama-auth-preprod",
    "karar-arama-knowledgebase-preprod", "extension-registry-preprod",
    "mcp-preprod",
    # Reserved for future use
    "test", "tests", "demo", "staging", "prod", "preprod", "dev",
})


# RFC 1035 host label, lowered: starts/ends alphanumeric, hyphens allowed
# in the middle, 1–63 chars total. Single-char slugs are allowed but
# pointless; the by-slug endpoint will accept them.
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class SlugError(ValueError):
    """Raised when a slug fails validation."""


def slugify(value: str) -> str:
    """Normalize a free-text org name into a candidate slug.

    Strips diacritics (Turkish: ö→o, ü→u, ş→s, ı→i, ç→c, ğ→g), lowercases,
    replaces any run of non-alphanumeric chars with a single hyphen, and
    trims leading/trailing hyphens. Output is not guaranteed to be valid
    (still may be empty or reserved) — callers must follow up with
    `validate_slug()` before persisting.
    """
    # Unicode NFKD splits accented chars into base + combining mark; we then
    # strip the marks. Turkish ı (dotless i) and İ are handled explicitly
    # because NFKD does not decompose them into "i".
    value = value.replace("ı", "i").replace("İ", "i")
    value = value.replace("ş", "s").replace("Ş", "s")
    value = value.replace("ğ", "g").replace("Ğ", "g")
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    hyphenated = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return hyphenated[:63]


def validate_slug(slug: Optional[str]) -> str:
    """Validate a slug; return it unchanged on success.

    Rejects empty/None, length > 63, charset violations, and reserved labels.
    Raises SlugError with a user-facing Turkish message on failure.
    """
    if not slug:
        raise SlugError("Subdomain (slug) boş olamaz")
    if len(slug) > 63:
        raise SlugError("Subdomain en fazla 63 karakter olabilir")
    if not _SLUG_RE.match(slug):
        raise SlugError(
            "Subdomain yalnızca küçük harf, rakam ve tire içerebilir; "
            "tire ile başlayamaz/bitemez"
        )
    if slug in RESERVED_SLUGS:
        raise SlugError(f"'{slug}' rezerve bir subdomain'dir, başka bir isim seçin")
    return slug
