import io
import json

import pandas as pd
from fastapi import HTTPException, UploadFile

from app.config import get_settings

settings = get_settings()


def parse_upload_to_dataframe(file: UploadFile, raw_bytes: bytes) -> pd.DataFrame:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(raw_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_mb}MB limit")

    filename = (file.filename or "").lower()

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(raw_bytes))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(raw_bytes))
        elif filename.endswith(".json"):
            data = json.loads(raw_bytes.decode("utf-8"))
            if isinstance(data, dict):
                # allow {"records": [...]} or a single-object payload
                data = data.get("records", data.get("data", [data]))
            df = pd.json_normalize(data)
        else:
            raise HTTPException(
                status_code=400, detail="Unsupported file type. Use CSV, Excel (.xlsx/.xls), or JSON."
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}") from exc

    if df.empty:
        raise HTTPException(status_code=400, detail="Uploaded file contains no rows")

    df.columns = [str(c).strip() for c in df.columns]
    return df


def dataframe_sample(df: pd.DataFrame, n: int = 10) -> list[dict]:
    sample = df.head(n).copy()
    # JSON-safe: NaN -> None, timestamps -> isoformat strings
    sample = sample.where(pd.notnull(sample), None)
    return json.loads(sample.to_json(orient="records", date_format="iso"))
