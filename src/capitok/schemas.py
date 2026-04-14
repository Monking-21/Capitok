from datetime import datetime
from typing import Any

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
