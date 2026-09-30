from pathlib import Path

STORAGE_ROOT = Path(__file__).resolve().parent.parent.parent / "storage" / "raw"
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


def raw_file_path(dataset_id: str, original_filename: str) -> Path:
    suffix = Path(original_filename or "").suffix or ".bin"
    return STORAGE_ROOT / f"{dataset_id}{suffix}"


def save_raw_file(dataset_id: str, original_filename: str, raw_bytes: bytes) -> str:
    path = raw_file_path(dataset_id, original_filename)
    path.write_bytes(raw_bytes)
    return str(path)
