"""
Merchant Extractor — intelligent merchant name extraction from bank descriptions.
Never returns "Unknown" if any alphabetic content can be salvaged from the input.
"""

import re

_PREFIXES = [
    "UPI/DR/", "UPI/CR/", "UPI-DR-", "UPI-CR-",
    "UPI/", "UPI-", "NEFT/", "NEFT-", "IMPS/", "IMPS-",
    "RTGS/", "RTGS-", "ATM/", "ATM-", "POS/", "POS-",
    "INB/", "INB-", "MOB/", "MOB-", "NET/", "NET-",
    "BY TRANSFER-", "TO TRANSFER-", "BY CLG-", "TO CLG-",
    "BIL/", "BIL-", "ACH/", "ACH-", "ECS/", "ECS-",
    "MMT/", "MMT-", "ATW-", "NFS/", "NFS-",
    "BRN CASH TXN CHGS INCL GST",
    "CASH TXN CHGS",
]

_BANK_NOISE = {
    "upi", "neft", "imps", "rtgs", "ecs", "ach", "bil", "atm",
    "ifsc", "ref", "txn", "transfer", "payment", "received",
    "paid", "dr", "cr", "inr", "rs", "nt", "mob", "net",
    "stk", "self", "auto", "debit", "credit", "phone",
    "ok", "okaxis", "okhdfcbank", "okicici", "oksbi", "okhd",
    "fcbank", "hdfc", "icici", "sbi", "axis", "kotak", "ybl",
    "paytm", "gpay", "ptys", "axl", "ibl", "apl",
    "barodampay", "freecharge", "airtel", "phonepe",
    "okbizaxis", "postbank", "pnb", "ioba", "barb",
    "utib", "sbin", "bkid", "idib", "kvbl", "punb",
    "yesb", "cbin", "cnrb", "ubin", "idfb", "ratn",
    "ut", "ci", "ne", "one", "dh",
    "paymentfromphone", "paymentfrompho", "paidviasupermone",
    "supermone", "supermoney",
    "apy", "installm", "instalment", "installment",
    "thisstatement", "address", "thisstatementaddress",
}

_NOISE_SUFFIXES = [
    " thisstatement address",
    " thisstatementaddress",
    " this statement address",
    " statement address",
]

# Address/door number noise: " No.13", " No.5", " No.1/2" etc.
_NO_SUFFIX_RE = re.compile(r"\s+No\.\s*\d[\d/]*\s*$", re.IGNORECASE)

_AT_HANDLE_RE = re.compile(r"@\S+", re.IGNORECASE)
_LONG_NUM_RE = re.compile(r"\b\d{6,}\b")
_IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
_DIGIT_HEAVY_RE = re.compile(r"^\d+$|^\d+[A-Z]\d*$|^[A-Z]?\d{4,}")
_ONLY_DIGITS_RE = re.compile(r"^\d+$")

_BANK_SUFFIXES = ["okaxis", "okhdfcbank", "okicici", "oksbi", "ibl", "axl", "ybl", "apl", "upi"]


def _remove_pdf_noise_suffix(text):
    lower_text = text.lower()
    for suffix in _NOISE_SUFFIXES:
        if lower_text.endswith(suffix):
            return text[:len(text) - len(suffix)].strip()
    return text

def _check_special_cases(text):
    upper_text = text.upper()
    if upper_text.startswith("ATW-") or upper_text.startswith("ATW/"):
        parts = text.split("-")
        if len(parts) >= 2:
            location = parts[-1].strip()
            if re.match(r"^[A-Za-z]{3,}$", location):
                return "ATW " + location.title()
        return "ATW Withdrawal"

    if re.match(r"^APY\d+", text, re.IGNORECASE):
        return "Apy Installment"

    for charge_prefix in ["BRN CASH TXN", "CASH TXN CHGS", "CHGS INCL GST"]:
        if upper_text.startswith(charge_prefix):
            return "Bank Charge"
    if re.match(r"^brn", text, re.IGNORECASE) and "chg" in text.lower():
        return "Bank Charge"
        
    return None

def _remove_mid_text_noise_suffix(text):
    lower_text = text.lower()
    for suffix in _NOISE_SUFFIXES:
        if suffix in lower_text:
            idx = lower_text.index(suffix)
            return text[:idx].strip()
    return text

