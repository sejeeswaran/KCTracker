"""
HDFC Bank Statement Parser — text-based line-by-line extraction.

Uses pdfplumber's layout-aware text extraction to get clean fixed-width text,
then parses each transaction line-by-line. This avoids the packed multi-line
table cell problem entirely.

HDFC text layout (each transaction = date-anchored line + continuation lines):
  01/02/26 UPI-IRFTURF-STK-...  0000117977927118 01/02/26  980.00            4,890.18
       IB0000553-117977927118-UPI

Columns (approximate positions):
  - Date: starts ~col 5 (DD/MM/YY)
  - Narration: starts after date
  - Ref/Chq No: before value date (long number)
  - Value Date: second DD/MM/YY occurrence
  - Withdrawal: amount before balance (if debit)
  - Deposit: amount before balance (if credit)
  - Closing Balance: rightmost number

Strategy:
  1. Extract all pages as layout text
  2. Parse each line — date-anchored lines start transactions
  3. Continuation lines extend the narration
  4. Use balance column as ground truth for amounts (balance delta)
  5. Extract clean merchant names from narration
"""

import re

# Date pattern: DD/MM/YY or DD/MM/YYYY
_DATE_RE = re.compile(r"(\d{2}/\d{2}/\d{2,4})")

# Amount pattern: number with optional commas and 2 decimal places
_AMOUNT_RE = re.compile(r"[\d,]+\.\d{2}")

# Currency symbols to strip
_CURRENCY_STRIP = re.compile(r"[₹$€£,\s]")

# Transaction line: starts with date, has at least a balance at the end
_TXN_LINE_RE = re.compile(
    r"^\s*(\d{2}/\d{2}/\d{2,4})\s+"  # Date
    r"(.+?)\s+"                        # Narration (greedy but not too much)
    r"([\d,]+\.\d{2})\s*$"            # Last number = closing balance
)

# Lines to skip (headers, footers, page info)
_SKIP_PATTERNS = [
    re.compile(r"Page\s*No\s*\.?\s*:", re.IGNORECASE),
    re.compile(r"HDFC\s*BANK\s*LIMITED", re.IGNORECASE),
    re.compile(r"Closing\s*balance\s*includes", re.IGNORECASE),
    re.compile(r"Contents\s*of\s*this\s*statement", re.IGNORECASE),
    re.compile(r"State\s*account\s*branch", re.IGNORECASE),
    re.compile(r"Registered\s*Office", re.IGNORECASE),
    re.compile(r"Statement\s*of\s*account", re.IGNORECASE),
    re.compile(r"From\s*:\s*\d{2}/\d{2}", re.IGNORECASE),
    re.compile(r"AccountBranch", re.IGNORECASE),
    re.compile(r"AccountNo", re.IGNORECASE),
    re.compile(r"Nomination", re.IGNORECASE),
    re.compile(r"JOINT\s*HOLDERS", re.IGNORECASE),
    re.compile(r"^\s*Date\s+Narration", re.IGNORECASE),
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"GSTN?\s*:", re.IGNORECASE),
]


def parse_hdfc_text(pdf):
    """
    Parse an HDFC PDF statement using layout-text extraction.

    Args:
        pdf: An opened pdfplumber PDF object
    
    Returns:
        List of transaction dicts with keys:
        {date, description, debit, credit, balance}
    """
    # Step 1: Extract ALL text from ALL pages
    all_lines = []
    for page in pdf.pages:
        text = page.extract_text(layout=True)
        if text:
            all_lines.extend(text.split("\n"))

    # Step 1b: Extract account holder name from header (for name repair)
    holder_name = _extract_holder_name(all_lines)

    # Step 2: Parse lines into raw transactions
    raw_txns = _parse_lines(all_lines)

    # Step 3: Compute amounts from balance deltas
    txns = _compute_amounts(raw_txns)

    # Step 4: Repair truncated names using account holder info
    if holder_name:
        _repair_truncated_names(txns, holder_name)

    return txns


def _extract_holder_name(lines):
    """
    Extract account holder's full name from PDF header.
    
    HDFC headers have: 'MR SEJEESWARANKANAGARAJ' or 'MRS FIRSTNAME LASTNAME'
    """
    for line in lines[:30]:  # Header is always in the first ~30 lines
        stripped = line.strip()
        # Look for lines starting with MR/MRS/MS followed by name
        match = re.match(r"^(MR|MRS|MS|SHRI|SMT)\s+(.+)$", stripped, re.IGNORECASE)
        if match:
            return match.group(2).strip().upper()
    return None


def _repair_truncated_names(txns, holder_name):
    """
    Fix names truncated by PDF line wraps using the full account holder name.
    
    E.g., holder = 'SEJEESWARANKANAGARAJ'
    If narration has 'KANAGARA' (truncated), replace with 'KANAGARAJ'.
    """
    holder_upper = holder_name.replace(" ", "").upper()
    for txn in txns:
        desc = txn.get("description", "")
        if desc:
            repaired = _repair_single_description(desc, holder_upper)
            if repaired != desc:
                txn["description"] = repaired


def _repair_single_description(desc, holder_upper):
    """Repair truncated name parts in a single description string."""
    parts = re.split(r"([\s\-/]+)", desc)
    repaired = []
    changed = False
    for part in parts:
        fixed = _try_extend_word(part, holder_upper)
        if fixed != part:
            changed = True
        repaired.append(fixed)
    return "".join(repaired) if changed else desc


