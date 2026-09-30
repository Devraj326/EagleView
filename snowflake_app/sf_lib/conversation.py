import uuid


def new_session_id() -> str:
    return uuid.uuid4().hex


def history_to_text(history: list[dict]) -> str:
    if not history:
        return "(no prior conversation in this session)"
    lines = []
    for msg in history:
        role = "User" if msg["ROLE"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['CONTENT']}")
    return "\n".join(lines)