def _process_segment_for_name(seg, name_parts):
    if _ONLY_DIGITS_RE.match(seg):
        return True # break

    if _LONG_NUM_RE.search(seg):
        before_num = _LONG_NUM_RE.split(seg)[0].strip()
        if len(before_num) > 2 and before_num.lower() not in _BANK_NOISE:
            if not _is_upi_handle(before_num):
                name_parts.append(before_num)
        return True # break

    if len(seg) <= 1 or seg.lower() in _BANK_NOISE:
        return False # continue

    if _is_upi_handle(seg):
        prefix = _alpha_prefix_fallback(seg)
        if prefix and prefix != "Unknown":
            name_parts.append(prefix)
        return True # break

    name_parts.append(seg)
    if len(name_parts) >= 1:
        return True # break
    
    return False

def _extract_best_name_segment(text):
    segments = text.split("-")
    name_parts = []

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        
        should_break = _process_segment_for_name(seg, name_parts)
        if should_break:
            break

    return " ".join(name_parts) if name_parts else None

def _clean_tokens_and_finalize(raw_name, original):
    clean_tokens = []
    for token in raw_name.split():
        token = token.strip().strip(".-_,")
        if not token or len(token) <= 1:
            continue
        if token.lower() in _BANK_NOISE or _DIGIT_HEAVY_RE.match(token) or token.replace(".", "").replace(",", "").isdigit():
            continue
        if _is_upi_handle(token):
            prefix = _alpha_prefix_fallback(token)
            if prefix and prefix != "Unknown":
                clean_tokens.append(prefix)
            continue
        clean_tokens.append(token.title())

    if not clean_tokens:
        return _alpha_prefix_fallback(original)

    result = " ".join(clean_tokens[:3])
    result = _NO_SUFFIX_RE.sub("", _strip_honorifics(result)).strip()
    return result


def clean_merchant_name(description):
    """
    Extract a clean, human-readable name from a bank transaction description.
    Falls back to best-effort extraction rather than returning 'Unknown'.
    """
    if not description:
        return "Unknown"

    original = str(description).strip()
    text = original

    # ── Strip address/door number suffix (No.13, No.5, etc.) ─────────────────
    text = _NO_SUFFIX_RE.sub("", text).strip()

    # ── Strip honorific prefixes (Mr, Mrs, Mrm, Mrd, Smt, Shri, etc.) ──────────
    text = _strip_honorifics(text)

    # ── Strip PDF noise suffix from end ───────────────────────────────────────
    text = _remove_pdf_noise_suffix(text)

    # ── Special cases ────────────────────────────────────────────────────────
    special_case = _check_special_cases(text)
    if special_case:
        return special_case

    # ── Gibberish single-token system IDs ─────────────────────────────────────
    if re.match(r"^[A-Z0-9]{4,}$", text) and re.search(r"[A-Z]\d|\d[A-Z]", text):
        return _alpha_prefix_fallback(text)

    # ── Normalize separators ──────────────────────────────────────────────────
    text = re.sub(r"[_|\\]", "-", text)
    text = text.replace("/", "-")

    # ── Strip transaction prefixes ────────────────────────────────────────────
    text = _strip_prefixes(text)

    # Skip leading numeric ref ID (IMPS: 604608944103-CHITRA-...)
    segs = text.split("-")
    if segs and _ONLY_DIGITS_RE.match(segs[0].strip()):
        text = "-".join(segs[1:])

    # Skip leading alphanumeric ref ID (NEFT: N123456789-JOHN DOE-...)
    segs = text.split("-")
    if segs and re.match(r"^[A-Z]\d{5,}$", segs[0].strip(), re.IGNORECASE):
        text = "-".join(segs[1:])

    # ── Cut at @handle ────────────────────────────────────────────────────────
    text = _AT_HANDLE_RE.split(text)[0]

    # ── Remove IFSC codes ─────────────────────────────────────────────────────
    text = _IFSC_RE.sub(" ", text)

    # ── Remove date patterns like 28-01-2026 ─────────────────────────────────
    text = re.sub(r"\b\d{2}-\d{2}-\d{4}\b", "", text)

    # ── Strip noise suffix that may appear mid-text ───────────────────────────
    text = _remove_mid_text_noise_suffix(text)

    # ── Split by hyphens and pick best name segment ───────────────────────────
    raw_name = _extract_best_name_segment(text)
    if not raw_name:
        return _alpha_prefix_fallback(original)

    # Fix doubled/repeated name suffix from PDF (Ssagenciesssagenci → Ssagencies)
    raw_name = _deduplicate_name(raw_name)

    # ── Clean individual tokens ───────────────────────────────────────────────
    return _clean_tokens_and_finalize(raw_name, original)


