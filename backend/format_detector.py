"""
Format Detector — auto-detects bank statement layout type.

Analyzes raw PDF rows/headers to determine:
- Column mode (dual_column, suffix_mode, single_amount)
- Whether balance column exists
- Date format style
- Column count
- Extraction confidence score
"""

import re

# Regex patterns
_DATE_RE = re.compile(r"\d{2}[-/]\d{2}[-/]\d{2,4}")
_AMOUNT_RE = re.compile(r"[-+]?\d{1,3}(?:,\d{3})*(?:\.\d{2})?")

# Header keywords for column identification
_DEBIT_KEYWORDS = {"debit", "withdrawal", "dr", "debit amount", "withdrawal amt"}
_CREDIT_KEYWORDS = {"credit", "deposit", "cr", "credit amount", "deposit amt"}
_BALANCE_KEYWORDS = {"balance", "closing balance", "available balance", "bal", "running balance"}
_DATE_KEYWORDS = {"date", "txn date", "transaction date", "value date", "posting date"}
_DESC_KEYWORDS = {"description", "narration", "particulars", "details", "transaction details"}

_DEFAULT_DATE_FORMAT = "DD/MM/YYYY"


def detect_format(raw_rows, headers=None):
    """
    Detect the format of a bank statement from raw rows and optional headers.

    Returns a format config dict:
    {
        "mode": "dual_column" | "suffix_mode" | "single_amount",
        "has_balance": bool,
        "date_format": str,
        "column_count": int,
        "confidence": float (0-1)
    }
    """
    config = {
        "mode": "dual_column",
        "has_balance": False,
        "date_format": _DEFAULT_DATE_FORMAT,
        "column_count": 0,
        "confidence": 0.5,
    }

    if not raw_rows:
        return config

    # Detect from headers if available
    if headers:
        config = _detect_from_headers(headers, config)
    else:
        # Try to detect from first few data rows
        config = _detect_from_data(raw_rows, config)

    # Detect date format from actual data
    config["date_format"] = _detect_date_format(raw_rows)

    # Calculate confidence
    config["confidence"] = _calculate_confidence(raw_rows, config)

    return config


def _detect_from_headers(headers, config):
    """Detect format from column headers."""
    header_lower = [str(h).strip().lower() for h in headers]
    config["column_count"] = len(header_lower)

    has_debit = any(h in _DEBIT_KEYWORDS for h in header_lower)
    has_credit = any(h in _CREDIT_KEYWORDS for h in header_lower)
    has_balance = any(h in _BALANCE_KEYWORDS for h in header_lower)
    has_amount = any("amount" in h for h in header_lower)
    has_drcr_col = any(h in ("dr/cr", "type", "cr/dr") for h in header_lower)

    config["has_balance"] = has_balance

    if has_debit and has_credit:
        config["mode"] = "dual_column"
    elif has_amount and has_drcr_col:
        config["mode"] = "suffix_mode"
    elif has_amount and not has_debit:
        config["mode"] = "single_amount"
    else:
        config["mode"] = "dual_column"

    return config


def _detect_from_data(raw_rows, config):
    """Detect format by analyzing data content when headers aren't available."""
    if not raw_rows:
        return config

    # Count columns from first few rows
    col_counts = []
    for row in raw_rows[:10]:
        if isinstance(row, (dict, list, tuple)):
            col_counts.append(len(row))

    if col_counts:
        config["column_count"] = max(set(col_counts), key=col_counts.count)

    # Check for DR/CR suffixes in data
    drcr_count = 0
    total_checked = 0
    for row in raw_rows[:20]:
        values = _get_row_values(row)
        for v in values:
            text = str(v).strip().upper()
            if text.endswith("DR") or text.endswith("CR"):
                drcr_count += 1
            total_checked += 1

    if total_checked > 0 and drcr_count / total_checked > 0.1:
        config["mode"] = "suffix_mode"

    # Check if we have a balance-like column (monotonic with amounts)
    config["has_balance"] = _detect_balance_column(raw_rows)

    return config


