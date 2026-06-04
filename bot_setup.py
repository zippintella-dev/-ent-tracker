"""
Run once locally to reply to any /start message with the sender's chat ID.

Usage:
    TELEGRAM_BOT_TOKEN=<token> python bot_setup.py

Each driver:
  1. Searches for the bot in Telegram and presses Start
  2. Runs this script → bot replies with their chat ID
  3. Driver shares the chat ID with ops → ops enters it in the Admin page
"""
import os
import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not TOKEN:
    raise SystemExit("Set TELEGRAM_BOT_TOKEN environment variable first.")

BASE = f"https://api.telegram.org/bot{TOKEN}"

updates = requests.get(f"{BASE}/getUpdates", timeout=10).json()
replied = 0

for update in updates.get("result", []):
    msg = update.get("message", {})
    if msg.get("text", "").strip() == "/start":
        cid = msg["chat"]["id"]
        name = msg["from"].get("first_name", "")
        requests.post(f"{BASE}/sendMessage", json={
            "chat_id": cid,
            "text": f"Hi {name}! Your Telegram Chat ID is:\n\n`{cid}`\n\nShare this with your ops team.",
            "parse_mode": "Markdown",
        }, timeout=10)
        print(f"Replied to {name} ({cid})")
        replied += 1

if replied == 0:
    print("No /start messages found. Make sure drivers have pressed Start on the bot first.")
else:
    print(f"Done — replied to {replied} driver(s).")
