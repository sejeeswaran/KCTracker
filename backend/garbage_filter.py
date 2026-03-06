"""
Garbage Filter — removes non-transaction rows from parsed data.

Filters out:
- Opening/closing balance rows
- Page numbers and footers
- Totals and summaries
- Blank or invalid rows
- Header rows that slipped through

Uses keyword scoring with configurable threshold.
"""

import re

_DATE_RE = re.compile(r"\d{2}[-/]\d{2}[-/]\d{2,4}")

# Blacklist keywords — presence in description/cells signals non-transaction row
_BLACKLIST_KEYWORDS = [
    "opening balance", "closing balance", "statement summary",
    "total", "page", "continued", "brought forward", "carried forward",
    "statement of account", "account statement", "generated on",
    "account number", "branch", "ifsc", "customer id", "cif",
    "from date", "to date", "period", "note:", "disclaimer",
    "this is a computer", "e-statement", "net banking",
]

# Header keywords — if a row looks like a header, remove it
_HEADER_KEYWORDS = {
    "date", "narration", "description", "withdrawal", "deposit",
    "debit", "credit", "balance", "particulars", "transaction",
    "chq", "cheque", "ref", "value date", "txn date", "s.no",
    "sl.no", "serial", "amount",
}

# Minimum threshold for blacklist scoring to drop a row
_BLACKLIST_THRESHOLD = 1


def filter_garbage(rows):
    """
    Remove non-transaction rows from the dataset.

    Applies in order:
    1. Remove header rows
    2. Remove blacklisted keyword rows
    3. Remove rows without valid dates
    4. Remove blank/empty rows
    """
    result = []
    for row in rows:
        if _is_header_row(row):
            continue
        if _is_blacklisted(row):
            continue
        if not _has_valid_date(row):
            continue
        if _is_empty_row(row):
            continue
        result.append(row)
    return result


def _is_header_row(row):
    """Check if a row looks like a table header."""
    values = _get_all_text(row)
    header_matches = sum(1 for v in values if v in _HEADER_KEYWORDS)
    return header_matches >= 2


def _is_blacklisted(row):
    """Check if a row contains blacklisted keywords (non-transaction content)."""
    full_text = " ".join(_get_all_text(row))
    score = sum(1 for kw in _BLACKLIST_KEYWORDS if kw in full_text)
    return score >= _BLACKLIST_THRESHOLD


def _has_valid_date(row):
    """Check if a row has a valid date."""
    if isinstance(row, dict):
        date_val = str(row.get("date", "")).strip()
        if _DATE_RE.search(date_val):
            return True
        # Check first value as fallback
        values = list(row.values())
        if values and _DATE_RE.search(str(values[0]).strip()):
            return True
    elif isinstance(row, (list, tuple)):
        if row and _DATE_RE.search(str(row[0]).strip()):
            return True
    return False


def _is_empty_row(row):
    """Check if a row is effectively empty."""
    values = _get_all_text(row)
    non_empty = [v for v in values if v and v not in ("nan", "none", "")]
    return len(non_empty) < 2


def _get_all_text(row):
    """Get all text values from a row as lowercase strings."""
    if isinstance(row, dict):
        return [str(v).strip().lower() for v in row.values() if v]
    if isinstance(row, (list, tuple)):
        return [str(v).strip().lower() for v in row if v]
    return [str(row).strip().lower()]
