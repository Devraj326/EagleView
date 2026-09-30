import io
import json

import pandas as pd

MAX_UPLOAD_MB = 25


class IngestionError(Exception):
    pass


def parse_upload_to_dataframe(filename: str, raw_bytes: bytes) -> pd.DataFrame:
    if len(raw_bytes) > MAX_UPLOAD_MB * 1024 * 1024:
        raise IngestionError(f"File exceeds {MAX_UPLOAD_MB}MB limit")

    lower = (filename or "").lower()
    try:
        if lower.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(raw_bytes))
        elif lower.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(raw_bytes))
        elif lower.endswith(".json"):
            data = json.loads(raw_bytes.decode("utf-8"))
            if isinstance(data, dict):
                data = data.get("records", data.get("data", [data]))
            df = pd.json_normalize(data)
        else:
            raise IngestionError("Unsupported file type. Use CSV, Excel (.xlsx/.xls), or JSON.")
    except IngestionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise IngestionError(f"Could not parse file: {exc}") from exc

    if df.empty:
        raise IngestionError("Uploaded file contains no rows")

    df.columns = [str(c).strip() for c in df.columns]
    return df


def dataframe_sample(df: pd.DataFrame, n: int = 10) -> list[dict]:
    sample = df.head(n).copy()
    sample = sample.where(pd.notnull(sample), None)
    return json.loads(sample.to_json(orient="records", date_format="iso"))
