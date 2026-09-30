import uuid

from sqlalchemy.orm import Session

from app.models import ConversationMessage

HISTORY_LIMIT = 8


def new_session_id() -> str:
    return uuid.uuid4().hex


def get_recent_history(db: Session, user_id: str, session_id: str) -> list[ConversationMessage]:
    return (
        db.query(ConversationMessage)
        .filter(ConversationMessage.user_id == user_id, ConversationMessage.session_id == session_id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(HISTORY_LIMIT)
        .all()[::-1]
    )


def history_to_text(history: list[ConversationMessage]) -> str:
    if not history:
        return "(no prior conversation in this session)"
    lines = []
    for msg in history:
        role = "User" if msg.role == "user" else "Assistant"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines)


def append_message(
    db: Session,
    user_id: str,
    session_id: str,
    role: str,
    content: str,
    entity_type: str = "",
    entity_id: str = "",
    sql_generated: str = "",
) -> None:
    db.add(
        ConversationMessage(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            entity_type=entity_type,
            entity_id=entity_id,
            sql_generated=sql_generated,
        )
    )
    db.commit()
