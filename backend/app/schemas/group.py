"""Pydantic schemas for group-related requests and responses."""

from datetime import datetime
from pydantic import BaseModel, Field


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=500)
    type: str = "other"


class GroupUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None


class MemberInfo(BaseModel):
    user_id: int
    name: str
    email: str
    role: str
    avatar_url: str | None = None
    joined_at: datetime

    model_config = {"from_attributes": True}


class GroupResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    type: str
    created_by: int
    created_at: datetime
    members: list[MemberInfo] = []
    member_count: int = 0

    model_config = {"from_attributes": True}


class GroupListResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    type: str
    created_by: int
    created_at: datetime
    member_count: int = 0

    model_config = {"from_attributes": True}


class AddMemberRequest(BaseModel):
    email: str
    role: str = "member"


class GroupSummary(BaseModel):
    group: GroupResponse
    total_expenses: float = 0
    expense_count: int = 0
