"""A visible trail of every agent/LLM call this session makes. Framework-
agnostic: works identically from Streamlit (accumulates across the whole
browser session) or from a stateless FastAPI request (accumulates only for
the current request, via `capture()`).
"""

import contextvars
import logging

logger = logging.getLogger("app.activity")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

_current: contextvars.ContextVar[list | None] = contextvars.ContextVar("activity_log_current", default=None)

try:
    import streamlit as st

    def _streamlit_active() -> bool:
        try:
            return st.runtime.exists()
        except Exception:  # noqa: BLE001
            return False
except Exception:  # noqa: BLE001 - streamlit not installed in this environment
    st = None  # type: ignore[assignment]

    def _streamlit_active() -> bool:
        return False


def log(message: str) -> None:
    logger.info(message)

    captured = _current.get()
    if captured is not None:
        captured.append(message)

    if _streamlit_active():
        st.session_state.setdefault("agent_log", []).append(message)


class capture:
    """Context manager: collects every log() call made inside it into a list,
    for callers (like a FastAPI request) that need just this call's entries
    rather than a whole persistent session's worth.
    """

    def __enter__(self) -> list:
        self.entries: list = []
        self._token = _current.set(self.entries)
        return self.entries

    def __exit__(self, *exc) -> None:
        _current.reset(self._token)
