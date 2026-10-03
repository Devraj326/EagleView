# EgleView MCP server

Exposes exactly two EgleView capabilities as MCP tools — nothing more:

- **`upload_data(filename, content_base64)`** — uploads a CSV/Excel/JSON file, lets the
  Orchestrator + domain agents route and propose a schema, and auto-confirms their own
  proposal (no manual review step) to merge it into Snowflake.
- **`ask_question(question, session_id=None)`** — asks a natural-language question; the
  relevant domain agent(s) are consulted automatically.

Both are thin, validated proxies onto the real FastAPI backend
(`backend/app/routers/datasets.py` / `query.py`) — no pipeline logic is reimplemented here.

## Auth

This server does not have its own user system. It requires `EGLEVIEW_API_TOKEN` — a real JWT
obtained by signing in through the backend's own `/api/auth/demo` or `/api/auth/google`
endpoint — and acts only as whichever EgleView user that token belongs to. The token is
checked against `GET /api/auth/me` before any tool call is allowed through; a missing,
invalid, or expired token fails clearly instead of as a confusing downstream 401.

## Validation

- `upload_data` rejects anything not ending in `.csv`/`.xlsx`/`.xls`/`.json`, invalid base64,
  empty files, and anything over 25MB.
- `ask_question` rejects empty or excessively long (>2000 char) questions.

## Setup

```bash
cd mcp_server
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Get a real token from your running backend (demo login, or swap in a Google token)
curl -s -X POST http://localhost:8001/api/auth/demo \
  -H "Content-Type: application/json" -d '{"demo_id":"demo-a"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['token'])"
```

## Run

```bash
EGLEVIEW_API_TOKEN=<token from above> \
EGLEVIEW_API_BASE_URL=http://localhost:8001 \
python server.py
```

Configure as an MCP server (stdio transport) in Claude Desktop / Claude Code / any MCP
client, pointing its command at this `server.py` with those two environment variables set.
