import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.models import User
from app.security import get_current_user
from app.services import snowpark_service  # noqa: F401 - sets up sf_lib's import path as a side effect

from sf_lib import query_pipeline  # noqa: E402
from sf_lib.activity_log import capture  # noqa: E402

logger = logging.getLogger("app.query")
router = APIRouter(prefix="/api/query", tags=["query"])


class QueryRequest(BaseModel):
    question: str
    session_id: str | None = None


@router.post("")
def ask_question(body: QueryRequest, user: User = Depends(get_current_user)) -> dict:
    session, ctx = snowpark_service.ready_context(user)
    with capture() as entries:
        result = query_pipeline.ask_question(
            session, ctx, body.question, body.session_id,
            session_factory=snowpark_service.new_session,
        )
    result["agent_log"] = entries
    return result
