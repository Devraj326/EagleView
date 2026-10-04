"""User isolation for the owner's-rights (warehouse-runtime) deployment.

True per-viewer RBAC enforcement (the app's SQL connection itself running as
the caller) needs Snowflake's "restricted caller's rights" feature, which as
of 2026 only works on the *container* runtime (a compute pool), not the
classic warehouse runtime this app deploys on — see deploy.py's comment.

Instead: `st.user.user_name` reliably identifies the real, logged-in
Snowflake viewer even in owner's-rights mode (Streamlit's own viewer-identity
API — this is not something the app can spoof, since it comes from the Snowsight
session, not from request data). Every dataset write and every generated query
is then explicitly scoped, in code, to that viewer's own assigned schema, with
the SQL validator as a second, independent enforcement layer. This is real
Snowflake identity with no separate login system — just enforced in the
application layer rather than by a GRANT, given the trial-tier/runtime
constraint above.
"""

import streamlit as st

DATABASE = "EGLE_VIEW"

# Extend this for more demo accounts; each username needs a matching
# CREATE USER + schema grant (see setup_rbac.sql).
USER_SCHEMA_MAP = {
    "DEMO_USER_A": "DEMO_A",
    "DEMO_USER_B": "DEMO_B",
}


class UnrecognizedViewerError(Exception):
    pass


def current_context(session) -> dict:
    user = getattr(st, "user", None)
    viewer = getattr(user, "user_name", None)
    if not viewer:
        legacy_user = getattr(st, "experimental_user", None)
        viewer = getattr(legacy_user, "user_name", None)
    if not viewer:
        # st.user.user_name is populated by the Snowsight/SiS runtime only —
        # a plain local `streamlit run` has no such identity. Fall back to a
        # manual picker purely for local testing; the deployed app never hits
        # this branch since real viewers always have a user_name.
        with st.sidebar:
            st.caption("⚠️ Local dev mode — no Snowsight viewer identity")
            viewer = st.selectbox("Test as", list(USER_SCHEMA_MAP.keys()), key="local_dev_viewer")
    schema = USER_SCHEMA_MAP.get(viewer.upper())
    if schema is None:
        raise UnrecognizedViewerError(
            f"User '{viewer}' has no dataset schema mapped in USER_SCHEMA_MAP. "
            "Ask an admin to provision this user (see snowflake_app/setup_rbac.sql)."
        )
    return {"role": None, "user": viewer, "database": DATABASE, "schema": schema}
