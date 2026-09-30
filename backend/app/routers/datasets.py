import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from app.models import User
from app.security import get_current_user
from app.services import snowpark_service  # noqa: F401 - sets up sf_lib's import path as a side effect
from app.services.storage import raw_file_path, save_raw_file

from sf_lib import demo_seed, ingestion_pipeline, metadata  # noqa: E402
from sf_lib.activity_log import capture  # noqa: E402
from sf_lib.domain_agents import DOMAIN_AGENTS  # noqa: E402
from sf_lib.ingestion import parse_upload_to_dataframe  # noqa: E402

logger = logging.getLogger("app.datasets")
router = APIRouter(prefix="/api/datasets", tags=["datasets"])


class ColumnUpdate(BaseModel):
    id: str
    target_column: str
    target_type: str
    nullable: bool
    include: bool


class DomainConfirm(BaseModel):
    domain_id: str
    columns: list[ColumnUpdate]


class ConfirmRequest(BaseModel):
    domains: list[DomainConfirm]


def _read_df(dataset_id: str, original_filename: str):
    path = raw_file_path(dataset_id, original_filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Uploaded file not found on server")
    return parse_upload_to_dataframe(original_filename, path.read_bytes())


def _serialize_column(c: dict) -> dict:
    return {
        "id": c["ID"], "order_index": c["ORDER_INDEX"], "source_column": c["SOURCE_COLUMN"],
        "suggested_column": c["SUGGESTED_COLUMN"], "target_column": c["TARGET_COLUMN"],
        "semantic_type": c["SEMANTIC_TYPE"], "suggested_type": c["SUGGESTED_TYPE"],
        "target_type": c["TARGET_TYPE"], "nullable": c["NULLABLE"],
        "primary_key_candidate": c["PRIMARY_KEY_CANDIDATE"], "foreign_key_candidate": c["FOREIGN_KEY_CANDIDATE"],
        "include": c["INCLUDE"], "confidence": c["CONFIDENCE"], "source": c["SOURCE"],
        "is_new_column": c["IS_NEW_COLUMN"],
    }


def _serialize_domains(session, ctx, domain_results: list[dict]) -> list[dict]:
    out = []
    for d in domain_results:
        columns = metadata.get_columns_for_domain(session, ctx, d["domainId"])
        out.append({
            "domain_id": d["domainId"],
            "agent_key": d["agentKey"],
            "agent_label": d["agentLabel"],
            "table_name": d["tableName"],
            "is_new_table": d["isNewTable"],
            "agent_note": d.get("agentNote"),
            "data_quality_issues": d.get("dataQualityIssues", []),
            "ambiguous_fields": d.get("ambiguousFields", []),
            "columns": [_serialize_column(c) for c in columns],
        })
    return out


@router.post("/upload")
async def upload_dataset(file: UploadFile, user: User = Depends(get_current_user)) -> dict:
    raw_bytes = await file.read()
    session, ctx = snowpark_service.ready_context(user)
    df = parse_upload_to_dataframe(file.filename or "", raw_bytes)
    name = (file.filename or "Untitled dataset").rsplit(".", 1)[0]
    dataset_id = metadata.create_dataset(session, ctx, name, file.filename or "")
    metadata.update_dataset(session, ctx, dataset_id, row_count=len(df))
    save_raw_file(dataset_id, file.filename or "", raw_bytes)
    return {"id": dataset_id, "name": name, "row_count": len(df), "status": "UPLOADED"}


@router.post("/seed-demo")
def seed_demo(user: User = Depends(get_current_user)) -> dict:
    session, ctx = snowpark_service.ready_context(user)
    with capture() as entries:
        results = demo_seed.seed_demo_datasets(session, ctx)
    return {"results": results, "agent_log": entries}


@router.post("/{dataset_id}/analyze")
def analyze_dataset(dataset_id: str, user: User = Depends(get_current_user)) -> dict:
    session, ctx = snowpark_service.ready_context(user)
    dataset = metadata.get_dataset(session, ctx, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    df = _read_df(dataset_id, dataset["ORIGINAL_FILENAME"])
    try:
        with capture() as entries:
            domain_results = ingestion_pipeline.analyze_dataset(session, ctx, dataset_id, df)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc
    return {
        "dataset_id": dataset_id,
        "domains": _serialize_domains(session, ctx, domain_results),
        "agent_log": entries,
    }


@router.post("/{dataset_id}/confirm")
def confirm_dataset(dataset_id: str, body: ConfirmRequest, user: User = Depends(get_current_user)) -> dict:
    session, ctx = snowpark_service.ready_context(user)
    dataset = metadata.get_dataset(session, ctx, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    for domain in body.domains:
        for col in domain.columns:
            metadata.update_column(
                session, ctx, col.id,
                target_column=col.target_column, target_type=col.target_type,
                nullable=col.nullable, include=col.include, source="USER_MODIFIED",
            )

    df = _read_df(dataset_id, dataset["ORIGINAL_FILENAME"])
    try:
        with capture() as entries:
            confirmed = ingestion_pipeline.confirm_dataset(session, ctx, dataset_id, df)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to load data into Snowflake: {exc}") from exc

    return {
        "dataset_id": dataset_id,
        "domains": [
            {
                "agent_key": c["AGENT_KEY"], "agent_label": DOMAIN_AGENTS.get(c["AGENT_KEY"], {}).get("label", c["AGENT_KEY"]),
                "table_name": c["TABLE_NAME"], "status": c["STATUS"], "row_count": c["ROW_COUNT"],
            }
            for c in confirmed
        ],
        "agent_log": entries,
    }


@router.get("")
def list_datasets(user: User = Depends(get_current_user)) -> dict:
    session, ctx = snowpark_service.ready_context(user)
    datasets = metadata.list_datasets(session, ctx)
    domains = metadata.list_ready_domains(session, ctx)
    return {
        "datasets": [
            {
                "id": d["ID"], "name": d["NAME"], "status": d["STATUS"],
                "row_count": d["ROW_COUNT"], "error_message": d["ERROR_MESSAGE"],
            }
            for d in datasets
        ],
        "domains": [
            {
                "agent_key": d["AGENT_KEY"],
                "agent_label": DOMAIN_AGENTS.get(d["AGENT_KEY"], {}).get("label", d["AGENT_KEY"]),
                "table_name": d["TABLE_NAME"], "row_count": d["ROW_COUNT"],
            }
            for d in domains
        ],
    }


@router.get("/{dataset_id}/status")
def dataset_status(dataset_id: str, user: User = Depends(get_current_user)) -> dict:
    session, ctx = snowpark_service.ready_context(user)
    d = metadata.get_dataset(session, ctx, dataset_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"id": d["ID"], "status": d["STATUS"], "error_message": d["ERROR_MESSAGE"], "row_count": d["ROW_COUNT"]}


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: str, user: User = Depends(get_current_user)) -> dict:
    session, ctx = snowpark_service.ready_context(user)
    metadata.delete_dataset(session, ctx, dataset_id)
    return {"deleted": True}
