"""Expense and Balance API endpoints."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.group import Group, GroupMember
from app.models.expense import Expense, ExpenseSplit, Settlement
from app.schemas.expense import (
    ExpenseCreate, ExpenseUpdate, ExpenseResponse, SplitResponse,
    BalanceResponse, SettlementSuggestion, SettleRequest,
)
from app.services.balance import calculate_balances
from app.services.settlement import compute_settlements

router = APIRouter(tags=["Expenses & Balances"])


async def _check_membership(group_id: int, user_id: int, db: AsyncSession):
    """Verify user is a member of the group."""
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="You are not a member of this group")


async def _get_user_name(user_id: int, db: AsyncSession) -> str:
    result = await db.execute(select(User.name).where(User.id == user_id))
    row = result.first()
    return row[0] if row else "Unknown"


# ─── Expenses ───────────────────────────────────────

@router.get("/groups/{group_id}/expenses", response_model=list[ExpenseResponse])
async def list_expenses(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all expenses in a group."""
    await _check_membership(group_id, current_user.id, db)

    result = await db.execute(
        select(Expense)
        .options(selectinload(Expense.splits))
        .where(Expense.group_id == group_id)
        .order_by(Expense.date.desc())
    )
    expenses = result.scalars().unique().all()

    responses = []
    for exp in expenses:
        paid_by_name = await _get_user_name(exp.paid_by, db)
        split_responses = []
        for s in exp.splits:
            uname = await _get_user_name(s.user_id, db)
            split_responses.append(SplitResponse(
                user_id=s.user_id,
                user_name=uname,
                amount=s.amount,
                percentage=s.percentage,
            ))
        responses.append(ExpenseResponse(
            id=exp.id,
            group_id=exp.group_id,
            paid_by=exp.paid_by,
            paid_by_name=paid_by_name,
            amount=exp.amount,
            description=exp.description,
            category=exp.category,
            split_type=exp.split_type,
            notes=exp.notes,
            date=exp.date,
            created_at=exp.created_at,
            splits=split_responses,
        ))

    return responses


@router.post("/groups/{group_id}/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    group_id: int,
    data: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an expense with automatic split calculation."""
    await _check_membership(group_id, current_user.id, db)

    # Get group members
    members_result = await db.execute(
        select(GroupMember.user_id).where(GroupMember.group_id == group_id)
    )
    member_ids = [row[0] for row in members_result.all()]

    if not member_ids:
        raise HTTPException(status_code=400, detail="Group has no members")

    # Create expense
    expense = Expense(
        group_id=group_id,
        paid_by=current_user.id,
        amount=data.amount,
        description=data.description,
        category=data.category,
        split_type=data.split_type,
        notes=data.notes,
        date=data.date or datetime.now(timezone.utc),
    )
    db.add(expense)
    await db.flush()

    # Calculate splits
    splits_to_create = []

    if data.split_type == "equal":
        per_person = round(data.amount / len(member_ids), 2)
        # Adjust rounding error for last person
        remainder = round(data.amount - per_person * len(member_ids), 2)
        for i, uid in enumerate(member_ids):
            amount = per_person + (remainder if i == len(member_ids) - 1 else 0)
            splits_to_create.append(ExpenseSplit(
                expense_id=expense.id,
                user_id=uid,
                amount=round(amount, 2),
            ))

    elif data.split_type == "unequal":
        if not data.splits:
            raise HTTPException(status_code=400, detail="Split details required for unequal splits")
        total_split = sum(s.amount or 0 for s in data.splits)
        if abs(total_split - data.amount) > 0.01:
            raise HTTPException(status_code=400, detail=f"Split amounts ({total_split}) must equal total ({data.amount})")
        for s in data.splits:
            splits_to_create.append(ExpenseSplit(
                expense_id=expense.id,
                user_id=s.user_id,
                amount=s.amount or 0,
            ))

    elif data.split_type == "percentage":
        if not data.splits:
            raise HTTPException(status_code=400, detail="Split details required for percentage splits")
        total_pct = sum(s.percentage or 0 for s in data.splits)
        if abs(total_pct - 100) > 0.01:
            raise HTTPException(status_code=400, detail=f"Percentages ({total_pct}%) must sum to 100%")
        for s in data.splits:
            pct = s.percentage or 0
            amount = round(data.amount * pct / 100, 2)
            splits_to_create.append(ExpenseSplit(
                expense_id=expense.id,
                user_id=s.user_id,
                amount=amount,
                percentage=pct,
            ))

    for split in splits_to_create:
        db.add(split)

    await db.flush()
    await db.refresh(expense)

    # Build response
    paid_by_name = await _get_user_name(expense.paid_by, db)
    split_responses = []
    for s in splits_to_create:
        uname = await _get_user_name(s.user_id, db)
        split_responses.append(SplitResponse(
            user_id=s.user_id,
            user_name=uname,
            amount=s.amount,
            percentage=s.percentage,
        ))

    return ExpenseResponse(
        id=expense.id,
        group_id=expense.group_id,
        paid_by=expense.paid_by,
        paid_by_name=paid_by_name,
        amount=expense.amount,
        description=expense.description,
        category=expense.category,
        split_type=expense.split_type,
        notes=expense.notes,
        date=expense.date,
        created_at=expense.created_at,
        splits=split_responses,
    )


@router.delete("/groups/{group_id}/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    group_id: int,
    expense_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an expense (only creator or admin can delete)."""
    await _check_membership(group_id, current_user.id, db)

    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.group_id == group_id)
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    if expense.paid_by != current_user.id:
        # Check if admin
        admin_check = await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == current_user.id,
                GroupMember.role == "admin",
            )
        )
        if not admin_check.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Only the creator or admin can delete this expense")

    await db.delete(expense)


# ─── Balances ───────────────────────────────────────

@router.get("/groups/{group_id}/balances", response_model=list[BalanceResponse])
async def get_balances(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get net balances for all members in a group."""
    await _check_membership(group_id, current_user.id, db)
    balances = await calculate_balances(group_id, db)
    return [BalanceResponse(**b) for b in balances]


@router.get("/groups/{group_id}/settlements", response_model=list[SettlementSuggestion])
async def get_settlements(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get optimized settlement suggestions."""
    await _check_membership(group_id, current_user.id, db)
    balances = await calculate_balances(group_id, db)
    suggestions = compute_settlements(balances)
    return [SettlementSuggestion(**s) for s in suggestions]


@router.post("/groups/{group_id}/settle", status_code=status.HTTP_201_CREATED)
async def settle_debt(
    group_id: int,
    data: SettleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a settlement between two users."""
    await _check_membership(group_id, current_user.id, db)

    settlement = Settlement(
        group_id=group_id,
        from_user=data.from_user,
        to_user=data.to_user,
        amount=data.amount,
    )
    db.add(settlement)
    await db.flush()

    return {"message": "Settlement recorded", "id": settlement.id}
