"""
notifier.py
Telegram bot integration for KC Tracker.
Handles Drive access request notifications and admin approval flow.
"""

import os
import json
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

_APPROVAL_FILE = os.path.join("data", "drive_approvals.json")


# ---------------------------------------------------------------------------
# Send notification to admin (YOU)
# ---------------------------------------------------------------------------
def notify_drive_request(username, gmail):
    """
    Send Telegram message to admin when a user requests Drive access.
    Returns (success: bool, message: str)
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "Telegram not configured in .env"

    message = (
        f"🔗 *KC Tracker — Drive Request*\n\n"
        f"👤 KC Username: `{username}`\n"
        f"📧 Gmail: `{gmail}`\n\n"
        f"➡️ Add `{gmail}` in:\n"
        f"Google Cloud Console → APIs & Services → OAuth consent screen → Test Users\n\n"
        f"✅ Once added, reply to this bot:\n`approved {username}`"
    )

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            },
            timeout=5
        )
        if resp.status_code == 200:
            return True, "Notification sent to admin."
        return False, f"Telegram API error: {resp.text}"
    except Exception as e:
        return False, f"Telegram request failed: {str(e)}"


# ---------------------------------------------------------------------------
# Poll Telegram for admin "approved <username>" replies
# ---------------------------------------------------------------------------
def poll_approvals():
    """
    Poll Telegram getUpdates for admin replies like 'approved sejee'.
    Saves approved usernames to data/drive_approvals.json.
    Called on every page load via context processor — lightweight, non-blocking.
    """
    if not TELEGRAM_BOT_TOKEN:
        return

    approvals = _load_approvals()
    offset = approvals.get("__offset__", 0)

    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
            params={"offset": offset, "timeout": 1},
            timeout=6
        )
        if resp.status_code != 200:
            return

        updates = resp.json().get("result", [])
        changed = False

        for update in updates:
            offset = update["update_id"] + 1
            text = update.get("message", {}).get("text", "").strip().lower()

            if text.startswith("approved "):
                uname = text.replace("approved ", "").strip()
                if uname and not approvals.get(uname):
                    approvals[uname] = True
                    changed = True
                    _send_admin_confirmation(uname)

        approvals["__offset__"] = offset
        if changed or updates:
            _save_approvals(approvals)

    except Exception:
        pass  # non-fatal — page still loads normally


def _send_admin_confirmation(username):
    """Reply to admin confirming the approval was registered."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    msg = f"✅ `{username}` marked as approved. They will see the connect button on next page load."
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=5
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Approval state helpers
# ---------------------------------------------------------------------------
def is_approved(username):
    """Return True if admin has approved this user's Drive access."""
    return bool(_load_approvals().get(username, False))


def _load_approvals():
    if os.path.exists(_APPROVAL_FILE):
        try:
            with open(_APPROVAL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_approvals(data):
    os.makedirs("data", exist_ok=True)
    with open(_APPROVAL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
