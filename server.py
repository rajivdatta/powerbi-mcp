"""powerbi-mcp - a Model Context Protocol server for Microsoft Power BI.

Exposes a small, focused tool set over the public Power BI and Microsoft
Fabric REST APIs:

  * list_workspaces       - workspaces (groups) you can access
  * list_datasets         - semantic models inside a workspace
  * get_model_definition  - a model's TMDL (tables, columns, measures, ...)
  * run_dax               - execute a DAX query and return the rows

Authentication is handled by auth.TokenProvider (MSAL + Windows broker).
Sign in once with:  python server.py --login
Then start the server with:  python server.py
"""
from __future__ import annotations

import base64
import json
import sys
import time

import requests
from fastmcp import FastMCP

from auth import TokenProvider

POWERBI_API = "https://api.powerbi.com/v1.0/myorg"
FABRIC_API = "https://api.fabric.microsoft.com/v1"

mcp = FastMCP("powerbi-mcp")
_tokens = TokenProvider()


# --------------------------------------------------------------------------- #
# Low-level HTTP helpers
# --------------------------------------------------------------------------- #
def _auth_header() -> dict:
    return {"Authorization": f"Bearer {_tokens.access_token()}"}


def _get_json(url: str) -> dict:
    resp = requests.get(url, headers=_auth_header(), timeout=60)
    resp.raise_for_status()
    return resp.json()


def _post(url: str, body: dict | None = None) -> requests.Response:
    headers = {**_auth_header(), "Content-Type": "application/json"}
    return requests.post(url, headers=headers, json=body, timeout=120)


def _await_operation(location: str, interval: int = 5, timeout: int = 300) -> dict:
    """Poll a Fabric long-running operation until it succeeds, then return its result."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(interval)
        status_resp = requests.get(location, headers=_auth_header(), timeout=60)
        status_resp.raise_for_status()
        body = status_resp.json()
        state = body.get("status")
        if state == "Succeeded":
            result = requests.get(f"{location}/result", headers=_auth_header(), timeout=60)
            result.raise_for_status()
            return result.json()
        if state == "Failed":
            raise RuntimeError(f"Operation failed: {body.get('error')}")
    raise TimeoutError("Timed out waiting for the operation to complete.")


# --------------------------------------------------------------------------- #
# MCP tools
# --------------------------------------------------------------------------- #
@mcp.tool()
def list_workspaces() -> str:
    """List the Power BI workspaces (groups) the signed-in user can access.

    Returns a JSON array of objects with `id` and `name`.
    """
    workspaces = _get_json(f"{POWERBI_API}/groups").get("value", [])
    return json.dumps([{"id": w["id"], "name": w["name"]} for w in workspaces], indent=2)


@mcp.tool()
def list_datasets(workspace_id: str) -> str:
    """List the datasets (semantic models) inside a workspace.

    Returns a JSON array of objects with `id` and `name`.
    """
    datasets = _get_json(f"{POWERBI_API}/groups/{workspace_id}/datasets").get("value", [])
    return json.dumps([{"id": d["id"], "name": d["name"]} for d in datasets], indent=2)


@mcp.tool()
def get_model_definition(workspace_id: str, dataset_id: str) -> str:
    """Return a semantic model's definition in TMDL form.

    Includes tables, columns, measures (with their DAX) and relationships.
    Useful context to gather before writing a DAX query with `run_dax`.
    """
    url = f"{FABRIC_API}/workspaces/{workspace_id}/semanticModels/{dataset_id}/getDefinition"
    resp = _post(url)

    if resp.status_code == 202:
        payload = _await_operation(resp.headers["Location"], int(resp.headers.get("Retry-After", 5)))
    elif resp.ok:
        payload = resp.json()
    else:
        return f"Could not read model definition: HTTP {resp.status_code} - {resp.text[:300]}"

    sections = []
    for part in payload.get("definition", {}).get("parts", []):
        path = part.get("path", "")
        if not path.endswith(".tmdl"):
            continue
        content = base64.b64decode(part["payload"]).decode("utf-8")
        sections.append(f"# === {path} ===\n{content}")

    return "\n\n".join(sections) if sections else "No TMDL parts were returned for this model."


@mcp.tool()
def run_dax(workspace_id: str, dataset_id: str, dax: str) -> str:
    """Execute a DAX query against a dataset and return the resulting rows as JSON.

    The query must be a complete DAX statement, e.g.
        EVALUATE SUMMARIZECOLUMNS('Date'[Year], "Sales", SUM('Sales'[Amount]))
    """
    url = f"{POWERBI_API}/groups/{workspace_id}/datasets/{dataset_id}/executeQueries"
    resp = _post(url, {"queries": [{"query": dax}]})
    if not resp.ok:
        return f"Query failed: HTTP {resp.status_code} - {resp.text[:300]}"

    results = resp.json().get("results", [])
    tables = results[0].get("tables", []) if results else []
    rows = tables[0].get("rows", []) if tables else []
    return json.dumps(rows, indent=2, default=str)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> None:
    if "--login" in sys.argv:
        upn = _tokens.sign_in()
        print(f"Signed in as {upn or 'the selected account'}. Token cached.")
        return
    mcp.run()


if __name__ == "__main__":
    main()
