from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Dataset


def get_owned_dataset(db: Session, user_id: str, dataset_id: str) -> Dataset:
    """The single chokepoint for per-user dataset isolation.

    Every route that touches a dataset must go through this instead of a bare
    `db.query(Dataset).get(id)` — otherwise user A could reach user B's dataset
    by guessing its id.
    """
    dataset = (
        db.query(Dataset).filter(Dataset.id == dataset_id, Dataset.user_id == user_id).one_or_none()
    )
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


def list_ready_datasets(db: Session, user_id: str) -> list[Dataset]:
    return db.query(Dataset).filter(Dataset.user_id == user_id, Dataset.status == "READY").all()
