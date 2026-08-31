from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from supply_planning.domain.models import RunMode


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class UserResponse(BaseModel):
    user_id: str
    email: str | None
    role: Literal["maintainer"] = "maintainer"


class CreatePlanningRunRequest(BaseModel):
    location_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")
    planning_as_of_at: datetime
    run_mode: RunMode = RunMode.SCENARIO
    master_data_version_id: UUID | None = None
    planning_input_import_id: UUID | None = None
    stock_import_id: UUID | None = None
    purchase_orders_import_id: UUID | None = None

    @field_validator("planning_as_of_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("planning_as_of_at must include a timezone offset")
        return value


class ImportResponse(BaseModel):
    id: UUID
    dataset_type: Literal["master_data", "planning_input", "stock", "purchase_orders"]
    location_id: str | None
    status: Literal[
        "received",
        "validating",
        "accepted",
        "accepted_with_warnings",
        "rejected",
    ]
    source_version: str
    source_as_of_at: datetime | None = None
    coverage_start_date: str | None = None
    coverage_end_date: str | None = None
    file_names: list[str]
    file_count: int
    total_bytes: int
    content_hash: str
    parser_version: str
    record_count: int
    warning_count: int
    error_count: int
    validation_issues: list[dict[str, Any]]
    metadata: dict[str, Any]
    supersedes_import_id: UUID | None = None
    created_at: datetime
    created_by: UUID | None = None


class ActivationResponse(BaseModel):
    id: UUID
    environment: str
    version_label: str
    status: Literal["active"]
    activated_at: datetime
    activated_by: UUID
