"""MCP server exposing exactly two EgleView capabilities: uploading a data
file and asking a natural-language question. Nothing else is exposed on
purpose — this is a thin, validated, authenticated proxy onto the real
FastAPI backend (`backend/app/routers/datasets.py` and `query.py`), not a
reimplementation of any pipeline logic.

Auth: requires EGLEVIEW_API_TOKEN, a real JWT obtained by signing in through
the backend's own /api/auth/demo or /api/auth/google endpoint. This server
does not implement its own user system or accept arbitrary credentials — it
only ever acts as the one already-authenticated EgleView user that token
belongs to, and the token is checked against /api/auth/me before any tool
call is allowed through.

Run:
    EGLEVIEW_API_TOKEN=<jwt> EGLEVIEW_API_BASE_URL=http://localhost:8001 \
        python server.py
"""

import base64
import os
import sys

import httpx
from mcp.server.mcpserver import MCPServer

API_BASE = os.environ.get("EGLEVIEW_API_BASE_URL", "http://localhost:8001")
API_TOKEN = os.environ.get("EGLEVIEW_API_TOKEN", "")

ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls", "json"}
MAX_UPLOAD_MB = 25
MAX_QUESTION_CHARS = 2000
REQUEST_TIMEOUT_SECONDS = 180.0

if not API_TOKEN:
    print(
        "FATAL: EGLEVIEW_API_TOKEN is not set. Sign in via POST /api/auth/demo "
        "(or /api/auth/google) against the EgleView backend and pass the returned "
        "token as EGLEVIEW_API_TOKEN.",
        file=sys.stderr,
    )
    sys.exit(1)

mcp = MCPServer("egleview")

_auth_checked = False


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=API_BASE,
        headers={"Authorization": f"Bearer {API_TOKEN}"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


def _ensure_authenticated() -> None:
    """Validates EGLEVIEW_API_TOKEN against the real backend exactly once per
    process, so a bad/expired token fails clearly instead of as a confusing
    downstream 401 on whichever tool happened to run first.
    """
    global _auth_checked
    if _auth_checked:
        return
    with _client() as client:
        resp = client.get("/api/auth/me")
    if resp.status_code != 200:
        raise RuntimeError(
            f"EGLEVIEW_API_TOKEN is invalid or expired (backend returned {resp.status_code}). "
            "Sign in again and set a fresh token."
        )
    _auth_checked = True


@mcp.tool()
def upload_data(filename: str, content_base64: str) -> dict:
    """Upload a business data file into EgleView.

    The Orchestrator Agent routes the file's columns across whichever domain
    agent(s) they belong to (customer, order, finance, delivery, product,
    inventory, supplier). Each domain agent's own proposed column mapping is
    accepted as-is (no manual review step here) before the data is merged and
    loaded into that domain's Snowflake table.

    Args:
        filename: original filename; must end in .csv, .xlsx, .xls, or .json
        content_base64: the file's raw bytes, base64-encoded
    """
    _ensure_authenticated()

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '.{ext}' - must be one of: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    try:
        raw = base64.b64decode(content_base64, validate=True)
    except Exception as exc:  # noqa: BLE001 - surfaced as a clear tool error
        raise ValueError(f"content_base64 is not valid base64: {exc}") from exc

    if len(raw) == 0:
        raise ValueError("File is empty")
    size_mb = len(raw) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        raise ValueError(f"File is {size_mb:.1f}MB, over the {MAX_UPLOAD_MB}MB limit")

    with _client() as client:
        upload_resp = client.post("/api/datasets/upload", files={"file": (filename, raw)})
        if upload_resp.status_code != 200:
            raise RuntimeError(f"Upload failed ({upload_resp.status_code}): {upload_resp.text}")
        dataset = upload_resp.json()
        dataset_id = dataset["id"]

        analyze_resp = client.post(f"/api/datasets/{dataset_id}/analyze")
        if analyze_resp.status_code != 200:
            raise RuntimeError(f"Analysis failed ({analyze_resp.status_code}): {analyze_resp.text}")
        analyzed = analyze_resp.json()

        confirm_body = {
            "domains": [
                {
                    "domain_id": d["domain_id"],
                    "columns": [
                        {
                            "id": col["id"],
                            "target_column": col["target_column"],
                            "target_type": col["target_type"],
                            "nullable": col["nullable"],
                            "include": col["include"],
                        }
                        for col in d["columns"]
                    ],
                }
                for d in analyzed["domains"]
            ]
        }
        confirm_resp = client.post(f"/api/datasets/{dataset_id}/confirm", json=confirm_body)
        if confirm_resp.status_code != 200:
            raise RuntimeError(f"Merge failed ({confirm_resp.status_code}): {confirm_resp.text}")
        confirmed = confirm_resp.json()

    return {
        "dataset_id": dataset_id,
        "name": dataset["name"],
        "domains": confirmed["domains"],
    }


@mcp.tool()
def ask_question(question: str, session_id: str | None = None) -> dict:
    """Ask a natural-language question about data already ingested into EgleView.

    The relevant domain agent(s) are consulted automatically based on the
    question's content.

    Args:
        question: your question, in plain English
        session_id: optional - pass back a previous response's session_id to continue that conversation
    """
    _ensure_authenticated()

    question = question.strip()
    if not question:
        raise ValueError("question must not be empty")
    if len(question) > MAX_QUESTION_CHARS:
        raise ValueError(f"question is too long ({len(question)} chars, max {MAX_QUESTION_CHARS})")

    with _client() as client:
        resp = client.post("/api/query", json={"question": question, "session_id": session_id})
    if resp.status_code != 200:
        raise RuntimeError(f"Query failed ({resp.status_code}): {resp.text}")

    body = resp.json()
    return {
        "answer": body.get("answer"),
        "entity": body.get("entity"),
        "agents_consulted": body.get("agents_consulted"),
        "session_id": body.get("session_id"),
    }


if __name__ == "__main__":
    mcp.run()
