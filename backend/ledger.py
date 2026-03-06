"""
Ledger module — generates structured ledger data from database.
Does NOT store formatted ledger. Purely dynamic generation.
Export functions are in backend/exporter.py.
"""

from backend.database import get_transactions_by_date, _get_per_bank_balances, connect_user_db


def generate_ledger(username, selected_date):
    """
    Generate a structured ledger object for a specific date.
    closing_balance = sum of each bank's last balance on that date (handles multi-bank correctly).
    bank_balances   = per-bank split dict for display only (empty if single bank).
    """
    rows = get_transactions_by_date(username, selected_date)

    debit_list  = []
    credit_list = []
    total_debit  = 0.0
    total_credit = 0.0
    debit_sno  = 1
    credit_sno = 1

    for row in rows:
        user_desc = row.get("user_description", "")

        if row["debit"] > 0:
            debit_list.append({
                "id":          row["id"],
                "sno":         debit_sno,
                "name":        row.get("name", ""),
                "description": user_desc,
                "narration":   row["description"],
                "amount":      row["debit"],
            })
            total_debit += row["debit"]
            debit_sno   += 1

        if row["credit"] > 0:
            credit_list.append({
                "id":          row["id"],
                "sno":         credit_sno,
                "name":        row.get("name", ""),
                "description": user_desc,
                "narration":   row["description"],
                "amount":      row["credit"],
            })
            total_credit += row["credit"]
            credit_sno   += 1

    # closing_balance = last transaction's balance field from the bank statement
    # NEVER computed from debit/credit math — that would give wrong results
    closing_balance = 0.0
    if rows:
        for row in reversed(rows):
            if row.get("balance") is not None:
                closing_balance = float(row["balance"])
                break
        else:
            # No row has a balance field — net flow fallback
            closing_balance = total_credit - total_debit

    # bank_balances = display split only (empty = show single balance bar)
    conn   = connect_user_db(username)
    cursor = conn.cursor()
    bank_balances = _get_per_bank_balances(cursor, selected_date)
    conn.close()

    return {
        "date":            selected_date,
        "debit":           debit_list,
        "credit":          credit_list,
        "total_debit":     total_debit,
        "total_credit":    total_credit,
        "closing_balance": closing_balance,
        "bank_balances":   bank_balances,
    }
