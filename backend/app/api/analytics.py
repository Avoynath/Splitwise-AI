"""Analytics API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract
from pydantic import BaseModel
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.expense import Expense
from app.models.group import GroupMember

router = APIRouter(prefix="/analytics", tags=["Analytics"])


class CategoryBreakdown(BaseModel):
    category: str
    total: float
    count: int
    percentage: float = 0


class MonthlyData(BaseModel):
    month: str
    total: float
    count: int


class TrendData(BaseModel):
    monthly: list[MonthlyData] = []
    categories: list[CategoryBreakdown] = []
    total_expenses: float = 0
    expense_count: int = 0
    avg_expense: float = 0


async def _check_membership(group_id: int, user_id: int, db: AsyncSession):
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this group")


@router.get("/{group_id}/categories", response_model=list[CategoryBreakdown])
async def get_category_breakdown(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get expense breakdown by category."""
    await _check_membership(group_id, current_user.id, db)

    result = await db.execute(
        select(
            Expense.category,
            func.sum(Expense.amount).label("total"),
            func.count(Expense.id).label("count"),
        )
        .where(Expense.group_id == group_id)
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc())
    )
    rows = result.all()

    grand_total = sum(r[1] for r in rows) if rows else 1

    return [
        CategoryBreakdown(
            category=row[0],
            total=round(row[1], 2),
            count=row[2],
            percentage=round(row[1] / grand_total * 100, 1),
        )
        for row in rows
    ]


@router.get("/{group_id}/trends", response_model=TrendData)
async def get_trends(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get spending trends over time."""
    await _check_membership(group_id, current_user.id, db)

    # Monthly totals (strftime works with SQLite; for PostgreSQL use to_char)
    month_expr = func.strftime('%Y-%m', Expense.date)
    monthly_result = await db.execute(
        select(
            month_expr.label("month"),
            func.sum(Expense.amount).label("total"),
            func.count(Expense.id).label("count"),
        )
        .where(Expense.group_id == group_id)
        .group_by(month_expr)
        .order_by(month_expr)
    )
    monthly_rows = monthly_result.all()

    # Overall stats
    stats_result = await db.execute(
        select(
            func.count(Expense.id),
            func.sum(Expense.amount),
            func.avg(Expense.amount),
        )
        .where(Expense.group_id == group_id)
    )
    stats_row = stats_result.first()

    # Categories
    categories = await get_category_breakdown(group_id, db, current_user)

    return TrendData(
        monthly=[MonthlyData(month=r[0], total=round(r[1], 2), count=r[2]) for r in monthly_rows],
        categories=categories,
        total_expenses=round(stats_row[1] or 0, 2),
        expense_count=stats_row[0] or 0,
        avg_expense=round(stats_row[2] or 0, 2),
    )
