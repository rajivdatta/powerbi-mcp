# powerbi-mcp

A small [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for
**Microsoft Power BI**. It lets an MCP-capable client (Claude, VS Code, etc.)
discover your workspaces and datasets, read a semantic model's structure, and run
DAX queries — all through the public Power BI and Microsoft Fabric REST APIs.

Authentication uses **MSAL with the Windows broker (WAM)**: you sign in once,
the token is cached locally, and the server refreshes it silently afterwards.
No tokens are ever pasted by hand or stored in config.

## Tools

| Tool | Description |
| --- | --- |
| `list_workspaces` | List the workspaces (groups) you can access. |
| `list_datasets` | List the datasets (semantic models) in a workspace. |
| `get_model_definition` | Return a model's TMDL: tables, columns, measures (with DAX) and relationships. |
| `run_dax` | Execute a DAX query and return the rows as JSON. |

## Requirements

- Python 3.10+
- A Power BI account with access to at least one workspace
- Windows is recommended (the interactive sign-in uses the OS broker)

## Setup

```bash
git clone https://github.com/<your-username>/powerbi-mcp.git
cd powerbi-mcp
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Sign in once (opens an interactive prompt and caches the token):

```bash
python server.py --login
```

## Configuration

All configuration is optional and supplied via environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `POWERBI_TENANT_ID` | `organizations` | Pin to a single Azure AD tenant (GUID or domain). |
| `POWERBI_CLIENT_ID` | Azure CLI public client | Use your own app registration instead. |

See [`.env.example`](.env.example).

## Using it with an MCP client

Point your client at `server.py`. Example MCP config (see
[`examples/mcp.json`](examples/mcp.json)):

```json
{
  "mcpServers": {
    "powerbi": {
      "command": "python",
      "args": ["C:\\path\\to\\powerbi-mcp\\server.py"],
      "env": { "POWERBI_TENANT_ID": "your-tenant-id-or-domain" }
    }
  }
}
```

A typical flow: `list_workspaces` -> `list_datasets` -> `get_model_definition`
(to learn the table and measure names) -> `run_dax`.

## Security

The MSAL token cache (`%LOCALAPPDATA%\powerbi-mcp\token_cache.bin`) contains a
refresh token. Treat it like a password; it is git-ignored and should never be
committed.

## License

[MIT](LICENSE) (c) 2026 Rajiv Datta
