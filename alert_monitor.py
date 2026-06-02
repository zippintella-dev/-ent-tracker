import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

import gspread
from google.oauth2.service_account import Credentials

from config import SHEET_ID, SHEET_NAME, ROSTER_SHEET_NAME, ALERT_LOG_SHEET_NAME, SCOPES

SERVICE_ACCOUNT_FILE = "service_account.json"


def get_credentials():
    return Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)


def _normalize_date(value: str) -> str:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return str(value).strip()


def get_roster_entry(creds, emp_id: str, date_str: str) -> dict | None:
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet(ROSTER_SHEET_NAME)
    for row in sheet.get_all_records():
        if (str(row.get("Login Driver Employee ID")) == str(emp_id)
                and _normalize_date(str(row.get("Date", ""))) == date_str):
            return row
    return None


def calculate_delay(actual_start: str, expected_start: str) -> int:
    if not expected_start or not actual_start:
        return 0
    try:
        if len(expected_start.split(":")) == 2:
            expected_start = expected_start + ":00"
        actual = datetime.strptime(actual_start, "%H:%M:%S")
        expected = datetime.strptime(expected_start, "%H:%M:%S")
        return max(0, int((actual - expected).total_seconds() / 60))
    except ValueError:
        return 0


def check_missing_trip(creds, emp_id: str, date_str: str) -> bool:
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    trips = sheet.get_all_records()
    return not any(
        str(t.get("Employee ID")) == str(emp_id) and str(t.get("Date")) == date_str
        for t in trips
    )


def alert_already_sent(creds, emp_id: str, date_str: str) -> bool:
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet(ALERT_LOG_SHEET_NAME)
    return any(
        str(r.get("Employee ID")) == str(emp_id) and str(r.get("Date")) == date_str
        for r in sheet.get_all_records()
    )


def log_alert(creds, row: dict):
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet(ALERT_LOG_SHEET_NAME)
    sheet.append_row(list(row.values()), value_input_option="USER_ENTERED")


def send_alert(driver_name: str, emp_id: str, expected_start: str, current_time: str):
    print(f"[ALERT] {driver_name} ({emp_id}) has not started their trip.")
    print(f"        Expected: {expected_start} | Current: {current_time}")
    # TODO: Send WhatsApp alert via Twilio or Meta Cloud API
    # TODO: Send Telegram alert via python-telegram-bot


def run_monitor():
    creds = get_credentials()
    today = datetime.now(IST).strftime("%Y-%m-%d")
    now = datetime.now(IST)
    now_str = now.strftime("%H:%M:%S")

    client = gspread.authorize(creds)
    roster = client.open_by_key(SHEET_ID).worksheet(ROSTER_SHEET_NAME).get_all_records()

    for entry in roster:
        if str(entry.get("Date")) != today:
            continue

        emp_id = str(entry.get("Login Driver Employee ID", "")).strip()
        driver_name = str(entry.get("Login Driver Name", "")).strip()
        expected_start = str(entry.get("Login Time", "")).strip()

        if not emp_id or not expected_start:
            continue

        normalized = expected_start if len(expected_start.split(":")) == 3 else expected_start + ":00"
        try:
            threshold = datetime.strptime(f"{today} {normalized}", "%Y-%m-%d %H:%M:%S") + timedelta(minutes=15)
        except ValueError:
            continue

        if now < threshold:
            continue

        if not check_missing_trip(creds, emp_id, today):
            continue

        if alert_already_sent(creds, emp_id, today):
            continue

        send_alert(driver_name, emp_id, expected_start, now_str)
        log_alert(creds, {
            "Date": today,
            "Employee ID": emp_id,
            "Driver Name": driver_name,
            "Alert Time": now_str,
            "Reason": f"No trip started as of {now_str}; expected at {expected_start}",
        })


if __name__ == "__main__":
    print("Alert monitor started. Checking every 5 minutes.")
    while True:
        try:
            run_monitor()
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(300)
