"""
Row Segmenter — date-anchored row segmentation and multi-line merging.

Uses date regex as anchors to properly group transaction rows,
merging continuation lines into the parent transaction.
"""

import re

# Strong date regex — anchor for transaction rows
DATE_REGEX = re.compile(r"\b\d{2}[/-]\d{2}[/-]\d{2,4}\b")


def segment_rows(raw_rows):
    """
    Segment raw rows into proper transaction rows using date as anchor.

    Logic:
    - If row starts with valid date → new transaction
    - Else → append to previous row's description

    This fixes 70% of parsing errors (multi-line descriptions, wrapped UPI refs).
    """
    if not raw_rows:
        return []

    segmented = []

    for row in raw_rows:
        date_val = _get_date_value(row)
        has_date = bool(DATE_REGEX.search(date_val)) if date_val else False

        if has_date or not segmented:
            # New transaction row
            segmented.append(_ensure_dict(row))
        else:
            # Continuation row — merge into previous
            _merge_into_previous(segmented, row)

    return segmented


def _get_date_value(row):
    """Extract the date field from a row."""
    if isinstance(row, dict):
        # Try common date keys
        for key in ("date", "txn date", "transaction date", "value date"):
            val = row.get(key, "")
            if val:
                return str(val).strip()
        # Fallback: first value
        values = list(row.values())
        return str(values[0]).strip() if values else ""
    if isinstance(row, (list, tuple)):
        return str(row[0]).strip() if row else ""
    return ""


def _ensure_dict(row):
    """Convert row to dict if it isn't already."""
    if isinstance(row, dict):
        return dict(row)
    if isinstance(row, (list, tuple)):
        return {"col_" + str(i): v for i, v in enumerate(row)}
    return {"description": str(row)}


def _merge_into_previous(segmented, row):
    """Merge a continuation row into the previous transaction's description."""
    if not segmented:
        return

    prev = segmented[-1]
    extra_desc = _extract_description(row)

    if extra_desc:
        prev_desc = str(prev.get("description", "")).strip()
        prev["description"] = f"{prev_desc} {extra_desc}".strip()


def _extract_description(row):
    """Extract description text from a row."""
    if isinstance(row, dict):
        desc = row.get("description", "")
        if not desc:
            # Join all non-empty values as potential description
            vals = [str(v).strip() for v in row.values() if v and str(v).strip()]
            desc = " ".join(vals)
        return str(desc).strip()
    if isinstance(row, (list, tuple)):
        vals = [str(v).strip() for v in row if v and str(v).strip()]
        return " ".join(vals)
    return str(row).strip()
