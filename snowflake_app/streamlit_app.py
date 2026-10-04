"""EgleView — native Streamlit-in-Snowflake build.

No FastAPI, no external LLM, no separate app database: this single app runs
entirely inside Snowflake. An Orchestrator Agent splits each upload across
however many business domains it actually belongs to; N real, separately
defined Cortex Agents (one per domain, see sf_lib/domain_agents.py) merge
data into their own persistent table and answer questions about it. Isolated
per-user by real Snowflake RBAC (this app is deployed EXECUTE AS CALLER, so
CURRENT_ROLE() is genuinely the viewer's own role).
"""

import os

import pandas as pd
import streamlit as st
from snowflake.snowpark import Session
from snowflake.snowpark.context import get_active_session

from sf_lib import demo_seed, ingestion_pipeline, metadata, query_pipeline, rbac

st.set_page_config(page_title="EgleView", page_icon="🧠", layout="wide")


def _build_local_session():
    return Session.builder.configs({
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_LOCAL_USER"],
        "password": os.environ["SNOWFLAKE_LOCAL_PASSWORD"],
        "role": os.environ["SNOWFLAKE_LOCAL_ROLE"],
        "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        "database": os.environ.get("SNOWFLAKE_DATABASE", "EGLE_VIEW"),
    }).create()


# get_active_session() only works inside the real Streamlit-in-Snowflake
# runtime, and there it's a singleton — calling it again doesn't yield an
# independent session, so parallel dispatch (which needs one session per
# concurrent call) is only safe to enable when we're on the local-dev
# fallback, where each call genuinely opens a new connection.
try:
    session = get_active_session()
    session_factory = None
except Exception:
    session = _build_local_session()
    session_factory = _build_local_session

try:
    ctx = rbac.current_context(session)
except rbac.UnrecognizedViewerError as exc:
    st.error(str(exc))
    st.stop()

metadata.ensure_metadata_tables(session, ctx)

TYPE_OPTIONS = ["VARCHAR", "INTEGER", "FLOAT", "NUMBER(18,2)", "BOOLEAN", "DATE", "TIMESTAMP_NTZ"]

if "phase" not in st.session_state:
    st.session_state.phase = "idle"
if "active_dataset_id" not in st.session_state:
    st.session_state.active_dataset_id = None
if "active_df" not in st.session_state:
    st.session_state.active_df = None
if "domain_results" not in st.session_state:
    st.session_state.domain_results = []
if "error_msg" not in st.session_state:
    st.session_state.error_msg = ""
if "chat_turns" not in st.session_state:
    st.session_state.chat_turns = []
if "chat_session_id" not in st.session_state:
    st.session_state.chat_session_id = None


def reset_onboarding():
    st.session_state.phase = "idle"
    st.session_state.active_dataset_id = None
    st.session_state.active_df = None
    st.session_state.domain_results = []
    st.session_state.error_msg = ""


# ---------------------------------------------------------------- sidebar --
with st.sidebar:
    st.markdown("### EgleView")
    st.caption(f"Signed in as **{ctx['user']}**")
    st.caption(f"Schema: `{ctx['database']}.{ctx['schema']}`")
    st.divider()
    page = st.radio("Navigate", ["Onboard data", "Dashboard", "SC Command Center"], label_visibility="collapsed")
    st.divider()

    agent_log = st.session_state.get("agent_log", [])
    with st.expander(f"🔍 Agent activity log ({len(agent_log)})", expanded=False):
        if not agent_log:
            st.caption("Nothing yet — upload data or ask a question to see agent activity here.")
        else:
            st.code("\n".join(agent_log), language=None)
        if agent_log and st.button("Clear log", use_container_width=True):
            st.session_state.agent_log = []
            st.rerun()


