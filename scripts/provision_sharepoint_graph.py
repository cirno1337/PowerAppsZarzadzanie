#!/usr/bin/env python3
"""Provisions the Applications/DocumentationJobs/DocumentationVersions/
Configuration lists (with columns) and the PowerPlatformDocumentation
document library on a real SharePoint site, using Microsoft Graph.

This is a verified, working alternative to
``sharepoint/provisioning/provision-lists.ps1`` (which requires PnP
PowerShell and has not been run against a real tenant) — this script *has*
been run successfully end-to-end against a real SharePoint site (2026-09).
See ``docs/SHAREPOINT_SETUP.md``.

Column definitions are read from ``sharepoint/lists/*.json`` — the single
source of truth (see ``sharepoint/README.md``) — so this script and the
documentation can't silently drift apart.

Requires an Azure AD app registration with a Microsoft Graph
**Application** permission of ``Sites.Manage.All`` (or broader), with
admin consent granted — see docs/CORPORATE_SETUP.md Phase 3. Reads four
values from environment variables (or a local, git-ignored ``.env`` file
at the repo root) and NEVER logs their values:

    TENANT_ID
    CLIENT_ID
    CLIENT_SECRET
    SHAREPOINT_SITE_URL

Usage:
    pip install msal requests
    python3 scripts/provision_sharepoint_graph.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import msal
import requests

GRAPH_APP_SCOPE = ["https://graph.microsoft.com/.default"]
GRAPH = "https://graph.microsoft.com/v1.0"

REPO_ROOT = Path(__file__).resolve().parents[1]
LISTS_DIR = REPO_ROOT / "sharepoint" / "lists"
ENV_FILE = REPO_ROOT / ".env"

LIST_FILES = ["Applications.json", "DocumentationJobs.json", "DocumentationVersions.json", "Configuration.json"]
DOCUMENT_LIBRARY_NAME = "PowerPlatformDocumentation"
DOCUMENT_LIBRARY_FOLDERS = ("_jobs", "_templates", "_logs")

BUILT_IN_COLUMNS = ("Title", "ID", "Created", "Modified", "Author", "Editor")

TYPE_TO_GRAPH_COLUMN = {
    "Single line of text": lambda col: {"text": {}},
    "Multiple lines of text": lambda col: {"text": {"allowMultipleLines": True}},
    "Number": lambda col: {"number": {}},
    "Yes/No": lambda col: {"boolean": {}},
    "Date and Time": lambda col: {"dateTime": {"format": "dateTime"}},
    "Person or Group": lambda col: {"personOrGroup": {"allowMultipleSelection": False}},
    "Hyperlink or Picture": lambda col: {"hyperlinkOrPicture": {"isPicture": False}},
    "Choice": lambda col: {"choice": {"choices": col.get("choices", []), "allowTextEntry": False}},
}


def _load_env_file(path: Path) -> dict:
    """Minimal .env parser. Values are read into memory only — never
    printed or logged anywhere in this script."""
    if not path.exists():
        return {}
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _config() -> dict:
    env = {**_load_env_file(ENV_FILE), **os.environ}
    missing = [k for k in ("TENANT_ID", "CLIENT_ID", "CLIENT_SECRET", "SHAREPOINT_SITE_URL") if not env.get(k)]
    if missing:
        raise RuntimeError(f"Missing required config: {', '.join(missing)} (set in .env or the environment)")
    return env


def get_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(scopes=GRAPH_APP_SCOPE)
    if "access_token" not in result:
        # error/error_description are safe to surface (e.g. missing admin
        # consent); the rest of the MSAL result can echo request metadata,
        # so it's deliberately not printed in full.
        raise RuntimeError(f"Auth failed: {result.get('error')}: {result.get('error_description')}")
    return result["access_token"]


def graph_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def get_site_id(token: str, site_url: str) -> str:
    parsed = urlparse(site_url)
    resp = requests.get(f"{GRAPH}/sites/{parsed.netloc}:{parsed.path}", headers=graph_headers(token))
    resp.raise_for_status()
    return resp.json()["id"]


def _find_existing_list_id(token: str, site_id: str, name: str) -> str:
    resp = requests.get(
        f"{GRAPH}/sites/{site_id}/lists", headers=graph_headers(token), params={"$filter": f"displayName eq '{name}'"}
    )
    resp.raise_for_status()
    return resp.json()["value"][0]["id"]


def build_graph_columns(list_def: dict) -> list[dict]:
    """Convert a sharepoint/lists/*.json column definition into Graph
    columnDefinition payloads. Skips built-in columns and Lookup columns
    (added in a second pass, once every list's real id is known)."""
    columns = []
    for col in list_def["columns"]:
        if col["name"] in BUILT_IN_COLUMNS or col["type"] == "Lookup":
            continue
        builder = TYPE_TO_GRAPH_COLUMN.get(col["type"])
        if builder is None:
            print(f"  WARNING: no Graph mapping for type '{col['type']}' (column '{col['name']}') -- skipping")
            continue
        payload = {"name": col["name"], "description": col.get("notes", "") or ""}
        payload.update(builder(col))
        columns.append(payload)
    return columns


def create_list(token: str, site_id: str, list_def: dict) -> str:
    name = list_def["listName"]
    payload = {"displayName": name, "columns": build_graph_columns(list_def), "list": {"template": "genericList"}}
    print(f"Creating list '{name}' with {len(payload['columns'])} custom columns...")
    resp = requests.post(f"{GRAPH}/sites/{site_id}/lists", headers=graph_headers(token), json=payload)
    if resp.status_code == 409:
        print(f"  '{name}' already exists, reusing it.")
        return _find_existing_list_id(token, site_id, name)
    if not resp.ok:
        print(f"  FAILED ({resp.status_code}): {resp.text[:2000]}")
        resp.raise_for_status()
    list_id = resp.json()["id"]
    print(f"  Created '{name}' -> {list_id}")
    return list_id


def add_lookup_columns(token: str, site_id: str, list_def: dict, list_ids: dict) -> None:
    lookups = [c for c in list_def["columns"] if c["type"] == "Lookup"]
    if not lookups:
        return
    this_list_id = list_ids[list_def["listName"]]
    for col in lookups:
        target_list_id = list_ids.get(col["lookupList"])
        if not target_list_id:
            print(f"  WARNING: lookup target list '{col['lookupList']}' not found -- skipping '{col['name']}'")
            continue
        payload = {
            "name": col["name"],
            "description": col.get("notes", "") or "",
            "lookup": {"listId": target_list_id, "columnName": col.get("lookupField", "Title")},
        }
        print(f"  Adding lookup column '{col['name']}' -> {col['lookupList']} ...")
        resp = requests.post(
            f"{GRAPH}/sites/{site_id}/lists/{this_list_id}/columns", headers=graph_headers(token), json=payload
        )
        if resp.ok:
            print("    OK")
        elif resp.status_code == 409:
            print("    already exists")
        else:
            print(f"    FAILED ({resp.status_code}): {resp.text[:2000]}")


def create_document_library(token: str, site_id: str) -> str:
    print(f"Creating document library '{DOCUMENT_LIBRARY_NAME}'...")
    resp = requests.post(
        f"{GRAPH}/sites/{site_id}/lists",
        headers=graph_headers(token),
        json={"displayName": DOCUMENT_LIBRARY_NAME, "list": {"template": "documentLibrary"}},
    )
    if resp.status_code == 409:
        print("  already exists")
        list_id = _find_existing_list_id(token, site_id, DOCUMENT_LIBRARY_NAME)
    else:
        resp.raise_for_status()
        list_id = resp.json()["id"]
        print(f"  Created -> {list_id}")

    drive_resp = requests.get(f"{GRAPH}/sites/{site_id}/lists/{list_id}/drive", headers=graph_headers(token))
    drive_resp.raise_for_status()
    drive_id = drive_resp.json()["id"]

    for folder in DOCUMENT_LIBRARY_FOLDERS:
        folder_resp = requests.post(
            f"{GRAPH}/drives/{drive_id}/root/children",
            headers=graph_headers(token),
            json={"name": folder, "folder": {}, "@microsoft.graph.conflictBehavior": "replace"},
        )
        print(f"  Folder '{folder}' {'OK' if folder_resp.ok else 'FAILED ' + str(folder_resp.status_code)}")
    return list_id


def main() -> None:
    config = _config()
    token = get_token(config["TENANT_ID"], config["CLIENT_ID"], config["CLIENT_SECRET"])
    site_id = get_site_id(token, config["SHAREPOINT_SITE_URL"])
    print(f"Site id: {site_id}")

    list_defs = [json.loads((LISTS_DIR / f).read_text(encoding="utf-8")) for f in LIST_FILES]

    list_ids: dict[str, str] = {}
    for list_def in list_defs:
        list_ids[list_def["listName"]] = create_list(token, site_id, list_def)

    for list_def in list_defs:
        add_lookup_columns(token, site_id, list_def, list_ids)

    create_document_library(token, site_id)

    print("\nDone. List ids:")
    for name, list_id in list_ids.items():
        print(f"  {name}: {list_id}")


if __name__ == "__main__":
    main()