def _alpha_prefix_fallback(text):
    """
    Extract the leading alphabetic portion from a UPI handle or system ID.
    e.g. Rohithganesan34    → Rohithganesan
         Ayyanhari06        → Ayyanhari
         Aswinshan000Okaxis → Aswinshan
         CHDFIHI1BBD2P5     → Chdfihi
         P3ENML03           → Unknown (too short / starts with digit)
    """
    if not text:
        return "Unknown"

    # Strip known bank suffixes first
    lower = text.lower()
    for suffix in _BANK_SUFFIXES:
        if lower.endswith(suffix):
            text = text[:len(text) - len(suffix)].strip()
            break

    # Strip trailing digits
    text = re.sub(r"\d+$", "", text).strip()

    # Extract leading alphabetic run
    match = re.match(r"^([A-Za-z]{4,})", text)
    if match:
        return match.group(1).title()

    return "Unknown"


def _is_upi_handle(text):
    """
    Returns True if text looks like a UPI handle / system ID, not a real name.
    Real names never contain digits: Dharshan, Kanagaraj, Hariroshankarthis
    UPI handles always do: Rohithganesan34, Ayyanhari06, Aswinshan000Okaxis
    """
    text = text.strip()
    if not text:
        return False
    if _ONLY_DIGITS_RE.match(text):
        return True
    # Any digit after a letter = UPI handle
    if re.search(r"[A-Za-z]\d+", text):
        return True
    lower = text.lower()
    for suffix in _BANK_SUFFIXES:
        if lower.endswith(suffix):
            return True
    return False


def _deduplicate_name(name):
    """Fix doubled name suffixes from PDF extraction: Ssagenciesssagenci → Ssagencies."""
    lower = name.lower()
    n = len(lower)
    for length in range(n - 1, 4, -1):
        prefix = lower[:length]
        rest = lower[length:]
        if not rest or len(rest) < 4:
            continue
        if prefix.startswith(rest) and len(rest) < len(prefix):
            return name[:length]
    return name


def _strip_honorifics(text):
    """
    Remove honorific prefixes from names.
    Handles both spaced and glued forms:
      'Mr Kavin' → 'Kavin'
      'Mrkavin'  → 'Kavin'
      'Mrshyamsundar' → 'Shyamsundar'
      'Mrd Kamalantham' → 'Kamalantham'
      'Mrm Gajendraboopath' → 'Gajendraboopath'
      'Smt Kanishka' → 'Kanishka'
    """
    import re as _re
    # Spaced honorifics first (Mr., Mrs., Ms., Dr., Shri, Smt, etc.)
    text = _re.sub(
        r'^(Mr\.|Mrs\.|Ms\.)\s+',
        '', text, flags=_re.IGNORECASE
    ).strip()
    # Rules:
    # SPACED: 'Mrm Foo', 'Mrd Foo', 'Mrs Foo', 'Mr Foo', 'Smt Foo' → strip prefix+space
    # GLUED:  Only strip 'Mr' (2 chars). 'Mrd'/'Mrm' glued = 'Mr'+'D...'/'Mr'+'M...'
    #   'Mrshyamsundar' = Mr + shyamsundar → Shyamsundar
    #   'Mrdharanibabu' = Mr + dharanibabu → Dharanibabu
    #   'Mrdineshkumar' = Mr + dineshkumar → Dineshkumar
    #   'Mrkanagaraj'   = Mr + kanagaraj   → Kanagaraj
    lower = text.lower()
    # Spaced Mr variants only: 'Mrm Foo', 'Mrd Foo', 'Mrs Foo', 'Mr Foo'
    for prefix in ['Mrm ', 'Mrd ', 'Mrs ', 'Mr ']:
        if lower.startswith(prefix.lower()):
            rest = text[len(prefix):].strip()
            if rest:
                text = rest[0].upper() + rest[1:]
            break
    else:
        # Glued: only strip 'Mr' (2 chars), rest gets capitalized
        if lower.startswith('mr') and len(text) > 2 and text[2].islower():
            rest = text[2:]
            text = rest[0].upper() + rest[1:]
    return text.strip()


def _strip_prefixes(text):
    """Remove common transaction prefixes (case-insensitive)."""
    upper = text.upper()
    for prefix in _PREFIXES:
        if upper.startswith(prefix.upper()):
            text = text[len(prefix):]
            upper = text.upper()
    return text.strip(" -")
