"""Pydantic schemas for expense-related requests and responses."""

from datetime import datetime
from pydantic import BaseModel, Field


class SplitDetail(BaseModel):
    user_id: int
    amount: float | None = None  # Required for unequal splits
    percentage: float | None = None  # Required for percentage splits


class ExpenseCreate(BaseModel):
    amount: float = Field(..., gt=0)
    description: str = Field(..., min_length=1, max_length=500)
    category: str = "general"
    split_type: str = "equal"  # equal, unequal, percentage
    notes: str | None = None
    date: datetime | None = None
    splits: list[SplitDetail] | None = None  # Required for unequal/percentage splits


class ExpenseUpdate(BaseModel):
    amount: float | None = Field(None, gt=0)
    description: str | None = Field(None, min_length=1, max_length=500)
    category: str | None = None
    notes: str | None = None


class SplitResponse(BaseModel):
    user_id: int
    user_name: str = ""
    amount: float
    percentage: float | None = None

    model_config = {"from_attributes": True}


class ExpenseResponse(BaseModel):
    id: int
    group_id: int
    paid_by: int
    paid_by_name: str = ""
    amount: float
    description: str
    category: str
    split_type: str
    notes: str | None = None
    date: datetime
    created_at: datetime
    splits: list[SplitResponse] = []

    model_config = {"from_attributes": True}


class BalanceResponse(BaseModel):
    user_id: int
    user_name: str
    net_balance: float  # positive = owed money, negative = owes money


class SettlementSuggestion(BaseModel):
    from_user_id: int
    from_user_name: str
    to_user_id: int
    to_user_name: str
    amount: float


class SettleRequest(BaseModel):
    from_user: int
    to_user: int
    amount: float = Field(..., gt=0)