# ------------------------------------------------------------- onboarding --
def render_onboarding():
    st.title("Onboard your data")
    st.caption(
        "Upload raw business data — CSV, Excel, or JSON. The Orchestrator Agent decides which "
        "business domain(s) it belongs to and can split one file across several domain agents. "
        "Nothing is written to Snowflake until you review and confirm the mapping below."
    )

    if st.session_state.phase == "idle":
        col1, col2 = st.columns([3, 2])
        with col1:
            uploaded = st.file_uploader("Drop a file here", type=["csv", "xlsx", "xls", "json"])
            if uploaded is not None:
                try:
                    dataset_id, df = ingestion_pipeline.upload_dataset(
                        session, ctx, uploaded.name, uploaded.getvalue()
                    )
                    st.session_state.active_dataset_id = dataset_id
                    st.session_state.active_df = df
                    st.session_state.phase = "analyzing"
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Upload failed: {exc}")
        with col2:
            st.info("⚡ **Seed demo data**\n\nLoad a realistic multi-domain dataset straight through "
                     "the real orchestrator + domain agent pipeline. Skips manual review.")
            if st.button("Load demo datasets", use_container_width=True):
                with st.spinner("Seeding demo data through the real pipeline… this can take a while."):
                    results = demo_seed.seed_demo_datasets(session, ctx)
                for r in results:
                    if r["status"] == "READY":
                        st.success(f"{r['name']}: READY")
                    else:
                        st.error(f"{r['name']}: {r['error']}")
                st.rerun()

    elif st.session_state.phase == "analyzing":
        with st.spinner("Orchestrator Agent is analyzing your data and routing it to domain agents…"):
            try:
                domain_results = ingestion_pipeline.analyze_dataset(
                    session, ctx, st.session_state.active_dataset_id, st.session_state.active_df
                )
                enriched = []
                for d in domain_results:
                    cols = metadata.get_columns_for_domain(session, ctx, d["domainId"])
                    enriched.append({**d, "reviewRows": cols})
                st.session_state.domain_results = enriched
                st.session_state.phase = "review"
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.session_state.error_msg = str(exc)
                st.session_state.phase = "error"
                st.rerun()

    elif st.session_state.phase == "review":
        domains = st.session_state.domain_results
        st.caption(f"The Orchestrator Agent routed this file to **{len(domains)}** domain agent(s):")
        tabs = st.tabs([d["agentLabel"] for d in domains])
        for tab, d in zip(tabs, domains):
            with tab:
                action = "will **create** a new table" if d["isNewTable"] else "will **extend** the existing table"
                st.caption(f"{action}: `{d['tableName']}`")
                if d.get("agentNote"):
                    st.info(f"🤖 **{d['agentLabel']}:** {d['agentNote']}")

                df_display = pd.DataFrame([
                    {
                        "id": c["ID"],
                        "Source column": c["SOURCE_COLUMN"],
                        "AI meaning": c["SEMANTIC_TYPE"],
                        "Target column": c["TARGET_COLUMN"],
                        "Type": c["TARGET_TYPE"],
                        "Nullable": c["NULLABLE"],
                        "New column?": c["IS_NEW_COLUMN"],
                        "Include": c["INCLUDE"],
                        "Confidence": c["CONFIDENCE"],
                    }
                    for c in d["reviewRows"]
                ])
                edited = st.data_editor(
                    df_display,
                    column_config={
                        "id": None,
                        "Source column": st.column_config.TextColumn(disabled=True),
                        "AI meaning": st.column_config.TextColumn(disabled=True),
                        "New column?": st.column_config.CheckboxColumn(disabled=True),
                        "Type": st.column_config.SelectboxColumn(options=TYPE_OPTIONS),
                        "Confidence": st.column_config.ProgressColumn(min_value=0, max_value=1),
                    },
                    hide_index=True,
                    use_container_width=True,
                    key=f"schema_editor_{d['domainId']}",
                )
                st.session_state[f"edited_{d['domainId']}"] = edited
                included = int(edited["Include"].sum())
                st.caption(f"{included} of {len(edited)} columns will be loaded")

        cc1, cc2 = st.columns(2)
        if cc1.button("Cancel", use_container_width=True):
            reset_onboarding()
            st.rerun()
        if cc2.button("Confirm & merge all domains", type="primary", use_container_width=True):
            for d in domains:
                edited = st.session_state.get(f"edited_{d['domainId']}")
                if edited is None:
                    continue
                for _, row in edited.iterrows():
                    metadata.update_column(
                        session, ctx, row["id"],
                        target_column=row["Target column"], target_type=row["Type"],
                        nullable=bool(row["Nullable"]), include=bool(row["Include"]),
                        source="USER_MODIFIED",
                    )
            st.session_state.phase = "confirming"
            st.rerun()

    elif st.session_state.phase == "confirming":
        with st.spinner("Domain agents are merging their tables and loading data…"):
            try:
                ingestion_pipeline.confirm_dataset(
                    session, ctx, st.session_state.active_dataset_id, st.session_state.active_df,
                )
                st.session_state.phase = "success"
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.session_state.error_msg = str(exc)
                st.session_state.phase = "error"
                st.rerun()

    elif st.session_state.phase == "success":
        st.success("Data is ready. Ask about it from the Dashboard tab.")
        if st.button("Upload another"):
            reset_onboarding()
            st.rerun()

    elif st.session_state.phase == "error":
        st.error(st.session_state.error_msg)
        if st.button("Start over"):
            reset_onboarding()
            st.rerun()

    st.divider()
    domains = metadata.list_ready_domains(session, ctx)
    if domains:
        st.markdown("#### Your domains")
        st.dataframe(
            pd.DataFrame([
                {"Domain": d["AGENT_KEY"], "Table": d["TABLE_NAME"], "Rows": d["ROW_COUNT"]}
                for d in domains
            ]),
            hide_index=True, use_container_width=True,
        )


