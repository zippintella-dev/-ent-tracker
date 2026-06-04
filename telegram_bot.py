import requests
import streamlit as st


def send_shift_message(chat_id: str, text: str) -> tuple[bool, str]:
    token = st.secrets["telegram"]["bot_token"]
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        timeout=10,
    )
    if resp.status_code == 200:
        return True, ""
    return False, resp.json().get("description", resp.text)
