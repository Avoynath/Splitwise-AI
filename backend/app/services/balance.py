"""Balance calculation service.

net_balance = total_paid - total_share
Positive means the user is owed money; negative means they owe money.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.expense import Expense, ExpenseSplit, Settlement
from app.models.group import GroupMember
from app.models.user import User


async def calculate_balances(group_id: int, db: AsyncSession) -> list[dict]:
    """Calculate net balances for all members of a group.

    net_balance = (total amount this user paid) - (total share this user owes)
                  + (settlements received) - (settlements paid)
    """
    # Get all group members
    members_result = await db.execute(
        select(GroupMember.user_id).where(GroupMember.group_id == group_id)
    )
    member_ids = [row[0] for row in members_result.all()]

    if not member_ids:
        return []

    # Get user names
    users_result = await db.execute(select(User).where(User.id.in_(member_ids)))
    users = {u.id: u.name for u in users_result.scalars().all()}

    # Calculate total paid by each user
    expenses_result = await db.execute(
        select(Expense).where(Expense.group_id == group_id)
    )
    expenses = expenses_result.scalars().all()

    paid_totals: dict[int, float] = {uid: 0.0 for uid in member_ids}
    for expense in expenses:
        if expense.paid_by in paid_totals:
            paid_totals[expense.paid_by] += expense.amount

    # Calculate total share for each user
    expense_ids = [e.id for e in expenses]
    share_totals: dict[int, float] = {uid: 0.0 for uid in member_ids}

    if expense_ids:
        splits_result = await db.execute(
            select(ExpenseSplit).where(ExpenseSplit.expense_id.in_(expense_ids))
        )
        for split in splits_result.scalars().all():
            if split.user_id in share_totals:
                share_totals[split.user_id] += split.amount

    # Factor in settlements
    settlements_result = await db.execute(
        select(Settlement).where(Settlement.group_id == group_id)
    )
    settlements = settlements_result.scalars().all()

    settlement_adjustments: dict[int, float] = {uid: 0.0 for uid in member_ids}
    for s in settlements:
        if s.from_user in settlement_adjustments:
            settlement_adjustments[s.from_user] += s.amount  # paid off debt
        if s.to_user in settlement_adjustments:
            settlement_adjustments[s.to_user] -= s.amount  # received payment

    # Calculate net balance
    balances = []
    for uid in member_ids:
        net = paid_totals[uid] - share_totals[uid] + settlement_adjustments.get(uid, 0)
        balances.append({
            "user_id": uid,
            "user_name": users.get(uid, "Unknown"),
            "net_balance": round(net, 2),
        })

    return balances