# --------------------------------------------------------------- dashboard --
def render_dashboard():
    st.title("Ask your data anything")
    domains = metadata.list_ready_domains(session, ctx)

    left, right = st.columns([1, 3])
    with left:
        st.markdown("#### My domains")
        if not domains:
            st.caption("No data ready yet — onboard some first.")
        for d in domains:
            st.markdown(f"**{d['AGENT_KEY']}**  \n{d['TABLE_NAME']} · {d['ROW_COUNT']} rows")
        if st.session_state.chat_turns and st.button("New conversation"):
            st.session_state.chat_turns = []
            st.session_state.chat_session_id = None
            st.rerun()

    with right:
        for turn in st.session_state.chat_turns:
            with st.chat_message(turn["role"]):
                if turn["role"] == "user":
                    st.write(turn["content"])
                else:
                    render_response(turn["response"])

        question = st.chat_input("Ask about your data…")
        if question:
            st.session_state.chat_turns.append({"role": "user", "content": question})
            with st.spinner("Consulting the relevant domain agent(s)… this can take a couple of minutes."):
                response = query_pipeline.ask_question(
                    session, ctx, question, st.session_state.chat_session_id,
                    session_factory=session_factory,
                )
            st.session_state.chat_session_id = response["session_id"]
            st.session_state.chat_turns.append({"role": "assistant", "response": response})
            st.rerun()


def render_response(response: dict):
    st.write(response.get("answer", ""))

    agents_consulted = response.get("agents_consulted")
    if agents_consulted:
        st.caption("🤖 Consulted: " + ", ".join(agents_consulted))

    entity = response.get("entity")
    if entity:
        st.caption(f"🔎 {entity['type']} · {entity['id']}")

    summary = response.get("summary")
    if summary:
        cols = st.columns(min(4, len(summary)) or 1)
        for i, (k, v) in enumerate(summary.items()):
            cols[i % len(cols)].metric(k.replace("_", " ").title(), str(v))

    viz = response.get("visualization")
    result = response.get("result") or []
    if viz and result:
        df = pd.DataFrame(result)
        vtype = viz.get("type")
        try:
            if vtype == "bar" and viz.get("x_field") in df.columns:
                st.bar_chart(df, x=viz["x_field"], y=viz.get("y_field"))
            elif vtype == "line" and viz.get("x_field") in df.columns:
                st.line_chart(df, x=viz["x_field"], y=viz.get("y_field"))
            elif vtype == "kpi" and viz.get("y_field") in df.columns:
                st.metric(viz.get("title") or viz["y_field"], df.iloc[0][viz["y_field"]])
        except Exception:  # noqa: BLE001
            pass  # fall through to the raw table below

    timeline = response.get("timeline") or []
    if timeline:
        st.markdown("**Timeline**")
        for ev in timeline:
            ts = ev.get("timestamp")
            st.markdown(f"- {f'`{ts}` ' if ts else ''}{ev.get('event', '')}")

    if result and (not viz or viz.get("type") in (None, "table")):
        st.dataframe(pd.DataFrame(result), hide_index=True, use_container_width=True)

    missing = response.get("missing_info") or []
    if missing:
        st.caption("Not available in your data: " + ", ".join(missing))


