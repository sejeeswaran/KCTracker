"""
Extractor module — extracts meaningful names from transaction descriptions.
Supports merchant alias learning from the user's database.
"""

# Common bank transaction prefixes to strip
_PREFIXES = [
    "UPI/", "UPI-", "NEFT/", "NEFT-", "IMPS/", "IMPS-",
    "RTGS/", "RTGS-", "ATM/", "ATM-", "POS/", "POS-",
    "INB/", "INB-", "MOB/", "MOB-", "NET/", "NET-",
    "BY TRANSFER-", "TO TRANSFER-", "BY CLG-", "TO CLG-",
]


def _strip_prefix(text):
    """Remove common transaction prefixes from text."""
    upper = text.upper()
    for prefix in _PREFIXES:
        if upper.startswith(prefix):
            return text[len(prefix):]
    return text


def _is_noise_token(token):
    """Return True if token is noise (number, short code, reference ID)."""
    if not token or len(token) <= 2:
        return True
    if token.replace(".", "").replace(",", "").isdigit():
        return True
    digit_count = sum(1 for c in token if c.isdigit())
    return len(token) > 4 and digit_count > len(token) * 0.5


def extract_raw_name(description):
    """
    Extract a human-readable name from a raw bank transaction description.
    Delegates to the professional merchant_extractor module.
    """
    from backend.merchant_extractor import clean_merchant_name
    return clean_merchant_name(description)


def apply_merchant_aliases(transactions, username=None):
    """
    Apply merchant alias corrections to a list of transaction dicts.
    If a merchant alias exists for the raw description, use the display_name.
    Otherwise, use extract_raw_name().

    transactions: list of dicts with 'description' key
    Returns the same list with 'name' key added/updated.
    """
    aliases = _load_aliases(username)

    for txn in transactions:
        desc = txn.get("description", "")
        txn["name"] = aliases.get(desc, extract_raw_name(desc))

    return transactions


def _load_aliases(username):
    """Load merchant aliases from database for the given user."""
    if not username:
        return {}
    try:
        from backend.database import get_all_merchant_aliases
        return {a["raw_text"]: a["display_name"] for a in get_all_merchant_aliases(username)}
    except Exception:
        return {}
