import gspread
from config import SHEET_ID, SHEET_NAME, ROSTER_SHEET_NAME, MASTER_ROSTER_SHEET_NAME, MASTER_ROSTER_COLUMNS, ROSTER_COLUMNS


def append_trip(creds, row: dict):
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SHEET_ID)
    sheet = spreadsheet.worksheet(SHEET_NAME)
    sheet.append_row(list(row.values()), value_input_option="USER_ENTERED")
    print(f"✅ Written to: {spreadsheet.title} → {sheet.title} (row ~{sheet.row_count})")


def update_trip_end(creds, trip_id: str, end_data: dict):
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    cell = sheet.find(trip_id, in_column=1)
    if not cell:
        raise ValueError(f"Trip {trip_id} not found in sheet")
    headers = sheet.row_values(1)
    for col_name, value in end_data.items():
        if col_name in headers:
            sheet.update_cell(cell.row, headers.index(col_name) + 1, value)


# ── Master Roster ────────────────────────────────────────────────────────────

def _open_master(creds):
    return gspread.authorize(creds).open_by_key(SHEET_ID).worksheet(MASTER_ROSTER_SHEET_NAME)


def get_master_roster(creds) -> list[dict]:
    sheet = _open_master(creds)
    rows = sheet.get_all_records()
    for i, row in enumerate(rows):
        row["_row"] = i + 2  # 1-based, row 1 is header
    return rows


def add_master_entry(creds, row: dict):
    sheet = _open_master(creds)
    sheet.append_row(
        [row.get(col, "") for col in MASTER_ROSTER_COLUMNS],
        value_input_option="USER_ENTERED",
    )


def update_master_entry(creds, row_number: int, row: dict):
    sheet = _open_master(creds)
    sheet.update(
        f"A{row_number}",
        [[row.get(col, "") for col in MASTER_ROSTER_COLUMNS]],
        value_input_option="USER_ENTERED",
    )


def delete_master_entry(creds, row_number: int):
    _open_master(creds).delete_rows(row_number)


# ── Daily Roster ─────────────────────────────────────────────────────────────

def _open_daily(creds):
    return gspread.authorize(creds).open_by_key(SHEET_ID).worksheet(ROSTER_SHEET_NAME)


def get_daily_roster(creds, date_str: str) -> list[dict]:
    sheet = _open_daily(creds)
    rows = sheet.get_all_records()
    result = []
    for i, row in enumerate(rows):
        if str(row.get("Date", "")) == date_str:
            row["_row"] = i + 2
            result.append(row)
    return result


def write_daily_roster(creds, date_str: str, rows: list[dict]):
    sheet = _open_daily(creds)
    all_rows = sheet.get_all_values()
    # Collect 1-based row indices (skip header at index 0) that match the date
    to_delete = [
        i + 2
        for i, r in enumerate(all_rows[1:])
        if r and r[0] == date_str
    ]
    for row_number in reversed(to_delete):
        sheet.delete_rows(row_number)
    for row in rows:
        sheet.append_row(
            [row.get(col, "") for col in ROSTER_COLUMNS],
            value_input_option="USER_ENTERED",
        )


def add_daily_entry(creds, row: dict):
    sheet = _open_daily(creds)
    sheet.append_row(
        [row.get(col, "") for col in ROSTER_COLUMNS],
        value_input_option="USER_ENTERED",
    )


def delete_daily_entry(creds, row_number: int):
    _open_daily(creds).delete_rows(row_number)