def render_sc_command_center():
    st.title("Supply Chain Command Center")
    st.caption(
        "Governed analytics powered by semantic views + Cortex Analyst. "
        "Same metric → same answer, regardless of which persona asks."
    )

    # ── Persona selector ──
    personas = ["Planning", "Procurement", "Logistics"]
    sel_persona = st.selectbox("Select your persona", personas, index=0)

    # ── KPI ribbon — live from dynamic tables ──
    st.markdown("### Key Supply Chain KPIs")
    kpi_cols = st.columns(4)
    try:
        fq = f'"{ctx["database"]}"."{ctx["schema"]}"'
        # OTD%
        otd_row = session.sql(f"""
            SELECT ROUND(SUM(on_time_count)*100.0/NULLIF(SUM(total_delivered),0),2) AS v
            FROM {fq}."SC_OTD_METRICS"
        """).collect()
        kpi_cols[0].metric("On-Time Delivery %", f"{otd_row[0]['V']}%" if otd_row and otd_row[0]['V'] else "N/A")

        # Fill Rate
        fr_row = session.sql(f"""
            SELECT ROUND(SUM(total_shipped)*100.0/NULLIF(SUM(total_requested),0),2) AS v
            FROM {fq}."SC_FILL_RATE"
        """).collect()
        kpi_cols[1].metric("Fill Rate %", f"{fr_row[0]['V']}%" if fr_row and fr_row[0]['V'] else "N/A")

        # DOI
        doi_row = session.sql(f"""
            SELECT ROUND(AVG(days_of_inventory),1) AS v
            FROM {fq}."SC_INVENTORY_POSITION" WHERE days_of_inventory IS NOT NULL
        """).collect()
        kpi_cols[2].metric("Avg Days of Inventory", doi_row[0]['V'] if doi_row and doi_row[0]['V'] else "N/A")

        # Landed Cost
        lc_row = session.sql(f"""
            SELECT ROUND(AVG(landed_cost_per_unit),2) AS v FROM {fq}."SC_LANDED_COST"
        """).collect()
        kpi_cols[3].metric("Avg Landed Cost/Unit", f"₹{lc_row[0]['V']}" if lc_row and lc_row[0]['V'] else "N/A")
    except Exception as exc:
        st.warning(f"KPI load failed (dynamic tables may not exist yet): {exc}")

    st.divider()

    # ── Governed chat ──
    st.markdown("### Ask a supply chain question")
    sc_question = st.chat_input("e.g. What is the on-time delivery % by carrier?")
    if sc_question:
        with st.spinner(f"Querying as {sel_persona} via Cortex Analyst + semantic view…"):
            response = query_pipeline.ask_question(
                session, ctx, sc_question, st.session_state.chat_session_id,
                session_factory=session_factory,
                persona=sel_persona,
            )
        st.session_state.chat_session_id = response["session_id"]

        st.write(response.get("answer", ""))
        agents = response.get("agents_consulted", [])
        if agents:
            st.caption(f"Routed via: {', '.join(agents)}")
        summary = response.get("summary")
        if summary:
            st.caption(f"Governed by: {summary.get('governed_by', 'N/A')} | Persona: {summary.get('persona', 'N/A')}")
        result = response.get("result", [])
        if result:
            st.dataframe(pd.DataFrame(result), hide_index=True, use_container_width=True)
        if response.get("sql"):
            with st.expander("Generated SQL"):
                st.code(response["sql"], language="sql")

    st.divider()

    # ── Persona consistency proof ──
    st.markdown("### Persona Consistency Proof")
    st.caption("Fire the same metric question across all 3 personas and compare results.")
    proof_question = st.text_input("Metric question to test", value="What is the overall on-time delivery percentage?")
    if st.button("Run consistency test", type="primary"):
        results_by_persona = {}
        for p in personas:
            with st.spinner(f"Querying as {p}…"):
                resp = query_pipeline.ask_question(
                    session, ctx, proof_question, None,
                    session_factory=session_factory,
                    persona=p,
                )
                results_by_persona[p] = resp

        proof_cols = st.columns(3)
        for i, p in enumerate(personas):
            r = results_by_persona[p]
            with proof_cols[i]:
                st.markdown(f"**{p}**")
                st.write(r.get("answer", "N/A"))
                agents = r.get("agents_consulted", [])
                if agents:
                    st.caption(f"Via: {', '.join(agents)}")
                res = r.get("result", [])
                if res:
                    st.dataframe(pd.DataFrame(res), hide_index=True, use_container_width=True)

        # Compare
        answers = [results_by_persona[p].get("answer", "") for p in personas]
        if len(set(answers)) == 1:
            st.success("All 3 personas returned the SAME answer. Governed consistency confirmed.")
        else:
            st.warning("Answers differ — check semantic view coverage.")


if page == "Onboard data":
    render_onboarding()
elif page == "Dashboard":
    render_dashboard()
else:
    render_sc_command_center()
