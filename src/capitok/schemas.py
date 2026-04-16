from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    user_id: str = Field(min_length=1, max_length=128)
    source: str = Field(default="agent", min_length=1, max_length=64)
    input: str = Field(default="")
    output: str = Field(default="")
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    status: str
    message: str


class SearchResult(BaseModel):
    id: str
    session_id: str
    user_id: str
    text: str
    score: float
    created_at: datetime


class SearchResponse(BaseModel):
    items: list[SearchResult]


class SessionListItem(BaseModel):
    session_id: str
    source: str
    preview: str
    started_at: datetime
    updated_at: datetime
    record_count: int


class SessionRecordListItem(BaseModel):
    id: str
    session_id: str
    source: str
    created_at: datetime
    input: str
    output: str


class SessionListResponse(BaseModel):
    view: Literal["sessions", "records"]
    items: list[SessionListItem | SessionRecordListItem]


class SessionTimelineItem(BaseModel):
    id: str
    created_at: datetime
    input: str
    output: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionDetailResponse(BaseModel):
    session_id: str
    source: str
    started_at: datetime
    updated_at: datetime
    record_count: int
    items: list[SessionTimelineItem]
