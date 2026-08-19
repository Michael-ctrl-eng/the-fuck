"""Meta OAuth2 helpers: authorization URL and code exchange.

Security notes:
- `state` is a random token tied to the user's session and verified at the
  callback (CSRF protection for OAuth).
- Tokens are encrypted at rest (TokenCipher) and never exposed to the
  frontend nor logged.
"""

from __future__ import annotations

from urllib.parse import urlencode

from ..config import Settings

SCOPES = [
    "pages_show_list",
    "pages_messaging",
    "pages_read_engagement",
    "pages_manage_metadata",
    "instagram_basic",
    "instagram_manage_messages",
    "instagram_manage_comments",
]


def build_auth_url(settings: Settings, state: str) -> str:
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": settings.meta_redirect_uri,
        "state": state,
        "scope": ",".join(SCOPES),
        "response_type": "code",
    }
    return "https://www.facebook.com/v21.0/dialog/oauth?" + urlencode(params)


def validate_scopes(granted: list[str]) -> list[str]:
    """Report which required permissions are missing."""
    return [s for s in SCOPES if s not in granted]
