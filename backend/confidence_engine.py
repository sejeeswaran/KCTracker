"""
Confidence Engine — per-transaction accuracy scoring.

Scores each transaction on:
- Valid date (20%)
- Valid amount (20%)
- Balance progression match (30%)
- Proper DR/CR classification (20%)
- Clean description (10%)

Marks transactions with score < 70% as LOW_CONFIDENCE.
"""


def score_transactions(df):
    """
    Add a confidence score to each transaction.

    Returns DataFrame with 'confidence' column (0.0 - 1.0).
    """
    df = df.copy()

    scores = []
    for i, row in df.iterrows():
        score = _score_row(row, i, df)
        scores.append(round(score, 2))

    df["confidence"] = scores
    return df


def _score_row(row, idx, df):
    """Calculate confidence score for a single transaction row."""
    score = 0.0

    # 1. Valid date (20%)
    date_val = str(row.get("date", "")).strip()
    if date_val and len(date_val) >= 8:
        score += 0.20

    # 2. Valid amount (20%)
    debit = float(row.get("debit", 0) or 0)
    credit = float(row.get("credit", 0) or 0)
    if debit > 0 or credit > 0:
        score += 0.20
    # Penalize if both are filled
    if debit > 0 and credit > 0:
        score -= 0.10

    # 3. Balance progression (30%)
    balance = float(row.get("balance", 0) or 0)
    if balance > 0:
        score += 0.15  # Has balance

        # Check if balance matches previous row's progression
        if idx > 0:
            prev_idx = df.index[df.index.get_loc(idx) - 1] if idx in df.index else None
            if prev_idx is not None:
                prev_row = df.loc[prev_idx]
                prev_bal = float(prev_row.get("balance", 0) or 0)
                if prev_bal > 0:
                    expected = prev_bal - debit + credit
                    if abs(expected - balance) <= 1.0:
                        score += 0.15  # Perfect progression match

    # 4. Proper DR/CR (20%)
    if (debit > 0) != (credit > 0):  # Exactly one is non-zero
        score += 0.20

    # 5. Clean description (10%)
    desc = str(row.get("description", "")).strip()
    if desc and len(desc) >= 3 and desc.lower() not in ("nan", "none", "unknown"):
        score += 0.10

    return min(score, 1.0)