def _extract_numeric_column_values(sample, key):
    """Extract numeric values for a specific column from a sample of rows."""
    values = []
    for row in sample:
        try:
            val = str(_get_value(row, key)).replace(",", "").strip()
            val = re.sub(r"[₹$€£\s]", "", val)
            val = re.sub(r"\s*(DR|CR|dr|cr)\s*$", "", val)
            if val:
                values.append(float(val))
        except (ValueError, TypeError):
            continue
    return values


def _detect_balance_column(raw_rows):
    """Check if any column looks like a running balance."""
    if not raw_rows or len(raw_rows) < 3:
        return False

    # For dict rows, check each numeric column
    sample = raw_rows[:min(20, len(raw_rows))]

    for key in _get_row_keys(sample[0]):
        values = _extract_numeric_column_values(sample, key)

        if len(values) >= 3:
            # Balance columns typically have large values that change gradually
            avg = sum(values) / len(values)
            if avg > 100:  # Likely a balance column, not small amounts
                return True

    return False


def _detect_date_format(raw_rows):
    """Detect the date format used in the data."""
    for row in raw_rows[:10]:
        values = _get_row_values(row)
        for v in values:
            text = str(v).strip()
            match = _DATE_RE.search(text)
            if match:
                date_str = match.group()
                if "/" in date_str:
                    return _DEFAULT_DATE_FORMAT
                return "DD-MM-YYYY"
    return _DEFAULT_DATE_FORMAT


def _calculate_confidence(raw_rows, config):
    """Calculate extraction confidence score."""
    score = 0.5

    if config["column_count"] >= 5:
        score += 0.15
    elif config["column_count"] >= 4:
        score += 0.10

    if config["has_balance"]:
        score += 0.15

    # Check date consistency
    date_count = 0
    for row in raw_rows[:20]:
        values = _get_row_values(row)
        if values and _DATE_RE.search(str(values[0])):
            date_count += 1

    if len(raw_rows) > 0:
        date_ratio = date_count / min(20, len(raw_rows))
        score += date_ratio * 0.2

    return min(score, 1.0)


def measure_table_quality(tables):
    """
    Measure the quality of extracted tables.
    Returns a score 0-1 indicating usefulness.
    """
    if not tables:
        return 0.0

    score = 0.0
    total_rows = 0
    non_empty_rows = 0
    col_consistency = 0

    for table in tables:
        if not table:
            continue

        col_counts = [len(row) for row in table if row]
        if not col_counts:
            continue

        total_rows += len(table)
        most_common_cols = max(set(col_counts), key=col_counts.count)
        col_consistency += sum(1 for c in col_counts if c == most_common_cols)

        for row in table:
            if row and any(cell for cell in row if cell and str(cell).strip()):
                non_empty_rows += 1

    if total_rows == 0:
        return 0.0

    # Non-empty ratio
    score += (non_empty_rows / total_rows) * 0.4
    # Column consistency
    score += (col_consistency / total_rows) * 0.3
    # Has enough rows for a real statement
    if total_rows >= 5:
        score += 0.3

    return min(score, 1.0)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def _get_row_values(row):
    """Get values from a row regardless of type."""
    if isinstance(row, dict):
        return list(row.values())
    if isinstance(row, (list, tuple)):
        return list(row)
    return []


def _get_row_keys(row):
    """Get keys from a row."""
    if isinstance(row, dict):
        return list(row.keys())
    if isinstance(row, (list, tuple)):
        return list(range(len(row)))
    return []


def _get_value(row, key):
    """Get a value from a row by key/index."""
    if isinstance(row, dict):
        return row.get(key, "")
    if isinstance(row, (list, tuple)) and isinstance(key, int) and key < len(row):
        return row[key]
    return ""
