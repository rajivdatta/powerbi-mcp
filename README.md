# powerbi-mcp

A small [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for
**Microsoft Power BI**. It lets an MCP-capable client (Claude, VS Code, etc.)
discover your workspaces and datasets, read a semantic model's structure, and run
DAX queries — all through the public Power BI and Microsoft Fabric REST APIs.

Authentication uses **MSAL with the Windows broker (WAM)**: you sign in once, the
token is cached locally, and the server refreshes it silently afterwards. No
tokens are ever pasted by hand or stored in config.

## Tools

| Tool | Description |
| --- | --- |
| `list_workspaces` | List the workspaces (groups) you can access. |
| `list_datasets` | List the datasets (semantic models) in a workspace. |
| `get_model_definition` | Return a model's TMDL: tables, columns, measures (with DAX) and relationships. |
| `run_dax` | Execute a DAX query and return the rows as JSON. |

## Prerequisites

- **Python 3.10+**
- A **Power BI account** with access to at least one workspace
- **Windows recommended** — the interactive sign-in uses the OS broker (WAM).
  On macOS/Linux it falls back to the system browser.

---

## Setup (step by step)

### 1. Install

```powershell
git clone https://github.com/rajivdatta/powerbi-mcp.git
cd powerbi-mcp
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
```

### 2. (Optional) Configure your tenant

All configuration is optional and via environment variables — copy
[`.env.example`](.env.example) to `.env` if you want to set any:

| Variable | Default | Purpose |
| --- | --- | --- |
| `POWERBI_TENANT_ID` | `organizations` | Pin sign-in to one Azure AD tenant. Use a GUID or domain (e.g. `contoso.com`). Recommended for work accounts. |
| `POWERBI_CLIENT_ID` | Azure CLI public client | Override only if you want to use your own app registration. The default is a Microsoft first-party public client that works with the Windows broker. |

> **Finding your tenant ID:** Azure Portal → *Microsoft Entra ID* → *Overview* →
> *Tenant ID*, or just use your email domain. Leaving it unset (`organizations`)
> lets any work/school account sign in.

`.env` is git-ignored.

### 3. Sign in once

```powershell
.venv\Scripts\activate
python server.py --login
```

This opens an interactive sign-in (Windows broker popup or browser) and caches a
refresh token at `%LOCALAPPDATA%\powerbi-mcp\token_cache.bin`. After this, the
server refreshes access tokens **silently** on every call — no re-login needed.

To switch accounts later, just run `--login` again and pick the other account.

### 4. Test it standalone

```powershell
python -c "import server; print(server.list_workspaces())"
```

You should get a JSON list of your workspaces (each with an `id` and `name`).

### 5. Register with your MCP host

Point your client at `server.py` (see [`examples/mcp.json`](examples/mcp.json)).
Use the venv's Python so dependencies resolve:

```json
{
  "mcpServers": {
    "powerbi": {
      "command": "C:\\path\\to\\powerbi-mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\powerbi-mcp\\server.py"],
      "env": { "POWERBI_TENANT_ID": "your-tenant-id-or-domain" }
    }
  }
}
```

Restart your MCP client, then try: *"using powerbi, list my workspaces"*.

## Usage flow

A typical sequence:

1. `list_workspaces` → pick a workspace `id`
2. `list_datasets(workspace_id)` → pick a dataset `id`
3. `get_model_definition(workspace_id, dataset_id)` → learn table & measure names
4. `run_dax(workspace_id, dataset_id, "EVALUATE ...")` → get results

## Security

The MSAL token cache (`%LOCALAPPDATA%\powerbi-mcp\token_cache.bin`) contains a
refresh token. Treat it like a password — it lives outside the repo and is never
committed.

## License

[MIT](LICENSE) (c) 2026 Rajiv Datta
