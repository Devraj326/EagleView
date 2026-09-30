# DataMind — AI-Powered Multi-Agent Data Ingestion & Analytics Platform

Upload raw business data → AI classifies it and proposes a Snowflake schema → you review
and confirm → data lands in your own isolated Snowflake schema → ask questions about it
in plain English, including deep "what happened with order 1234?" style investigations.

## Stack

- **Backend**: FastAPI (Python 3.12), SQLite for app metadata, Snowflake for analytical data,
  Gemini for every AI agent (classification, schema, query understanding, SQL generation,
  result interpretation), Google Sign-In for auth.
- **Frontend**: React + TypeScript + Vite, Apple-HIG-inspired design system, Recharts for
  visualization.

## Architecture

```
frontend/          React app (onboarding flow + analytics dashboard)
backend/
  app/
    routers/        auth.py, datasets.py, query.py — the HTTP surface
    services/
      gemini_client.py               thin Gemini wrapper shared by every agent
      classification_service.py      Classification Agent (Stage 1)
      domain_agents.py               registry of the 6 specialized domain agents
      schema_service.py              schema proposal, column casting, relationship discovery
      snowflake_service.py           the SnowflakeQueryService — schema/table DDL, load, execute
      sql_validator.py               read-only + per-user-schema SQL firewall
      query_understanding_service.py Query Understanding Agent (Stage 2)
      sql_generation_service.py      SQL Generation Agent
      result_interpretation_service.py  Result Agent → natural language + timeline/summary
      conversation_service.py        follow-up context per chat session
      catalog_service.py             renders a user's tables/columns/relationships for prompts
      dataset_service.py             the single per-user ownership check (isolation chokepoint)
    models.py, schemas.py, security.py, config.py, db.py
```

**Isolation model**: one Snowflake database, one schema per user (`USER_<sha256 hash>` —
never the raw user id), tables named by dataset type inside it. Every dataset row, every
query, and every generated SQL statement is scoped through the authenticated user's own
schema; `sql_validator.py` rejects anything else, plus any non-`SELECT` statement.

**"Snowflake Agent / COCO CLI"**: there's no `snow`/COCO CLI binary available in this
environment, so `SnowflakeQueryService` (in `snowflake_service.py`) does NL→SQL generation
via Gemini and execution via `snowflake-connector-python`, isolated behind one interface —
swap in a real Cortex Agents/COCO CLI call later without touching any caller.

## Setup

### 1. Backend

```bash
cd backend
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in the values below
uvicorn app.main:app --reload --port 8000
```

Fill in `backend/.env`:
- `JWT_SECRET` — any long random string
- `GOOGLE_CLIENT_ID` — OAuth 2.0 Client ID from console.cloud.google.com (Web application,
  authorized JavaScript origin `http://localhost:5173`)
- `GEMINI_API_KEY` — from Google AI Studio
- `SNOWFLAKE_ACCOUNT` / `SNOWFLAKE_USER` / `SNOWFLAKE_PASSWORD` (or
  `SNOWFLAKE_PRIVATE_KEY_PATH`) / `SNOWFLAKE_ROLE` / `SNOWFLAKE_WAREHOUSE` /
  `SNOWFLAKE_DATABASE` — the role needs `CREATE SCHEMA` on that database and
  `CREATE TABLE`/`INSERT`/`SELECT` within it.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # VITE_GOOGLE_CLIENT_ID must match the backend's GOOGLE_CLIENT_ID
npm run dev
```

Open http://localhost:5173.

## Definition of done (matches the spec)

1. Sign in with Google.
2. Upload `orders.csv` (or any business CSV/Excel/JSON) on **Upload data**.
3. AI classifies it, routes to a specialized agent, proposes a schema.
4. Review/edit the column mapping, rename the table if you like, confirm.
5. Data lands in your own Snowflake schema; dataset shows **Ready**.
6. Go to **Dashboard**, ask "What was our total revenue last month?" or
   "What happened with order 1234?" — answered in plain English, grounded only in
   what's actually in your data.
7. A second Google account never sees the first account's datasets or data.
