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


def _compute_shift_expected_time(roster_rows: list, emp_id: str, date_str: str, current_time_str: str) -> str:
    """
    From pre-fetched roster rows, return the expected start time for whichever
    shift (login or logout) is closest to current_time_str.
    Uses circular 24h arithmetic so overnight shifts resolve correctly.
    """
    def to_minutes(t: str) -> int | None:
        try:
            parts = t.strip().split(":")
            return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError, AttributeError):
            return None

    def circular_diff(a: int, b: int) -> int:
        d = abs(a - b)
        return min(d, 1440 - d)

    try:
        h, m, s = current_time_str.split(":")
        now_min = int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return ""

    best_time = ""
    best_diff = float("inf")

    for row in roster_rows:
        if _normalize_date(str(row.get("Date", ""))) != date_str:
            continue

        if str(row.get("Login Driver Employee ID", "")) == str(emp_id):
            t = to_minutes(str(row.get("Login Time", "")))
            if t is not None:
                diff = circular_diff(now_min, t)
                if diff < best_diff:
                    best_diff = diff
                    best_time = str(row.get("Login Time", "")).strip()

        if str(row.get("Logout Driver Employee ID", "")) == str(emp_id):
            t = to_minutes(str(row.get("Logout Time", "")))
            if t is not None:
                diff = circular_diff(now_min, t)
                if diff < best_diff:
                    best_diff = diff
                    best_time = str(row.get("Logout Time", "")).strip()

    return best_time


def get_shift_expected_time(creds, emp_id: str, date_str: str, current_time_str: str) -> str:
    """Fetch the daily roster then delegate to _compute_shift_expected_time."""
    client = gspread.authorize(creds)
    rows = client.open_by_key(SHEET_ID).worksheet(ROSTER_SHEET_NAME).get_all_records()
    return _compute_shift_expected_time(rows, emp_id, date_str, current_time_str)


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

    # Read all three sheets once — previously made 1 + 2N reads per run
    spreadsheet = gspread.authorize(creds).open_by_key(SHEET_ID)
    roster     = spreadsheet.worksheet(ROSTER_SHEET_NAME).get_all_records()
    trips      = spreadsheet.worksheet(SHEET_NAME).get_all_records()
    alerts_log = spreadsheet.worksheet(ALERT_LOG_SHEET_NAME).get_all_records()

    started_keys = {
        (str(t.get("Employee ID")), str(t.get("Date")))
        for t in trips
    }
    alerted_keys = {
        (str(a.get("Employee ID")), str(a.get("Date")))
        for a in alerts_log
    }

    alert_sheet = spreadsheet.worksheet(ALERT_LOG_SHEET_NAME)

    for entry in roster:
        if _normalize_date(str(entry.get("Date", ""))) != today:
            continue

        emp_id = str(entry.get("Login Driver Employee ID", "")).strip()
        driver_name = str(entry.get("Login Driver Name", "")).strip()
        expected_start = str(entry.get("Login Time", "")).strip()

        if not emp_id or not expected_start:
            continue

        normalized = expected_start if len(expected_start.split(":")) == 3 else expected_start + ":00"
        try:
            threshold = (
                datetime.strptime(f"{today} {normalized}", "%Y-%m-%d %H:%M:%S")
                + timedelta(minutes=15)
            )
        except ValueError:
            continue

        if now < threshold:
            continue
        if (emp_id, today) in started_keys:
            continue
        if (emp_id, today) in alerted_keys:
            continue

        send_alert(driver_name, emp_id, expected_start, now_str)
        alert_row = {
            "Date": today,
            "Employee ID": emp_id,
            "Driver Name": driver_name,
            "Alert Time": now_str,
            "Reason": f"No trip started as of {now_str}; expected at {expected_start}",
        }
        alert_sheet.append_row(list(alert_row.values()), value_input_option="USER_ENTERED")
        alerted_keys.add((emp_id, today))  # prevent double-alert within same run


if __name__ == "__main__":
    print("Alert monitor started. Checking every 5 minutes.")
    while True:
        try:
            run_monitor()
        except Exception as e:
            print(f"[ERROR] {e}")
        time.sleep(300)
