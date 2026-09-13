"""Thin Microsoft Graph REST wrapper used by RealSharePointAdapter.

Verified interactively (2026-09) against a real SharePoint site on a
personal test tenant — list/column/library creation via
``scripts/provision_sharepoint_graph.py``, and item CRUD here. REQUIRES
CORPORATE ACCESS to re-verify against the company's own tenant.

Auth: app-only (client credentials), reading TENANT_ID/CLIENT_ID/
CLIENT_SECRET from environment variables set by the caller — this module
never logs their values. See docs/SHAREPOINT_SETUP.md.

``requests`` and ``msal`` are imported lazily (inside the methods that need
them) rather than at module level: this module is imported unconditionally
by ``worker/adapters/factory.py`` regardless of ``PPDM_SHAREPOINT_MODE``,
and the project's mock path must have zero third-party dependencies (see
CLAUDE.md) — only actually using ``PPDM_SHAREPOINT_MODE=real`` should
require them to be installed.
"""

from __future__ import annotations

from urllib.parse import urlparse

GRAPH = "https://graph.microsoft.com/v1.0"
GRAPH_APP_SCOPE = ["https://graph.microsoft.com/.default"]


class GraphError(RuntimeError):
    """A Graph call failed. Never includes the access token or credentials."""


class GraphClient:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, site_url: str):
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self.site_url = site_url
        self._token: str | None = None
        self._site_id: str | None = None

    def _get_token(self) -> str:
        if self._token:
            return self._token
        import msal  # imported lazily: only needed for PPDM_SHAREPOINT_MODE=real

        app = msal.ConfidentialClientApplication(
            self._client_id,
            authority=f"https://login.microsoftonline.com/{self._tenant_id}",
            client_credential=self._client_secret,
        )
        result = app.acquire_token_for_client(scopes=GRAPH_APP_SCOPE)
        if "access_token" not in result:
            raise GraphError(f"Graph auth failed: {result.get('error')}: {result.get('error_description')}")
        self._token = result["access_token"]
        return self._token

    def _headers(self, **extra) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json", **extra}

    @property
    def site_id(self) -> str:
        if self._site_id:
            return self._site_id
        parsed = urlparse(self.site_url)
        resp = self.request("GET", f"/sites/{parsed.netloc}:{parsed.path}")
        self._site_id = resp["id"]
        return self._site_id

    def request(self, method: str, path_or_url: str, **kwargs) -> dict | None:
        import requests

        url = path_or_url if path_or_url.startswith("http") else f"{GRAPH}{path_or_url}"
        headers = kwargs.pop("headers", {})
        resp = requests.request(method, url, headers=self._headers(**headers), **kwargs)
        if not resp.ok:
            raise GraphError(f"{method} {path_or_url} failed (HTTP {resp.status_code}): {resp.text[:500]}")
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def find_list_id(self, display_name: str) -> str:
        result = self.request(
            "GET", f"/sites/{self.site_id}/lists", params={"$filter": f"displayName eq '{display_name}'"}
        )
        values = result.get("value", [])
        if not values:
            raise GraphError(f"List '{display_name}' not found on {self.site_url}")
        return values[0]["id"]

    def list_items(self, list_id: str, filter_expr: str | None = None) -> list[dict]:
        params = {"expand": "fields"}
        headers = {}
        if filter_expr:
            params["$filter"] = filter_expr
            headers["Prefer"] = "HonorNonIndexedQueriesWarningMayFailRandomly"
        result = self.request("GET", f"/sites/{self.site_id}/lists/{list_id}/items", params=params, headers=headers)
        return result.get("value", [])

    def create_item(self, list_id: str, fields: dict) -> dict:
        return self.request("POST", f"/sites/{self.site_id}/lists/{list_id}/items", json={"fields": fields})

    def update_item_fields(self, list_id: str, item_id: str, fields: dict, etag: str | None = None) -> dict:
        headers = {"If-Match": etag} if etag else {}
        return self.request(
            "PATCH", f"/sites/{self.site_id}/lists/{list_id}/items/{item_id}/fields", json=fields, headers=headers
        )

    def get_item(self, list_id: str, item_id: str) -> dict:
        return self.request("GET", f"/sites/{self.site_id}/lists/{list_id}/items/{item_id}", params={"expand": "fields"})

    def upload_file(self, drive_path: str, content: str | bytes) -> dict:
        """PUT content to a document library path, e.g. 'PowerPlatformDocumentation/App/1.0/snapshot.json'."""
        if isinstance(content, str):
            content = content.encode("utf-8")
        return self.request(
            "PUT",
            f"/sites/{self.site_id}/drive/root:/{drive_path}:/content",
            data=content,
            headers={"Content-Type": "application/octet-stream"},
        )

    def read_file(self, drive_path: str) -> str:
        import requests

        url = f"{GRAPH}/sites/{self.site_id}/drive/root:/{drive_path}:/content"
        resp = requests.get(url, headers={"Authorization": f"Bearer {self._get_token()}"})
        if not resp.ok:
            raise GraphError(f"GET {drive_path} failed (HTTP {resp.status_code})")
        return resp.text
