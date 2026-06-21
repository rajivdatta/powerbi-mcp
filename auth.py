"""Azure AD authentication for the Power BI MCP server.

Uses MSAL to obtain delegated access tokens for the Power BI REST API.
On Windows the OS broker (WAM) is used for the interactive sign-in, and the
resulting token is cached on disk so the sign-in is only needed once. After
that, tokens are refreshed silently.

Run `python server.py --login` once to perform the interactive sign-in.
"""
from __future__ import annotations

import os
import pathlib

import msal

# The public Azure CLI application id. It is a Microsoft first-party public
# client that supports delegated Power BI access and works with the Windows
# broker. Override with POWERBI_CLIENT_ID to use your own app registration.
DEFAULT_CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"

# `.default` requests every delegated Power BI scope already consented to the
# client, which is what we want for read-style discovery and DAX execution.
POWERBI_SCOPES = ["https://analysis.windows.net/powerbi/api/.default"]


def _cache_path() -> pathlib.Path:
    base = os.environ.get("LOCALAPPDATA") or pathlib.Path.home()
    folder = pathlib.Path(base) / "powerbi-mcp"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "token_cache.bin"


class TokenProvider:
    """Acquires and caches Power BI access tokens via MSAL."""

    def __init__(self, client_id: str | None = None, tenant_id: str | None = None):
        self.client_id = client_id or os.environ.get("POWERBI_CLIENT_ID", DEFAULT_CLIENT_ID)
        # "organizations" lets any work/school account sign in. Set
        # POWERBI_TENANT_ID to pin the server to a single tenant.
        self.tenant_id = tenant_id or os.environ.get("POWERBI_TENANT_ID", "organizations")

        self._cache = msal.SerializableTokenCache()
        self._cache_file = _cache_path()
        if self._cache_file.exists():
            self._cache.deserialize(self._cache_file.read_text(encoding="utf-8"))

        self._app = msal.PublicClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            token_cache=self._cache,
            enable_broker_on_windows=True,
        )

    def _flush(self) -> None:
        if self._cache.has_state_changed:
            self._cache_file.write_text(self._cache.serialize(), encoding="utf-8")

    def sign_in(self) -> str:
        """Run the one-time interactive sign-in. Returns the signed-in UPN."""
        result = self._app.acquire_token_interactive(
            POWERBI_SCOPES,
            parent_window_handle=self._app.CONSOLE_WINDOW_HANDLE,
        )
        self._flush()
        if "access_token" not in result:
            raise RuntimeError(result.get("error_description", "Interactive sign-in failed."))
        return result.get("id_token_claims", {}).get("preferred_username", "")

    def access_token(self) -> str:
        """Return a valid access token, refreshing silently from the cache."""
        accounts = self._app.get_accounts()
        result = self._app.acquire_token_silent(POWERBI_SCOPES, account=accounts[0]) if accounts else None
        if not result or "access_token" not in result:
            raise RuntimeError(
                "No cached Power BI credentials. Run `python server.py --login` to sign in."
            )
        self._flush()
        return result["access_token"]
