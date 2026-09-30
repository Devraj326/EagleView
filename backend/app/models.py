import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    google_sub: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, default="")
    picture: Mapped[str] = mapped_column(String, default="")
    snowflake_schema: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    datasets: Mapped[list["Dataset"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)

    name: Mapped[str] = mapped_column(String)
    original_filename: Mapped[str] = mapped_column(String, default="")
    dataset_type: Mapped[str] = mapped_column(String, default="unknown")
    agent: Mapped[str] = mapped_column(String, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    status: Mapped[str] = mapped_column(String, default="UPLOADED")
    error_message: Mapped[str] = mapped_column(Text, default="")

    snowflake_database: Mapped[str] = mapped_column(String, default="")
    snowflake_schema: Mapped[str] = mapped_column(String, default="")
    snowflake_table: Mapped[str] = mapped_column(String, default="")
    row_count: Mapped[int] = mapped_column(Integer, default=0)

    classification_json: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_storage_path: Mapped[str] = mapped_column(String, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    user: Mapped["User"] = relationship(back_populates="datasets")
    columns: Mapped[list["DatasetColumn"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", order_by="DatasetColumn.order_index"
    )
    relationships_out: Mapped[list["DatasetRelationship"]] = relationship(
        back_populates="source_dataset",
        cascade="all, delete-orphan",
        foreign_keys="DatasetRelationship.source_dataset_id",
    )


class DatasetColumn(Base):
    __tablename__ = "dataset_columns"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    source_column: Mapped[str] = mapped_column(String)
    suggested_column: Mapped[str] = mapped_column(String)
    target_column: Mapped[str] = mapped_column(String)

    semantic_type: Mapped[str] = mapped_column(String, default="")
    suggested_type: Mapped[str] = mapped_column(String, default="VARCHAR")
    target_type: Mapped[str] = mapped_column(String, default="VARCHAR")

    nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    primary_key_candidate: Mapped[bool] = mapped_column(Boolean, default=False)
    foreign_key_candidate: Mapped[bool] = mapped_column(Boolean, default=False)
    include: Mapped[bool] = mapped_column(Boolean, default=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String, default="AI_SUGGESTED")  # AI_SUGGESTED | USER_MODIFIED

    dataset: Mapped["Dataset"] = relationship(back_populates="columns")


class DatasetRelationship(Base):
    __tablename__ = "dataset_relationships"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String, index=True)
    source_dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    target_dataset_id: Mapped[str] = mapped_column(String, index=True)
    source_column: Mapped[str] = mapped_column(String)
    target_column: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    source_dataset: Mapped["Dataset"] = relationship(
        back_populates="relationships_out", foreign_keys=[source_dataset_id]
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String, index=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    role: Mapped[str] = mapped_column(String)  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(String, default="")
    entity_id: Mapped[str] = mapped_column(String, default="")
    sql_generated: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
