"""Stage 1 orchestration: orchestrator splits the upload across domains ->
classify each domain's slice against its own persistent table -> (human
review happens in the UI, per domain) -> confirm -> merge/extend each
domain's table via its real Cortex Agent -> load -> detect relationships.
"""

import logging

from sf_lib import domain_agent, metadata, orchestrator, schema_service
from sf_lib.activity_log import log
from sf_lib.classification import classify_domain_slice
from sf_lib.domain_agents import DOMAIN_AGENTS, table_name_for
from sf_lib.ingestion import dataframe_sample, parse_upload_to_dataframe

logger = logging.getLogger("app.ingestion_pipeline")


def upload_dataset(session, ctx: dict, filename: str, raw_bytes: bytes) -> tuple[str, "pd.DataFrame"]:
    """Parses immediately (no separate raw-file staging step) and creates the
    dataset metadata row in UPLOADED status. Returns (dataset_id, dataframe).
    """
    df = parse_upload_to_dataframe(filename, raw_bytes)
    name = (filename or "Untitled dataset").rsplit(".", 1)[0]
    dataset_id = metadata.create_dataset(session, ctx, name, filename or "")
    metadata.update_dataset(session, ctx, dataset_id, row_count=len(df))
    return dataset_id, df


def analyze_dataset(session, ctx: dict, dataset_id: str, df) -> list[dict]:
    """Runs the Orchestrator Agent to split the upload's columns across
    business domains, then classifies + persists a proposed schema per
    domain. Returns one dict per targeted domain (for the review UI). Raises
    on failure after marking the dataset FAILED.
    """
    metadata.update_dataset(session, ctx, dataset_id, status="ANALYZING")
    try:
        sample = dataframe_sample(df)
        assignments = orchestrator.split_by_domain(session, list(df.columns), sample)
        if not assignments:
            raise ValueError("The orchestrator couldn't match any column in this file to a known business domain.")

        domain_results = []
        for agent_key, source_cols in assignments.items():
            table_name = table_name_for(agent_key)
            existing_cols = metadata.get_existing_table_columns(session, ctx, table_name)
            log(f"🏷️ Classifying slice for {agent_key}: columns={source_cols}")
            classification = classify_domain_slice(session, agent_key, existing_cols, source_cols, sample)

            domain_id = metadata.create_domain_slice(session, ctx, dataset_id, agent_key, table_name)
            columns = schema_service.build_columns_from_classification(classification, existing_cols)
            metadata.replace_columns_for_domain(session, ctx, domain_id, columns)

            try:
                agent_note = domain_agent.ask_about_ambiguity(session, ctx, agent_key, classification)
            except Exception:  # noqa: BLE001
                agent_note = None

            metadata.update_domain_slice(
                session, ctx, domain_id,
                agent_note=agent_note or "", classification_json=classification, status="SCHEMA_PROPOSED",
            )

            domain_results.append({
                "domainId": domain_id,
                "agentKey": agent_key,
                "agentLabel": DOMAIN_AGENTS[agent_key]["label"],
                "tableName": table_name,
                "isNewTable": not existing_cols,
                "sampleRows": sample,
                "agentNote": agent_note,
                **classification,
            })

        metadata.update_dataset(session, ctx, dataset_id, status="SCHEMA_PROPOSED")
        return domain_results
    except Exception as exc:  # noqa: BLE001
        metadata.update_dataset(session, ctx, dataset_id, status="FAILED", error_message=str(exc))
        logger.exception("Classification failed for dataset %s", dataset_id)
        raise


def confirm_dataset(session, ctx: dict, dataset_id: str, raw_df) -> list[dict]:
    """Applies the (already-edited-in-UI) column list for every domain slice
    of this upload: merges/extends each domain's persistent table via its
    real Cortex Agent, loads the cast rows, and detects cross-domain
    relationships. Raises on failure after marking the dataset FAILED.
    """
    domain_slices = metadata.list_domain_slices_for_dataset(session, ctx, dataset_id)
    if not domain_slices:
        raise ValueError("No domain slices to confirm for this dataset")

    metadata.update_dataset(session, ctx, dataset_id, status="LOADING")
    try:
        total_rows = 0
        for slice_ in domain_slices:
            domain_id = slice_["ID"]
            agent_key = slice_["AGENT_KEY"]
            table_name = slice_["TABLE_NAME"]

            columns = metadata.get_columns_for_domain(session, ctx, domain_id)
            included = [c for c in columns if c["INCLUDE"]]
            if not included:
                metadata.update_domain_slice(session, ctx, domain_id, status="SKIPPED")
                continue

            norm_cols = [
                {
                    "source_column": c["SOURCE_COLUMN"], "target_column": c["TARGET_COLUMN"],
                    "target_type": c["TARGET_TYPE"], "nullable": c["NULLABLE"],
                    "include": c["INCLUDE"], "foreign_key_candidate": c["FOREIGN_KEY_CANDIDATE"],
                    "primary_key_candidate": c["PRIMARY_KEY_CANDIDATE"],
                }
                for c in included
            ]
            load_df = schema_service.build_load_dataframe(raw_df, norm_cols)

            # The table is merged/extended by a real Cortex Agent tool call
            # (MergeDomainTable -> MERGE_TABLE_PROC), not by this code running
            # DDL directly — the confirmed mapping is handed to the domain
            # agent, which performs the action.
            agent_note = domain_agent.merge_table_via_agent(session, ctx, agent_key, table_name, norm_cols)
            logger.info("%s: %s", agent_key, agent_note)

            row_count = schema_service.load_rows(session, ctx, table_name, load_df, norm_cols)
            total_rows += row_count
            metadata.update_domain_slice(
                session, ctx, domain_id, status="READY", row_count=row_count, agent_note=agent_note,
            )

            for rel in schema_service.detect_relationships(session, ctx, agent_key, norm_cols):
                metadata.add_relationship_if_new(session, ctx, rel)

        metadata.update_dataset(session, ctx, dataset_id, status="READY", row_count=total_rows)
        return metadata.list_domain_slices_for_dataset(session, ctx, dataset_id)
    except Exception as exc:  # noqa: BLE001
        metadata.update_dataset(session, ctx, dataset_id, status="FAILED", error_message=str(exc))
        logger.exception("Load failed for dataset %s", dataset_id)
        raise
