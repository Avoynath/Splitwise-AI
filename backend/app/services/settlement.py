"""Settlement optimization algorithm.

Uses a greedy approach to minimize the number of transactions needed.
Time complexity: O(n log n) using sorted debtors/creditors.
"""

import heapq


def compute_settlements(balances: list[dict]) -> list[dict]:
    """Compute minimum transactions to settle all debts.

    Algorithm:
    1. Separate users into creditors (positive balance) and debtors (negative balance)
    2. Use a max-heap for creditors and min-heap (max of absolute) for debtors
    3. Greedily match the largest debtor with the largest creditor
    4. This minimizes the total number of transactions

    Args:
        balances: List of {"user_id": int, "user_name": str, "net_balance": float}

    Returns:
        List of settlement suggestions
    """
    # Separate into creditors and debtors
    # Creditors: positive balance (they are owed money)
    # Debtors: negative balance (they owe money)
    creditors = []  # max-heap (negate for heapq)
    debtors = []    # max-heap of absolute values (negate for heapq)

    for b in balances:
        balance = b["net_balance"]
        if balance > 0.01:  # creditor (is owed money)
            heapq.heappush(creditors, (-balance, b["user_id"], b["user_name"]))
        elif balance < -0.01:  # debtor (owes money)
            heapq.heappush(debtors, (balance, b["user_id"], b["user_name"]))  # already negative

    settlements = []

    while creditors and debtors:
        credit_amount, credit_id, credit_name = heapq.heappop(creditors)
        debit_amount, debit_id, debit_name = heapq.heappop(debtors)

        # Convert back to positive
        credit_amount = -credit_amount
        debit_amount = -debit_amount

        # The settlement amount is the minimum of the two
        settle_amount = min(credit_amount, debit_amount)

        settlements.append({
            "from_user_id": debit_id,
            "from_user_name": debit_name,
            "to_user_id": credit_id,
            "to_user_name": credit_name,
            "amount": round(settle_amount, 2),
        })

        # Remaining amounts
        remaining_credit = credit_amount - settle_amount
        remaining_debit = debit_amount - settle_amount

        if remaining_credit > 0.01:
            heapq.heappush(creditors, (-remaining_credit, credit_id, credit_name))
        if remaining_debit > 0.01:
            heapq.heappush(debtors, (-remaining_debit, debit_id, debit_name))

    return settlements
