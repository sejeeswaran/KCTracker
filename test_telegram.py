"""
test_telegram.py
Run this once to verify your Telegram bot is working correctly.

Usage:
    python test_telegram.py

Expected result:
    You should receive a test message on your Telegram from @KCTracker_bot
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

if not TOKEN or not CHAT_ID:
    print("❌ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not found in .env")
    exit(1)

print(f"🔍 Testing bot token: {TOKEN[:20]}...")
print(f"🔍 Sending to chat ID: {CHAT_ID}")

message = (
    "✅ *KC Tracker Bot — Test Message*\n\n"
    "Bot is working correctly!\n\n"
    "When a user requests Drive access, you'll receive:\n"
    "👤 KC Username\n"
    "📧 Their Gmail\n\n"
    "You reply: `approved <username>`\n"
    "And they get notified in the app automatically."
)

resp = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    json={
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    },
    timeout=10
)

if resp.status_code == 200:
    print("✅ SUCCESS! Check your Telegram — message sent.")
else:
    print(f"❌ FAILED — Status: {resp.status_code}")
    print(f"   Response: {resp.text}")
    print("\n💡 Common fixes:")
    print("   - Make sure you clicked START on @KCTracker_bot in Telegram")
    print("   - Double-check TELEGRAM_BOT_TOKEN in your .env")
    print("   - Double-check TELEGRAM_CHAT_ID in your .env")
