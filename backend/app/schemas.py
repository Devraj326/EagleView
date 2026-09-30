from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------- Auth ----------
class GoogleAuthRequest(BaseModel):
    id_token: str


class DemoAuthRequest(BaseModel):
    demo_id: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    picture: str

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    token: str
    user: UserOut


# ---------- Datasets ----------
class DatasetOut(BaseModel):
    id: str
    name: str
    original_filename: str
    dataset_type: str
    agent: str
    confidence: float
    status: str
    error_message: str = ""
    snowflake_table: str = ""
    row_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ColumnMappingOut(BaseModel):
    id: str
    order_index: int
    source_column: str
    suggested_column: str
    target_column: str
    semantic_type: str
    suggested_type: str
    target_type: str
    nullable: bool
    primary_key_candidate: bool
    foreign_key_candidate: bool
    include: bool
    confidence: float
    source: str

    class Config:
        from_attributes = True


class RelationshipOut(BaseModel):
    target_dataset_id: str
    source_column: str
    target_column: str
    confidence: float

    class Config:
        from_attributes = True


class SchemaProposalOut(BaseModel):
    dataset: DatasetOut
    suggested_table_name: str
    columns: list[ColumnMappingOut]
    relationships: list[RelationshipOut] = []
    data_quality_issues: list[str] = []
    ambiguous_fields: list[str] = []
    sample_rows: list[dict[str, Any]] = []


class ColumnMappingUpdate(BaseModel):
    id: str
    target_column: str
    target_type: str
    nullable: bool = True
    include: bool = True
    primary_key_candidate: bool = False
    foreign_key_candidate: bool = False


class ConfirmSchemaRequest(BaseModel):
    table_name: str = Field(min_length=1, max_length=128)
    columns: list[ColumnMappingUpdate]


class DemoSeedResult(BaseModel):
    name: str
    filename: str
    status: str
    error: Optional[str] = None
    dataset_id: Optional[str] = None


class DatasetStatusOut(BaseModel):
    id: str
    status: str
    error_message: str = ""
    row_count: int = 0


# ---------- Query ----------
class QueryRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    dataset_id: Optional[str] = None


class TimelineEvent(BaseModel):
    timestamp: Optional[str] = None
    event: str


class EntityRef(BaseModel):
    type: str
    id: str


class Visualization(BaseModel):
    type: str  # bar | line | pie | kpi | table | none
    x_field: Optional[str] = None
    y_field: Optional[str] = None
    series_field: Optional[str] = None
    title: Optional[str] = None


class QueryResponse(BaseModel):
    session_id: str
    answer: str
    intent: str  # analytics | entity_investigation | clarification | error
    entity: Optional[EntityRef] = None
    result: list[dict[str, Any]] = []
    timeline: list[TimelineEvent] = []
    summary: Optional[dict[str, Any]] = None
    visualization: Optional[Visualization] = None
    sql: Optional[str] = None
    datasets_used: list[str] = []
    missing_info: list[str] = []