def _try_extend_word(part, holder_upper):
    """If a word is a truncated prefix of the holder name, extend it."""
    alpha_only = re.sub(r"[^A-Za-z]", "", part).upper()
    if len(alpha_only) < 4 or alpha_only not in holder_upper:
        return part
    pos = holder_upper.find(alpha_only)
    end = pos + len(alpha_only)
    while end < len(holder_upper) and holder_upper[end].isalpha():
        end += 1
    full_word = holder_upper[pos:end]
    missing = len(full_word) - len(alpha_only)
    if 1 <= missing <= 3:
        return re.sub(alpha_only, full_word, part, flags=re.IGNORECASE)
    return part


def _should_skip(line):
    """Check if a line should be skipped (header, footer, etc.)."""
    stripped = line.strip()
    if not stripped:
        return True
    for pat in _SKIP_PATTERNS:
        if pat.search(stripped):
            return True
    return False


def _parse_num(val):
    """Parse a numeric string into float."""
    try:
        return float(_CURRENCY_STRIP.sub("", str(val)))
    except (ValueError, TypeError):
        return 0.0


def _parse_lines(lines):
    """
    Parse layout-text lines into raw transaction list.
    Returns list of dicts: {date, narration, amounts[], balance}
    """
    transactions = []
    current_txn = None

    for line in lines:
        if _should_skip(line) or not line.strip():
            continue

        date_match = re.match(r"^\s{0,10}(\d{2}/\d{2}/\d{2,4})\s+(.+)", line)

        if date_match:
            if current_txn:
                transactions.append(current_txn)
            current_txn = _build_txn_from_match(date_match)
        elif current_txn:
            _append_continuation(current_txn, line.strip())

    if current_txn:
        transactions.append(current_txn)
    return transactions


def _build_txn_from_match(date_match):
    """Build a transaction dict from a date-anchored regex match."""
    date_str = date_match.group(1)
    rest = date_match.group(2)
    amounts = _AMOUNT_RE.findall(rest)
    narration = _extract_narration(rest, amounts)
    balance = _parse_num(amounts[-1]) if amounts else 0.0
    return {"date": date_str, "narration": narration, "amounts": amounts, "balance": balance}


def _extract_narration(rest, amounts):
    """Extract narration text from the non-amount portion of a line."""
    if not amounts:
        return rest
    first_amt_pos = rest.find(amounts[0])
    ref_match = re.search(r"\s(0{3,}\d{10,})\s", rest)
    if ref_match and ref_match.start() < first_amt_pos:
        return rest[:ref_match.start()].strip()
    return rest[:first_amt_pos].strip()


def _append_continuation(current_txn, stripped):
    """Append a continuation line to the current transaction narration."""
    if len(stripped) > 2 and not stripped.replace(",", "").replace(".", "").isdigit():
        current_txn["narration"] += " " + stripped


def _compute_amounts(raw_txns):
    """Compute debit/credit amounts using balance delta."""
    if not raw_txns:
        return []
    results = []
    for i, txn in enumerate(raw_txns):
        if i > 0:
            debit, credit = _calc_from_delta(raw_txns[i - 1]["balance"], txn["balance"])
        else:
            debit, credit = _calc_first_txn(txn)
        results.append({
            "date": txn["date"],
            "description": txn["narration"],
            "debit": f"{debit:.2f}" if debit > 0 else "",
            "credit": f"{credit:.2f}" if credit > 0 else "",
            "balance": f"{txn['balance']:.2f}",
        })
    return results


def _calc_from_delta(prev_bal, curr_bal):
    """Calculate debit/credit from balance delta."""
    if prev_bal <= 0 or curr_bal <= 0:
        return 0.0, 0.0
    delta = curr_bal - prev_bal
    amount = abs(delta)
    if amount < 0.01:
        return 0.0, 0.0
    return (amount, 0.0) if delta < 0 else (0.0, amount)


def _infer_direction_from_narration(narration):
    """
    Infer debit/credit direction from HDFC UPI narration text.

    HDFC embeds /DR/ or /CR/ in UPI strings:
      UPI/640194291777/DR/sejeeswaran@ok/HDF → Debit
      UPI/118017605353/CR/SEJEESWARAN KA/HDF → Credit
    Also handles NEFT-BNA credit lines and CHRGS- debit patterns.
    Returns 'DR', 'CR', or None.
    """
    if not narration:
        return None
    upper = narration.upper()
    # UPI narrations: look for /DR/ or /CR/ token
    if "/DR/" in upper:
        return "DR"
    if "/CR/" in upper:
        return "CR"
    # NEFT receipts labelled with BNA (credit from other bank)
    if "BNA-" in upper or upper.startswith("NEFT"):
        return "CR"
    # Bank charges / SMS alerts are debits
    if upper.startswith("CHRGS") or upper.startswith("CHG"):
        return "DR"
    # Interest paid is a credit
    if upper.startswith("INT.PD") or upper.startswith("INTEREST"):
        return "CR"
    return None


def _calc_first_txn(txn):
    """
    Calculate debit/credit for the first transaction.

    Strategy (in order):
    1. Read /DR/ or /CR/ from the narration text (most reliable for HDFC UPI).
    2. If two amounts exist on the line, use the penultimate one as the txn amount
       and assign it to the correct side based on direction.
    3. Fallback: treat as debit (original behaviour).
    """
    amounts = txn.get("amounts", [])
    narration = txn.get("narration", "")
    direction = _infer_direction_from_narration(narration)

    # Get the transaction amount (second-to-last number, last is the closing balance)
    txn_amount = _parse_num(amounts[-2]) if len(amounts) >= 2 else 0.0

    if txn_amount <= 0:
        return 0.0, 0.0

    if direction == "CR":
        return 0.0, txn_amount
    # Default to debit (DR or unknown)
    return txn_amount, 0.0
